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
            await self.repository.commit() # Unit of Work Commit
            context_log.info("Journal entry added successfully", transaction_id=tx_id)
            return tx_id
        except Exception as e:
            context_log.error("Failed to add journal entry", error=str(e))
            raise

    async def update_journal_entry(self, transaction: Transaction) -> bool:
        context_log = self.log.bind(
            transaction_id=transaction.id,
            description=transaction.description
        )
        try:
            context_log.info("Updating journal entry")
            success = await self.repository.update_transaction(transaction)
            if success:
                await self.repository.commit()
                context_log.info("Journal entry updated successfully")
                return True
            else:
                context_log.warning("Journal entry not found for update")
                return False
        except Exception as e:
            context_log.error("Failed to update journal entry", error=str(e))
            raise

    async def get_entries(self, start_date=None, end_date=None, include_deleted: bool = False):
        # Renamed get_journal_entries to get_entries to match Step 2567 signature?
        # Step 2567: async def get_entries(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[Transaction]:
        # Step 2568: async def get_journal_entries(self): (No args)
        # I MUST match the original signature.
        
        try:
            self.log.debug("Fetching journal entries")
            # Step 2567: return await self.repo.get_transactions(start_date, end_date)
            entries = await self.repository.get_transactions(start_date, end_date, include_deleted=include_deleted)
            self.log.info("Fetched journal entries", count=len(entries))
            return entries
        except Exception as e:
            self.log.error("Failed to fetch journal entries", error=str(e))
            raise

    async def add_journal_entry_with_evidence(self, transaction: Transaction, file_bytes: bytes, file_service) -> int:
        context_log = self.log.bind(
            date=transaction.date.isoformat(),
            description=transaction.description,
            counterparty=transaction.counterparty 
        )
        try:
            context_log.info("Adding journal entry with evidence")
            
            # 1. Add Transaction (Flush only)
            tx_id = await self.repository.add_transaction(transaction)
            
            # 2. Save Evidence File
            # Calculate amount from lines for filename
            total_amount = sum(l.debit for l in transaction.lines)
            corp_name = transaction.counterparty or "Unknown"
            
            evidence_path = file_service.save_evidence_for_transaction(
                file_bytes=file_bytes,
                transaction_id=tx_id,
                date_obj=transaction.date,
                amount=total_amount,
                corp_name=corp_name
            )
            
            # 3. Update DB with path (This requires a way to update the specific field without full save? 
            # Or since we have the object or ID, we can update it. 
            # Ideally Repo has update method. 
            # For brevity/pragmatism in this flow, we can re-fetch or assume attached session object is live?
            # Actually, `add_transaction` flushes, so the object is in session identity map.
            # But we don't return the ORM object, we returned ID.
            # We need a way to update the path. Let's add a quick update method to repo or trust that we can't easily do it without one.
            # Wait, `add_transaction` in repo created `db_tx`.
            # If we want to clean UoW, we should probably pass the path IN `transaction` before calling add?
            # BUT: We need ID to generate filename. So ID must exist first.
            # So: Insert -> Get ID -> Gen Filename -> Update Path -> Commit.
            # We need an `update_evidence_path` method in repository, OR use raw SQL in service (bad), OR fetch-modify-flush.
            # Let's use fetch-modify mechanism or add specialized method.
            # Adding `update_evidence(id, path)` to interface is cleanest for this specific requirement.
            # But let's check if we can easier way: 
            # If we rely on SQLAlchemy session, we can fetch, modify, commit.
            
            # Let's add `update_evidence_path` to Repo for explicit clarity. 
            # Or just use `add_transaction` creates it without path, then we fetch and update.
            # Let's assume we add `update_evidence_path` to ILedgerRepository.
            await self.repository.update_evidence_path(tx_id, evidence_path)
            
            # 4. Commit
            await self.repository.commit()
            
            context_log.info("Journal entry with evidence added", transaction_id=tx_id, path=evidence_path)
            return tx_id

        except Exception as e:
            context_log.error("Failed to add entry with evidence", error=str(e))
            # Rollback is handled by session context usually, or explicit?
            # We should probably rollback if we could.
            # self.repository.rollback() ? (Not in interface yet, but maybe session auto-rolls back on close/error?)
            raise

    async def delete_entry(self, transaction_id: int):
        context_log = self.log.bind(transaction_id=transaction_id)
        try:
            context_log.info("Deleting journal entry")
            await self.repository.delete_transaction(transaction_id)
            context_log.info("Journal entry deleted successfully")
        except Exception as e:
            context_log.error("Failed to delete journal entry", error=str(e))
            raise

    async def export_journal_entries_csv(self, start_date=None, end_date=None) -> str:
        """
        Exports journal entries to CSV string.
        """
        import csv
        import io
        
        try:
            # Fetch transactions with relationships
            transactions = await self.repository.get_transactions(
                start_date=start_date, 
                end_date=end_date, 
                include_deleted=False, 
                include_relationships=True
            )
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([
                "取引日", "ID", "摘要", "取引先", "登録番号", "勘定科目コード", "勘定科目", "借方金額", "貸方金額"
            ])
            
            for t in transactions:
                # Common fields for all lines in this transaction
                common = [
                    t.date.isoformat(),
                    t.id,
                    t.description,
                    t.counterparty or "",
                    t.invoice_number or ""
                ]
                
                for line in t.lines:
                    # Account might be loaded
                    account_code = line.account.code if line.account else ""
                    account_name = line.account.name if line.account else f"ID:{line.account_id}"
                    
                    row = common + [
                        account_code,
                        account_name,
                        line.debit if line.debit > 0 else 0,
                        line.credit if line.credit > 0 else 0
                    ]
                    writer.writerow(row)
                    
            return output.getvalue()
            
        except Exception as e:
            self.log.error("Failed to export CSV", error=str(e))
            raise
