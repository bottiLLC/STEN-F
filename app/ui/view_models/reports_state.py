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
from typing import List, Optional, Dict
from datetime import date
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.financial_report import TrialBalanceRow, FinancialReport
from app.domain.models.account import Account
from ..di import DI

class ReportsState(rx.State):
    """State for Reports page."""
    
    fiscal_years: List[FiscalYear] = []
    selected_fy_id: str = "" 
    
    # Dropdown Helpers
    fy_options: List[str] = []
    fy_map: Dict[str, str] = {} # Label -> ID
    
    # Account Dropdown
    account_labels: List[str] = []
    account_map: Dict[str, str] = {}

    # Report Data
    trial_balance: List[TrialBalanceRow] = []
    financial_report: Optional[FinancialReport] = None
    general_ledger: List[Dict] = []
    
    # Filters
    accounts: List[Account] = [] # For GL selector
    gl_selected_account_id: str = ""

    # PDF Export
    report_date: str = date.today().isoformat()
    audit_date: str = date.today().isoformat()
    
    def set_report_date(self, v: str): self.report_date = v
    def set_audit_date(self, v: str): self.audit_date = v

    async def export_pdf(self):
        """Generate and download the annual report PDF."""
        if not self.selected_fy_id: 
            return rx.window_alert("会計年度を選択してください。")
            
        try:
             # Ensure data is loaded
             fy_id_int = int(self.selected_fy_id)
             
             # Fetch needed data
             async with DI.get_master_service() as master_service:
                 corp = await master_service.get_corporation()
                 
             if not corp:
                  return rx.window_alert("法人情報が設定されていません。")

             async with DI.get_ledger_service() as ledger_service:
                 # Re-generate report to ensure freshness or use cached?
                 # Safe to regenerate.
                 report_obj = await ledger_service.generate_financial_report(fy_id_int)
                 
             # Get current fiscal year object for metadata
             current_fy = next((f for f in self.fiscal_years if f.id == fy_id_int), None)
             if not current_fy:
                  return rx.window_alert("会計年度データが見つかりません。")

             # Generate PDF (Sync process -> offload to thread)
             pdf_service = DI.get_pdf_service()
             # Convert dates
             from datetime import date
             r_date = date.fromisoformat(self.report_date)
             a_date = date.fromisoformat(self.audit_date)
             
             import asyncio
             pdf_bytes = await asyncio.to_thread(
                 pdf_service.generate_annual_report,
                 corp, report_obj, current_fy, r_date, a_date
             )
             
             # Return download event
             return rx.download(
                 data=pdf_bytes,
                 filename=f"AnnualReport_{current_fy.name}.pdf",
             )

        except Exception as e:
            return rx.window_alert(f"PDF作成エラー: {e}")

    async def load_fiscal_years(self):
        """Load fiscal years and accounts."""
        async with DI.get_master_service() as service:
            self.fiscal_years = await service.get_fiscal_years()
            self.accounts = await service.get_accounts()
            
            # Build options
            self.fy_options = [f"{fy.name} (第{fy.period_number}期)" for fy in self.fiscal_years]
            self.fy_map = {f"{fy.name} (第{fy.period_number}期)": str(fy.id) for fy in self.fiscal_years}
            
            self.account_labels = [f"{a.code}: {a.name}" for a in self.accounts]
            self.account_map = {f"{a.code}: {a.name}": str(a.id) for a in self.accounts}

            if self.fiscal_years and not self.selected_fy_id:
                # Default to the most recent one or valid one?
                # Original logic: session.get("report_fy_id") or first.
                # Here we just pick first.
                self.selected_fy_id = str(self.fiscal_years[0].id)
                # Auto-load data if FY is set
                await self.load_report_data()

    async def set_fy_label(self, label: str):
        if label in self.fy_map:
            self.selected_fy_id = self.fy_map[label]
            await self.load_report_data()

    async def set_fy_id(self, fy_id: str):
        self.selected_fy_id = fy_id
        await self.load_report_data()

    async def set_gl_account_label(self, label: str):
        if label in self.account_map:
            self.gl_selected_account_id = self.account_map[label]
            await self.load_general_ledger()

    async def load_report_data(self):
        """Load data based on active tab? Or just load all for simplicity if small."""
        # For efficiency we might want to load only on tab change, but let's load TB first.
        if not self.selected_fy_id: 
            return
        try:
            fy_id_int = int(self.selected_fy_id)
            async with DI.get_ledger_service() as service:
                self.trial_balance = await service.get_trial_balance(fy_id_int)
                # We can lazy load others or load everything.
                # Let's load FS as well.
                # Financial Report logic in LedgerService seems available.
                self.financial_report = await service.generate_financial_report(fy_id_int)
                
        except ValueError:
            pass

    async def load_general_ledger(self):
        if not self.selected_fy_id or not self.gl_selected_account_id:
            return
            
        try:
            fy_id_int = int(self.selected_fy_id)
            acc_id_int = int(self.gl_selected_account_id)
            
            async with DI.get_ledger_service() as service:
                df = await service.get_general_ledger(fy_id_int, acc_id_int)
                if not df.empty:
                    # Convert dates to string to avoid serialization issues
                    if '日付' in df.columns:
                        df['日付'] = df['日付'].astype(str)
                    self.general_ledger = df.to_dict('records')
                else:
                    self.general_ledger = []
        except ValueError:
            pass

    def set_gl_account(self, acc_id: str):
        self.gl_selected_account_id = acc_id
        # Trigger load
        # We can't await here directly in a setter if it's UI event? 
        # Reflex event handlers can be async.
        # But set_gl_account is likely bound to on_change which expects correct signature.
        # We can make it async.
        
    async def handle_gl_account_change(self, acc_id: str):
        self.gl_selected_account_id = acc_id
        await self.load_general_ledger()
