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

from typing import List, Optional
import structlog
from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.interfaces.i_master_repository import IMasterRepository
from app.domain.models.abstract import Abstract
from app.domain.models.account import Account
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.system import SystemSettings

log = structlog.get_logger()


class MasterService:
    def __init__(
        self,
        repository: IMasterRepository,
        ledger_repository: Optional[ILedgerRepository] = None,
    ):
        self.repository = repository
        self.ledger_repository = ledger_repository
        self.log = log.bind(service="MasterService")

    async def get_system_settings(self) -> SystemSettings:
        return await self.repository.get_system_settings()

    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        return await self.repository.save_system_settings(settings)

    async def get_corporation(self) -> Optional[Corporation]:
        return await self.repository.get_corporation()

    async def save_corporation(self, corp: Corporation) -> None:
        await self.repository.save_corporation(corp)

    async def get_fiscal_years(self) -> List[FiscalYear]:
        return await self.repository.get_fiscal_years()

    async def get_fiscal_year_by_id(self, fy_id: int) -> Optional[FiscalYear]:
        return await self.repository.get_fiscal_year(fy_id)

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        return await self.repository.save_fiscal_year(fy)

    async def create_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        return await self.save_fiscal_year(fy)

    async def delete_fiscal_year(self, fy_id: int) -> None:
        await self.repository.delete_fiscal_year(fy_id)

    async def get_accounts(self) -> List[Account]:
        return await self.repository.get_accounts()

    async def save_account(self, account: Account) -> Account:
        return await self.repository.save_account(account)

    async def delete_account(self, account_id: int) -> None:
        if (
            self.ledger_repository
            and await self.ledger_repository.has_transactions_for_account(account_id)
        ):
            raise ValueError("この勘定科目は仕訳で使用されているため削除できません。")
        await self.repository.delete_account(account_id)

    async def initialize_default_accounts(self) -> int:
        from app.domain.constants.default_accounts import DEFAULT_ACCOUNTS

        existing = {a.code for a in await self.get_accounts()}
        to_add = [d for d in DEFAULT_ACCOUNTS if d["code"] not in existing]
        for data in to_add:
            await self.save_account(
                Account(code=data["code"], name=data["name"], type=data["type"], description=data.get("description"))
            )
        return len(to_add)


    async def get_abstracts(self) -> List[Abstract]:
        return await self.repository.get_abstracts()

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        return await self.repository.save_abstract(abstract)

    async def delete_abstract(self, abstract_id: int) -> None:
        await self.repository.delete_abstract(abstract_id)

    LEGAL_ENTITY_KANA = [
        "カブシキガイシャ",
        "カブシキカイシャ",
        "カ）",
        "（カ",
        "ユウゲンガイシャ",
        "ユウゲンカイシャ",
        "ユ）",
        "（ユ",
        "ゴウドウガイシャ",
        "ド）",
        "（ド",
        "イッパンシャダンホウジン",
        "コウエキシャダンホウジン",
        "ガッコウホウジン",
        "シュウキョウホウジン",
        "イリョウホウジン",
        "シャカイフクシホウジン",
        "トクテイヒエイリカツドウホウジン",
        "　",
        " ",
    ]

    async def get_counterparties(self) -> List[Counterparty]:
        cps = await self.repository.get_counterparties()

        def sort_key(cp: Counterparty):
            key = cp.name_kana if cp.name_kana else cp.name
            for word in self.LEGAL_ENTITY_KANA:
                key = key.replace(word, "")
            return key

        cps.sort(key=sort_key)
        return cps

    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        return await self.repository.save_counterparty(counterparty)

    async def delete_counterparty(self, counterparty_id: int) -> None:
        await self.repository.delete_counterparty(counterparty_id)

    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]:
        if not keyword:
            return None
        return await self.repository.get_counterparty_by_keyword(keyword)
