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
from ...view_models.master_states.system_state import SystemState

def render_system_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("システム管理", size="4"),
        
        rx.divider(margin_y="2"),
        
        rx.vstack(
             rx.text("AI API連携設定", weight="bold"),
             rx.text("OpenAI または Gemini (Gemini Desktop等) のAPIキーを設定します。システムは画像読み取りやLLM推論にこのキーを使用します。", size="2", color="gray"),
             rx.input(
                 value=SystemState.ai_api_key,
                 on_change=SystemState.set_ai_api_key,
                 type="password",
                 placeholder="sk-...",
                 width="500px"
             ),
             rx.button(
                 "APIキーを保存", 
                 on_click=SystemState.save_api_key,
                 loading=SystemState.is_saving_key,
                 disabled=SystemState.is_saving_key
             ),
             spacing="3",
             padding="4",
             border="1px solid var(--gray-5)",
             border_radius="8px",
             width="100%"
        ),
        
        rx.divider(margin_y="2"),
        
        rx.vstack(
             rx.text("データベースバックアップ", weight="bold"),
             rx.text("現在のデータベースのバックアップを作成します。", size="2", color="gray"),
             rx.input(
                 value=SystemState.backup_path,
                 on_change=SystemState.set_backup_path,
                 placeholder="保存先フォルダ",
                 width="500px"
             ),
             rx.button("バックアップ実行", on_click=SystemState.create_backup),
             spacing="3",
             padding="4",
             border="1px solid var(--gray-5)",
             border_radius="8px",
             width="100%"
        ),
        
        width="100%",
        spacing="5"
    )
