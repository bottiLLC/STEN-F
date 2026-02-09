import streamlit as st
import pandas as pd
from datetime import date
from domain.models.transaction import Transaction, TransactionLine
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
    
    # --- OCR Section ---
    uploaded_file = st.file_uploader("証憑アップロード (AI自動読取)", type=["pdf", "jpg", "png", "jpeg"])
    
    if uploaded_file:
        if st.button("AIで読み取る"):
            with st.spinner("AI解析中 (Gemini 2.5 Flash-Lite)..."):
                file_bytes = uploaded_file.getvalue()
                file_type = uploaded_file.name.split('.')[-1]
                ocr_result = await ocr_service.extract_receipt_data(file_bytes, file_type)
                
                if ocr_result:
                    st.success("読み取り成功！フォームに反映しました。")
                    # Update State via SessionManager
                    d = date.fromisoformat(ocr_result.date) if ocr_result.date else date.today()
                    desc = f"{ocr_result.store_name} ({ocr_result.suggested_account_type})"
                    
                    session.set("default_date", d)
                    session.set("default_desc", desc)
                    session.set("ocr_amount", ocr_result.total_amount)
                    session.set("ocr_account_type", ocr_result.suggested_account_type)
                else:
                    st.error("読み取りに失敗しました。")

    # --- Input Form (Head) ---
    col1, col2 = st.columns(2)
    with col1:
        tx_date = st.date_input("日付", value=session.default_date)
    with col2:
        # Note: key="desc_input" binds directly to st.session_state["desc_input"].
        # We manually sync initial value from SessionManager.
        tx_desc = st.text_input("摘要", value=session.default_desc, key="desc_input")
        # Sync back to session manager if needed, but text_input key handles it for reactivity.
        # However, to persist across OCR updates, we used set() above.

    # --- Input Form (Lines) ---
    st.caption("仕訳明細")
    
    # Access Journal DataFrame via SessionManager
    # It handles default initialization internally
    df = session.journal_lines_df
        
    # Apply OCR data if present
    ocr_amount = session.get("ocr_amount")
    if ocr_amount is not None:
        matched_account_str = None
        target_type = session.get("ocr_account_type", "")
        
        # Simple match logic
        for opt in acc_options:
            if target_type and target_type in opt:
                matched_account_str = opt
                break
        
        new_row = {"借方": ocr_amount, "貸方": 0, "勘定科目": matched_account_str}
        session.journal_lines_df = pd.DataFrame([new_row])
        
        # Cleanup temporary keys via Manager
        session.clear_journal_temp_data()
        
        # Reload to reflect changes
        df = session.journal_lines_df

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        column_config={
            "勘定科目": st.column_config.SelectboxColumn(
                "勘定科目",
                options=acc_options,
                required=True,
                width="large"
            ),
            "借方": st.column_config.NumberColumn("借方", min_value=0, format="%d"),
            "貸方": st.column_config.NumberColumn("貸方", min_value=0, format="%d")
        },
        use_container_width=True,
        # We don't bind key parameter here to avoid double state issues 
        # but we need to capture edits.
        # Streamlit data_editor returns the edited dataframe.
        # We should update session state with the result if we want persistence.
        key="journal_editor" 
    )
    
    # Sync edited_df back to session manager for persistence across reruns
    if not edited_df.equals(session.journal_lines_df):
        session.journal_lines_df = edited_df

    # Abstract selection logic
    selected_acc_ids = []
    for index, row in edited_df.iterrows():
        acc_str = row.get("勘定科目")
        if acc_str and acc_str in acc_code_name_map:
            selected_acc_ids.append(acc_code_name_map[acc_str])

    abstracts = await master_service.get_abstracts()
    filtered_abstracts_txt = []
    if selected_acc_ids:
        filtered_abstracts_txt = [a.text for a in abstracts if a.account_id in selected_acc_ids]
    else:
        filtered_abstracts_txt = [a.text for a in abstracts]
        
    def on_abstract_change():
        # Direct session state access for callback consistency
        st.session_state.desc_input = st.session_state.selected_abstract

    if filtered_abstracts_txt:
        label = "よく使う摘要 (関連科目)" if selected_acc_ids else "よく使う摘要 (全件)"
        st.selectbox(
            label, 
            options=[""] + list(set(filtered_abstracts_txt)), 
            key="selected_abstract",
            on_change=on_abstract_change,
            placeholder="摘要を選択..."
        )

    # --- Post Button ---
    if st.button("仕訳登録", type="primary"):
        lines = []
        try:
            for i, row in edited_df.iterrows():
                # Skip empty rows
                if not row["勘定科目"] and row["借方"] == 0 and row["貸方"] == 0:
                    continue
                
                if not row["勘定科目"]:
                    st.error(f"行 {i+1}: 勘定科目が選択されていません。")
                    return

                acc_id = acc_code_name_map[row["勘定科目"]]
                debit = int(row["借方"] or 0)
                credit = int(row["貸方"] or 0)
                
                if debit == 0 and credit == 0:
                    continue
                
                lines.append(TransactionLine(
                    account_id=acc_id,
                    debit=debit,
                    credit=credit
                ))
            
            if not lines:
                st.warning("仕訳明細が空です。")
                return

            total_debit = sum(l.debit for l in lines)
            total_credit = sum(l.credit for l in lines)
            
            if total_debit != total_credit:
                st.error(f"借方合計 ({total_debit}) と貸方合計 ({total_credit}) が一致しません。")
                return
            
            # Create Transaction Object
            transaction = Transaction(
                date=tx_date,
                description=tx_desc,
                lines=lines
            )
            
            # Save to DB
            await journal_service.add_journal_entry(transaction)

            # Save Evidence if uploaded
            if uploaded_file:
                 saved_path = file_service.save_evidence(
                     uploaded_file.getvalue(), 
                     uploaded_file.name, 
                     tx_date, 
                     tx_desc, 
                     total_debit
                 )
                 st.success(f"証憑を保存しました: {saved_path}")

            st.success("登録しました！")
            
            # Reset via SessionManager
            session.journal_lines_df = pd.DataFrame(
                [{"借方": 0, "貸方": 0, "勘定科目": None}]
            )
            st.rerun()
            
        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
