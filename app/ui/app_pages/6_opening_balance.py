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

import streamlit as st
import structlog

from app.domain.models.account import AccountType
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("期首残高設定 (開始貸借対照表)", divider="blue")
st.caption(
    "事業年度の開始日時点における資産・負債・純資産（元入金等）の残高を設定します。左右の合計（貸借）が一致する必要があります。"
)


# --- Fetch Fiscal Year & Accounts ---
async def fetch_init():
    async with DI.get_master_service() as service:
        fys = await service.get_fiscal_years()
        open_fy = next((f for f in fys if f.status == "OPEN"), None)
        accounts = await service.get_accounts()
    return open_fy, accounts


open_fy, accounts = run_async(fetch_init())

if not open_fy:
    st.warning(
        "進行中 (OPEN) の会計年度がありません。マスタ管理から会計年度を登録してください。"
    )
    st.stop()

st.info(
    f"📅 **対象会計年度:** **{open_fy.name}** (期首日: `{open_fy.start_date}` 〜 期末日: `{open_fy.end_date}`)"
)

# Split accounts into Balance Sheet categories
asset_accounts = sorted(
    [
        a
        for a in accounts
        if a.type
        in (
            AccountType.CURRENT_ASSET,
            AccountType.FIXED_ASSET,
            AccountType.DEFERRED_ASSET,
        )
    ],
    key=lambda x: int(x.code),
)
liability_accounts = sorted(
    [
        a
        for a in accounts
        if a.type in (AccountType.CURRENT_LIABILITY, AccountType.FIXED_LIABILITY)
    ],
    key=lambda x: int(x.code),
)
equity_accounts = sorted(
    [a for a in accounts if a.type == AccountType.EQUITY],
    key=lambda x: int(x.code),
)

with st.form("opening_balance_form", clear_on_submit=False):
    col_assets, col_liab_eq = st.columns(2)

    debit_balances = {}
    credit_balances = {}

    with col_assets:
        st.markdown(
            "### <span class='badge-debit'>【 借方 : 資産の部 (Assets) 】</span>",
            unsafe_allow_html=True,
        )
        for acc in asset_accounts:
            val = st.number_input(
                f"{acc.code}: {acc.name}",
                min_value=0,
                step=10000,
                key=f"ob_debit_{acc.id}",
            )
            if val > 0:
                debit_balances[acc.id] = int(val)

    with col_liab_eq:
        st.markdown(
            "### <span class='badge-credit'>【 貸方 : 負債の部 (Liabilities) 】</span>",
            unsafe_allow_html=True,
        )
        for acc in liability_accounts:
            val = st.number_input(
                f"{acc.code}: {acc.name}",
                min_value=0,
                step=10000,
                key=f"ob_credit_liab_{acc.id}",
            )
            if val > 0:
                credit_balances[acc.id] = int(val)

        st.markdown(
            "### <span class='badge-credit'>【 貸方 : 純資産の部 (Equity) 】</span>",
            unsafe_allow_html=True,
        )
        for acc in equity_accounts:
            val = st.number_input(
                f"{acc.code}: {acc.name}",
                min_value=0,
                step=10000,
                key=f"ob_credit_eq_{acc.id}",
            )
            if val > 0:
                credit_balances[acc.id] = int(val)

    total_debit = sum(debit_balances.values())
    total_credit = sum(credit_balances.values())
    diff = total_debit - total_credit

    st.divider()
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("借方合計 (資産の部)", f"¥{total_debit:,}")
    with col_m2:
        st.metric("貸方合計 (負債 + 純資産)", f"¥{total_credit:,}")
    with col_m3:
        st.metric(
            "貸借バランス",
            "完全一致 ✅" if diff == 0 and total_debit > 0 else "不一致 ⚠️",
            delta=f"差額: ¥{abs(diff):,}",
            delta_color="normal" if diff == 0 else "inverse",
        )

    submit_btn = st.form_submit_button(
        "💾 期首残高を登録する", type="primary", icon=":material/save:"
    )

    if submit_btn:
        if total_debit == 0 and total_credit == 0:
            st.error("残高が入力されていません。金額を入力してください。")
        elif diff != 0:
            st.error(
                f"貸借不一致エラー: 借方合計 ¥{total_debit:,} と 貸方合計 ¥{total_credit:,} が一致していません。(差額: ¥{abs(diff):,})"
            )
        else:
            try:

                async def save_opening_bs():
                    async with DI.get_journal_service() as service:
                        await service.register_opening_balance(
                            opening_date=open_fy.start_date,
                            debit_balances=debit_balances,
                            credit_balances=credit_balances,
                        )

                run_async(save_opening_bs())
                st.toast("期首残高を登録しました！", icon="🎉")
                st.success(f"{open_fy.name} の期首残高を正常に登録しました。")
            except Exception as e:
                log.error(
                    "Failed to register opening balance", error=str(e), exc_info=True
                )
                st.error(f"登録エラー: {e}")
