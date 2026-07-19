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
from typing import List, Dict
from datetime import date
import structlog
from app.domain.models.account import AccountType
from app.core.utils import normalize_amount
from ..di import DI

log = structlog.get_logger()


class OpeningBSState(rx.State):
    """State for the Opening Balance Sheet entry page."""

    # 貸借対照表 (B/S) 全科目
    bs_accounts: List[Dict[str, str]] = []

    # 科目IDをキーにした残高の辞書
    debit_balances: Dict[str, str] = {}
    credit_balances: Dict[str, str] = {}

    is_loading: bool = False

    async def load_accounts(self):
        self.is_loading = True
        yield
        try:
            async with DI.get_master_service() as service:
                all_accounts = await service.get_accounts()

                # B/S科目のみ抽出（PL科目は除外）
                allowed_types = [
                    AccountType.CURRENT_ASSET,
                    AccountType.FIXED_ASSET,
                    AccountType.DEFERRED_ASSET,
                    AccountType.CURRENT_LIABILITY,
                    AccountType.FIXED_LIABILITY,
                    AccountType.EQUITY,
                ]

                filtered_accounts = [
                    acc for acc in all_accounts if acc.type in allowed_types
                ]

                self.bs_accounts = [
                    {
                        "id": str(a.id),
                        "code": a.code,
                        "name": a.name,
                        "type": a.type.value,
                    }
                    for a in filtered_accounts
                ]

                # Sort by code
                self.bs_accounts.sort(key=lambda x: x["code"])

                # Initialize balances map if not exists
                for acc in filtered_accounts:
                    if str(acc.id) not in self.debit_balances:
                        self.debit_balances[str(acc.id)] = ""
                    if str(acc.id) not in self.credit_balances:
                        self.credit_balances[str(acc.id)] = ""

        except Exception as e:
            log.error(
                "Failed to load accounts for Opening BS", error=str(e), exc_info=True
            )
            yield rx.window_alert("勘定科目の読み込みに失敗しました。")
        finally:
            self.is_loading = False
            yield

    def update_debit_balance(self, account_id: str, value: str):
        """Update debit balance for a specific account."""
        new_balances = self.debit_balances.copy()
        new_balances[account_id] = value
        self.debit_balances = new_balances

    def update_credit_balance(self, account_id: str, value: str):
        """Update credit balance for a specific account."""
        new_balances = self.credit_balances.copy()
        new_balances[account_id] = value
        self.credit_balances = new_balances

    @rx.var
    def total_debit(self) -> int:
        """借方合計"""
        total = 0
        for val_str in self.debit_balances.values():
            if val_str:
                total += normalize_amount(val_str)
        return total

    @rx.var
    def total_credit(self) -> int:
        """貸方合計"""
        total = 0
        for val_str in self.credit_balances.values():
            if val_str:
                total += normalize_amount(val_str)
        return total

    @rx.var
    def difference(self) -> int:
        """貸借差額"""
        return abs(self.total_debit - self.total_credit)

    @rx.var
    def is_balanced(self) -> bool:
        """貸借が一致しており、かつ何か入力があるか"""
        return self.total_debit == self.total_credit and self.total_debit > 0

    async def get_fiscal_start_date(self) -> date | None:
        """マスタから現在の会計年度（または最新）の期首日を取得する。設定がない場合はNoneを返す。"""
        try:
            async with DI.get_master_service() as service:
                fys = await service.get_fiscal_years()
                if fys:
                    # 進行中の期を優先、なければ一番新しいものを取得
                    open_fys = [fy for fy in fys if fy.status == "OPEN"]
                    if open_fys:
                        open_fys.sort(key=lambda x: x.period_number or 0, reverse=True)
                        return open_fys[0].start_date
                    else:
                        fys.sort(key=lambda x: x.period_number or 0, reverse=True)
                        return fys[0].start_date
        except Exception as e:
            log.error("Failed to fetch fiscal year start date", error=str(e))

        return None

    async def submit(self):
        """期首残高として仕訳を登録する"""
        if not self.is_balanced:
            return rx.window_alert("貸借が一致していません。")

        opening_date = await self.get_fiscal_start_date()
        if not opening_date:
            return rx.window_alert(
                "会計年度が設定されていません。「マスタ管理」から会計年度を登録してください。"
            )

        try:
            async with DI.get_journal_service() as service:
                await service.register_opening_balance(
                    opening_date=opening_date,
                    debit_balances=self.debit_balances,
                    credit_balances=self.credit_balances,
                )

            # Clear form safely for Reflex reactivity
            cleared_debits = self.debit_balances.copy()
            cleared_credits = self.credit_balances.copy()
            for acc_id in cleared_debits:
                cleared_debits[acc_id] = ""
                cleared_credits[acc_id] = ""
            self.debit_balances = cleared_debits
            self.credit_balances = cleared_credits

            return rx.toast("期首残高を登録しました！", duration=3000)

        except Exception as e:
            log.error("Failed to submit opening BS", error=str(e), exc_info=True)
            return rx.window_alert(f"登録エラーが発生しました: {str(e)}")
