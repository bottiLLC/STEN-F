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
    cp_default_account_id: str = "" # Use string for select component
    
    cp_account_options: List[List[str]] = [] # [[value, label]]

    def set_cp_name(self, v: str): self.cp_name = v
    def set_cp_name_kana(self, v: str): self.cp_name_kana = v
    def set_cp_invoice_number(self, v: str): self.cp_invoice_number = v
    def set_cp_default_account_id(self, v: str): self.cp_default_account_id = v

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
        self.cp_default_account_id = str(cp.default_account_id) if cp.default_account_id else ""

    def clear_counterparty_form(self):
        self.cp_id = None
        self.cp_name = ""
        self.cp_name_kana = ""
        self.cp_invoice_number = ""
        self.cp_default_account_id = ""



    async def save_counterparty_data(self):
        async with DI.get_master_service() as service:
            try:
                cp = Counterparty(
                    id=self.cp_id,
                    name=self.cp_name,
                    name_kana=self.cp_name_kana,
                    invoice_number=self.cp_invoice_number,
                    default_account_id=int(self.cp_default_account_id) if self.cp_default_account_id else None
                )
                await service.save_counterparty(cp)
                await self.load_counterparties()
                self.clear_counterparty_form()
                return rx.toast("取引先を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_counterparty_data(self):
        if not self.cp_id: return
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
            self.cp_account_options = [[str(a.id), f"{a.code}: {a.name}"] for a in accounts]


