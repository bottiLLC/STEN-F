import reflex as rx
from datetime import date
from typing import List
from app.domain.models.fiscal_year import FiscalYear
from app.ui.di import DI

class FiscalYearState(rx.State):
    fiscal_years: List[FiscalYear] = []
    
    # Form State
    new_fy_name: str = ""
    new_fy_period: int = 1
    new_fy_start: str = date.today().isoformat()
    new_fy_end: str = date.today().isoformat()
    new_fy_status: str = "OPEN"

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
                return rx.toast("会計年度を作成しました。")
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
