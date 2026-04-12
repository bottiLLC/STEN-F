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

    def set_new_fy_name(self, v: str): 
        self.new_fy_name = v
        
    def set_new_fy_period(self, v: str): 
        try: 
            self.new_fy_period = int(v)
        except ValueError: 
            pass
            
    def set_new_fy_start(self, v: str): 
        self.new_fy_start = v
        
    def set_new_fy_end(self, v: str): 
        self.new_fy_end = v
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

    is_processing_close: bool = False
    show_close_dialog: bool = False
    target_close_fy_id: int = 0
    next_fy_name_input: str = ""

    def open_close_dialog(self, current_period: int, fy_id: int):
        self.target_close_fy_id = fy_id
        self.next_fy_name_input = f"第{current_period + 1}期"
        self.show_close_dialog = True

    def toggle_close_dialog(self):
        self.show_close_dialog = not self.show_close_dialog
        
    def set_next_fy_name_input(self, v: str):
        self.next_fy_name_input = v

    async def update_fiscal_year_name(self, fy_id: int, new_name: str):
        async with DI.get_master_service() as service:
            try:
                fy = await service.get_fiscal_year_by_id(fy_id)
                if fy:
                    fy.name = new_name
                    await service.save_fiscal_year(fy)
                    self.fiscal_years = await service.get_fiscal_years()
            except Exception as e:
                return rx.window_alert(f"名称更新エラー: {e}")

    async def close_fiscal_year(self):
        self.is_processing_close = True
        self.show_close_dialog = False
        yield
        try:
            async with DI.get_fiscal_year_service() as service:
                await service.close_fiscal_year(self.target_close_fy_id, next_fy_name=self.next_fy_name_input)
            
            # Reload the list
            async with DI.get_master_service() as m_service:
                self.fiscal_years = await m_service.get_fiscal_years()
            yield rx.window_alert("期末処理が完了し、次年度の期首残高（開始仕訳）を登録しました！")
            return
        except Exception as e:
            yield rx.window_alert(f"期末処理エラー: {e}")
            return
        finally:
            self.is_processing_close = False
            yield
