import streamlit as st
import pandas as pd

async def render_journal_list(container):
    st.subheader("仕訳帳")
    
    journal_service = await container.get_journal_service()
    master_service = await container.get_master_service()
    
    # Need accounts to resolve names
    accounts = await master_service.get_accounts()
    acc_map = {a.id: a for a in accounts}
    
    entries = await journal_service.get_entries() # Consider adding date filter here
    
    if entries:
        for t in entries:
            with st.expander(f"{t.date} | {t.description} | ID: {t.id}"):
                t_rows = []
                for l in t.lines:
                    # Resolve Name
                    acc_name = acc_map.get(l.account_id).name if acc_map.get(l.account_id) else str(l.account_id)
                    t_rows.append({
                        "勘定科目": acc_name,
                        "借方": l.debit if l.debit > 0 else "",
                        "貸方": l.credit if l.credit > 0 else ""
                    })
                st.dataframe(pd.DataFrame(t_rows), hide_index=True, use_container_width=True)
                
                if st.button("削除", key=f"del_{t.id}"):
                    await journal_service.delete_entry(t.id)
                    st.rerun()
