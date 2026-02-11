from abc import ABC, abstractmethod
from typing import List, Optional
from domain.models.corporation import Corporation
from domain.models.fiscal_year import FiscalYear
from domain.models.account import Account
from domain.models.abstract import Abstract

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
