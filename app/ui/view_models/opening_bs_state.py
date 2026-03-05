import reflex as rx
from typing import List, Dict
from datetime import date
from domain.models.account import AccountType
from core.logging import logger
from ..di import DI

class OpeningBSState(rx.State):
    """State for the Opening Balance Sheet entry page."""
    
    # 資産の部 (Assets)
    asset_accounts: List[Dict[str, str]] = []
    # 負債・純資産の部 (Liabilities & Equity)
    liability_equity_accounts: List[Dict[str, str]] = []
    
    # 科目IDをキーにした残高の辞書 (文字列で保持し入力欄の変更を受け付ける)
    balances: Dict[str, str] = {}
    
    is_loading: bool = False

    async def on_mount(self):
        """Called when the opening BS page is mounted."""
        return self.load_accounts()

    async def load_accounts(self):
        self.is_loading = True
        yield
        try:
            async with DI.get_master_service() as service:
                all_accounts = await service.get_accounts()
                
                # 資産運用法人として不要な固定資産等を除外するフィルタリング
                # B/S科目のみ抽出（PL科目は除外）
                allowed_types = [
                    AccountType.CURRENT_ASSET,
                    AccountType.DEFERRED_ASSET,
                    AccountType.CURRENT_LIABILITY,
                    AccountType.FIXED_LIABILITY,
                    AccountType.EQUITY
                ]
                
                filtered_accounts = [
                    acc for acc in all_accounts 
                    if acc.type in allowed_types and acc.name not in ["車両運搬具", "建物", "備品"]
                ]
                
                self.asset_accounts = [
                    {"id": str(a.id), "code": a.code, "name": a.name}
                    for a in filtered_accounts 
                    if a.type in [AccountType.CURRENT_ASSET, AccountType.DEFERRED_ASSET]
                ]
                self.liability_equity_accounts = [
                    {"id": str(a.id), "code": a.code, "name": a.name}
                    for a in filtered_accounts 
                    if a.type in [AccountType.CURRENT_LIABILITY, AccountType.FIXED_LIABILITY, AccountType.EQUITY]
                ]
                
                # Sort by code
                self.asset_accounts.sort(key=lambda x: x["code"])
                self.liability_equity_accounts.sort(key=lambda x: x["code"])
                
                # Initialize balances map if not exists
                for acc in filtered_accounts:
                    if str(acc.id) not in self.balances:
                        self.balances[str(acc.id)] = "0"
                        
        except Exception as e:
            logger.error("Failed to load accounts for Opening BS", error=str(e), exc_info=True)
            yield rx.window_alert("勘定科目の読み込みに失敗しました。")
        finally:
            self.is_loading = False
            yield

    def update_balance(self, account_id: str, value: str):
        """Update balance for a specific account. 
        Note: We must reassign the dict to trigger Reflex reactivity."""
        if not value:
            value = "0"
        new_balances = self.balances.copy()
        new_balances[account_id] = value
        self.balances = new_balances

    @rx.var
    def total_assets(self) -> int:
        """借方（資産）合計"""
        total = 0
        for acc in self.asset_accounts:
            val_str = self.balances.get(acc["id"], "0")
            try:
                total += int(val_str)
            except ValueError:
                pass
        return total

    @rx.var
    def total_liabilities_equity(self) -> int:
        """貸方（負債・純資産）合計"""
        total = 0
        for acc in self.liability_equity_accounts:
            val_str = self.balances.get(acc["id"], "0")
            try:
                total += int(val_str)
            except ValueError:
                pass
        return total

    @rx.var
    def difference(self) -> int:
        """貸借差額"""
        return self.total_assets - self.total_liabilities_equity

    @rx.var
    def is_balanced(self) -> bool:
        """貸借が一致しており、かつ何か入力があるか"""
        return self.difference == 0 and self.total_assets > 0

    async def get_fiscal_start_date(self) -> date | None:
        """マスタから現在の会計年度（または最新）の期首日を取得する。設定がない場合はNoneを返す。"""
        try:
            async with DI.get_master_service() as service:
                fys = await service.get_fiscal_years()
                if fys:
                    # 進行中の期を優先、なければ一番新しいものを取得
                    open_fys = [fy for fy in fys if fy.status == "OPEN"]
                    if open_fys:
                        open_fys.sort(key=lambda x: x.period_number, reverse=True)
                        return open_fys[0].start_date
                    else:
                        fys.sort(key=lambda x: x.period_number, reverse=True)
                        return fys[0].start_date
        except Exception as e:
            logger.error("Failed to fetch fiscal year start date", error=str(e))
            
        return None

    async def submit(self):
        """期首残高として仕訳を登録する"""
        if not self.is_balanced:
            return rx.window_alert("貸借が一致していません。")
            
        opening_date = await self.get_fiscal_start_date()
        if not opening_date:
            return rx.window_alert("会計年度が設定されていません。「マスタ管理」から会計年度を登録してください。")

        try:
            async with DI.get_journal_service() as service:
                await service.register_opening_balance(
                    opening_date=opening_date,
                    balances=self.balances,
                    asset_accounts=self.asset_accounts,
                    liability_equity_accounts=self.liability_equity_accounts
                )
                
            # Clear form safely for Reflex reactivity
            cleared_balances = self.balances.copy()
            for acc_id in cleared_balances:
                cleared_balances[acc_id] = "0"
            self.balances = cleared_balances
                
            return rx.toast("期首残高を登録しました！", duration=3000)
            
        except Exception as e:
            logger.error("Failed to submit opening BS", error=str(e), exc_info=True)
            return rx.window_alert(f"登録エラーが発生しました: {str(e)}")
