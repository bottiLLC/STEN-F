from core.logging import logger
from domain.models.transaction import Transaction
from domain.interfaces.i_ledger_repository import ILedgerRepository

class JournalService:
    def __init__(self, repository: ILedgerRepository):
        self.repository = repository
        self.log = logger.bind(service="JournalService")

    async def add_journal_entry(self, transaction: Transaction):
        context_log = self.log.bind(
            date=transaction.date.isoformat(),
            description=transaction.description,
            line_count=len(transaction.lines)
        )
        
        try:
            context_log.info("Adding new journal entry")
            # In Step 2567 it was self.repo.add_transaction(transaction)
            # In Step 2568 I wrote await self.repository.add(transaction)
            # "add" vs "add_transaction". I suspect "add_transaction" is correct.
            tx_id = await self.repository.add_transaction(transaction)
            context_log.info("Journal entry added successfully", transaction_id=tx_id)
            return tx_id
        except Exception as e:
            context_log.error("Failed to add journal entry", error=str(e))
            raise

    async def get_entries(self, start_date=None, end_date=None):
        # Renamed get_journal_entries to get_entries to match Step 2567 signature?
        # Step 2567: async def get_entries(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        # Step 2568: async def get_journal_entries(self): (No args)
        # I MUST match the original signature.
        
        try:
            self.log.debug("Fetching journal entries")
            # Step 2567: return await self.repo.get_transactions(start_date, end_date)
            entries = await self.repository.get_transactions(start_date, end_date)
            self.log.info("Fetched journal entries", count=len(entries))
            return entries
        except Exception as e:
            self.log.error("Failed to fetch journal entries", error=str(e))
            raise

    async def delete_entry(self, transaction_id: int):
        context_log = self.log.bind(transaction_id=transaction_id)
        try:
            context_log.info("Deleting journal entry")
            # Step 2567: return await self.repo.delete_transaction(transaction_id)
            await self.repository.delete_transaction(transaction_id)
            context_log.info("Journal entry deleted successfully")
        except Exception as e:
            context_log.error("Failed to delete journal entry", error=str(e))
            raise
