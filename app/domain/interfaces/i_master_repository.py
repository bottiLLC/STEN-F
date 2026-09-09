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
from app.domain.models.abstract import Abstract
from app.domain.models.account import Account
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.system import SystemSettings


class IMasterRepository(ABC):
    @abstractmethod
    async def get_system_settings(self) -> SystemSettings: ...
    @abstractmethod
    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings: ...
    @abstractmethod
    async def get_corporation(self) -> Optional[Corporation]: ...
    @abstractmethod
    async def save_corporation(self, corp: Corporation) -> Corporation: ...
    @abstractmethod
    async def get_fiscal_years(self) -> List[FiscalYear]: ...
    @abstractmethod
    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]: ...
    @abstractmethod
    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear: ...
    @abstractmethod
    async def delete_fiscal_year(self, fy_id: int) -> bool: ...
    @abstractmethod
    async def get_counterparties(self) -> List[Counterparty]: ...
    @abstractmethod
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty: ...
    @abstractmethod
    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]: ...
    @abstractmethod
    async def delete_counterparty(self, cp_id: int) -> bool: ...
    @abstractmethod
    async def get_accounts(self) -> List[Account]: ...
    @abstractmethod
    async def save_account(self, account: Account) -> Account: ...
    @abstractmethod
    async def delete_account(self, account_id: int) -> bool: ...
    @abstractmethod
    async def get_abstracts(self) -> List[Abstract]: ...
    @abstractmethod
    async def save_abstract(self, abstract: Abstract) -> Abstract: ...
    @abstractmethod
    async def delete_abstract(self, abs_id: int) -> bool: ...
