# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from decimal import Decimal, ROUND_HALF_UP
import functools
import logging
from pathlib import Path
import sys
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final, ParamSpec, TypeVar

from pydantic_settings import BaseSettings, SettingsConfigDict
import sniffio
import structlog
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager
    from app.ai_ocr_service import GeminiOCRService
    from app.application_services import (
        FiscalYearService,
        JournalService,
        LedgerService,
        MasterService,
    )
    from app.external_services import LocalFileService, PDFService

P = ParamSpec("P")
T = TypeVar("T")
S = TypeVar("S")

# --- 1. Datum Plane (Configuration & Constants) ---
_TRANS_DICT: Final[dict[str, str | None]] = {
    "０": "0",
    "１": "1",
    "２": "2",
    "３": "3",
    "４": "4",
    "５": "5",
    "６": "6",
    "７": "7",
    "８": "8",
    "９": "9",
    "，": "",
    ",": "",
    "　": "",
    " ": "",
}
_TRANS_MAP: Final[MappingProxyType[int, str | None]] = MappingProxyType(
    str.maketrans(_TRANS_DICT)
)


class Settings(BaseSettings):
    """Immutable application settings anchored to filesystem location."""

    APP_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    STORAGE_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "storage"
    BACKUP_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "backups"

    DB_NAME: str = "sten_f.db"
    DATABASE_URL: str | None = None

    GEMINI_API_KEY: str | None = None
    GEMINI_DEFAULT_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: str | None = None
    OPENAI_DEFAULT_MODEL: str = "gpt-5.6-terra"
    OPENAI_REASONING_EFFORT: str = "high"

    APP_TITLE: str = "STEN-F"
    CURRENCY_SYMBOL: str = "¥"

    WINDOWS_FONT_PATH: Path = Path("C:/Windows/Fonts/msgothic.ttc")
    FONT_PATH: Path | None = None
    FONT_NAME: str = "HeiseiMin-W3"

    model_config = SettingsConfigDict(
        env_file=(".env", "data/.env"),
        env_file_encoding="utf-8",
        extra="forbid",
        case_sensitive=True,
    )

    def model_post_init(self, __context: object) -> None:
        """Resolve dynamic database URLs, ensure data directories, and system fonts upon initialization.

        Args:
            __context: Initialization context provided by Pydantic.
        """
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        if not self.DATABASE_URL or "bookkeeping.db" in self.DATABASE_URL:
            db_path = self.DATA_DIR / self.DB_NAME
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

        if self.WINDOWS_FONT_PATH.exists():
            self.FONT_PATH = self.WINDOWS_FONT_PATH
            self.FONT_NAME = "MSGothic"
        else:
            self.FONT_PATH = None
            self.FONT_NAME = "HeiseiMin-W3"


settings: Final[Settings] = Settings()


# --- 2. Internal Pure Transformations ---
def normalize_amount(value: object) -> int:
    """Normalize and round monetary values to integer safely.

    Args:
        value: Input monetary representation (int, float, or string).

    Returns:
        Cleaned integer amount, rounded half up, or 0 on conversion failure.
    """
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    val_str = str(value).strip().translate(_TRANS_MAP)
    if not val_str:
        return 0
    try:
        return int(Decimal(val_str).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0


def configure_logging() -> None:
    """Configure structured JSON logging for runtime observability."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger: Final[structlog.stdlib.BoundLogger] = structlog.get_logger()
log: Final[structlog.stdlib.BoundLogger] = logger


# --- 3. Public Orchestration Layer ---
def resilient_api_call(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorate async callable with exponential backoff retry clamping.

    Args:
        max_retries: Maximum number of execution attempts.
        base_delay: Initial exponential delay factor in seconds.
        exceptions: Tuple of catchable exception types eligible for retry.

    Returns:
        Decorated async function wrapper.
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            def before_sleep(retry_state: tenacity.RetryCallState) -> None:
                log.warning(
                    "api_call_retry",
                    function=func.__name__,
                    attempt=retry_state.attempt_number,
                    max_retries=max_retries,
                    error=str(
                        retry_state.outcome.exception()
                        if retry_state.outcome
                        else "unknown"
                    ),
                    delay=retry_state.next_action.sleep
                    if retry_state.next_action
                    else 0,
                )

            async for attempt in tenacity.AsyncRetrying(
                wait=wait_exponential(multiplier=base_delay, min=2, max=10),
                stop=stop_after_attempt(max_retries),
                reraise=True,
                retry=retry_if_exception_type(exceptions),
                before_sleep=before_sleep,
            ):
                with attempt:
                    return await func(*args, **kwargs)
            raise RuntimeError("Retry loop exhausted unexpectedly")

        return wrapper

    return decorator


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Execute async coroutine within synchronous Streamlit context.

    Args:
        coro: Asynchronous coroutine instance to execute.

    Returns:
        Awaited result of type T.
    """
    try:
        sniffio.current_async_library_cvar.set("asyncio")
    except Exception:
        pass

    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop is not None and running_loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    try:
        loop = asyncio.get_event_loop()
        if not loop.is_closed():
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass

    return asyncio.run(coro)


def run_scoped(
    scope_ctx: AbstractAsyncContextManager[S],
    coro_fn: Callable[[S], Awaitable[T]],
) -> T:
    """Execute coroutine safely bounded by async context manager.

    Args:
        scope_ctx: Asynchronous context manager managing scope lifecycle.
        coro_fn: Callable accepting scope instance and returning awaitable.

    Returns:
        Result produced by coro_fn.
    """

    async def _runner() -> T:
        async with scope_ctx as s:
            return await coro_fn(s)

    return run_async(_runner())


class DI:
    """Service resolver facade delegating to application container."""

    @staticmethod
    def get_journal_service() -> AbstractAsyncContextManager[JournalService]:
        """Resolve journal service scope context.

        Returns:
            Async context manager yielding JournalService.
        """
        from app.application_services import container

        return container.journal_service_scope()

    @staticmethod
    def get_master_service() -> AbstractAsyncContextManager[MasterService]:
        """Resolve master service scope context.

        Returns:
            Async context manager yielding MasterService.
        """
        from app.application_services import container

        return container.master_service_scope()

    @staticmethod
    def get_ledger_service() -> AbstractAsyncContextManager[LedgerService]:
        """Resolve ledger service scope context.

        Returns:
            Async context manager yielding LedgerService.
        """
        from app.application_services import container

        return container.ledger_service_scope()

    @staticmethod
    def get_fiscal_year_service() -> AbstractAsyncContextManager[FiscalYearService]:
        """Resolve fiscal year service scope context.

        Returns:
            Async context manager yielding FiscalYearService.
        """
        from app.application_services import container

        return container.fiscal_year_service_scope()

    @staticmethod
    def get_ocr_service() -> GeminiOCRService:
        """Resolve OCR service instance.

        Returns:
            GeminiOCRService singleton or transient instance.
        """
        from app.application_services import container

        return container.get_ocr_service()

    @staticmethod
    def get_file_service() -> LocalFileService:
        """Resolve local file service instance.

        Returns:
            LocalFileService instance.
        """
        from app.application_services import container

        return container.get_file_service()

    @staticmethod
    def get_pdf_service() -> PDFService:
        """Resolve PDF service instance.

        Returns:
            PDFService instance.
        """
        from app.application_services import container

        return container.get_pdf_service()


def call_master(fn: Callable[[MasterService], Awaitable[T]]) -> T:
    """Execute MasterService coroutine within scoped session.

    Args:
        fn: Async callable taking MasterService.

    Returns:
        Result produced by fn.
    """
    return run_scoped(DI.get_master_service(), fn)


def call_journal(fn: Callable[[JournalService], Awaitable[T]]) -> T:
    """Execute JournalService coroutine within scoped session.

    Args:
        fn: Async callable taking JournalService.

    Returns:
        Result produced by fn.
    """
    return run_scoped(DI.get_journal_service(), fn)


def call_ledger(fn: Callable[[LedgerService], Awaitable[T]]) -> T:
    """Execute LedgerService coroutine within scoped session.

    Args:
        fn: Async callable taking LedgerService.

    Returns:
        Result produced by fn.
    """
    return run_scoped(DI.get_ledger_service(), fn)


def call_fiscal_year(fn: Callable[[FiscalYearService], Awaitable[T]]) -> T:
    """Execute FiscalYearService coroutine within scoped session.

    Args:
        fn: Async callable taking FiscalYearService.

    Returns:
        Result produced by fn.
    """
    return run_scoped(DI.get_fiscal_year_service(), fn)
