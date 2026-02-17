import reflex as rx
from ...view_models.master_state import MasterState

def render_fiscal_year_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("会計年度一覧", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("期"),
                    rx.table.column_header_cell("名称"),
                    rx.table.column_header_cell("期間"),
                    rx.table.column_header_cell("ステータス"),
                    rx.table.column_header_cell("操作"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    MasterState.fiscal_years,
                    lambda fy: rx.table.row(
                        rx.table.cell(fy.period_number),
                        rx.table.cell(fy.name),
                        rx.table.cell(f"{fy.start_date} ~ {fy.end_date}"),
                        rx.table.cell(fy.status),
                        rx.table.cell(
                            rx.button(
                                rx.icon("trash-2", size=16),
                                color_scheme="red", 
                                variant="ghost",
                                on_click=lambda: MasterState.delete_fiscal_year(fy.id)
                            )
                        ),
                    )
                )
            ),
            width="100%"
        ),
        rx.divider(),
        rx.heading("新規会計年度作成", size="4"),
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.text("年度名 (例: 第10期)"),
                    rx.input(value=MasterState.new_fy_name, on_change=MasterState.set_new_fy_name)
                ),
                rx.vstack(
                    rx.text("期数"),
                    rx.input(value=MasterState.new_fy_period, on_change=MasterState.set_new_fy_period, type="number")
                ),
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("開始日"),
                    rx.input(value=MasterState.new_fy_start, on_change=MasterState.set_new_fy_start, type="date")
                ),
                rx.vstack(
                    rx.text("終了日"),
                    rx.input(value=MasterState.new_fy_end, on_change=MasterState.set_new_fy_end, type="date")
                ),
                rx.vstack(
                    rx.text("ステータス"),
                    rx.select(
                        ["OPEN", "CLOSED"], 
                        value=MasterState.new_fy_status, 
                        on_change=MasterState.set_new_fy_status
                    )
                ),
            ),
            rx.button("作成する", on_click=MasterState.save_fiscal_year),
            spacing="4",
            padding="1em",
            border="1px solid #eaeaea",
            border_radius="8px",
            width="100%"
        ),
        spacing="4",
        width="100%"
    )
