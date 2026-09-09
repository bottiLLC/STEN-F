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
from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st
import structlog

from app.domain.models.transaction import Transaction, TransactionLine
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("仕訳帳 (General Journal)", divider="blue")
st.caption(
    "すべての取引が日付順に記録された複式簿記の主要帳簿です。検索・証憑確認・編集・CSV出力が行えます。"
)


# --- Fetch Initial Data (Fiscal Years, Accounts, Abstracts) ---
async def fetch_page_init_data():
    async with DI.get_master_service() as service:
        fys = await service.get_fiscal_years()
        open_fy = next((f for f in fys if f.status == "OPEN"), None)
        accounts = await service.get_accounts()
        abstracts = await service.get_abstracts()
        return open_fy, fys, accounts, abstracts


open_fy, all_fys, accounts, abstracts = run_async(fetch_page_init_data())
account_map: Dict[int, str] = {a.id: f"{a.code}: {a.name}" for a in accounts}

# Account options sorted by code
account_labels: List[str] = [""] + [
    f"{a.code}: {a.name}" for a in sorted(accounts, key=lambda x: int(x.code))
]
account_options: Dict[str, str] = {
    f"{a.code}: {a.name}": str(a.id)
    for a in sorted(accounts, key=lambda x: int(x.code))
}
account_options[""] = ""

abstract_options: List[str] = [""] + sorted(
    list(set(ab.text for ab in abstracts if ab.text))
)

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
    st.caption(
        "💡 行をクリックすると、下に振替伝票形式で詳細が表示され、直接編集・更新が行えます。"
    )
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

    # Determine selected entry from row selection
    selected_entry: Optional[Transaction] = None
    selection_obj = getattr(selection_event, "selection", None)
    if selection_obj and hasattr(selection_obj, "rows") and selection_obj.rows:
        selected_row_idx = selection_obj.rows[0]
        if isinstance(selected_row_idx, int) and selected_row_idx in row_to_entry:
            selected_entry = row_to_entry[selected_row_idx]

    # --- Actions & Edit Form when row is selected ---
    if selected_entry:
        st.markdown("---")
        with st.container(border=True):
            st.subheader(f"📝 選択仕訳の詳細・編集 (ID: {selected_entry.id})")
            st.caption(
                "仕訳の内容（日付・摘要・取引先・借方/貸方明細）を直接修正して更新保存できます。"
            )

            # 1. 証憑ダウンロード & 削除ボタン
            col_act_left, col_act_right = st.columns([3, 2])
            with col_act_left:
                if selected_entry.evidence_path and os.path.exists(
                    selected_entry.evidence_path
                ):
                    with open(selected_entry.evidence_path, "rb") as f:
                        file_data = f.read()
                    file_name = os.path.basename(selected_entry.evidence_path)
                    st.download_button(
                        label=f"📥 添付証憑 ({file_name}) をダウンロード",
                        data=file_data,
                        file_name=file_name,
                        type="secondary",
                        icon=":material/download:",
                        key=f"dl_evidence_{selected_entry.id}",
                    )
                elif selected_entry.evidence_path:
                    st.warning("⚠️ 証憑ファイルがストレージ上に見つかりません。")
                else:
                    st.caption("※ この仕訳に添付された証憑はありません。")

            with col_act_right:
                if not selected_entry.is_deleted:
                    if st.button(
                        "この仕訳を削除する",
                        type="secondary",
                        icon=":material/delete:",
                        key=f"del_tx_btn_{selected_entry.id}",
                    ):

                        async def delete_selected_tx():
                            async with DI.get_journal_service() as j_service:
                                await j_service.delete_entry(selected_entry.id)

                        run_async(delete_selected_tx())
                        st.toast(
                            f"仕訳 (ID: {selected_entry.id}) を削除しました。", icon="🗑️"
                        )
                        st.rerun()

            st.markdown("---")

            # 2. 振替伝票形式の編集フォーム (Step 2: 振替伝票 相当)
            # Prepare initial lines from selected entry
            debit_lines = [line for line in selected_entry.lines if line.debit > 0]
            credit_lines = [line for line in selected_entry.lines if line.credit > 0]
            initial_line_count = max(len(debit_lines), len(credit_lines), 1)

            default_edit_lines = []
            for i in range(initial_line_count):
                d_line = debit_lines[i] if i < len(debit_lines) else None
                c_line = credit_lines[i] if i < len(credit_lines) else None
                d_acc = account_map.get(d_line.account_id, "") if d_line else ""
                c_acc = account_map.get(c_line.account_id, "") if c_line else ""
                default_edit_lines.append(
                    {
                        "debit_acc": d_acc,
                        "debit_amt": d_line.debit if d_line else 0,
                        "credit_acc": c_acc,
                        "credit_amt": c_line.credit if c_line else 0,
                    }
                )

            # Manage line count state
            line_count_key = f"edit_line_count_{selected_entry.id}"
            if line_count_key not in st.session_state:
                st.session_state[line_count_key] = len(default_edit_lines)

            # Transaction Header Info
            col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 2, 2])
            with col_h1:
                edit_tx_date = st.date_input(
                    "取引日 (発生日)",
                    value=selected_entry.date,
                    key=f"edit_tx_date_{selected_entry.id}",
                )

            with col_h2:
                # Determine default abstract selection
                curr_desc = selected_entry.description or ""
                default_abstract_idx = 0
                for idx, opt in enumerate(abstract_options):
                    if opt and opt == curr_desc.strip():
                        default_abstract_idx = idx
                        break

                edit_abstract_choice = st.selectbox(
                    "よく使う摘要から選ぶ",
                    abstract_options,
                    index=default_abstract_idx,
                    key=f"edit_abstract_choice_{selected_entry.id}",
                )
                edit_desc_input = st.text_input(
                    "摘要 (取引内容)",
                    value=curr_desc,
                    key=f"edit_desc_input_{selected_entry.id}",
                )
                edit_final_desc = (
                    edit_abstract_choice if edit_abstract_choice else edit_desc_input
                )

            with col_h3:
                edit_cp = st.text_input(
                    "取引先 (支払先/売上先)",
                    value=selected_entry.counterparty or "",
                    key=f"edit_cp_{selected_entry.id}",
                )

            with col_h4:
                edit_inv = st.text_input(
                    "インボイス登録番号",
                    value=selected_entry.invoice_number or "",
                    help="適格請求書発行事業者の登録番号 (例: T1234567890123)",
                    key=f"edit_inv_{selected_entry.id}",
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

            edit_line_inputs: List[Dict[str, Any]] = []
            curr_lines_num = int(st.session_state[line_count_key])

            for i in range(curr_lines_num):
                d_line_def = (
                    default_edit_lines[i]
                    if i < len(default_edit_lines)
                    else {
                        "debit_acc": "",
                        "debit_amt": 0,
                        "credit_acc": "",
                        "credit_amt": 0,
                    }
                )

                col_d_acc, col_d_amt, col_c_acc, col_c_amt = st.columns([3, 2, 3, 2])

                with col_d_acc:
                    d_acc_val = str(d_line_def["debit_acc"])
                    d_idx = (
                        account_labels.index(d_acc_val)
                        if d_acc_val in account_labels
                        else 0
                    )
                    debit_acc = st.selectbox(
                        f"借方科目 (行 {i + 1})",
                        account_labels,
                        index=d_idx,
                        key=f"edit_debit_acc_{selected_entry.id}_{i}",
                    )

                with col_d_amt:
                    debit_amt = st.number_input(
                        f"借方金額 (行 {i + 1})",
                        min_value=0,
                        value=int(str(d_line_def.get("debit_amt", 0))),
                        step=1000,
                        key=f"edit_debit_amt_{selected_entry.id}_{i}",
                    )

                with col_c_acc:
                    c_acc_val = str(d_line_def["credit_acc"])
                    c_idx = (
                        account_labels.index(c_acc_val)
                        if c_acc_val in account_labels
                        else 0
                    )
                    credit_acc = st.selectbox(
                        f"貸方科目 (行 {i + 1})",
                        account_labels,
                        index=c_idx,
                        key=f"edit_credit_acc_{selected_entry.id}_{i}",
                    )

                with col_c_amt:
                    credit_amt = st.number_input(
                        f"貸方金額 (行 {i + 1})",
                        min_value=0,
                        value=int(str(d_line_def.get("credit_amt", 0))),
                        step=1000,
                        key=f"edit_credit_amt_{selected_entry.id}_{i}",
                    )

                edit_line_inputs.append(
                    {
                        "debit_acc": str(debit_acc),
                        "debit_amt": int(debit_amt),
                        "credit_acc": str(credit_acc),
                        "credit_amt": int(credit_amt),
                    }
                )

            # Add / Remove Line Buttons
            col_l_btn1, col_l_btn2, col_l_sp = st.columns([2, 2, 4])
            with col_l_btn1:
                if st.button(
                    "＋ 行を追加",
                    type="secondary",
                    icon=":material/add:",
                    key=f"edit_add_line_{selected_entry.id}",
                ):
                    st.session_state[line_count_key] += 1
                    st.rerun()

            with col_l_btn2:
                if curr_lines_num > 1 and st.button(
                    "－ 最後の行を削除",
                    type="secondary",
                    icon=":material/remove:",
                    key=f"edit_del_line_{selected_entry.id}",
                ):
                    st.session_state[line_count_key] -= 1
                    st.rerun()

            st.markdown("---")

            # Calculate Totals & Balance
            total_debit_edit: int = sum(
                int(line["debit_amt"]) for line in edit_line_inputs
            )
            total_credit_edit: int = sum(
                int(line["credit_amt"]) for line in edit_line_inputs
            )
            is_edit_balanced = (
                total_debit_edit == total_credit_edit and total_debit_edit > 0
            )

            # Realtime Balance Indicators
            col_b1, col_b2, col_b3 = st.columns(3)
            with col_b1:
                st.metric("修正後 借方合計", f"¥{total_debit_edit:,}")
            with col_b2:
                st.metric("修正後 貸方合計", f"¥{total_credit_edit:,}")
            with col_b3:
                if is_edit_balanced:
                    st.metric("貸借バランス", "一致 (登録可能) ✅", delta="¥0")
                elif total_debit_edit == 0 and total_credit_edit == 0:
                    st.metric("貸借バランス", "金額未入力", delta="¥0")
                else:
                    diff = abs(total_debit_edit - total_credit_edit)
                    st.metric(
                        "貸借バランス", "不一致 (要確認) ⚠️", delta=f"差額: ¥{diff:,}"
                    )

            st.markdown("---")

            # Update Submit Button
            if selected_entry.is_deleted:
                st.warning("⚠️ この仕訳は削除済みのため編集できません。")
            else:
                if st.button(
                    "💾 修正内容で仕訳を更新する",
                    type="primary",
                    icon=":material/save:",
                    use_container_width=True,
                    disabled=not is_edit_balanced,
                    key=f"save_edit_tx_btn_{selected_entry.id}",
                ):
                    # Validate inputs
                    lines_to_save: List[TransactionLine] = []
                    for item in edit_line_inputs:
                        d_acc_str = str(item["debit_acc"])
                        c_acc_str = str(item["credit_acc"])
                        d_amt_val = int(item["debit_amt"])
                        c_amt_val = int(item["credit_amt"])

                        d_acc_id_str = account_options.get(d_acc_str)
                        c_acc_id_str = account_options.get(c_acc_str)

                        if d_acc_id_str and d_amt_val > 0:
                            lines_to_save.append(
                                TransactionLine(
                                    account_id=int(d_acc_id_str),
                                    debit=d_amt_val,
                                    credit=0,
                                )
                            )
                        if c_acc_id_str and c_amt_val > 0:
                            lines_to_save.append(
                                TransactionLine(
                                    account_id=int(c_acc_id_str),
                                    debit=0,
                                    credit=c_amt_val,
                                )
                            )

                    if not lines_to_save:
                        st.error("有効な借方・貸方の明細行が入力されていません。")
                    elif total_debit_edit != total_credit_edit:
                        st.error(
                            f"借方合計（¥{total_debit_edit:,}）と貸方合計（¥{total_credit_edit:,}）が一致していません。"
                        )
                    else:
                        updated_tx = Transaction(
                            id=selected_entry.id,
                            date=edit_tx_date,
                            description=edit_final_desc,
                            counterparty=edit_cp,
                            invoice_number=edit_inv,
                            evidence_path=selected_entry.evidence_path,
                            is_deleted=selected_entry.is_deleted,
                            lines=lines_to_save,
                        )

                        async def do_update_tx():
                            async with DI.get_journal_service() as j_service:
                                return await j_service.update_journal_entry(updated_tx)

                        try:
                            success = run_async(do_update_tx())
                            if success:
                                st.toast(
                                    f"仕訳 (ID: {selected_entry.id}) を正常に更新しました！",
                                    icon="✅",
                                )
                                st.rerun()
                            else:
                                st.error(
                                    "仕訳の更新に失敗しました（仕訳が見つかりません）。"
                                )
                        except Exception as e:
                            log.error(
                                "Failed to update journal entry",
                                error=str(e),
                                exc_info=True,
                            )
                            st.error(f"仕訳更新エラー: {e}")

else:
    st.info("指定した条件に一致する仕訳データはありません。")
