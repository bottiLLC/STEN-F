import streamlit as st
import pandas as pd
import os

async def render_journal_list(container):
    st.subheader("仕訳帳")
    
    journal_service = await container.get_journal_service()
    master_service = await container.get_master_service()
    
    # Need accounts to resolve names
    accounts = await master_service.get_accounts()
    acc_map = {a.id: a for a in accounts}
    
    col1, col2 = st.columns([0.8, 0.2])
    with col2:
        show_deleted = st.checkbox("削除済を表示", value=False)
    
    entries = await journal_service.get_entries(include_deleted=show_deleted) # Consider adding date filter here
    
    if entries:
        for t in entries:
            is_deleted = t.deleted_at is not None
            label_prefix = "🗑️ [削除済] " if is_deleted else ""
            
            cp_str = f" | {t.counterparty}" if t.counterparty else ""
            
            with st.expander(f"{label_prefix}{t.date}{cp_str} | {t.description} | ID: {t.id}"):
                if is_deleted:
                    st.warning(f"削除日時: {t.deleted_at}")
                
                # Evidence Button
                if t.evidence_path and os.path.exists(t.evidence_path):
                    if st.button("📄 証憑ファイルを開く", key=f"ev_{t.id}"):
                        try:
                            os.startfile(t.evidence_path)
                        except Exception as e:
                            st.error(f"ファイルを開けませんでした: {e}")
                
                t_rows = []
                for l in t.lines:
                    # Resolve Name
                    acc_name = acc_map.get(l.account_id).name if acc_map.get(l.account_id) else str(l.account_id)
                    t_rows.append({
                        "勘定科目": acc_name,
                        "借方": l.debit,
                        "貸方": l.credit
                    })
                st.dataframe(pd.DataFrame(t_rows), hide_index=True, use_container_width=True)
                
                if not is_deleted:
                    if st.button("削除", key=f"del_{t.id}"):
                        await journal_service.delete_entry(t.id)
                        st.rerun()
