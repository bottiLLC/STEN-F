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
from ..layout import layout
from ..view_models.journal import JournalCoordinatorState
from ..components.journal.input_form import render_journal_input
from ..components.journal.list_view import render_journal_list


def journal_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("仕訳入力", size="8"),
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("仕訳入力", value="input"),
                    rx.tabs.trigger("仕訳帳 (履歴)", value="list"),
                ),
                rx.tabs.content(render_journal_input(), value="input"),
                rx.tabs.content(render_journal_list(), value="list"),
                default_value="input",
                on_change=JournalCoordinatorState.handle_tab_change,
            ),
            on_mount=[JournalCoordinatorState.on_mount_journal],
            spacing="5",
            padding="2em",
            width="100%",
        )
    )
