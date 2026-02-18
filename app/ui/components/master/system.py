import reflex as rx
from ...view_models.master_states.system_state import SystemState
from app.ui.styles import master_form_style

def render_system_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("システム管理", size="4"),
        rx.vstack(
             rx.text("データベースバックアップ", weight="bold"),
             rx.text("現在のデータベースのバックアップを作成します。"),
             rx.input(
                 value=SystemState.backup_path,
                 on_change=SystemState.set_backup_path,
                 placeholder="保存先フォルダ",
                 width="500px"
             ),
             rx.button("バックアップ実行", on_click=SystemState.create_backup),
             spacing="3",

             **master_form_style
        ),
        width="100%"
    )
