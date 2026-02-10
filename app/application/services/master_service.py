from core.logging import logger
from domain.interfaces.i_master_repository import IMasterRepository
from domain.models.corporation import Corporation
from domain.models.fiscal_year import FiscalYear
from domain.models.account import Account
from domain.models.abstract import Abstract
from domain.models.counterparty import Counterparty

class MasterService:
    def __init__(self, repository: IMasterRepository):
        self.repository = repository
        self.log = logger.bind(service="MasterService")

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

    async def save_fiscal_year(self, fy: FiscalYear):
        self.log.info("Saving Fiscal Year", name=fy.name, period=fy.period_number)
        await self.repository.save_fiscal_year(fy)
        self.log.info("Fiscal Year saved")

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
        await self.repository.delete_account(account_id)
        self.log.info("Account deleted")

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
