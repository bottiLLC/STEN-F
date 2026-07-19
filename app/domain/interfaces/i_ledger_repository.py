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
from datetime import date
from app.domain.models.transaction import Transaction
from app.domain.models.account import Account

class ILedgerRepository(ABC):
    @abstractmethod
    async def get_accounts(self) -> List[Account]:
        """Fetch all accounts."""
        pass

    @abstractmethod
    async def get_transactions(self, start_date: Optional[date] = None, end_date: Optional[date] = None, include_deleted: bool = False, include_relationships: bool = False) -> List[Transaction]:
        """Fetch transactions within a date range."""
        pass

    @abstractmethod
    async def get_transactions_by_account(self, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None, include_deleted: bool = False) -> List[Transaction]:
        """Fetch transactions for a specific account within a date range."""
        pass

    @abstractmethod
    async def add_transaction(self, transaction: Transaction) -> int:
        """Add a new transaction and return its ID."""
        pass
        
    @abstractmethod
    async def has_transactions_for_account(self, account_id: int) -> bool:
        """Check if any transactions exist for the given account ID."""
        pass
        
    @abstractmethod
    async def delete_transaction(self, transaction_id: int) -> bool:
        """Delete a transaction by ID."""
        pass
    
    @abstractmethod
    async def get_trial_balance_data(self, fiscal_year_id: int) -> List[dict]:
        """
        Fetch aggregated data for Trial Balance.
        Returns list of dicts with account_id, debit_total, credit_total.
        """
        pass

    @abstractmethod
    async def commit(self):
        """Commit the current transaction."""
        pass

    @abstractmethod
    async def update_transaction(self, transaction: Transaction) -> bool:
        """Update an existing transaction."""
        pass

    @abstractmethod
    async def update_evidence_path(self, transaction_id: int, path: str) -> bool:
        """Update the evidence path for a transaction."""
        pass

    @abstractmethod
    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]:
        """Get IDs of frequently used accounts."""
        pass
