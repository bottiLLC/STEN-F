import streamlit as st
from container import Container
from presentation.constants import ACCOUNT_TYPE_JP, FY_STATUS_JP
from config import CURRENCY_SYMBOL
from presentation.state.session_manager import SessionManager

from presentation.components.reports.trial_balance_tab import render_trial_balance_tab
from presentation.components.reports.financial_statements_tab import render_financial_statements_tab
from presentation.components.reports.general_ledger_tab import render_general_ledger_tab
from presentation.components.reports.pdf_export_tab import render_pdf_export_tab

async def render_reports_page(container: Container):
    st.header("レポート")
    
    # Dependencies
    ledger_service = await container.get_ledger_service()
    master_service = await container.get_master_service()
    session = SessionManager()

    # Fiscal Year Selection
    fys = await master_service.get_fiscal_years()
    if not fys:
        st.warning("会計年度が設定されていません。")
        return

    fy_options = {fy.id: f"{fy.name} (第{fy.period_number}期)" for fy in fys} # Modified to include period_number for display
    
    # Default to current session state or first available
    current_fy_id = session.get("report_fy_id")
    if current_fy_id is None or current_fy_id not in fy_options:
        current_fy_id = fys[0].id
        session.set("report_fy_id", current_fy_id)

    col1, col2 = st.columns([1, 3])
    with col1:
        selected_fy_id = st.selectbox(
            "会計年度", 
            options=list(fy_options.keys()), 
            format_func=lambda x: fy_options[x],
            index=list(fy_options.keys()).index(current_fy_id),
            key="fy_selector" 
        )
        
        # Sync selection back to session manager
        if selected_fy_id != current_fy_id:
            session.set("report_fy_id", selected_fy_id)
            session.set("report_run", False) # Reset run state on FY change
            st.rerun()

    with col2:
        st.write("") 
        st.write("")
        if st.button("集計実行", type="primary"):
            session.set("report_run", True)
            st.rerun()

    # Display FY details
    current_fy = next((f for f in fys if f.id == selected_fy_id), None)
    if current_fy:
        st.caption(f"期間: {current_fy.start_date} 〜 {current_fy.end_date} (ステータス: {FY_STATUS_JP.get(current_fy.status, current_fy.status)})")

    if not session.get("report_run", False):
        st.info("会計年度を選択して「集計実行」ボタンを押してください。")
        return

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "合計残高試算表", 
        "財務諸表 (B/S, P/L)", # Reverted to original tab name for consistency
        "総勘定元帳", 
        "PDF出力"
    ])
    
    # current_fy is already resolved above

    with tab1:
        await render_trial_balance_tab(ledger_service, selected_fy_id)

    with tab2:
        await render_financial_statements_tab(ledger_service, selected_fy_id)

    with tab3:
        await render_general_ledger_tab(ledger_service, master_service, selected_fy_id)

    with tab4:
        await render_pdf_export_tab(container, ledger_service, master_service, selected_fy_id, current_fy)

