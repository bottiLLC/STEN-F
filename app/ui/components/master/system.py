import reflex as rx
from ...view_models.master_state import MasterState

def render_system_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("システム管理", size="4"),
        rx.vstack(
             rx.text("データベースバックアップ", weight="bold"),
             rx.text("現在のデータベースのバックアップを作成します。"),
             rx.input(
                 value=MasterState.backup_path,
                 on_change=MasterState.set_backup_path,
                 placeholder="保存先フォルダ"
             ),
             rx.button("バックアップ実行", on_click=MasterState.create_backup),
             spacing="3",
             padding="1em",
             border="1px solid #eaeaea",
             border_radius="8px",
             width="100%"
        ),
        width="100%"
    )
