import streamlit as st
import os
from container import Container

async def render_system_tab(container: Container):
    st.subheader("システム管理")
    st.markdown("##### データベースバックアップ")
    st.write("現在のデータベースのバックアップを作成します。")
    
    default_path = st.session_state.get('backup_path', os.path.abspath("./backups"))
    backup_path = st.text_input("保存先フォルダ", value=default_path)
    st.session_state['backup_path'] = backup_path
    
    if st.button("バックアップ実行"):
        backup_service = container.get_backup_service()
        with st.spinner("バックアップ作成中..."):
            try:
                saved_path = await backup_service.create_backup(backup_path)
                st.success(f"バックアップが完了しました！\n保存場所: `{saved_path}`")
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
