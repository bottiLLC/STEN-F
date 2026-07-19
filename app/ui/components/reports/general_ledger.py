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
from ...view_models.reports_state import ReportsState


def render_general_ledger_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("総勘定元帳", size="4"),
        rx.select(
            ReportsState.account_labels,
            placeholder="勘定科目を選択...",
            on_change=ReportsState.set_gl_account_label,
            width="300px",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("日付"),
                    rx.table.column_header_cell("摘要"),
                    rx.table.column_header_cell("借方"),
                    rx.table.column_header_cell("貸方"),
                    rx.table.column_header_cell("残高"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    ReportsState.general_ledger,
                    lambda row: rx.table.row(
                        rx.table.cell(row["日付"]),
                        rx.table.cell(row["摘要"]),
                        rx.table.cell(f"{row['借方']:,}"),
                        rx.table.cell(f"{row['貸方']:,}"),
                        rx.table.cell(f"{row['残高']:,}"),
                    ),
                )
            ),
            width="100%",
        ),
        width="100%",
    )
