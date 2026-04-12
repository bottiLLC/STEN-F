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
from ...view_models.master_states.corporation_state import CorporationState
from app.ui.styles import master_form_style

def render_corporation_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("法人情報編集", size="4"),
        rx.vstack(
            rx.text("法人名", weight="bold"),
            rx.input(value=CorporationState.corp_name, on_change=CorporationState.set_corp_name, width="100%"),
            rx.text("本店所在地", weight="bold"),
            rx.input(value=CorporationState.corp_address, on_change=CorporationState.set_corp_address, width="100%"),
            rx.hstack(
                rx.vstack(
                    rx.text("代表役職", weight="bold"),
                    rx.input(value=CorporationState.corp_rep_title, on_change=CorporationState.set_corp_rep_title, width="100%")
                ),
                rx.vstack(
                    rx.text("代表者氏名", weight="bold"),
                    rx.input(value=CorporationState.corp_rep_name, on_change=CorporationState.set_corp_rep_name, width="100%")
                ),
                width="100%",
                spacing="4"
            ),
            rx.button("保存する", on_click=CorporationState.save_corporation, size="3", color_scheme="blue", width="100%", margin_top="1em"),
            spacing="4",
            **master_form_style
        ),
        spacing="4",
        width="100%"
    )
