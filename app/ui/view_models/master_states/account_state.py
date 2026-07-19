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
from app.domain.models.account import Account, AccountType
from app.ui.di import DI


class AccountState(rx.State):
    accounts: List[Account] = []

    # Form State
    acc_id: Optional[int] = None
    acc_code: str = ""
    acc_name: str = ""
    acc_type: str = AccountType.CURRENT_ASSET.label
    acc_desc: str = ""

    @rx.var
    def account_labels(self) -> List[str]:
        return [f"{a.code}: {a.name}" for a in self.accounts]

    # Options for Select
    acc_type_options: List[str] = [t.label for t in AccountType]

    def set_acc_code(self, v: str):
        self.acc_code = v

    def set_acc_name(self, v: str):
        self.acc_name = v

    def set_acc_type(self, v: str):
        self.acc_type = v

    def set_acc_desc(self, v: str):
        self.acc_desc = v

    def select_account_by_id(self, acc_id: int):
        target = next((a for a in self.accounts if a.id == acc_id), None)
        if target:
            self.acc_id = target.id
            self.acc_code = target.code
            self.acc_name = target.name
            self.acc_type = target.type.label
            self.acc_desc = target.description or ""

    def clear_account_form(self):
        self.acc_id = None
        self.acc_code = ""
        self.acc_name = ""
        self.acc_type = AccountType.CURRENT_ASSET.label
        self.acc_desc = ""

    async def save_account(self):
        async with DI.get_master_service() as service:
            try:
                new_acc = Account(
                    id=self.acc_id,
                    code=self.acc_code,
                    name=self.acc_name,
                    type=AccountType.from_label(self.acc_type),
                    description=self.acc_desc,
                )
                await service.save_account(new_acc)
                self.accounts = await service.get_accounts()
                from .counterparty_state import CounterpartyState

                cp_state = await self.get_state(CounterpartyState)
                await cp_state.load_counterparties()

                self.clear_account_form()
                return rx.toast("保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_account(self, acc_id: int):
        async with DI.get_master_service() as service:
            try:
                await service.delete_account(acc_id)
                self.accounts = await service.get_accounts()
                from .counterparty_state import CounterpartyState

                cp_state = await self.get_state(CounterpartyState)
                await cp_state.load_counterparties()

                if self.acc_id == acc_id:
                    self.clear_account_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")
