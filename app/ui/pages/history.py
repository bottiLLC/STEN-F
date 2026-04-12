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
from ..components.journal.list_view import render_journal_list

def history_page() -> rx.Component:
    """Standalone page for viewing journal history."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.heading("仕訳履歴", size="8"),
                rx.spacer(),
                # Optional: button to go back to journal input quickly
                rx.link(
                    rx.button(
                        rx.icon("notebook-pen", size=18),
                        "仕訳入力へ戻る",
                        size="3",
                        variant="soft"
                    ),
                    href="/",
                ),
                width="100%",
                align_items="center"
            ),
            
            # Re-use the existing list view component
            rx.box(
                render_journal_list(),
                width="100%",
                padding_top="1em"
            ),

            # Make sure state builds up correctly when this page is loaded directly
            on_mount=[JournalCoordinatorState.on_mount_journal],
            spacing="5",
            padding="2em",
            width="100%",
        )
    )
