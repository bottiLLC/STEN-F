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
from ...view_models.master_states.account_state import AccountState
from app.ui.styles import master_form_style


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
                                AccountState.accounts,
                                lambda acc: rx.table.row(
                                    rx.table.cell(acc.code),
                                    rx.table.cell(acc.name),
                                    rx.table.cell(acc.type_label),
                                    rx.table.cell(
                                        rx.button(
                                            "編集",
                                            size="1",
                                            variant="soft",
                                            on_click=lambda: (
                                                AccountState.select_account_by_id(
                                                    acc.id
                                                )
                                            ),
                                            white_space="nowrap",
                                        )
                                    ),
                                ),
                            )
                        ),
                        width="100%",
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
                    rx.cond(AccountState.acc_id, "科目編集", "新規作成"), size="4"
                ),
                rx.button(
                    "新規作成モード (クリア)",
                    on_click=AccountState.clear_account_form,
                    variant="outline",
                    size="1",
                ),
                rx.text("コード"),
                rx.input(
                    value=AccountState.acc_code,
                    on_change=AccountState.set_acc_code,
                    width="100%",
                ),
                rx.text("科目名"),
                rx.input(
                    value=AccountState.acc_name,
                    on_change=AccountState.set_acc_name,
                    width="100%",
                ),
                rx.text("区分"),
                rx.select(
                    AccountState.acc_type_options,
                    value=AccountState.acc_type,
                    on_change=AccountState.set_acc_type,
                    width="100%",
                ),
                rx.text("説明"),
                rx.input(
                    value=AccountState.acc_desc,
                    on_change=AccountState.set_acc_desc,
                    width="100%",
                ),
                rx.hstack(
                    rx.button("保存", on_click=AccountState.save_account, flex="1"),
                    rx.cond(
                        AccountState.acc_id,
                        rx.button(
                            "削除",
                            on_click=lambda: AccountState.delete_account(
                                AccountState.acc_id
                            ),
                            color_scheme="red",
                            variant="soft",
                            flex="1",
                        ),
                    ),
                    width="100%",
                    spacing="2",
                ),
                **dict(master_form_style, width="40%"),
            ),
            spacing="4",
            width="100%",
            align_items="start",
        ),
        width="100%",
    )
