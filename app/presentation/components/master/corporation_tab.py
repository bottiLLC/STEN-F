import streamlit as st
from datetime import date
from domain.models.corporation import Corporation
# Type hinting only
if False:
    from application.services.master_service import MasterService

async def render_corporation_tab(master_service: "MasterService"):
    st.subheader("法人情報")
    corp = await master_service.get_corporation()
    
    with st.form("corp_form"):
        name = st.text_input("法人名", value=corp.name if corp else "")
        address = st.text_input("住所", value=corp.address if corp else "")
        rep_title = st.text_input("代表者役職", value=corp.representative_title if corp else "")
        rep_name = st.text_input("代表者氏名", value=corp.representative_name if corp else "")
        
        if st.form_submit_button("保存"):
            new_corp = Corporation(
                id=corp.id if corp else None,
                name=name,
                address=address,
                representative_title=rep_title,
                representative_name=rep_name
            )
            await master_service.save_corporation(new_corp)
            st.success("法人情報を保存しました。")
            st.rerun()
