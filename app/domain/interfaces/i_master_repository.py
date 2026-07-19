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

from abc import ABC, abstractmethod
from typing import List, Optional
from app.domain.models.corporation import Corporation
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import Account
from app.domain.models.abstract import Abstract
from app.domain.models.counterparty import Counterparty
from app.domain.models.system import SystemSettings


class IMasterRepository(ABC):
    # System Settings
    @abstractmethod
    async def get_system_settings(self) -> SystemSettings:
        pass

    @abstractmethod
    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        pass

    # Corporation
    @abstractmethod
    async def get_corporation(self) -> Optional[Corporation]:
        pass

    @abstractmethod
    async def save_corporation(self, corp: Corporation) -> Corporation:
        pass

    # Fiscal Year
    @abstractmethod
    async def get_fiscal_years(self) -> List[FiscalYear]:
        pass

    @abstractmethod
    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]:
        pass

    # Counterparty
    @abstractmethod
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        pass

    @abstractmethod
    async def get_counterparties(self) -> List[Counterparty]:
        pass

    @abstractmethod
    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]:
        pass

    @abstractmethod
    async def delete_counterparty(self, cp_id: int) -> bool:
        pass

    @abstractmethod
    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        pass

    @abstractmethod
    async def delete_fiscal_year(self, fy_id: int) -> bool:
        pass

    # Account
    @abstractmethod
    async def get_accounts(self) -> List[Account]:
        pass

    @abstractmethod
    async def save_account(self, account: Account) -> Account:
        pass

    @abstractmethod
    async def delete_account(self, account_id: int) -> bool:
        pass

    # Abstract
    @abstractmethod
    async def get_abstracts(self) -> List[Abstract]:
        pass

    @abstractmethod
    async def save_abstract(self, abstract: Abstract) -> Abstract:
        pass

    @abstractmethod
    async def delete_abstract(self, abs_id: int) -> bool:
        pass
