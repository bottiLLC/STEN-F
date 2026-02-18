from contextlib import asynccontextmanager
from typing import AsyncGenerator

from infrastructure.db.session import AsyncSessionLocal
from infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from infrastructure.repositories.master_repository_impl import SQLAlchemyMasterRepository
from infrastructure.external.ocr_service import GoogleOCRService
from infrastructure.external.file_service import LocalFileService
from application.services.ledger_service import LedgerService
from application.services.master_service import MasterService
from application.services.journal_service import JournalService
from application.services.fiscal_year_service import FiscalYearService

class Container:
    """
    Dependency Injection Container ensuring scoped session management.
    """
    
    @asynccontextmanager
    async def session_scope(self):
        """Provide a transactional scope."""
        session = AsyncSessionLocal()
        try:
            yield session
            # Commit is usually handled by Service or Repository commit() methods explicitly
            # But we could auto-commit here if we wanted.
            # For now, we leave it to explicit commit in services.
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def journal_service_scope(self) -> AsyncGenerator[JournalService, None]:
        async with self.session_scope() as session:
            repo = SQLAlchemyLedgerRepository(session)
            service = JournalService(repo)
            yield service

    @asynccontextmanager
    async def master_service_scope(self) -> AsyncGenerator[MasterService, None]:
        async with self.session_scope() as session:
            repo = SQLAlchemyMasterRepository(session)
            ledger_repo = SQLAlchemyLedgerRepository(session)
            service = MasterService(repo, ledger_repository=ledger_repo)
            yield service

    @asynccontextmanager
    async def ledger_service_scope(self) -> AsyncGenerator[LedgerService, None]:
        async with self.session_scope() as session:
            repo = SQLAlchemyLedgerRepository(session)
            service = LedgerService(repo)
            yield service

    @asynccontextmanager
    async def fiscal_year_service_scope(self) -> AsyncGenerator[FiscalYearService, None]:
        # FY Service needs Master, Ledger, Journal services.
        # They should share the SAME session for consistency.
        async with self.session_scope() as session:
            master_repo = SQLAlchemyMasterRepository(session)
            ledger_repo = SQLAlchemyLedgerRepository(session)
            
            # Construct services sharing the repos (and thus the session)
            master_service = MasterService(master_repo, ledger_repository=ledger_repo)
            ledger_service = LedgerService(ledger_repo)
            journal_service = JournalService(ledger_repo)
            
            service = FiscalYearService(master_service, ledger_service, journal_service)
            yield service

    def get_ocr_service(self) -> GoogleOCRService:
        return GoogleOCRService()

    def get_file_service(self) -> LocalFileService:
        return LocalFileService()

    def get_pdf_service(self):
        from infrastructure.external.pdf_service import PDFService
        return PDFService()

    def get_backup_service(self):
        from infrastructure.external.backup_service import BackupService
        return BackupService()

# Global instance
container = Container()
