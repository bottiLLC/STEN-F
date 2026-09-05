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

import nest_asyncio
import streamlit as st
import structlog

# Apply nest_asyncio at the very top to prevent Tornado event loop conflicts
nest_asyncio.apply()

from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles
from app.infrastructure.db.seed_data import seed_accounts

log = structlog.get_logger()

# Configure page layout
st.set_page_config(
    page_title="STEN-F 会計システム",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_app_state():
    """Initializes global session state and runs startup seeding if needed."""
    if "initialized" not in st.session_state:
        try:
            run_async(seed_accounts())
            st.session_state.initialized = True
            log.info("App initialized and accounts seeded.")
        except Exception as e:
            log.error("Startup seeding error", error=str(e), exc_info=True)


init_app_state()
apply_accounting_styles()

# Define navigation pages grouped by standard accounting workflows
pages = {
    "日常の記帳": [
        st.Page(
            "app/ui/app_pages/1_journal_entry.py",
            title="仕訳入力 (AI/振替伝票)",
            icon=":material/edit_note:",
            default=True,
        ),
        st.Page(
            "app/ui/app_pages/2_journal_history.py",
            title="仕訳帳",
            icon=":material/receipt_long:",
        ),
        st.Page(
            "app/ui/app_pages/3_general_ledger.py",
            title="総勘定元帳",
            icon=":material/menu_book:",
        ),
    ],
    "帳簿・決算": [
        st.Page(
            "app/ui/app_pages/4_trial_balance.py",
            title="合計残高試算表 (T/B)",
            icon=":material/table_chart:",
        ),
        st.Page(
            "app/ui/app_pages/5_financial_statements.py",
            title="決算書 (B/S・P/L)",
            icon=":material/analytics:",
        ),
    ],
    "設定・管理": [
        st.Page(
            "app/ui/app_pages/6_opening_balance.py",
            title="期首残高設定 (B/S)",
            icon=":material/account_balance:",
        ),
        st.Page(
            "app/ui/app_pages/7_master_management.py",
            title="マスタ・システム管理",
            icon=":material/settings:",
        ),
    ],
}

nav = st.navigation(pages)

# Render global sidebar status
with st.sidebar:
    st.title("STEN-F 会計")
    st.caption("Simple Tough Effective Next-generation Finance")
    st.divider()

    try:

        async def fetch_global_info():
            async with DI.get_master_service() as service:
                corp = await service.get_corporation()
                fys = await service.get_fiscal_years()
                open_fy = next((f for f in fys if f.status == "OPEN"), None)
                return corp, open_fy

        corp_info, open_fiscal_year = run_async(fetch_global_info())

        if corp_info and corp_info.name:
            st.markdown(f"🏢 **{corp_info.name}**")
            if corp_info.representative_name:
                st.caption(
                    f"代表者: {corp_info.representative_title or ''} {corp_info.representative_name}"
                )
        else:
            st.caption("🏢 ※ 自社情報未設定 (マスタ管理で登録)")

        st.markdown("---")

        if open_fiscal_year:
            st.info(
                f"📅 **進行中の会計年度**\n\n**{open_fiscal_year.name}**\n\n`{open_fiscal_year.start_date}` 〜 `{open_fiscal_year.end_date}`"
            )
        else:
            st.warning("⚠️ 進行中の会計年度がありません。マスタ管理から登録してください。")
    except Exception as e:
        log.error("Failed to load sidebar global info", error=str(e))

    st.divider()
    st.caption("© 2026 合同会社ぼっち (GPL-3.0)")

# Execute the routed page
nav.run()
