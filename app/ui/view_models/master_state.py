import reflex as rx
import os
from datetime import date
from typing import List, Optional, Dict
from app.domain.models.corporation import Corporation
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import Account, AccountType
from app.domain.models.abstract import Abstract
from ..di import DI

class MasterState(rx.State):
    """State for Master Management page."""
    
    # Active Tab
    current_tab: str = "corporation"

    # Data
    corporation: Optional[Corporation] = None
    fiscal_years: List[FiscalYear] = []
    accounts: List[Account] = []
    abstracts: List[Abstract] = []

    # System Tab
    backup_path: str = os.path.abspath("./backups")
    
    async def load_all(self):
        """Load all master data."""
        async with DI.get_master_service() as service:
            self.corporation = await service.get_corporation()
            self.fiscal_years = await service.get_fiscal_years()
            self.accounts = await service.get_accounts()
            # Abstracts might not be implemented in service yet based on previous check?
            # Let's check service again or try/except.
            # Referring to previous file view of master_service.py lines 88-89: 
            # async def get_abstracts(self) -> list[Abstract]: return await self.repository.get_abstracts()
            # So it exists.
            self.abstracts = await service.get_abstracts()
            
            # Init forms if needed
            if self.corporation:
                self.corp_name = self.corporation.name
                self.corp_address = self.corporation.address or ""
                self.corp_rep_title = self.corporation.representative_title or ""
                self.corp_rep_name = self.corporation.representative_name or ""

    # --- Corporation ---
    corp_name: str = ""
    corp_address: str = ""
    corp_rep_title: str = ""
    corp_rep_name: str = ""
    
    def set_corp_name(self, v: str): self.corp_name = v
    def set_corp_address(self, v: str): self.corp_address = v
    def set_corp_rep_title(self, v: str): self.corp_rep_title = v
    def set_corp_rep_name(self, v: str): self.corp_rep_name = v

    async def save_corporation(self):
        async with DI.get_master_service() as service:
            try:
                # Use existing ID if available
                corp_id = self.corporation.id if self.corporation else None
                new_corp = Corporation(
                    id=corp_id,
                    name=self.corp_name,
                    address=self.corp_address,
                    representative_title=self.corp_rep_title,
                    representative_name=self.corp_rep_name
                )
                await service.save_corporation(new_corp)
                self.corporation = await service.get_corporation()
                return rx.window_alert("法人情報を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    # --- Fiscal Year ---
    new_fy_name: str = ""
    new_fy_period: int = 1
    new_fy_start: str = date.today().isoformat()
    new_fy_end: str = date.today().isoformat()
    new_fy_status: str = "OPEN" # Key logic handled in UI or here? Let's use simple string.

    def set_new_fy_name(self, v: str): self.new_fy_name = v
    def set_new_fy_period(self, v: str): 
        try: self.new_fy_period = int(v)
        except: pass
    def set_new_fy_start(self, v: str): self.new_fy_start = v
    def set_new_fy_end(self, v: str): self.new_fy_end = v
    def set_new_fy_status(self, v: str): self.new_fy_status = v

    async def save_fiscal_year(self):
        async with DI.get_master_service() as service:
            try:
                new_fy = FiscalYear(
                    name=self.new_fy_name,
                    period_number=self.new_fy_period,
                    start_date=date.fromisoformat(self.new_fy_start),
                    end_date=date.fromisoformat(self.new_fy_end),
                    status=self.new_fy_status
                )
                await service.create_fiscal_year(new_fy)
                self.fiscal_years = await service.get_fiscal_years()
                return rx.window_alert("会計年度を作成しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_fiscal_year(self, fy_id: int):
        async with DI.get_master_service() as service:
            try:
                await service.delete_fiscal_year(fy_id)
                self.fiscal_years = await service.get_fiscal_years()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    # --- Account ---
    acc_id: Optional[int] = None
    acc_code: str = ""
    acc_name: str = ""
    acc_type: str = AccountType.CURRENT_ASSET.value
    acc_desc: str = ""
    
    # Options for Select
    acc_type_options: List[str] = [t.value for t in AccountType]

    def set_acc_code(self, v: str): self.acc_code = v
    def set_acc_name(self, v: str): self.acc_name = v
    def set_acc_type(self, v: str): self.acc_type = v
    def set_acc_desc(self, v: str): self.acc_desc = v

    def select_account(self, acc: Dict): # receiving dict from event? or object?
        # Reflex event args are often serialized. Let's assume we pass ID and find it, or pass individual fields.
        # Simplest: Pass object if possible or ID.
        pass 
    
    def select_account_by_id(self, acc_id: int):
        target = next((a for a in self.accounts if a.id == acc_id), None)
        if target:
            self.acc_id = target.id
            self.acc_code = target.code
            self.acc_name = target.name
            self.acc_type = target.type.value
            self.acc_desc = target.description or ""

    def clear_account_form(self):
        self.acc_id = None
        self.acc_code = ""
        self.acc_name = ""
        self.acc_type = AccountType.CURRENT_ASSET.value
        self.acc_desc = ""

    async def save_account(self):
        async with DI.get_master_service() as service:
            try:
                new_acc = Account(
                    id=self.acc_id,
                    code=self.acc_code,
                    name=self.acc_name,
                    type=AccountType(self.acc_type),
                    description=self.acc_desc
                )
                await service.save_account(new_acc)
                self.accounts = await service.get_accounts()
                self.clear_account_form()
                return rx.toast("保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_account(self, acc_id: int):
        async with DI.get_master_service() as service:
            try:
                await service.delete_account(acc_id)
                self.accounts = await service.get_accounts()
                if self.acc_id == acc_id:
                    self.clear_account_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    # --- Abstract ---
    abs_text: str = ""
    abs_acc_label: str = "" # Selected label from dropdown
    
    def set_abs_text(self, v: str): self.abs_text = v
    def set_abs_acc_label(self, v: str): self.abs_acc_label = v

    async def save_abstract(self):
        async with DI.get_master_service() as service:
            try:
                # Resolve account ID from label
                # We need the map. Let's reuse JournalState logic or build map here.
                # Ideally we build a map on load.
                acc_map = {f"{a.code}: {a.name}": a.id for a in self.accounts}
                acc_id = acc_map.get(self.abs_acc_label)
                
                if not acc_id:
                     return rx.window_alert("関連科目を選択してください。")

                new_abs = Abstract(account_id=acc_id, text=self.abs_text)
                await service.save_abstract(new_abs)
                self.abstracts = await service.get_abstracts()
                self.abs_text = ""
                return rx.toast("登録しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    # Helper for dropdowns
    @rx.var
    def account_labels(self) -> List[str]:
        return [f"{a.code}: {a.name}" for a in self.accounts]

    def set_backup_path(self, path: str):
        self.backup_path = path

    async def create_backup(self):
        """Create a database backup."""
        service = DI.get_backup_service()
        try:
             saved_path = await service.create_backup(self.backup_path)
             return rx.window_alert(f"バックアップが完了しました！\n保存場所: {saved_path}")
        except Exception as e:
             return rx.window_alert(f"エラーが発生しました: {str(e)}")
