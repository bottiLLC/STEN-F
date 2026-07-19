# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import reflex as rx
from ...view_models.master_states.fiscal_year_state import FiscalYearState
from app.ui.styles import master_form_style


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
                    FiscalYearState.fiscal_years,
                    lambda fy: rx.table.row(
                        rx.table.cell(fy.period_number),
                        rx.table.cell(
                            rx.input(
                                default_value=fy.name,
                                on_blur=lambda val: (
                                    FiscalYearState.update_fiscal_year_name(fy.id, val)
                                ),
                                variant="soft",
                                width="120px",
                            )
                        ),
                        rx.table.cell(f"{fy.start_date} ~ {fy.end_date}"),
                        rx.table.cell(fy.status),
                        rx.table.cell(
                            rx.hstack(
                                rx.cond(
                                    fy.status == "OPEN",
                                    rx.button(
                                        "年度締めを実行",
                                        color_scheme="blue",
                                        size="1",
                                        on_click=lambda: (
                                            FiscalYearState.open_close_dialog(
                                                fy.period_number, fy.id
                                            )
                                        ),
                                        disabled=FiscalYearState.is_processing_close,
                                    ),
                                    rx.text("処理済", color="gray", size="1"),
                                ),
                                rx.button(
                                    rx.icon("trash-2", size=16),
                                    color_scheme="red",
                                    variant="ghost",
                                    on_click=lambda: FiscalYearState.delete_fiscal_year(
                                        fy.id
                                    ),
                                ),
                                spacing="2",
                            )
                        ),
                    ),
                )
            ),
            width="100%",
        ),
        rx.divider(),
        rx.heading("新規会計年度作成", size="4"),
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.text("年度名 (例: 第10期)"),
                    rx.input(
                        value=FiscalYearState.new_fy_name,
                        on_change=FiscalYearState.set_new_fy_name,
                    ),
                ),
                rx.vstack(
                    rx.text("期数"),
                    rx.input(
                        value=FiscalYearState.new_fy_period,
                        on_change=FiscalYearState.set_new_fy_period,
                        type="number",
                    ),
                ),
            ),
            rx.hstack(
                rx.vstack(
                    rx.text("開始日"),
                    rx.input(
                        value=FiscalYearState.new_fy_start,
                        on_change=FiscalYearState.set_new_fy_start,
                        type="date",
                    ),
                ),
                rx.vstack(
                    rx.text("終了日"),
                    rx.input(
                        value=FiscalYearState.new_fy_end,
                        on_change=FiscalYearState.set_new_fy_end,
                        type="date",
                    ),
                ),
                rx.vstack(
                    rx.text("ステータス"),
                    rx.select(
                        ["OPEN", "CLOSED"],
                        value=FiscalYearState.new_fy_status,
                        on_change=FiscalYearState.set_new_fy_status,
                    ),
                ),
            ),
            rx.button("作成する", on_click=FiscalYearState.save_fiscal_year),
            spacing="4",
            **master_form_style,
        ),
        # Closing Fiscal Year Dialog
        rx.dialog.root(
            rx.dialog.content(
                rx.dialog.title("年度締め（次年度開始）の実行"),
                rx.dialog.description(
                    "当期の損益を繰越利益剰余金へ振り替え、次年度の期首残高を作成します。"
                ),
                rx.vstack(
                    rx.text("次年度の名称", weight="bold", size="2"),
                    rx.input(
                        value=FiscalYearState.next_fy_name_input,
                        on_change=FiscalYearState.set_next_fy_name_input,
                        width="100%",
                    ),
                    spacing="4",
                    padding_top="4",
                ),
                rx.hstack(
                    rx.button(
                        "キャンセル",
                        color_scheme="gray",
                        variant="soft",
                        on_click=FiscalYearState.toggle_close_dialog,
                    ),
                    rx.button(
                        rx.cond(
                            FiscalYearState.is_processing_close,
                            rx.spinner(size="2"),
                            "確定して締めを実行",
                        ),
                        color_scheme="blue",
                        on_click=FiscalYearState.close_fiscal_year,
                        disabled=FiscalYearState.is_processing_close,
                    ),
                    spacing="3",
                    margin_top="16px",
                    justify="end",
                ),
            ),
            open=FiscalYearState.show_close_dialog,
        ),
        spacing="4",
        width="100%",
    )
