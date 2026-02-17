import contextlib
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from app.infrastructure.repositories.master_repository_impl import SQLAlchemyMasterRepository
from app.application.services.journal_service import JournalService
from app.application.services.master_service import MasterService
from app.application.services.ledger_service import LedgerService
from app.infrastructure.external.ocr_service import GoogleOCRService
from app.infrastructure.external.file_service import LocalFileService

class DI:
    @staticmethod
    @contextlib.asynccontextmanager
    async def get_journal_service() -> JournalService:
        session: AsyncSession = AsyncSessionLocal()
        try:
            repo = SQLAlchemyLedgerRepository(session)
            yield JournalService(repo)
        finally:
            await session.close()

    @staticmethod
    @contextlib.asynccontextmanager
    async def get_master_service() -> MasterService:
        session: AsyncSession = AsyncSessionLocal()
        try:
            repo = SQLAlchemyMasterRepository(session)
            ledger_repo = SQLAlchemyLedgerRepository(session)
            yield MasterService(repo, ledger_repository=ledger_repo)
        finally:
            await session.close()

    @staticmethod
    @contextlib.asynccontextmanager
    async def get_ledger_service() -> LedgerService:
        session: AsyncSession = AsyncSessionLocal()
        try:
            repo = SQLAlchemyLedgerRepository(session)
            yield LedgerService(repo)
        finally:
            await session.close()

    @staticmethod
    def get_ocr_service() -> GoogleOCRService:
        return GoogleOCRService()

    @staticmethod
    def get_file_service() -> LocalFileService:
        return LocalFileService()

    @staticmethod
    def get_backup_service():
        from app.infrastructure.external.backup_service import BackupService
        return BackupService()

    @staticmethod
    def get_pdf_service():
        from app.infrastructure.external.pdf_service import PDFService
        return PDFService()
