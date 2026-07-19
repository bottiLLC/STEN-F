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
from ..styles import sidebar_style, sidebar_text_color, sidebar_hover_bg


def sidebar_item(text: str, icon: str, url: str) -> rx.Component:
    """Sidebar navigation item."""
    return rx.link(
        rx.hstack(
            rx.icon(icon, size=20),
            rx.text(text, font_weight="500"),
            width="100%",
            padding="10px",
            border_radius="8px",
            color=sidebar_text_color,
            _hover={
                "background_color": sidebar_hover_bg,
                "color": "white",
            },
            align_items="center",
            spacing="3",
        ),
        href=url,
        width="100%",
        text_decoration="none",
    )


def sidebar() -> rx.Component:
    """The sidebar component."""
    return rx.box(
        rx.vstack(
            rx.heading("STEN-F", color="white", size="6", margin_bottom="2em"),
            rx.vstack(
                sidebar_item("仕訳入力", "notebook-pen", "/"),
                sidebar_item("仕訳履歴", "history", "/history"),
                sidebar_item("期首BS入力", "scale", "/opening_bs"),
                sidebar_item("マスタ管理", "database", "/master"),
                sidebar_item("レポート", "chart-bar", "/reports"),
                width="100%",
                spacing="2",
            ),
            style=sidebar_style,
            align_items="start",
        )
    )
