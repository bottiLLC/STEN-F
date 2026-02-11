import streamlit as st
import pandas as pd
from domain.models.account import Account, AccountType
from presentation.constants import ACCOUNT_TYPE_JP

if False:
    from application.services.master_service import MasterService

async def render_account_tab(master_service: "MasterService"):
    st.subheader("勘定科目一覧")
    
    # Session State Initialization
    if "account_form_id" not in st.session_state:
        st.session_state.account_form_id = None
        st.session_state.account_form_code = ""
        st.session_state.account_form_name = ""
        st.session_state.account_form_type = list(ACCOUNT_TYPE_JP.values())[0]
        st.session_state.account_form_desc = ""

    def clear_form():
        st.session_state.account_form_id = None
        st.session_state.account_form_code = ""
        st.session_state.account_form_name = ""
        # Keep type as is or reset? Resetting to first might be annoying if adding multiple of same type.
        # Let's keep type current.
        st.session_state.account_form_desc = ""

    # Handle delayed clear from previous run (to avoid widget modification error)
    if st.session_state.get("should_clear_form", False):
        clear_form()
        st.session_state.should_clear_form = False

    # Fetch Data
    accounts = await master_service.get_accounts()
    
    # Prepare Dataframe
    if accounts:
        table_data = []
        for acc in accounts:
            row = acc.model_dump()
            row['type_display'] = ACCOUNT_TYPE_JP.get(acc.type, str(acc.type))
            table_data.append(row)
            
        df_acc = pd.DataFrame(table_data)
        # Rename for display
        df_display = df_acc.rename(columns={
            "code": "コード",
            "name": "科目名",
            "type_display": "区分",
            "description": "説明"
        })
        
        # Display Table with Selection
        selection = st.dataframe(
            df_display[["コード", "科目名", "区分", "説明"]], 
            height=300, 
            hide_index=True, 
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Handle Selection
        if selection.selection.rows:
            selected_index = selection.selection.rows[0]
            # Ensure index is valid (dataframe might have shrunk)
            if selected_index < len(df_acc):
                selected_row = df_acc.iloc[selected_index]
                
                # Update Form State if different account selected
                selected_id = int(selected_row['id'])
                if st.session_state.account_form_id != selected_id:
                     st.session_state.account_form_id = selected_id
                     st.session_state.account_form_code = str(selected_row['code'])
                     st.session_state.account_form_name = str(selected_row['name'])
                     st.session_state.account_form_type = ACCOUNT_TYPE_JP.get(selected_row['type'], str(selected_row['type']))
                     st.session_state.account_form_desc = selected_row['description'] or ""
                     st.rerun() # Force rerun to update widget values

    col_header, col_btn = st.columns([3, 1])
    with col_header:
        st.markdown(f"### {'新規作成' if st.session_state.account_form_id is None else '編集'}")
    
    with col_btn:
        if st.button("新規作成 (クリア)"):
            clear_form()
            st.rerun()

    with st.form("account_form"):
        # We use key=... to bind to session_state
        a_code = st.text_input("コード", key="account_form_code")
        a_name = st.text_input("科目名", key="account_form_name")
        
        type_options = list(ACCOUNT_TYPE_JP.values())
        # Provide index if exists
        try:
             type_index = type_options.index(st.session_state.account_form_type)
        except ValueError:
             type_index = 0
             
        a_type_disp = st.selectbox("区分", type_options, index=type_index, key="account_form_type_widget")
        
        a_type_val = next((k for k, v in ACCOUNT_TYPE_JP.items() if v == a_type_disp), None)
        a_desc = st.text_input("説明", key="account_form_desc")
        
        col_save, col_delete = st.columns([1, 1])
        with col_save:
            submitted = st.form_submit_button("保存", type="primary")
        
        with col_delete:
            delete_submitted = st.form_submit_button("削除")

        if submitted:
            if not a_code:
                st.error("コードを入力してください。")
            elif not a_name:
                st.error("科目名を入力してください。")
            else:
                try:
                    # Update logic: If ID exists, update. Else create.
                    new_acc = Account(
                        id=st.session_state.account_form_id,
                        code=a_code,
                        name=a_name,
                        type=AccountType(a_type_val),
                        description=a_desc
                    )
                    await master_service.save_account(new_acc)
                    st.success(f"勘定科目 '{a_name}' を保存しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"エラーが発生しました: {e}")

        if delete_submitted:
            if st.session_state.account_form_id:
                try:
                    # Ensure plain int (handle numpy types from dataframe)
                    acc_id = int(st.session_state.account_form_id)
                    await master_service.delete_account(acc_id)
                    st.success("削除しました。")
                    # Set flag to clear form on next run (avoid widget Modification error)
                    st.session_state.should_clear_form = True
                    st.rerun()
                except ValueError as ve:
                     st.error(f"削除できません: {ve}")
                except Exception as e:
                     st.error(f"削除エラー: {e}")
            else:
                st.info("削除するデータを選択してください（保存前のデータは削除できません）。")
