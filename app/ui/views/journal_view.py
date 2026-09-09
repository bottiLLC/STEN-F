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

import io
from datetime import date
from typing import List, Optional
import pandas as pd
import streamlit as st
import structlog

from app.domain.models.transaction import Transaction, TransactionLine
from app.ui.async_helper import run_async
from app.ui.di import DI

log = structlog.get_logger()

st.header("仕訳・記帳", divider="blue")
st.caption(
    "AI OCR（領収書・請求書自動読取）起点での振替伝票作成、および仕訳帳の一覧・検索・CSV出力を一元的に行います。"
)


async def load_masters():
    async with DI.get_master_service() as s:
        return (
            await s.get_accounts(),
            await s.get_abstracts(),
            await s.get_counterparties(),
            await s.get_fiscal_years(),
        )


accounts, abstracts, counterparties, all_fys = run_async(load_masters())
open_fy = next((f for f in all_fys if f.status == "OPEN"), None)
account_labels = [""] + [
    f"{a.code}: {a.name}" for a in sorted(accounts, key=lambda x: int(x.code))
]
account_code_to_id = {f"{a.code}: {a.name}": a.id for a in accounts}
account_id_to_label = {a.id: f"{a.code}: {a.name}" for a in accounts}
abstract_options = [""] + sorted(list(set(a.text for a in abstracts if a.text)))

tab_entry, tab_history = st.tabs(
    ["📝 振替伝票・AI仕訳入力", "📖 仕訳帳 (General Journal)"]
)

# 1. 振替伝票入力
with tab_entry:
    st.subheader("Step 1: 証憑のアップロード ＆ AI自動読取")
    uploaded_file = st.file_uploader(
        "領収書・請求書をドラッグ＆ドロップ",
        type=["pdf", "png", "jpg", "jpeg"],
        key="journal_file_uploader",
    )

    if uploaded_file and st.button(
        "🤖 AIで自動読み取りを実行", type="primary", key="btn_run_ocr"
    ):
        fb, mime = uploaded_file.getvalue(), uploaded_file.type or "image/png"

        async def run_ai(b, m):
            async with DI.get_ocr_service() as s:
                return await s.analyze_receipt(b, m)

        with st.spinner("Gemini AI が証憑を解析中..."):
            try:
                ocr_res = run_async(run_ai(fb, mime))
                st.session_state["ocr_result"] = ocr_res
                st.session_state["ocr_bytes"] = fb
                st.session_state["ocr_filename"] = uploaded_file.name
                st.success("AI解析が完了しました！下の振替伝票に自動展開されました。")
            except Exception as e:
                st.error(f"AI解析エラー: {e}")

    ocr = st.session_state.get("ocr_result")
    st.markdown("---")
    st.subheader("Step 2: 振替伝票入力")

    ocr_date = date.today()
    if ocr and ocr.transaction_date:
        try:
            ocr_date = date.fromisoformat(ocr.transaction_date)
        except Exception:
            pass

    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 2])
    with col_h1:
        tx_date = st.date_input("取引日", value=ocr_date, key="tx_header_date")
    with col_h2:
        abs_choice = st.selectbox(
            "よく使う摘要から選ぶ", abstract_options, key="tx_header_abs_choice"
        )
        tx_desc = st.text_input(
            "伝票摘要 (取引内容)",
            value=abs_choice
            if abs_choice
            else (ocr.description if ocr and ocr.description else ""),
            key="tx_header_desc",
        )
    with col_h3:
        tx_cp = st.text_input(
            "取引先",
            value=ocr.merchant_name if ocr and ocr.merchant_name else "",
            key="tx_header_cp",
        )
    with col_h4:
        tx_inv = st.text_input(
            "インボイス番号 (T+13桁)",
            value=ocr.invoice_registration_number
            if ocr and ocr.invoice_registration_number
            else "",
            key="tx_header_inv",
        )

    d_init, c_init, init_amt = "", "", 0
    if ocr:
        init_amt = ocr.total_amount_incl_tax or 0
        if ocr.inferred_debit_account_id:
            d_init = account_id_to_label.get(int(ocr.inferred_debit_account_id), "")
        if ocr.inferred_credit_account_id:
            c_init = account_id_to_label.get(int(ocr.inferred_credit_account_id), "")

    lines_df = pd.DataFrame(
        [
            {
                "debit_account": d_init,
                "debit_amount": init_amt,
                "credit_account": c_init,
                "credit_amount": init_amt,
                "line_desc": ocr.description if ocr and ocr.description else "",
            }
        ]
    )
    col_cfg = {
        "debit_account": st.column_config.SelectboxColumn(
            "借方科目", options=account_labels
        ),
        "debit_amount": st.column_config.NumberColumn(
            "借方金額 (¥)", min_value=0, step=1000, required=True
        ),
        "credit_account": st.column_config.SelectboxColumn(
            "貸方科目", options=account_labels
        ),
        "credit_amount": st.column_config.NumberColumn(
            "貸方金額 (¥)", min_value=0, step=1000, required=True
        ),
        "line_desc": st.column_config.TextColumn("行摘要"),
    }

    st.markdown("##### 【 振替伝票 明細行 】")
    edited_lines_df = st.data_editor(
        lines_df,
        column_config=col_cfg,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="journal_voucher_lines_editor",
    )

    total_debit, total_credit = 0, 0
    tx_lines: List[TransactionLine] = []
    for _, r in edited_lines_df.iterrows():
        d_acc, d_amt = r.get("debit_account"), int(r.get("debit_amount") or 0)
        c_acc, c_amt = r.get("credit_account"), int(r.get("credit_amount") or 0)
        if d_acc and d_amt > 0:
            aid = account_code_to_id.get(str(d_acc))
            if aid:
                tx_lines.append(TransactionLine(account_id=aid, debit=d_amt, credit=0))
                total_debit += d_amt
        if c_acc and c_amt > 0:
            aid = account_code_to_id.get(str(c_acc))
            if aid:
                tx_lines.append(TransactionLine(account_id=aid, debit=0, credit=c_amt))
                total_credit += c_amt

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("借方合計", f"¥{total_debit:,}")
    col_m2.metric("貸方合計", f"¥{total_credit:,}")
    is_balanced = total_debit == total_credit > 0
    col_m3.metric(
        "貸借バランス",
        "✅ 一致" if is_balanced else f"差額: ¥{total_debit - total_credit:,}",
    )

    if st.button(
        "💾 この内容で仕訳帳に登録する",
        type="primary",
        disabled=not is_balanced,
        use_container_width=True,
    ):
        new_tx = Transaction(
            date=tx_date,
            description=tx_desc.strip() if tx_desc else "振替仕訳",
            counterparty=tx_cp.strip() if tx_cp else None,
            invoice_number=tx_inv.strip() if tx_inv else None,
            lines=tx_lines,
        )

        async def commit_tx(tx_obj: Transaction, fb: Optional[bytes] = None):
            async with DI.get_journal_service() as s:
                if fb:
                    return await s.add_journal_entry_with_evidence(
                        tx_obj, fb, DI.get_file_service()
                    )
                return await s.add_journal_entry(tx_obj)

        try:
            ocr_raw_bytes: Optional[bytes] = st.session_state.get("ocr_bytes")
            run_async(commit_tx(new_tx, ocr_raw_bytes))
            st.session_state["ocr_result"] = None
            st.session_state["ocr_bytes"] = None
            st.success("仕訳が正常に登録されました！")
            st.rerun()
        except Exception as e:
            st.error(f"仕訳登録エラー: {e}")

# 2. 仕訳帳一覧
with tab_history:
    st.subheader("仕訳帳 (General Journal) 一覧・検索・CSV出力")
    col_f1, col_f2 = st.columns(2)
    s_date = st.date_input(
        "開始日",
        value=open_fy.start_date if open_fy else date(date.today().year, 1, 1),
        key="hist_s_date",
    )
    e_date = st.date_input(
        "終了日",
        value=open_fy.end_date if open_fy else date(date.today().year, 12, 31),
        key="hist_e_date",
    )

    async def fetch_entries(sd, ed):
        async with DI.get_journal_service() as s:
            return await s.get_entries(start_date=sd, end_date=ed)

    entries = run_async(fetch_entries(s_date, e_date))
    if not entries:
        st.info("該当する仕訳データはありません。")
    else:
        rows = []
        for tx in entries:
            d_lines = [line for line in tx.lines if line.debit > 0]
            c_lines = [line for line in tx.lines if line.credit > 0]
            for i in range(max(len(d_lines), len(c_lines), 1)):
                d = d_lines[i] if i < len(d_lines) else None
                c = c_lines[i] if i < len(c_lines) else None
                rows.append(
                    {
                        "id": tx.id,
                        "取引日": str(tx.date),
                        "借方科目": account_id_to_label.get(d.account_id, "")
                        if d
                        else "",
                        "借方金額": d.debit if d else 0,
                        "貸方科目": account_id_to_label.get(c.account_id, "")
                        if c
                        else "",
                        "貸方金額": c.credit if c else 0,
                        "摘要": tx.description or "",
                        "取引先": tx.counterparty or "",
                        "インボイス番号": tx.invoice_number or "",
                    }
                )

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        csv_buf = io.StringIO()
        pd.DataFrame(rows).to_csv(csv_buf, index=False)
        st.download_button(
            "📥 仕訳帳 CSV をエクスポート",
            data=csv_buf.getvalue().encode("utf_8_sig"),
            file_name=f"journal_{s_date}_{e_date}.csv",
            mime="text/csv",
        )
