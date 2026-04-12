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

class State(rx.State):
    """The base state for the app."""
    current_page: str = "journal"
    
    # Global flag for cross-session updates (stored as timestamp)
    last_journal_update: float = 0.0

    def navigate_to(self, page: str):
        self.current_page = page
        return rx.redirect(f"/{page}" if page != "journal" else "/")
