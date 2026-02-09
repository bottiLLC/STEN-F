import streamlit as st
import pandas as pd
from domain.models.abstract import Abstract

if False:
    from application.services.master_service import MasterService

async def render_abstract_tab(master_service: "MasterService"):
    st.subheader("摘要登録")
    abstracts = await master_service.get_abstracts()
    accounts = await master_service.get_accounts() # Need accounts for dropdown
    
    if abstracts:
        df_abs = pd.DataFrame([a.model_dump() for a in abstracts])
        st.dataframe(df_abs, hide_index=True, use_container_width=True)
        
    with st.form("abstract_form"):
        acc_options = {f"{a.code} - {a.name}": a.id for a in accounts} if accounts else {}
        selected_acc_label = st.selectbox("関連科目", list(acc_options.keys()))
        abs_text = st.text_input("摘要内容")
        
        if st.form_submit_button("登録"):
            if selected_acc_label:
                acc_id = acc_options[selected_acc_label]
                new_abs = Abstract(account_id=acc_id, text=abs_text)
                await master_service.save_abstract(new_abs)
                st.success("摘要を登録しました。")
                st.rerun()
