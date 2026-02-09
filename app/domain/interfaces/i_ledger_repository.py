from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from domain.models.transaction import Transaction
from domain.models.account import Account

class ILedgerRepository(ABC):
    @abstractmethod
    async def get_accounts(self) -> List[Account]:
        """Fetch all accounts."""
        pass

    @abstractmethod
    async def get_transactions(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        """Fetch transactions within a date range."""
        pass

    @abstractmethod
    async def get_transactions_by_account(self, account_id: int, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        """Fetch transactions for a specific account within a date range."""
        pass

    @abstractmethod
    async def add_transaction(self, transaction: Transaction) -> int:
        """Add a new transaction and return its ID."""
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
