import streamlit as st
import pandas as pd
from datetime import date
from domain.models.transaction import Transaction, TransactionLine
from domain.models.counterparty import Counterparty
from presentation.state.session_manager import SessionManager

async def render_journal_input(container):
    st.subheader("仕訳入力")
    
    # Dependencies
    journal_service = await container.get_journal_service()
    master_service = await container.get_master_service()
    ocr_service = container.get_ocr_service()
    file_service = container.get_file_service()
    session = SessionManager()
    
    # Master Data
    accounts = await master_service.get_accounts()
    acc_map = {a.id: a for a in accounts}
    acc_code_name_map = {f"{a.code}: {a.name}": a.id for a in accounts}
    acc_options = list(acc_code_name_map.keys())
    
    # 1. OCR Section
    uploaded_file = st.file_uploader("証憑アップロード (AI自動読取)", type=["pdf", "jpg", "png", "jpeg"])
    if uploaded_file:
         # Pass acc_options to OCR
         await _handle_ocr(uploaded_file, ocr_service, session, acc_options)

    # 2. Input Form
    tx_date, tx_desc, tx_counterparty, tx_invoice_num = _render_header_form(session)

    # 3. Lines Editor
    edited_df = _render_lines_editor(session, acc_options)
    
    # 4. Abstract Selection (Auto-fill Desc)
    await _handle_abstract_selection(edited_df, master_service, acc_code_name_map)

    # 5. Submission
    register_master = st.checkbox("取引先マスタに登録/更新する", value=True if session.get("ocr_counterparty") else False)
    if st.button("仕訳登録", type="primary"):
        await _handle_submission(
            session, 
            journal_service, 
            master_service, 
            file_service,
            uploaded_file,
            edited_df,
            acc_code_name_map,
            tx_date,
            tx_desc,
            tx_counterparty,
            tx_invoice_num,
            register_master
        )

async def _handle_ocr(uploaded_file, ocr_service, session, acc_options):
    if st.button("AIで読み取る"):
        with st.spinner("AI解析中 (Gemini 2.5 Flash-Lite - Sten-gun Mode)..."):
            file_bytes = uploaded_file.getvalue()
            file_type = uploaded_file.name.split('.')[-1]
            # Pass account list for strict mapping
            ocr_result = await ocr_service.extract_receipt_data(file_bytes, file_type, acc_options)
            
            if ocr_result:
                if ocr_result.needs_manual_review:
                    st.warning(f"要確認: {ocr_result.error_message or '信頼度が低いため内容を確認してください'}")
                else:
                    st.success("読み取り成功 (Sten-gun Mode)")
                
                _apply_ocr_result(session, ocr_result)
            else:
                st.error("読み取りに失敗しました。")

def _apply_ocr_result(session, ocr_result):
    d = date.fromisoformat(ocr_result.transaction_date) if ocr_result.transaction_date else date.today()
    # Use new field names
    vendor = ocr_result.merchant_name or ""
    # account = ocr_result.account_item or "" # Start using manual selection
    
    desc = f"{vendor}"
    
    session.set("default_date", d)
    session.set("default_desc", desc)
    session.set("ocr_amount", ocr_result.total_amount_incl_tax)
    # session.set("ocr_account_type", account) # Logic uses this to match dropdown
    session.set("ocr_counterparty", vendor)
    session.set("ocr_invoice_num", ocr_result.invoice_registration_number)
    
    # Direct update of widget keys to ensure UI reflects changes immediately
    if "cp_input" in st.session_state:
        st.session_state["cp_input"] = vendor
    if "desc_input" in st.session_state:
        st.session_state["desc_input"] = desc
    if "inv_input" in st.session_state:
        st.session_state["inv_input"] = ocr_result.invoice_registration_number

def _render_header_form(session):
    # Initialize session state for widgets if not present
    if "cp_input" not in st.session_state:
        st.session_state["cp_input"] = session.get("ocr_counterparty", "")
    if "desc_input" not in st.session_state:
        st.session_state["desc_input"] = session.default_desc
    if "inv_input" not in st.session_state:
        st.session_state["inv_input"] = session.get("ocr_invoice_num", "")

    col1, col2 = st.columns(2)
    with col1:
        tx_date = st.date_input("日付", value=session.default_date)
        tx_counterparty = st.text_input("取引先 (任意)", key="cp_input")
    with col2:
        tx_desc = st.text_input("摘要", key="desc_input")
        tx_invoice_num = st.text_input("T番号 (任意)", key="inv_input")
        
    return tx_date, tx_desc, tx_counterparty, tx_invoice_num

def _render_lines_editor(session, acc_options):
    st.caption("仕訳明細")
    
    # OCR Line Application Logic
    ocr_amount = session.get("ocr_amount")
    if ocr_amount is not None:
        # No account type from OCR, so manual selection required
        # target_type = session.get("ocr_account_type", "")
        # matched_account_str = next((opt for opt in acc_options if target_type and target_type in opt), None)
        
        new_row = {"借方": ocr_amount, "貸方": 0, "勘定科目": None}
        session.journal_lines_df = pd.DataFrame([new_row])
        session.clear_journal_temp_data()

    df = session.journal_lines_df
    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "勘定科目": st.column_config.SelectboxColumn("勘定科目", options=acc_options, required=True, width="large"),
            "借方": st.column_config.NumberColumn("借方", min_value=0, format="%d"),
            "貸方": st.column_config.NumberColumn("貸方", min_value=0, format="%d")
        },
        use_container_width=True,
        key="journal_editor" 
    )
    
    if not edited_df.equals(session.journal_lines_df):
        session.journal_lines_df = edited_df
        
    return edited_df

async def _handle_abstract_selection(edited_df, master_service, acc_code_name_map):
    selected_acc_ids = []
    for index, row in edited_df.iterrows():
        acc_str = row.get("勘定科目")
        if acc_str and acc_str in acc_code_name_map:
            selected_acc_ids.append(acc_code_name_map[acc_str])

    abstracts = await master_service.get_abstracts()
    filtered_abstracts_txt = [a.text for a in abstracts if not selected_acc_ids or a.account_id in selected_acc_ids]
    
    def on_abstract_change():
        st.session_state.desc_input = st.session_state.selected_abstract

    if filtered_abstracts_txt:
        label = "よく使う摘要 (関連科目)" if selected_acc_ids else "よく使う摘要 (全件)"
        st.selectbox(label, options=[""] + list(set(filtered_abstracts_txt)), key="selected_abstract", on_change=on_abstract_change, placeholder="摘要を選択...")

async def _handle_submission(session, journal_service, master_service, file_service, uploaded_file, edited_df, acc_code_name_map, tx_date, tx_desc, tx_counterparty, tx_invoice_num, register_master):
    try:
        # 1. Validate & Build Lines
        lines = _validate_and_build_lines(edited_df, acc_code_name_map)
        
        # 2. Build Transaction Object
        transaction = Transaction(
            date=tx_date,
            description=tx_desc,
            lines=lines,
            counterparty=tx_counterparty,
            invoice_number=tx_invoice_num,
            evidence_path=None
        )
        
        # 3. Handle Master Data Registration
        if register_master:
            await _register_counterparty(master_service, tx_counterparty, tx_invoice_num)

        # 4. Save Transaction (with optional evidence)
        await _save_transaction(journal_service, file_service, transaction, uploaded_file)
        
        # 5. Reset & Rerun
        _reset_form(session)
        st.rerun()
        
    except ValueError as ve:
        st.error(str(ve))
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")

def _reset_form(session):
    session.journal_lines_df = pd.DataFrame([{"借方": 0, "貸方": 0, "勘定科目": None}])
    session.set("ocr_counterparty", None)
    session.set("ocr_invoice_num", None)
    session.set("ocr_amount", None)
    session.set("ocr_account_type", None)
    
    # Reset widget keys to clear form inputs
    if "cp_input" in st.session_state:
        st.session_state["cp_input"] = ""
    if "desc_input" in st.session_state:
        st.session_state["desc_input"] = ""
    if "inv_input" in st.session_state:
        st.session_state["inv_input"] = ""

def _validate_and_build_lines(edited_df, acc_code_name_map):
    lines = []
    for i, row in edited_df.iterrows():
        if not row["勘定科目"] and row["借方"] == 0 and row["貸方"] == 0: continue
        if not row["勘定科目"]:
            raise ValueError(f"行 {i+1}: 勘定科目が選択されていません。")

        acc_id = acc_code_name_map[row["勘定科目"]]
        debit = int(row["借方"] or 0)
        credit = int(row["貸方"] or 0)
        
        if debit == 0 and credit == 0: continue
        
        lines.append(TransactionLine(account_id=acc_id, debit=debit, credit=credit))
    
    if not lines:
        raise ValueError("仕訳明細が空です。")

    total_debit = sum(l.debit for l in lines)
    total_credit = sum(l.credit for l in lines)
    
    if total_debit != total_credit:
         raise ValueError(f"借方合計 ({total_debit}) と貸方合計 ({total_credit}) が一致しません。")
         
    return lines

async def _register_counterparty(master_service, name, invoice_num):
    if name or invoice_num:
        cp = Counterparty(name=name or "Unknown", invoice_number=invoice_num)
        try:
            await master_service.save_counterparty(cp)
            st.info(f"取引先マスタを更新しました: {cp.name}")
        except Exception as e:
            st.warning(f"マスタ登録に失敗しましたが、仕訳は続行します: {e}")

async def _save_transaction(journal_service, file_service, transaction, uploaded_file):
    if uploaded_file:
        await journal_service.add_journal_entry_with_evidence(transaction, uploaded_file.getvalue(), file_service)
        st.success("証憑付きで登録しました！")
    else:
        await journal_service.add_journal_entry(transaction)
        st.success("登録しました！")
