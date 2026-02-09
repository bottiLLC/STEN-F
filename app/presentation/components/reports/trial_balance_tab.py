import streamlit as st
import pandas as pd
from presentation.constants import ACCOUNT_TYPE_JP
from application.services.ledger_service import LedgerService

async def render_trial_balance_tab(ledger_service: LedgerService, selected_fy_id: int):
    st.subheader("合計残高試算表")
    with st.spinner("データ取得中..."):
        tb_rows = await ledger_service.get_trial_balance(selected_fy_id)
    
    if tb_rows:
        df_data = []
        for r in tb_rows:
            df_data.append({
                "コード": r.account_code,
                "勘定科目": r.account_name,
                "区分": ACCOUNT_TYPE_JP.get(r.account_type, str(r.account_type)),
                "借方合計": f"{r.debit_total:,}",
                "貸方合計": f"{r.credit_total:,}",
                "残高": f"{r.balance:,}"
            })
        st.dataframe(pd.DataFrame(df_data), hide_index=True, use_container_width=True)
    else:
        st.info("データがありません。")
