import reflex as rx
from ...view_models.master_state import MasterState

def render_abstract_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("摘要登録", size="4"),
        rx.hstack(
            rx.vstack(
                rx.heading("新規登録", size="3"),
                rx.text("関連科目"),
                rx.select(
                    MasterState.account_labels,
                    placeholder="科目選択...",
                    value=MasterState.abs_acc_label,
                    on_change=MasterState.set_abs_acc_label,
                    width="100%"
                ),
                rx.text("摘要内容"),
                rx.input(
                    value=MasterState.abs_text, 
                    on_change=MasterState.set_abs_text,
                    width="100%"
                ),
                rx.button("登録する", on_click=MasterState.save_abstract, width="100%"),
                
                padding="1em",
                border="1px solid #eaeaea",
                border_radius="8px",
                width="40%"
            ),
            rx.vstack(
                rx.heading("登録済み摘要一覧", size="3"),
                rx.list.unordered(
                    rx.foreach(
                        MasterState.abstracts,
                        lambda abs: rx.list.item(abs.text) # Can implement full display if needed
                    )
                ),
                width="60%"
            ),
            spacing="5",
            width="100%",
            align_items="start"
        ),
        spacing="4",
        width="100%"
    )
