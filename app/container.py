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

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from app.application.services.fiscal_year_service import FiscalYearService
from app.application.services.journal_service import JournalService
from app.application.services.ledger_service import LedgerService
from app.application.services.master_service import MasterService
from app.infrastructure.db.session import AsyncSessionLocal
from app.infrastructure.external.backup_service import BackupService
from app.infrastructure.external.file_service import LocalFileService
from app.infrastructure.external.ocr_service import GeminiOCRService
from app.infrastructure.external.pdf_service import PDFService
from app.infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from app.infrastructure.repositories.master_repository_impl import SQLAlchemyMasterRepository


class Container:
    @asynccontextmanager
    async def session_scope(self):
        session = AsyncSessionLocal()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def journal_service_scope(self) -> AsyncGenerator[JournalService, None]:
        async with self.session_scope() as s:
            yield JournalService(SQLAlchemyLedgerRepository(s), master_repository=SQLAlchemyMasterRepository(s))

    @asynccontextmanager
    async def master_service_scope(self) -> AsyncGenerator[MasterService, None]:
        async with self.session_scope() as s:
            yield MasterService(SQLAlchemyMasterRepository(s), ledger_repository=SQLAlchemyLedgerRepository(s))

    @asynccontextmanager
    async def ledger_service_scope(self) -> AsyncGenerator[LedgerService, None]:
        async with self.session_scope() as s:
            yield LedgerService(SQLAlchemyLedgerRepository(s))

    @asynccontextmanager
    async def fiscal_year_service_scope(self) -> AsyncGenerator[FiscalYearService, None]:
        async with self.session_scope() as s:
            master_repo = SQLAlchemyMasterRepository(s)
            ledger_repo = SQLAlchemyLedgerRepository(s)
            yield FiscalYearService(
                MasterService(master_repo, ledger_repository=ledger_repo),
                LedgerService(ledger_repo),
                JournalService(ledger_repo, master_repository=master_repo),
            )

    def get_ocr_service(self) -> GeminiOCRService:
        return GeminiOCRService()

    def get_file_service(self) -> LocalFileService:
        return LocalFileService()

    def get_pdf_service(self) -> PDFService:
        return PDFService()
    def get_backup_service(self) -> BackupService:
        return BackupService()


container = Container()
