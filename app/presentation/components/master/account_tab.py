import streamlit as st
import pandas as pd
from domain.models.account import Account, AccountType
from presentation.constants import ACCOUNT_TYPE_JP

if False:
    from application.services.master_service import MasterService

async def render_account_tab(master_service: "MasterService"):
    st.subheader("勘定科目一覧")
    accounts = await master_service.get_accounts()
    
    if accounts:
        table_data = []
        for acc in accounts:
            row = acc.model_dump()
            row['type'] = ACCOUNT_TYPE_JP.get(acc.type, str(acc.type))
            table_data.append(row)
            
        df_acc = pd.DataFrame(table_data)
        st.dataframe(df_acc[["code", "name", "type", "description"]], height=300, hide_index=True, use_container_width=True)
    
    with st.expander("勘定科目 追加/編集"):
        with st.form("account_form"):
            a_code = st.text_input("コード")
            a_name = st.text_input("科目名")
            type_options = list(ACCOUNT_TYPE_JP.values())
            a_type_disp = st.selectbox("区分", type_options)
            a_type_val = next((k for k, v in ACCOUNT_TYPE_JP.items() if v == a_type_disp), None)
            a_desc = st.text_input("説明")
            
            if st.form_submit_button("保存"):
                existing = next((a for a in accounts if a.code == a_code), None)
                acc_id = existing.id if existing else None
                new_acc = Account(
                    id=acc_id,
                    code=a_code,
                    name=a_name,
                    type=AccountType(a_type_val),
                    description=a_desc
                )
                await master_service.save_account(new_acc)
                st.success(f"勘定科目 '{a_name}' を{'更新' if acc_id else '保存'}しました。")
                st.rerun()
