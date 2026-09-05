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

import pandas as pd
import streamlit as st
import structlog

from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("合計残高試算表 (Trial Balance)", divider="blue")
st.caption(
    "すべての勘定科目の借方・貸方の合計および残高を一覧集計し、複式簿記の貸借一致を検証する帳票です。"
)


# --- Fetch Fiscal Years ---
async def fetch_fiscal_years():
    async with DI.get_master_service() as m_service:
        return await m_service.get_fiscal_years()


fiscal_years = run_async(fetch_fiscal_years())

if not fiscal_years:
    st.warning("会計年度が登録されていません。マスタ管理から登録してください。")
    st.stop()

# Fiscal Year Selector
fy_options = {
    f"{fy.name} ({fy.start_date} 〜 {fy.end_date}) [{fy.status}]": fy
    for fy in fiscal_years
}
selected_fy_label = st.selectbox("対象会計年度", list(fy_options.keys()))
selected_fy = fy_options[selected_fy_label]


# Fetch Trial Balance Rows
async def fetch_trial_balance():
    async with DI.get_ledger_service() as service:
        return await service.get_trial_balance(selected_fy.id)


tb_rows = run_async(fetch_trial_balance())

if tb_rows:
    # Calculate overall sums for balance check
    total_debit_sum = sum(r.debit_total for r in tb_rows)
    total_credit_sum = sum(r.credit_total for r in tb_rows)
    total_debit_bal_sum = sum(r.debit_balance for r in tb_rows)
    total_credit_bal_sum = sum(r.credit_balance for r in tb_rows)

    is_totals_balanced = total_debit_sum == total_credit_sum
    is_balances_balanced = total_debit_bal_sum == total_credit_bal_sum

    # Top Balance Status Banner
    with st.container(border=True):
        col_b1, col_b2, col_b3, col_b4 = st.columns(4)
        with col_b1:
            st.metric("借方 合計総額", f"¥{total_debit_sum:,}")
        with col_b2:
            st.metric("貸方 合計総額", f"¥{total_credit_sum:,}")
        with col_b3:
            st.metric(
                "合計 貸借一致",
                "完全一致 ✅" if is_totals_balanced else "不一致 ⚠️",
                delta=f"差額: ¥{abs(total_debit_sum - total_credit_sum):,}",
            )
        with col_b4:
            st.metric(
                "残高 貸借一致",
                "完全一致 ✅" if is_balances_balanced else "不一致 ⚠️",
                delta=f"差額: ¥{abs(total_debit_bal_sum - total_credit_bal_sum):,}",
            )

    st.markdown("---")

    # Format into standard 7-column Trial Balance Table
    # [ 借方残高 | 借方合計 | コード | 勘定科目名 | 科目区分 | 貸方合計 | 貸方残高 ]
    table_data = []
    for r in tb_rows:
        # Hide accounts with zero movements if desired, but standard TB usually lists active ones
        if (
            r.debit_total > 0
            or r.credit_total > 0
            or r.debit_balance > 0
            or r.credit_balance > 0
        ):
            table_data.append(
                {
                    "借方残高 (Debit Bal)": f"¥{r.debit_balance:,}"
                    if r.debit_balance > 0
                    else "-",
                    "借方合計 (Debit Tot)": f"¥{r.debit_total:,}"
                    if r.debit_total > 0
                    else "-",
                    "コード": r.account_code,
                    "勘定科目名": r.account_name,
                    "区分": r.account_type.label
                    if hasattr(r.account_type, "label")
                    else str(r.account_type),
                    "貸方合計 (Credit Tot)": f"¥{r.credit_total:,}"
                    if r.credit_total > 0
                    else "-",
                    "貸方残高 (Credit Bal)": f"¥{r.credit_balance:,}"
                    if r.credit_balance > 0
                    else "-",
                }
            )

    if table_data:
        # Add Total Row
        table_data.append(
            {
                "借方残高 (Debit Bal)": f"¥{total_debit_bal_sum:,}",
                "借方合計 (Debit Tot)": f"¥{total_debit_sum:,}",
                "コード": "【合計】",
                "勘定科目名": "貸借合計・残高総計",
                "区分": "総合計",
                "貸方合計 (Credit Tot)": f"¥{total_credit_sum:,}",
                "貸方残高 (Credit Bal)": f"¥{total_credit_bal_sum:,}",
            }
        )

        df = pd.DataFrame(table_data)
        st.dataframe(
            df,
            column_config={
                "借方残高 (Debit Bal)": st.column_config.TextColumn(
                    "借方残高", width="medium"
                ),
                "借方合計 (Debit Tot)": st.column_config.TextColumn(
                    "借方合計", width="medium"
                ),
                "コード": st.column_config.TextColumn("コード", width="small"),
                "勘定科目名": st.column_config.TextColumn("勘定科目名", width="medium"),
                "区分": st.column_config.TextColumn("科目区分", width="medium"),
                "貸方合計 (Credit Tot)": st.column_config.TextColumn(
                    "貸方合計", width="medium"
                ),
                "貸方残高 (Credit Bal)": st.column_config.TextColumn(
                    "貸方残高", width="medium"
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

        # CSV Download
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            label="📥 合計残高試算表をCSVエクスポート",
            data=csv_bytes,
            file_name=f"trial_balance_{selected_fy.name}.csv",
            mime="text/csv",
            icon=":material/download:",
            type="secondary",
        )
    else:
        st.info("この会計年度には取引実績・残高のある科目がありません。")
else:
    st.info("試算表データを取得できませんでした。")
