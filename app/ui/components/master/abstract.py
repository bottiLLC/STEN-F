import reflex as rx
from ...view_models.master_states.abstract_state import AbstractState
from ...view_models.master_states.account_state import AccountState
from app.ui.styles import master_form_style

def render_abstract_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("摘要登録", size="4"),
        rx.hstack(
            rx.vstack(
                rx.heading("新規登録・編集", size="3"),
                rx.text("関連科目"),
                rx.select(
                    AccountState.account_labels,
                    placeholder="科目選択...",
                    value=AbstractState.abs_acc_label,
                    on_change=AbstractState.set_abs_acc_label,
                    width="100%"
                ),
                rx.text("摘要内容"),
                rx.input(
                    value=AbstractState.abs_text, 
                    on_change=AbstractState.set_abs_text,
                    width="100%"
                ),
                
                rx.hstack(
                    rx.button("クリア", on_click=AbstractState.clear_abstract_form, variant="outline"),
                    rx.button("保存", on_click=AbstractState.save_abstract, color_scheme="blue"),
                    rx.cond(
                        AbstractState.abs_id,
                        rx.button("削除", on_click=AbstractState.delete_abstract_data, color_scheme="red", variant="outline"),
                    ),
                    spacing="3",
                    margin_top="1em",
                    width="100%",
                    wrap="wrap"
                ),
                
                **dict(master_form_style, width="40%")
            ),
            rx.vstack(
                rx.heading("登録済み摘要一覧", size="3"),
                rx.cond(
                    AbstractState.abstracts,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("", width="50px"),
                                rx.table.column_header_cell("摘要"),
                                rx.table.column_header_cell("関連科目"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                AbstractState.abstracts,
                                lambda abs: rx.table.row(
                                    rx.table.cell(
                                        rx.cond(
                                            AbstractState.abs_id == abs.id,
                                            rx.icon("circle-dot", color="blue", size=20, on_click=lambda: AbstractState.toggle_abstract_selection(abs, False)),
                                            rx.icon("circle", color="gray", size=20, on_click=lambda: AbstractState.toggle_abstract_selection(abs, True))
                                        ),
                                        padding="0.5em",
                                        align="center"
                                    ),
                                    rx.table.cell(abs.text),
                                    rx.table.cell(abs.account_name),
                                    _hover={"bg": "#f5f5f5"}
                                )
                            )
                        ),
                        width="100%"
                    ),
                    rx.text("登録された摘要はありません。")
                ),
                width="60%",
                padding="1em"
            ),
            spacing="5",
            width="100%",
            align_items="start"
        ),
        spacing="4",
        width="100%"
    )
