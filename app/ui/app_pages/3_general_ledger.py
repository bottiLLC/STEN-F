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

from app.domain.models.account import AccountType
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("総勘定元帳 (General Ledger)", divider="blue")
st.caption("勘定科目ごとにすべての取引明細と残高推移を記録した主要帳簿です。")


# --- Fetch Fiscal Years & Accounts ---
async def fetch_init_data():
    async with DI.get_master_service() as m_service:
        fys = await m_service.get_fiscal_years()
        accounts = await m_service.get_accounts()
        return fys, accounts


fiscal_years, accounts = run_async(fetch_init_data())

if not fiscal_years:
    st.warning("会計年度が登録されていません。マスタ管理から登録してください。")
    st.stop()

# Select Fiscal Year & Account
col_sel1, col_sel2 = st.columns([2, 3])

with col_sel1:
    fy_options = {
        f"{fy.name} ({fy.start_date} 〜 {fy.end_date}) [{fy.status}]": fy
        for fy in fiscal_years
    }
    selected_fy_label = st.selectbox("対象会計年度", list(fy_options.keys()))
    selected_fy = fy_options[selected_fy_label]

with col_sel2:
    acc_options = {
        f"{a.code}: {a.name} ({a.type.label if hasattr(a.type, 'label') else a.type})": a
        for a in sorted(accounts, key=lambda x: int(x.code))
    }
    selected_acc_label = st.selectbox("勘定科目を選択", list(acc_options.keys()))
    selected_acc = acc_options[selected_acc_label]


# Fetch General Ledger DataFrame
async def fetch_gl():
    async with DI.get_ledger_service() as service:
        return await service.get_general_ledger(selected_fy.id, selected_acc.id)


gl_df = run_async(fetch_gl())


# Fetch Trial Balance for summary
async def fetch_acc_tb():
    async with DI.get_ledger_service() as service:
        tb_rows = await service.get_trial_balance(selected_fy.id)
        return next((r for r in tb_rows if r.account_id == selected_acc.id), None)


acc_tb = run_async(fetch_acc_tb())

# Account Summary Cards
with st.container(border=True):
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("勘定科目", f"{selected_acc.code} {selected_acc.name}")
    with col_s2:
        debit_tot = acc_tb.debit_total if acc_tb else 0
        st.metric("期間 借方合計", f"¥{debit_tot:,}")
    with col_s3:
        credit_tot = acc_tb.credit_total if acc_tb else 0
        st.metric("期間 貸方合計", f"¥{credit_tot:,}")
    with col_s4:
        bal = acc_tb.balance if acc_tb else 0
        is_debit_side = selected_acc.type in [
            AccountType.CURRENT_ASSET,
            AccountType.FIXED_ASSET,
            AccountType.DEFERRED_ASSET,
            AccountType.COST_OF_SALES,
            AccountType.SGA,
            AccountType.NON_OPERATING_EXPENSE,
            AccountType.EXTRAORDINARY_LOSS,
        ]
        side_label = "借方残高" if is_debit_side else "貸方残高"
        st.metric(f"期末残高 ({side_label})", f"¥{bal:,}")

st.markdown("---")

if not gl_df.empty:
    # Format DataFrame for accounting presentation
    display_rows = []
    for _, row in gl_df.iterrows():
        d_val = int(row["借方"])
        c_val = int(row["貸方"])
        b_val = int(row["残高"])
        tx_date_str = str(row["日付"])

        display_rows.append(
            {
                "日付": tx_date_str,
                "摘要": row["摘要"],
                "借方金額 (Debit)": f"¥{d_val:,}" if d_val > 0 else "-",
                "貸方金額 (Credit)": f"¥{c_val:,}" if c_val > 0 else "-",
                "差引残高 (Balance)": f"¥{b_val:,}",
                "伝票ID": row.get("TransactionID", "-"),
            }
        )

    out_df = pd.DataFrame(display_rows)
    st.dataframe(
        out_df,
        column_config={
            "日付": st.column_config.TextColumn("日付", width="small"),
            "摘要": st.column_config.TextColumn("摘要", width="large"),
            "借方金額 (Debit)": st.column_config.TextColumn("借方金額", width="medium"),
            "貸方金額 (Credit)": st.column_config.TextColumn(
                "貸方金額", width="medium"
            ),
            "差引残高 (Balance)": st.column_config.TextColumn(
                "差引残高", width="medium"
            ),
            "伝票ID": st.column_config.TextColumn("伝票ID", width="small"),
        },
        hide_index=True,
        use_container_width=True,
    )

    # Download CSV
    csv_bytes = out_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=f"📥 {selected_acc.name} の元帳をCSVエクスポート",
        data=csv_bytes,
        file_name=f"ledger_{selected_acc.code}_{selected_fy.name}.csv",
        mime="text/csv",
        icon=":material/download:",
        type="secondary",
    )
else:
    st.info(
        f"「{selected_acc.code}: {selected_acc.name}」の該当期間における取引履歴はありません。"
    )
