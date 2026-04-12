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
from .components.sidebar import sidebar
from .styles import content_style

def layout(content: rx.Component) -> rx.Component:
    """The main app layout with sidebar and content area."""
    return rx.box(
        rx.flex(
            sidebar(),
            rx.box(
                content,
                style=content_style,
                width="100%",
            ),
            width="100%",
        ),
        background_color="#f4f6f8",
    )
