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


def render_trial_balance_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("合計残高試算表", size="4"),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("勘定科目"),
                    rx.table.column_header_cell("借方残高"),
                    rx.table.column_header_cell("貸方残高"),
                )
            ),
            rx.table.body(
                rx.foreach(
                    ReportsState.trial_balance,
                    lambda row: rx.table.row(
                        rx.table.cell(row.account_name),
                        rx.table.cell(f"{row.debit_balance:,}"),
                        rx.table.cell(f"{row.credit_balance:,}"),
                    ),
                )
            ),
            width="100%",
        ),
        width="100%",
    )
