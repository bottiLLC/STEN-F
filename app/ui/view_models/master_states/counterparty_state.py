import reflex as rx
from typing import List, Optional
from app.domain.models.counterparty import Counterparty
from app.domain.models.account import AccountType
from app.ui.di import DI

class CounterpartyState(rx.State):
    counterparties: List[Counterparty] = []
    
    # Form State
    cp_id: Optional[int] = None
    cp_name: str = ""
    cp_name_kana: str = ""
    cp_invoice_number: str = ""
    cp_default_account_type: str = AccountType.COST_OF_SALES.label
    
    cp_account_type_options: List[str] = [t.label for t in AccountType]

    def set_cp_name(self, v: str): self.cp_name = v
    def set_cp_name_kana(self, v: str): self.cp_name_kana = v
    def set_cp_invoice_number(self, v: str): self.cp_invoice_number = v
    def set_cp_default_account_type(self, v: str): self.cp_default_account_type = v

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
        self.cp_default_account_type = AccountType(cp.default_account_type).label if cp.default_account_type else AccountType.COST_OF_SALES.label

    def clear_counterparty_form(self):
        self.cp_id = None
        self.cp_name = ""
        self.cp_name_kana = ""
        self.cp_invoice_number = ""
        self.cp_default_account_type = AccountType.COST_OF_SALES.label



    async def save_counterparty_data(self):
        async with DI.get_master_service() as service:
            try:
                cp = Counterparty(
                    id=self.cp_id,
                    name=self.cp_name,
                    name_kana=self.cp_name_kana,
                    invoice_number=self.cp_invoice_number,
                    default_account_type=AccountType.from_label(self.cp_default_account_type).value
                )
                await service.save_counterparty(cp)
                self.counterparties = await service.get_counterparties()
                self.clear_counterparty_form()
                return rx.toast("取引先を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_counterparty_data(self):
        if not self.cp_id: return
        async with DI.get_master_service() as service:
            try:
                await service.delete_counterparty(self.cp_id)
                self.counterparties = await service.get_counterparties()
                self.clear_counterparty_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")


