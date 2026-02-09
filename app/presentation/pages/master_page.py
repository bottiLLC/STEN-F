import streamlit as st
from container import Container

from presentation.components.master.corporation_tab import render_corporation_tab
from presentation.components.master.fiscal_year_tab import render_fiscal_year_tab
from presentation.components.master.account_tab import render_account_tab
from presentation.components.master.abstract_tab import render_abstract_tab
from presentation.components.master.system_tab import render_system_tab

async def render_master_page(container: Container):
    st.header("マスタ管理")
    
    master_service = await container.get_master_service()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["法人設定", "会計年度", "勘定科目", "摘要", "システム"])
    
    with tab1:
        await render_corporation_tab(master_service)

    with tab2:
        await render_fiscal_year_tab(master_service)

    with tab3:
        await render_account_tab(master_service)

    with tab4:
        await render_abstract_tab(master_service)

    with tab5:
        await render_system_tab(container)
