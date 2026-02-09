from infrastructure.db.session import get_session
from infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from infrastructure.repositories.master_repository_impl import SQLAlchemyMasterRepository
from infrastructure.external.ocr_service import GoogleOCRService
from infrastructure.external.file_service import LocalFileService
from application.services.ledger_service import LedgerService
from application.services.master_service import MasterService
from application.services.journal_service import JournalService
from sqlalchemy.ext.asyncio import AsyncSession

class Container:
    def __init__(self):
        self._session_factory = get_session
        self._ledger_repo = None
        self._ledger_service = None

    async def get_db_session(self) -> AsyncSession:
        from infrastructure.db.session import AsyncSessionLocal
        return AsyncSessionLocal()

    async def get_ledger_repository(self) -> SQLAlchemyLedgerRepository:
        session = await self.get_db_session()
        return SQLAlchemyLedgerRepository(session)
    
    async def get_master_repository(self) -> SQLAlchemyMasterRepository:
        session = await self.get_db_session()
        return SQLAlchemyMasterRepository(session)

    async def get_ledger_service(self) -> LedgerService:
        repo = await self.get_ledger_repository()
        return LedgerService(repo)

    async def get_master_service(self) -> MasterService:
        repo = await self.get_master_repository()
        return MasterService(repo)

    async def get_journal_service(self) -> JournalService:
        repo = await self.get_ledger_repository()
        return JournalService(repo)

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

# Global Container instance for simplicity (or instantiated in main)
# But handling async session lifecycle properly is key.
# For Clean Arch, we usually use a request-scoped container.
# In Streamlit, the script runs top-down.
# We will instantiate Container in main.
