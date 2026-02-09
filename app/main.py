import streamlit as st
import asyncio
import sys
from pathlib import Path

# Add project root to pythonpath
sys.path.append(str(Path(__file__).parent))

from container import Container
from presentation.pages.master_page import render_master_page
from presentation.pages.journal_page import render_journal_page
from presentation.pages.reports_page import render_reports_page

st.set_page_config(page_title="STEN-F", layout="wide")

async def main():
    # Initialize Container
    container = Container()
    
    st.sidebar.title("STEN-F")
    page = st.sidebar.radio("メニュー", ["仕訳入力", "マスタ管理", "レポート"])
    
    if page == "仕訳入力":
        await render_journal_page(container)
        
    elif page == "マスタ管理":
        await render_master_page(container)
        
    elif page == "レポート":
        await render_reports_page(container)

if __name__ == "__main__":
    # Streamlit runs in its own loop, but for async main:
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if current_loop and current_loop.is_running():
        # We are already in an event loop (Streamlit)
        asyncio.create_task(main())
    else:
        asyncio.run(main())
