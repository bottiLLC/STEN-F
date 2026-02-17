import reflex as rx
from ...view_models.master_state import MasterState

def render_account_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("勘定科目編集", size="4"),
        rx.hstack(
            # Left: List
            rx.vstack(
                rx.heading("一覧 (クリックで編集)", size="2", color="gray"),
                rx.scroll_area(
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("コード"),
                                rx.table.column_header_cell("名称"),
                                rx.table.column_header_cell("区分"),
                                rx.table.column_header_cell("操作"), 
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                MasterState.accounts,
                                lambda acc: rx.table.row(
                                    rx.table.cell(acc.code),
                                    rx.table.cell(acc.name),
                                    rx.table.cell(acc.type),
                                    rx.table.cell(
                                        rx.button(
                                            "編集",
                                            size="1",
                                            variant="soft",
                                            on_click=lambda: MasterState.select_account_by_id(acc.id)
                                        )
                                    ),
                                )
                            )
                        ),
                        width="100%"
                    ),
                    type="always",
                    scrollbars="vertical",
                    style={"height": "500px"},
                ),
                width="60%",
            ),
            # Right: Form
            rx.vstack(
                rx.heading(
                    rx.cond(MasterState.acc_id, "科目編集", "新規作成"), 
                    size="4"
                ),
                rx.button("新規作成モード (クリア)", on_click=MasterState.clear_account_form, variant="outline", size="1"),
                
                rx.text("コード"),
                rx.input(value=MasterState.acc_code, on_change=MasterState.set_acc_code, width="100%"),
                
                rx.text("科目名"),
                rx.input(value=MasterState.acc_name, on_change=MasterState.set_acc_name, width="100%"),
                
                rx.text("区分"),
                rx.select(
                    MasterState.acc_type_options,
                    value=MasterState.acc_type,
                    on_change=MasterState.set_acc_type,
                    width="100%"
                ),

                rx.text("説明"),
                rx.input(value=MasterState.acc_desc, on_change=MasterState.set_acc_desc, width="100%"),

                rx.hstack(
                    rx.button("保存", on_click=MasterState.save_account, width="100%"),
                    rx.cond(
                         MasterState.acc_id,
                         rx.button("削除", on_click=lambda: MasterState.delete_account(MasterState.acc_id), color_scheme="red", variant="soft"),
                    ),
                    width="100%",
                    spacing="2"
                ),
                
                padding="1em",
                border="1px solid #eaeaea",
                border_radius="8px",
                width="40%",
                background_color="#f9f9f9",
            ),
            spacing="4",
            width="100%",
            align_items="start"
        ),
        width="100%"
    )
