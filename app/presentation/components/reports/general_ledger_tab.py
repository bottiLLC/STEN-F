import streamlit as st
import pandas as pd
from application.services.ledger_service import LedgerService
from application.services.master_service import MasterService

async def render_general_ledger_tab(ledger_service: LedgerService, master_service: MasterService, selected_fy_id: int):
    st.subheader("総勘定元帳")
    accounts = await master_service.get_accounts()
    # Select Account
    acc_map = {f"{a.code}: {a.name}": a.id for a in accounts}
    sel_acc_label = st.selectbox("科目選択", list(acc_map.keys()))
    
    if sel_acc_label:
        sel_acc_id = acc_map[sel_acc_label]
        with st.spinner("明細取得中..."):
            gl_data = await ledger_service.get_general_ledger(selected_fy_id, sel_acc_id)
        
        if not gl_data.empty:
            # Format
            df_gl = pd.DataFrame(gl_data)
            # Adjust column order and formatting
            # gl_data keys: "日付", "摘要", "借方", "貸方", "残高", "TransactionID"
            df_gl["借方"] = df_gl["借方"].apply(lambda x: f"{x:,}")
            df_gl["貸方"] = df_gl["貸方"].apply(lambda x: f"{x:,}")
            df_gl["残高"] = df_gl["残高"].apply(lambda x: f"{x:,}")
            
            st.dataframe(
                df_gl[["日付", "摘要", "借方", "貸方", "残高"]], 
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("取引データがありません。")
