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
from datetime import date
from typing import Any, Dict, List, Optional
from app.domain.models.account import Account
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.transaction import Transaction


class ILedgerRepository(ABC):
    @abstractmethod
    async def get_accounts(self) -> List[Account]: ...
    @abstractmethod
    async def get_transactions(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
        include_relationships: bool = False,
    ) -> List[Transaction]: ...
    @abstractmethod
    async def get_transactions_by_account(
        self,
        account_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
    ) -> List[Transaction]: ...
    @abstractmethod
    async def add_transaction(self, transaction: Transaction) -> int: ...
    @abstractmethod
    async def has_transactions_for_account(self, account_id: int) -> bool: ...
    @abstractmethod
    async def delete_transaction(self, transaction_id: int) -> bool: ...
    @abstractmethod
    async def get_trial_balance_data(
        self, fiscal_year_id: int
    ) -> List[Dict[str, Any]]: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def update_transaction(self, transaction: Transaction) -> bool: ...
    @abstractmethod
    async def update_evidence_path(self, transaction_id: int, path: str) -> bool: ...
    @abstractmethod
    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]: ...
    @abstractmethod
    async def get_fiscal_year(self, fiscal_year_id: int) -> Optional[FiscalYear]: ...
