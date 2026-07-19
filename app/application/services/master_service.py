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

from app.core.logging import logger
from app.domain.interfaces.i_master_repository import IMasterRepository
from app.domain.models.corporation import Corporation
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import Account
from app.domain.models.abstract import Abstract
from app.domain.models.counterparty import Counterparty
from app.domain.models.system import SystemSettings

from app.domain.interfaces.i_ledger_repository import ILedgerRepository

class MasterService:
    def __init__(self, repository: IMasterRepository, ledger_repository: ILedgerRepository = None):
        self.repository = repository
        self.ledger_repository = ledger_repository
        self.log = logger.bind(service="MasterService")

    # --- System Settings ---
    async def get_system_settings(self) -> SystemSettings:
        return await self.repository.get_system_settings()

    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        self.log.info("Saving System Settings")
        saved = await self.repository.save_system_settings(settings)
        self.log.info("System Settings saved")
        return saved
        
    # --- Corporation ---
    async def get_corporation(self) -> Corporation:
        return await self.repository.get_corporation()

    async def save_corporation(self, corp: Corporation):
        self.log.info("Saving Corporation data", name=corp.name)
        await self.repository.save_corporation(corp)
        self.log.info("Corporation data saved")

    # --- Fiscal Year ---
    async def get_fiscal_years(self) -> list[FiscalYear]:
        return await self.repository.get_fiscal_years()

    async def get_fiscal_year_by_id(self, fy_id: int) -> FiscalYear:
        return await self.repository.get_fiscal_year(fy_id)

    async def save_fiscal_year(self, fy: FiscalYear):
        self.log.info("Saving Fiscal Year", name=fy.name, period=fy.period_number)
        saved = await self.repository.save_fiscal_year(fy)
        self.log.info("Fiscal Year saved")
        return saved

    async def create_fiscal_year(self, fy: FiscalYear):
        return await self.save_fiscal_year(fy)
    
    async def delete_fiscal_year(self, fy_id: int):
        self.log.info("Deleting Fiscal Year", fy_id=fy_id)
        await self.repository.delete_fiscal_year(fy_id)
        self.log.info("Fiscal Year deleted")

    # --- Account ---
    async def get_accounts(self) -> list[Account]:
        return await self.repository.get_accounts()

    async def save_account(self, account: Account):
        self.log.info("Saving Account", code=account.code, name=account.name)
        await self.repository.save_account(account)
        self.log.info("Account saved")
    
    async def delete_account(self, account_id: int):
        self.log.info("Deleting Account", account_id=account_id)
        
        if self.ledger_repository:
            has_tx = await self.ledger_repository.has_transactions_for_account(account_id)
            if has_tx:
                self.log.warning("Cannot delete account with existing transactions", account_id=account_id)
                raise ValueError("この勘定科目は仕訳で使用されているため削除できません。")

        await self.repository.delete_account(account_id)
        self.log.info("Account deleted")

    async def initialize_default_accounts(self) -> int:
        """Initializes default accounts if they don't exist."""
        from domain.constants.default_accounts import DEFAULT_ACCOUNTS
        
        self.log.info("Initializing default accounts")
        existing_accounts = await self.get_accounts()
        existing_codes = {acc.code for acc in existing_accounts}
        
        count = 0
        for data in DEFAULT_ACCOUNTS:
            if data["code"] not in existing_codes:
                new_acc = Account(
                    code=data["code"],
                    name=data["name"],
                    type=data["type"],
                    description=data["description"]
                )
                await self.save_account(new_acc)
                count += 1
        
        self.log.info("Default accounts initialized", count=count)
        return count

    # --- Abstract ---
    async def get_abstracts(self) -> list[Abstract]:
        return await self.repository.get_abstracts()

    async def save_abstract(self, abstract: Abstract):
        self.log.info("Saving Abstract", text=abstract.text)
        await self.repository.save_abstract(abstract)
        self.log.info("Abstract saved")

    async def delete_abstract(self, abstract_id: int):
        self.log.info("Deleting Abstract", abstract_id=abstract_id)
        await self.repository.delete_abstract(abstract_id)
        self.log.info("Abstract deleted")

    # --- Counterparty ---
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        self.log.info("Saving Counterparty", name=counterparty.name)
        saved = await self.repository.save_counterparty(counterparty)
        self.log.info("Counterparty saved")
        return saved

    # Common legal entity strings (Kana) to remove for sorting
    LEGAL_ENTITY_KANA = [
        "カブシキガイシャ", "カブシキカイシャ", "カ）", "（カ", 
        "ユウゲンガイシャ", "ユウゲンカイシャ", "ユ）", "（ユ",
        "ゴウドウガイシャ", "ド）", "（ド",
        "イッパンシャダンホウジン",
        "コウエキシャダンホウジン",
        "ガッコウホウジン",
        "シュウキョウホウジン",
        "イリョウホウジン",
        "シャカイフクシホウジン",
        "トクテイヒエイリカツドウホウジン", # NPO
        "　", " " # Spaces
    ]

    async def get_counterparties(self) -> list[Counterparty]:
        cps = await self.repository.get_counterparties()
        
        def sort_key(cp: Counterparty):
            # 1. Use kana if available, else name
            key = cp.name_kana if cp.name_kana else cp.name
            
            # 2. Normalize: Remove common legal entity strings
            for word in self.LEGAL_ENTITY_KANA:
                key = key.replace(word, "")
                
            return key

        # Python's sort is stable
        cps.sort(key=sort_key)
        return cps

    async def get_counterparty_by_keyword(self, keyword: str) -> Counterparty | None:
        if not keyword:
            return None
        return await self.repository.get_counterparty_by_keyword(keyword)

    async def delete_counterparty(self, cp_id: int):
        self.log.info("Deleting Counterparty", cp_id=cp_id)
        await self.repository.delete_counterparty(cp_id)
        self.log.info("Counterparty deleted")


