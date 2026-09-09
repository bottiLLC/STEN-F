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

from app.infrastructure.db.seed_data import seed_accounts
from app.ui.async_helper import run_async
from app.ui.di import DI

nest_asyncio.apply()

log = structlog.get_logger()

st.set_page_config(
    page_title="STEN-F 会計システム",
    page_icon="📑",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "initialized" not in st.session_state:
    try:
        run_async(seed_accounts())
        st.session_state.initialized = True
    except Exception as e:
        log.error("Startup seeding error", error=str(e))

pages = [
    st.Page("app/ui/views/journal_view.py", title="仕訳・記帳ワークスペース", icon=":material/edit_note:", default=True),
    st.Page("app/ui/views/ledger_view.py", title="元帳・決算ワークスペース", icon=":material/analytics:"),
    st.Page("app/ui/views/master_view.py", title="マスタ・設定ワークスペース", icon=":material/settings:"),
]
nav = st.navigation(pages)

with st.sidebar:
    st.title("STEN-F 会計")
    st.caption("Simple Tough Effective Next-generation Finance")
    st.divider()
    try:
        async def fetch_info():
            async with DI.get_master_service() as s:
                c = await s.get_corporation()
                f = await s.get_fiscal_years()
                return c, next((x for x in f if x.status == "OPEN"), None)

        corp_info, open_fy = run_async(fetch_info())
        if corp_info and corp_info.name:
            st.markdown(f"🏢 **{corp_info.name}**")
            if corp_info.representative_name:
                st.caption(f"代表者: {corp_info.representative_title or ''} {corp_info.representative_name}")
        else:
            st.caption("🏢 ※ 自社情報未設定 (マスタ管理で登録)")

        st.markdown("---")
        if open_fy:
            st.info(f"📅 **進行中の会計年度**\n\n**{open_fy.name}**\n\n`{open_fy.start_date}` 〜 `{open_fy.end_date}`")
        else:
            st.warning("⚠️ 進行中の会計年度がありません。")
    except Exception as e:
        log.error("Failed to load sidebar global info", error=str(e))

    st.divider()
    st.caption("© 2026 合同会社ぼっち (GPL-3.0)")

nav.run()
