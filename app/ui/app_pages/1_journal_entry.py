# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from datetime import date
import unicodedata
import streamlit as st
import structlog

from app.domain.models.counterparty import Counterparty
from app.domain.models.transaction import Transaction, TransactionLine
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("仕訳入力 (AIレシート読取 ＆ 振替伝票)", divider="blue")
st.caption(
    "PDFや画像の領収書・請求書をアップロードすると、AIが取引内容を自動抽出して振替伝票に展開します。"
)


# --- Master Data Fetching ---
async def load_master_data():
    async with DI.get_master_service() as master_service:
        accounts = await master_service.get_accounts()
        abstracts = await master_service.get_abstracts()
        cps = await master_service.get_counterparties()
        return accounts, abstracts, cps


accounts, abstracts, counterparties = run_async(load_master_data())

account_options = {
    f"{a.code}: {a.name}": str(a.id)
    for a in sorted(accounts, key=lambda x: int(x.code))
}
account_labels = [""] + list(account_options.keys())
abstract_options = [""] + sorted(list(set(a.text for a in abstracts if a.text)))

# --- Session State Initialization ---
if "ocr_result" not in st.session_state:
    st.session_state.ocr_result = None
if "ocr_file_bytes" not in st.session_state:
    st.session_state.ocr_file_bytes = None
if "ocr_filename" not in st.session_state:
    st.session_state.ocr_filename = None
if "num_lines" not in st.session_state:
    st.session_state.num_lines = 1
if "form_entry_key" not in st.session_state:
    st.session_state.form_entry_key = 0
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "last_registered_summary" not in st.session_state:
    st.session_state.last_registered_summary = None


def reset_all():
    """仕訳入力フォームおよびアップローダー、OCR状態を完全に初期化する"""
    st.session_state.ocr_result = None
    st.session_state.ocr_file_bytes = None
    st.session_state.ocr_filename = None
    st.session_state.num_lines = 1
    st.session_state.form_entry_key += 1
    st.session_state.uploader_key += 1


# 直前の登録完了サマリー通知
if st.session_state.last_registered_summary:
    st.success(
        f"✅ 前回の仕訳を登録しました: **{st.session_state.last_registered_summary}** （続けて次の仕訳を入力できます）"
    )

current_form_prefix = f"v{st.session_state.form_entry_key}"
current_uploader_prefix = f"u{st.session_state.uploader_key}"

# ==============================================================================
# Step 1: 📄 証憑アップロード & AI OCR 読み取り (ファーストビュー最優先)
# ==============================================================================
with st.container(border=True):
    col_hdr1, col_hdr2 = st.columns([3, 1])
    with col_hdr1:
        st.subheader("📄 Step 1: 証憑（PDF/画像）のアップロード & AI自動読取")
    with col_hdr2:
        if (
            st.session_state.ocr_result is not None
            or st.session_state.last_registered_summary is not None
        ):
            if st.button(
                "入力内容をクリア",
                icon=":material/refresh:",
                key=f"btn_clear_ocr_{current_form_prefix}",
            ):
                st.session_state.last_registered_summary = None
                reset_all()
                st.rerun()

    uploaded_file = st.file_uploader(
        "レシート・領収書・請求書のPDFまたは画像ファイルをドロップしてください",
        type=["pdf", "png", "jpg", "jpeg"],
        key=f"receipt_uploader_{current_uploader_prefix}",
        help="PDFまたは画像ファイルをアップロードすると、AIが日付、取引先、登録番号、金額、勘定科目を自動解析します。",
    )

    if uploaded_file is not None:
        col_up1, col_up2 = st.columns([2, 3])
        with col_up1:
            st.caption(
                f"📎 アップロード中: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)"
            )
            # Show preview for images
            if uploaded_file.type.startswith("image/"):
                st.image(
                    uploaded_file, caption="証憑プレビュー", use_container_width=True
                )
            elif uploaded_file.name.lower().endswith(".pdf"):
                st.info("📄 PDF形式の証憑がセットされました。")

        with col_up2:
            st.markdown("👇 **AI読み取りを実行して振替伝票に自動展開します**")
            if st.button(
                "🤖 AIで自動読み取りを実行",
                type="primary",
                icon=":material/document_scanner:",
                key=f"btn_run_ocr_{current_form_prefix}",
            ):
                with st.spinner(
                    "AIが証憑を解析中 (取引日・金額・取引先・科目を推論)..."
                ):
                    try:
                        file_bytes = uploaded_file.getvalue()
                        file_type = uploaded_file.name.split(".")[-1].lower()

                        ocr_service = DI.get_ocr_service()
                        acc_str_options = list(account_options.keys())
                        cp_str_options = [c.name for c in counterparties if c.name]

                        result = run_async(
                            ocr_service.extract_receipt_data(
                                file_bytes, file_type, acc_str_options, cp_str_options
                            )
                        )

                        if result:
                            st.session_state.ocr_result = result
                            st.session_state.ocr_file_bytes = file_bytes
                            st.session_state.ocr_filename = uploaded_file.name
                            st.session_state.last_registered_summary = None
                            # フォームのキーバージョンを進めることで、Step 2 のウィジェットに OCR 読取結果が自動反映される
                            st.session_state.form_entry_key += 1

                            if result.is_registered_merchant:
                                st.toast(
                                    f"登録済み取引先「{result.merchant_name}」と一致しました。",
                                    icon="✅",
                                )
                            else:
                                st.toast(
                                    "AI読み取り完了！振替伝票に反映しました", icon="🎉"
                                )
                            st.rerun()
                        else:
                            st.error(
                                "読み取りに失敗しました。ファイル形式や画像の内容をご確認ください。"
                            )
                    except Exception as e:
                        log.error("OCR extraction failed", error=str(e), exc_info=True)
                        err_msg = str(e)
                        st.error(err_msg)
                        if "API" in err_msg or "キー" in err_msg or "設定" in err_msg:
                            st.info(
                                "💡 **設定確認**: 画面左メニューの「設定・管理」→「マスタ・システム管理」→「⚙️ AI・システム設定」タブから Gemini API キーの登録・保存が行えます。"
                            )


# ==============================================================================
# マスタ参照 & 振替伝票への自動仮入力値の解決
# ==============================================================================
default_date = date.today()
default_desc = ""
default_cp = ""
default_inv = ""
default_abstract_idx = 0
matched_cp: Counterparty | None = None
target_debit_acc_id: str | None = None
target_credit_acc_id: str | None = None
total_amt: int = 0

if st.session_state.ocr_result:
    ocr = st.session_state.ocr_result

    # 1. 取引日
    if ocr.transaction_date:
        try:
            default_date = date.fromisoformat(ocr.transaction_date)
        except ValueError:
            pass

    # 2. 金額
    if ocr.total_amount_incl_tax:
        total_amt = int(ocr.total_amount_incl_tax)

    # 3. 取引先マスタとの照合
    if ocr.invoice_registration_number:
        inv_clean = ocr.invoice_registration_number.strip().upper()
        default_inv = inv_clean
        matched_cp = next(
            (
                c
                for c in counterparties
                if c.invoice_number and c.invoice_number.strip().upper() == inv_clean
            ),
            None,
        )

    if not matched_cp and ocr.merchant_name:
        default_cp = ocr.merchant_name
        norm_ocr_name = (
            unicodedata.normalize("NFKC", ocr.merchant_name)
            .replace(" ", "")
            .replace("　", "")
            .lower()
        )
        for c in counterparties:
            if not c.name:
                continue
            norm_c_name = (
                unicodedata.normalize("NFKC", c.name)
                .replace(" ", "")
                .replace("　", "")
                .lower()
            )
            if (
                norm_c_name == norm_ocr_name
                or norm_c_name in norm_ocr_name
                or norm_ocr_name in norm_c_name
            ):
                matched_cp = c
                break

    if matched_cp:
        default_cp = matched_cp.name
        if matched_cp.invoice_number:
            default_inv = matched_cp.invoice_number
        if matched_cp.debit_account_id:
            target_debit_acc_id = str(matched_cp.debit_account_id)
        if matched_cp.credit_account_id:
            target_credit_acc_id = str(matched_cp.credit_account_id)
        if matched_cp.description_template:
            default_desc = matched_cp.description_template

    # 4. 摘要マスタとの照合
    if not default_desc:
        if ocr.description:
            default_desc = ocr.description
        elif ocr.merchant_name:
            default_desc = ocr.merchant_name

    # よく使う摘要マスタから一致する候補を探索
    if default_desc:
        for idx, opt in enumerate(abstract_options):
            if opt and (
                opt == default_desc or opt in default_desc or default_desc in opt
            ):
                default_abstract_idx = idx
                break

    # 5. 勘定科目の決定
    if not target_debit_acc_id and ocr.inferred_debit_account_id:
        target_debit_acc_id = str(ocr.inferred_debit_account_id)
    if not target_credit_acc_id and ocr.inferred_credit_account_id:
        target_credit_acc_id = str(ocr.inferred_credit_account_id)

    # デフォルトの貸方科目が未設定の場合、現金や普通預金、未払金などマスタから適切な科目を補完
    if not target_credit_acc_id:
        # 現金 (101) を優先探索
        cash_acc = next(
            (
                aid
                for lbl, aid in account_options.items()
                if "101" in lbl or "現金" in lbl
            ),
            None,
        )
        if cash_acc:
            target_credit_acc_id = cash_acc

    debit_lbl = next(
        (lbl for lbl, aid in account_options.items() if aid == target_debit_acc_id),
        "",
    )
    credit_lbl = next(
        (lbl for lbl, aid in account_options.items() if aid == target_credit_acc_id),
        "",
    )

    default_lines = [
        {
            "debit_acc": debit_lbl,
            "debit_amt": total_amt,
            "credit_acc": credit_lbl,
            "credit_amt": total_amt,
        }
    ]
else:
    default_lines = [
        {"debit_acc": "", "debit_amt": 0, "credit_acc": "", "credit_amt": 0}
    ]


# ==============================================================================
# Step 2: 📝 振替伝票
# ==============================================================================
with st.container(border=True):
    st.subheader("📝 Step 2: 振替伝票")
    st.caption("複式簿記の標準形式で借方・貸方を左右対照に入力・確認できます。")

    # AI読み取り結果の展開案内（AI解析サマリと兼用）
    if st.session_state.ocr_result:
        ocr = st.session_state.ocr_result
        match_info = "（取引先マスタ一致 ✅）" if matched_cp else ""
        st.info(
            f"🤖 **AIが証憑とマスタを参照し、下記の振替伝票に候補を自動仮入力しました** {match_info}\n\n"
            "内容をご確認の上、必要に応じて修正して「💾 この内容で仕訳帳に登録する」を押してください。"
        )
        if ocr.needs_manual_review:
            st.warning(f"⚠️ 確認推奨: {ocr.error_message}")

    # Transaction Header info
    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 2, 2])
    with col_h1:
        tx_date = st.date_input(
            "取引日 (発生日)",
            value=default_date,
            key=f"tx_date_input_{current_form_prefix}",
        )
    with col_h2:
        abstract_choice = st.selectbox(
            "よく使う摘要から選ぶ",
            abstract_options,
            index=default_abstract_idx,
            key=f"abstract_choice_input_{current_form_prefix}",
        )
        desc_input = st.text_input(
            "摘要 (取引内容)",
            value=default_desc,
            key=f"desc_input_field_{current_form_prefix}",
        )
        final_desc = abstract_choice if abstract_choice else desc_input
    with col_h3:
        final_cp = st.text_input(
            "取引先 (支払先/売上先)",
            value=default_cp,
            key=f"cp_input_field_{current_form_prefix}",
        )
    with col_h4:
        final_inv = st.text_input(
            "インボイス登録番号",
            value=default_inv,
            help="適格請求書発行事業者の登録番号 (例: T1234567890123)",
            key=f"inv_input_field_{current_form_prefix}",
        )

    st.markdown("---")

    # Column header for Voucher table (Traditional Bookkeeping Style)
    col_hdr_l, col_hdr_r = st.columns(2)
    with col_hdr_l:
        st.markdown(
            "### <span class='badge-debit'>【 借 方 (Debit) : 費用 / 資産の増加 】</span>",
            unsafe_allow_html=True,
        )
    with col_hdr_r:
        st.markdown(
            "### <span class='badge-credit'>【 貸 方 (Credit) : 支払元 / 負債・収益 】</span>",
            unsafe_allow_html=True,
        )

    line_inputs = []
    line_count = max(st.session_state.num_lines, len(default_lines))

    for i in range(line_count):
        d_line = (
            default_lines[i]
            if i < len(default_lines)
            else {
                "debit_acc": "",
                "debit_amt": 0,
                "credit_acc": "",
                "credit_amt": 0,
            }
        )

        col_d_acc, col_d_amt, col_c_acc, col_c_amt = st.columns([3, 2, 3, 2])

        with col_d_acc:
            debit_acc = st.selectbox(
                f"借方科目 (行 {i + 1})",
                account_labels,
                index=account_labels.index(d_line["debit_acc"])
                if d_line["debit_acc"] in account_labels
                else 0,
                key=f"debit_acc_{current_form_prefix}_{i}",
            )
        with col_d_amt:
            debit_amt = st.number_input(
                f"借方金額 (行 {i + 1})",
                min_value=0,
                value=int(str(d_line.get("debit_amt", 0))),
                step=1000,
                key=f"debit_amt_{current_form_prefix}_{i}",
            )
        with col_c_acc:
            credit_acc = st.selectbox(
                f"貸方科目 (行 {i + 1})",
                account_labels,
                index=account_labels.index(str(d_line.get("credit_acc", "")))
                if str(d_line.get("credit_acc", "")) in account_labels
                else 0,
                key=f"credit_acc_{current_form_prefix}_{i}",
            )
        with col_c_amt:
            credit_amt = st.number_input(
                f"貸方金額 (行 {i + 1})",
                min_value=0,
                value=int(str(d_line.get("credit_amt", 0))),
                step=1000,
                key=f"credit_amt_{current_form_prefix}_{i}",
            )

        line_inputs.append(
            {
                "debit_acc": str(debit_acc),
                "debit_amt": int(debit_amt),
                "credit_acc": str(credit_acc),
                "credit_amt": int(credit_amt),
            }
        )

    # Line controls
    col_ctrl1, col_ctrl2, _ = st.columns([2, 2, 4])
    with col_ctrl1:
        if st.button("➕ 明細行を追加", key=f"btn_add_line_{current_form_prefix}"):
            st.session_state.num_lines += 1
            st.rerun()
    with col_ctrl2:
        if st.session_state.num_lines > 1:
            if st.button(
                "➖ 最後の行を削除", key=f"btn_remove_line_{current_form_prefix}"
            ):
                st.session_state.num_lines -= 1
                st.rerun()

    # Calculate Totals & Balance Check
    total_debit = sum(
        int(str(line["debit_amt"])) for line in line_inputs if line["debit_acc"]
    )
    total_credit = sum(
        int(str(line["credit_amt"])) for line in line_inputs if line["credit_acc"]
    )
    balance_diff = total_debit - total_credit
    is_balanced = total_debit > 0 and balance_diff == 0

    st.markdown("---")

    # Realtime Balance Indicator (Poka-Yoke)
    col_bal1, col_bal2, col_bal3 = st.columns(3)
    with col_bal1:
        st.metric("借方合計 (Debit)", f"¥{total_debit:,}")
    with col_bal2:
        st.metric("貸方合計 (Credit)", f"¥{total_credit:,}")
    with col_bal3:
        if total_debit == 0 and total_credit == 0:
            st.metric("貸借バランス", "未入力")
        elif is_balanced:
            st.metric("貸借バランス", "一致 (正常 ✅)", delta="¥0")
        else:
            st.metric(
                "貸借差額 (不一致 ⚠️)",
                f"¥{abs(balance_diff):,}",
                delta=f"{'+' if balance_diff > 0 else '-'}¥{abs(balance_diff):,}",
                delta_color="inverse",
            )

    st.divider()

    col_opt1, col_opt2 = st.columns([3, 2])
    with col_opt1:
        save_cp_master = st.checkbox(
            "この取引先を取引先マスタに自動登録/更新する",
            value=True if final_cp else False,
            key=f"chk_save_cp_{current_form_prefix}",
        )
    with col_opt2:
        if st.session_state.ocr_file_bytes:
            st.caption("🔒 添付証憑: 電子帳簿保存法対応ストレージに自動保存されます")

    submit_btn = st.button(
        "💾 この内容で仕訳帳に登録する",
        type="primary",
        icon=":material/save:",
        key=f"btn_submit_journal_{current_form_prefix}",
        use_container_width=True,
    )

    if submit_btn:
        valid_transaction_lines = []
        calc_debit = 0
        calc_credit = 0

        for line in line_inputs:
            d_acc_str = str(line["debit_acc"])
            d_amt_int = int(str(line["debit_amt"]))
            c_acc_str = str(line["credit_acc"])
            c_amt_int = int(str(line["credit_amt"]))

            if d_acc_str and d_amt_int > 0:
                aid = account_options[d_acc_str]
                valid_transaction_lines.append(
                    TransactionLine(
                        account_id=int(aid),
                        debit=d_amt_int,
                        credit=0,
                    )
                )
                calc_debit += d_amt_int

            if c_acc_str and c_amt_int > 0:
                aid = account_options[c_acc_str]
                valid_transaction_lines.append(
                    TransactionLine(
                        account_id=int(aid),
                        debit=0,
                        credit=c_amt_int,
                    )
                )
                calc_credit += c_amt_int

        if not valid_transaction_lines:
            st.error(
                "有効な仕訳明細が入力されていません。科目と金額を指定してください。"
            )
        elif calc_debit != calc_credit:
            st.error(
                f"貸借不一致エラー: 借方合計 ¥{calc_debit:,} / 貸方合計 ¥{calc_credit:,} (差額: ¥{abs(calc_debit - calc_credit):,})"
            )
        else:
            try:
                tx = Transaction(
                    date=tx_date,
                    description=final_desc or "取引",
                    counterparty=final_cp or None,
                    invoice_number=final_inv.strip().upper()
                    if final_inv.strip()
                    else None,
                    lines=valid_transaction_lines,
                    evidence_path=None,
                )

                async def execute_save():
                    async with DI.get_journal_service() as j_service:
                        if st.session_state.ocr_file_bytes:
                            file_service = DI.get_file_service()
                            await j_service.add_journal_entry_with_evidence(
                                tx,
                                st.session_state.ocr_file_bytes,
                                file_service,
                            )
                        else:
                            await j_service.add_journal_entry(tx)

                    if save_cp_master and (final_cp or final_inv):
                        async with DI.get_master_service() as m_service:
                            cp = Counterparty(
                                name=final_cp or "Unknown",
                                invoice_number=final_inv.strip().upper()
                                if final_inv.strip()
                                else None,
                            )
                            await m_service.save_counterparty(cp)

                run_async(execute_save())

                # 登録完了サマリーを保持してフォームを完全初期化
                summary_str = f"{tx.date.strftime('%Y/%m/%d')} | {tx.description} | ¥{calc_debit:,}"
                st.session_state.last_registered_summary = summary_str
                reset_all()

                st.toast("仕訳帳に登録しました！次の仕訳を入力できます。", icon="🎉")
                st.rerun()

            except ValueError as ve:
                st.error(f"登録エラー: {str(ve)}")
            except Exception as e:
                log.error(
                    "Failed to register journal entry", error=str(e), exc_info=True
                )
                st.error(f"登録処理中にエラーが発生しました: {str(e)}")
