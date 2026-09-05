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

import os
from datetime import date
import pandas as pd
import streamlit as st
import structlog

from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("仕訳帳 (General Journal)", divider="blue")
st.caption(
    "すべての取引が日付順に記録された複式簿記の主要帳簿です。検索・証憑確認・CSV出力が行えます。"
)


# --- Fetch Fiscal Years for Date Defaults ---
async def fetch_fiscal_years_and_accounts():
    async with DI.get_master_service() as service:
        fys = await service.get_fiscal_years()
        open_fy = next((f for f in fys if f.status == "OPEN"), None)
        accounts = await service.get_accounts()
        return open_fy, fys, accounts


open_fy, all_fys, accounts = run_async(fetch_fiscal_years_and_accounts())
account_map = {a.id: f"{a.code}: {a.name}" for a in accounts}

default_start = open_fy.start_date if open_fy else date(date.today().year, 1, 1)
default_end = open_fy.end_date if open_fy else date(date.today().year, 12, 31)

# --- Filter Controls ---
with st.container(border=True):
    st.subheader("🔍 帳簿の検索・絞り込み")
    col1, col2, col3, col4 = st.columns([2, 2, 3, 2])

    with col1:
        filter_start = st.date_input("開始日", value=default_start)
    with col2:
        filter_end = st.date_input("終了日", value=default_end)
    with col3:
        acc_filter_options = ["すべて"] + [
            f"{a.code}: {a.name}" for a in sorted(accounts, key=lambda x: int(x.code))
        ]
        selected_acc_filter = st.selectbox("勘定科目で絞り込み", acc_filter_options)
    with col4:
        keyword = st.text_input("キーワード (摘要/取引先)")

    col_opt1, col_opt2 = st.columns([3, 2])
    with col_opt1:
        show_deleted = st.checkbox("削除済みの仕訳も含めて表示", value=False)
    with col_opt2:
        evidence_only = st.checkbox("証憑添付ありのみ表示", value=False)


# --- Fetch Entries ---
async def fetch_entries():
    async with DI.get_journal_service() as j_service:
        return await j_service.get_entries(
            start_date=filter_start,
            end_date=filter_end,
            include_deleted=show_deleted,
        )


entries = run_async(fetch_entries())

# Filter in-memory by account, keyword, evidence
if selected_acc_filter != "すべて":
    selected_code = selected_acc_filter.split(":")[0].strip()
    target_acc_id = next((a.id for a in accounts if a.code == selected_code), None)
    if target_acc_id:
        entries = [
            e
            for e in entries
            if any(line.account_id == target_acc_id for line in e.lines)
        ]

if keyword:
    kw = keyword.lower()
    entries = [
        e
        for e in entries
        if (e.description and kw in e.description.lower())
        or (e.counterparty and kw in e.counterparty.lower())
    ]

if evidence_only:
    entries = [e for e in entries if e.evidence_path]

# --- Summary Metrics ---
total_debit_all = sum(
    sum(line.debit for line in e.lines) for e in entries if not e.is_deleted
)
total_credit_all = sum(
    sum(line.credit for line in e.lines) for e in entries if not e.is_deleted
)

col_m1, col_m2, col_m3, col_m4 = st.columns([2, 3, 3, 2])
with col_m1:
    st.metric("仕訳件数", f"{len(entries)} 件")
with col_m2:
    st.metric("期間 借方合計", f"¥{total_debit_all:,}")
with col_m3:
    st.metric("期間 貸方合計", f"¥{total_credit_all:,}")
with col_m4:
    is_bal = total_debit_all == total_credit_all
    st.metric(
        "貸借バランス",
        "一致 ✅" if is_bal else "不一致 ⚠️",
        delta="¥0" if is_bal else f"¥{abs(total_debit_all - total_credit_all):,}",
    )

st.markdown("---")

# --- Export CSV Button ---
col_act1, col_act2 = st.columns([3, 5])
with col_act1:

    async def get_csv_data():
        async with DI.get_journal_service() as j_service:
            return await j_service.export_journal_entries_csv(
                start_date=filter_start, end_date=filter_end
            )

    csv_data = run_async(get_csv_data())
    st.download_button(
        label="📥 仕訳帳データをCSVエクスポート",
        data=csv_data,
        file_name=f"journal_entries_{filter_start}_{filter_end}.csv",
        mime="text/csv",
        icon=":material/download:",
        type="secondary",
    )

# --- Table Display (Traditional Journal Ledger Style) ---
if entries:
    rows = []
    row_to_entry = {}

    for e in entries:
        debit_lines = [line for line in e.lines if line.debit > 0]
        credit_lines = [line for line in e.lines if line.credit > 0]
        max_lines = max(len(debit_lines), len(credit_lines), 1)

        for i in range(max_lines):
            d_line = debit_lines[i] if i < len(debit_lines) else None
            c_line = credit_lines[i] if i < len(credit_lines) else None

            rows.append(
                {
                    "ID": str(e.id) if i == 0 else "",
                    "取引日": e.date.isoformat() if i == 0 else "",
                    "借方科目": (
                        account_map.get(d_line.account_id, str(d_line.account_id))
                        if d_line
                        else ""
                    ),
                    "借方金額": f"¥{d_line.debit:,}" if d_line else "",
                    "貸方科目": (
                        account_map.get(c_line.account_id, str(c_line.account_id))
                        if c_line
                        else ""
                    ),
                    "貸方金額": f"¥{c_line.credit:,}" if c_line else "",
                    "摘要 (取引内容)": (e.description or "") if i == 0 else "",
                    "取引先": (e.counterparty or "") if i == 0 else "",
                    "登録番号": (e.invoice_number or "") if i == 0 else "",
                    "証憑": ("📄 あり" if e.evidence_path else "-") if i == 0 else "",
                    "状態": ("🗑️ 削除済" if e.is_deleted else "有効") if i == 0 else "",
                }
            )
            row_to_entry[len(rows) - 1] = e

    df = pd.DataFrame(rows)
    selection_event = st.dataframe(
        df,
        column_config={
            "ID": st.column_config.TextColumn("ID", width="small"),
            "取引日": st.column_config.TextColumn("取引日", width="small"),
            "借方科目": st.column_config.TextColumn("借方科目", width="medium"),
            "借方金額": st.column_config.TextColumn("借方金額", width="small"),
            "貸方科目": st.column_config.TextColumn("貸方科目", width="medium"),
            "貸方金額": st.column_config.TextColumn("貸方金額", width="small"),
            "摘要 (取引内容)": st.column_config.TextColumn(
                "摘要 (取引内容)", width="medium"
            ),
            "取引先": st.column_config.TextColumn("取引先", width="medium"),
            "登録番号": st.column_config.TextColumn("登録番号", width="small"),
            "証憑": st.column_config.TextColumn("証憑", width="small"),
            "状態": st.column_config.TextColumn("状態", width="small"),
        },
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        use_container_width=True,
    )

    # Determine selected entry from row selection checkbox
    selected_entry = None
    selection_obj = getattr(selection_event, "selection", None)
    if selection_obj and hasattr(selection_obj, "rows") and selection_obj.rows:
        selected_row_idx = selection_obj.rows[0]
        if isinstance(selected_row_idx, int) and selected_row_idx in row_to_entry:
            selected_entry = row_to_entry[selected_row_idx]

    # --- Actions when row is selected ---
    if selected_entry:
        st.markdown("---")
        with st.container(border=True):
            st.markdown(
                f"### 🎯 選択仕訳の詳細: `ID: {selected_entry.id}` ({selected_entry.date} / {selected_entry.description or '摘要なし'})"
            )
            col_action1, col_action2 = st.columns([3, 2])

            with col_action1:
                if selected_entry.evidence_path and os.path.exists(
                    selected_entry.evidence_path
                ):
                    with open(selected_entry.evidence_path, "rb") as f:
                        file_data = f.read()
                    file_name = os.path.basename(selected_entry.evidence_path)
                    st.download_button(
                        label=f"📥 証憑ファイル ({file_name}) をダウンロード",
                        data=file_data,
                        file_name=file_name,
                        type="primary",
                        icon=":material/download:",
                    )
                elif selected_entry.evidence_path:
                    st.warning("⚠️ 証憑ファイルがストレージ上に見つかりません。")
                else:
                    st.caption("※ この仕訳に添付された証憑はありません。")

            with col_action2:
                if not selected_entry.is_deleted:
                    if st.button(
                        "この仕訳を削除する", type="secondary", icon=":material/delete:"
                    ):

                        async def delete_selected_tx():
                            async with DI.get_journal_service() as j_service:
                                await j_service.delete_entry(selected_entry.id)

                        run_async(delete_selected_tx())
                        st.toast("仕訳を削除しました（論理削除）。", icon="🗑️")
                        st.rerun()

else:
    st.info("指定した条件に一致する仕訳データはありません。")
