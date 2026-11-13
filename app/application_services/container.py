# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.application_services.fiscal_year_service import FiscalYearService
from app.application_services.journal_service import JournalService
from app.application_services.ledger_service import LedgerService
from app.application_services.master_service import MasterService
from app.storage_repository import (
    AsyncSessionLocal,
    SQLAlchemyLedgerRepository,
    SQLAlchemyMasterRepository,
)

if TYPE_CHECKING:
    from app.ai_ocr_service import GeminiOCRService
    from app.external_services import LocalFileService, PDFService


class Container:
    """Dependency injection container managing session-scoped service lifetimes."""

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        """Provide managed async session scope.

        Yields:
            Session bounded to unit-of-work lifecycle.
        """
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
        """Yield JournalService bound to dedicated session scope.

        Yields:
            Scoped JournalService instance.
        """
        async with self.session_scope() as s:
            yield JournalService(
                SQLAlchemyLedgerRepository(s),
                master_repository=SQLAlchemyMasterRepository(s),
            )

    @asynccontextmanager
    async def master_service_scope(self) -> AsyncGenerator[MasterService, None]:
        """Yield MasterService bound to dedicated session scope.

        Yields:
            Scoped MasterService instance.
        """
        async with self.session_scope() as s:
            yield MasterService(
                SQLAlchemyMasterRepository(s),
                ledger_repository=SQLAlchemyLedgerRepository(s),
            )

    @asynccontextmanager
    async def ledger_service_scope(self) -> AsyncGenerator[LedgerService, None]:
        """Yield LedgerService bound to dedicated session scope.

        Yields:
            Scoped LedgerService instance.
        """
        async with self.session_scope() as s:
            yield LedgerService(SQLAlchemyLedgerRepository(s))

    @asynccontextmanager
    async def fiscal_year_service_scope(
        self,
    ) -> AsyncGenerator[FiscalYearService, None]:
        """Yield FiscalYearService bound to dedicated session scope.

        Yields:
            Scoped FiscalYearService instance.
        """
        async with self.session_scope() as s:
            master_repo = SQLAlchemyMasterRepository(s)
            ledger_repo = SQLAlchemyLedgerRepository(s)
            ms = MasterService(master_repo, ledger_repository=ledger_repo)
            ls = LedgerService(ledger_repo)
            js = JournalService(ledger_repo, master_repository=master_repo)
            yield FiscalYearService(ms, ls, js)

    def get_ocr_service(self) -> GeminiOCRService:
        """Instantiate OCR external service.

        Returns:
            GeminiOCRService instance.
        """
        from app.ai_ocr_service import GeminiOCRService

        return GeminiOCRService()

    def get_file_service(self) -> LocalFileService:
        """Instantiate local file storage service.

        Returns:
            LocalFileService instance.
        """
        from app.external_services import LocalFileService

        return LocalFileService()

    def get_pdf_service(self) -> PDFService:
        """Instantiate PDF report generation service.

        Returns:
            PDFService instance.
        """
        from app.external_services import PDFService

        return PDFService()


container: Final[Container] = Container()
