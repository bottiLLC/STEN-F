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
from app.domain.models.counterparty import Counterparty
from app.ui.di import DI


class CounterpartyState(rx.State):
    counterparties: List[Counterparty] = []

    # Form State
    cp_id: Optional[int] = None
    cp_name: str = ""
    cp_name_kana: str = ""
    cp_invoice_number: str = ""
    cp_debit_account_id: str = ""
    cp_credit_account_id: str = ""
    cp_description_template: str = ""

    cp_account_options: List[List[str]] = []  # [[value, label]]

    def set_cp_name(self, v: str):
        self.cp_name = v

    def set_cp_name_kana(self, v: str):
        self.cp_name_kana = v

    def set_cp_invoice_number(self, v: str):
        self.cp_invoice_number = v

    def set_cp_debit_account_id(self, v: str):
        self.cp_debit_account_id = v

    def set_cp_credit_account_id(self, v: str):
        self.cp_credit_account_id = v

    def set_cp_description_template(self, v: str):
        self.cp_description_template = v

    def toggle_counterparty_selection(self, cp: Counterparty, checked: bool):
        if checked:
            self.select_counterparty(cp)
        else:
            if self.cp_id == cp.id:
                self.clear_counterparty_form()

    def select_counterparty(self, cp: Counterparty):
        self.cp_id = cp.id
        self.cp_name = cp.name
        self.cp_name_kana = cp.name_kana or ""
        self.cp_invoice_number = cp.invoice_number or ""
        self.cp_debit_account_id = (
            str(cp.debit_account_id) if cp.debit_account_id else ""
        )
        self.cp_credit_account_id = (
            str(cp.credit_account_id) if cp.credit_account_id else ""
        )
        self.cp_description_template = cp.description_template or ""

    def clear_counterparty_form(self):
        self.cp_id = None
        self.cp_name = ""
        self.cp_name_kana = ""
        self.cp_invoice_number = ""
        self.cp_debit_account_id = ""
        self.cp_credit_account_id = ""
        self.cp_description_template = ""

    async def save_counterparty_data(self):
        async with DI.get_master_service() as service:
            try:
                cp = Counterparty(
                    id=self.cp_id,
                    name=self.cp_name,
                    name_kana=self.cp_name_kana,
                    invoice_number=self.cp_invoice_number,
                    debit_account_id=int(self.cp_debit_account_id)
                    if self.cp_debit_account_id
                    else None,
                    credit_account_id=int(self.cp_credit_account_id)
                    if self.cp_credit_account_id
                    else None,
                    description_template=self.cp_description_template,
                )
                await service.save_counterparty(cp)
                await self.load_counterparties()
                self.clear_counterparty_form()
                return rx.toast("取引先を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_counterparty_data(self):
        if not self.cp_id:
            return
        async with DI.get_master_service() as service:
            try:
                await service.delete_counterparty(self.cp_id)
                await service.delete_counterparty(self.cp_id)
                await self.load_counterparties()
                self.clear_counterparty_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def load_counterparties(self):
        async with DI.get_master_service() as service:
            self.counterparties = await service.get_counterparties()
            accounts = await service.get_accounts()
            # [[value, label]]
            self.cp_account_options = [
                [str(a.id), f"{a.code}: {a.name}"] for a in accounts
            ]
