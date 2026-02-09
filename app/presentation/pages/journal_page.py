import streamlit as st
from container import Container
from presentation.components.journal_input import render_journal_input
from presentation.components.journal_list import render_journal_list

async def render_journal_page(container: Container):
    st.header("仕訳入力")
    
    tab1, tab2 = st.tabs(["仕訳入力", "仕訳帳"])
    
    with tab1:
        await render_journal_input(container)
        
    with tab2:
        await render_journal_list(container)
