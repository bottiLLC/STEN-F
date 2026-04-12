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
from typing import List, Optional
from app.domain.models.abstract import Abstract
from app.ui.di import DI

from .account_state import AccountState

class AbstractState(rx.State):
    abstracts: List[Abstract] = []
    
    # Form State
    abs_id: Optional[int] = None
    abs_text: str = ""
    abs_acc_label: str = "" 
    
    def set_abs_text(self, v: str): self.abs_text = v
    def set_abs_acc_label(self, v: str): self.abs_acc_label = v

    async def toggle_abstract_selection(self, abs_data: Abstract, checked: bool):
        if checked:
            self.abs_id = abs_data.id
            self.abs_text = abs_data.text
            if abs_data.account_name:
                acc_state = await self.get_state(AccountState)
                target_acc = next((a for a in acc_state.accounts if a.id == abs_data.account_id), None)
                if target_acc:
                    self.abs_acc_label = f"{target_acc.code}: {target_acc.name}"
        else:
             if self.abs_id == abs_data.id:
                 self.clear_abstract_form()

    def clear_abstract_form(self):
        self.abs_id = None
        self.abs_text = ""
        self.abs_acc_label = ""

    async def save_abstract(self):
        async with DI.get_master_service() as service:
            try:
                # Resolve account ID from label
                acc_state = await self.get_state(AccountState)
                acc_map = {f"{a.code}: {a.name}": a.id for a in acc_state.accounts}
                
                acc_id = acc_map.get(self.abs_acc_label)
                
                if not acc_id:
                     return rx.window_alert("関連科目を選択してください。")

                new_abs = Abstract(
                    id=self.abs_id,
                    account_id=acc_id, 
                    text=self.abs_text
                )
                await service.save_abstract(new_abs)
                self.abstracts = await service.get_abstracts()
                self.clear_abstract_form()
                return rx.toast("登録・保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_abstract_data(self):
        if not self.abs_id: 
            return
        async with DI.get_master_service() as service:
            try:
                await service.delete_abstract(self.abs_id)
                self.abstracts = await service.get_abstracts()
                self.clear_abstract_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")
