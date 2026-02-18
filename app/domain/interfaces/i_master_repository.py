from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.corporation import Corporation
from domain.models.fiscal_year import FiscalYear
from domain.models.account import Account
from domain.models.abstract import Abstract
from domain.models.counterparty import Counterparty

class IMasterRepository(ABC):
    # Corporation
    @abstractmethod
    async def get_corporation(self) -> Optional[Corporation]: pass
    
    @abstractmethod
    async def save_corporation(self, corp: Corporation) -> Corporation: pass
    
    # Fiscal Year
    @abstractmethod
    async def get_fiscal_years(self) -> List[FiscalYear]: pass

    @abstractmethod
    async def get_fiscal_year(self, fy_id: int) -> Optional[FiscalYear]: pass
    
    # Counterparty
    @abstractmethod
    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty: pass
    
    @abstractmethod
    async def get_counterparties(self) -> List[Counterparty]: pass
    
    @abstractmethod
    async def delete_counterparty(self, cp_id: int) -> bool: pass
    
    @abstractmethod
    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear: pass
    
    # Account
    @abstractmethod
    async def get_accounts(self) -> List[Account]: pass
    
    @abstractmethod
    async def save_account(self, account: Account) -> Account: pass
    
    @abstractmethod
    async def delete_account(self, account_id: int) -> bool: pass
    
    # Abstract
    @abstractmethod
    async def get_abstracts(self) -> List[Abstract]: pass
    
    @abstractmethod
    async def save_abstract(self, abstract: Abstract) -> Abstract: pass
