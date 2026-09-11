# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from decimal import Decimal, ROUND_HALF_UP
import functools
import logging
from pathlib import Path
import sys
from typing import Any, Optional, TypeVar
import nest_asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
import sniffio
import structlog
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

T = TypeVar("T")
nest_asyncio.apply()

# --- 1. Datum Plane (Configuration & Constants) ---
_TRANS_MAP = str.maketrans(
    {
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
)


class Settings(BaseSettings):
    """Immutable application settings anchored to filesystem location."""

    APP_DIR: Path = Path(__file__).resolve().parent
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

    DB_NAME: str = "sten_f.db"
    DATABASE_URL: Optional[str] = None

    GEMINI_API_KEY: Optional[str] = None
    GEMINI_DEFAULT_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_DEFAULT_MODEL: str = "gpt-5.6-terra"
    OPENAI_REASONING_EFFORT: str = "high"

    APP_TITLE: str = "STEN-F"
    CURRENCY_SYMBOL: str = "¥"

    WINDOWS_FONT_PATH: Path = Path("C:/Windows/Fonts/msgothic.ttc")
    FONT_PATH: Optional[Path] = None
    FONT_NAME: str = "HeiseiMin-W3"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="forbid", case_sensitive=True
    )

    def model_post_init(self, __context: Any) -> None:
        """Resolve dynamic database URLs and system fonts upon initialization."""
        if not self.DATABASE_URL:
            db_path = self.PROJECT_ROOT / "data" / self.DB_NAME
            self.DATABASE_URL = f"sqlite+aiosqlite:///{db_path}"

        if self.WINDOWS_FONT_PATH.exists():
            self.FONT_PATH = self.WINDOWS_FONT_PATH
            self.FONT_NAME = "MSGothic"
        else:
            self.FONT_PATH = None
            self.FONT_NAME = "HeiseiMin-W3"


settings = Settings()


# --- 2. Internal Pure Transformations ---
def normalize_amount(value: Any) -> int:
    """Normalize and round monetary values to integer safely."""
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


logger = structlog.get_logger()
log = logger


# --- 3. Public Orchestration Layer ---
def resilient_api_call(
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorate async callable with exponential backoff retry clamping."""

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
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
    """Execute async coroutine within synchronous Streamlit context."""
    try:
        sniffio.current_async_library_cvar.set("asyncio")
    except Exception:
        pass
    return asyncio.run(coro)


def run_scoped(scope_ctx: Any, coro_fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute coroutine safely bounded by async context manager."""

    async def _runner() -> T:
        async with scope_ctx as s:
            return await coro_fn(s)

    return run_async(_runner())


class DI:
    """Service resolver facade delegating to application container."""

    @staticmethod
    def get_journal_service() -> Any:
        """Resolve journal service scope context."""
        from app.application_services import container

        return container.journal_service_scope()

    @staticmethod
    def get_master_service() -> Any:
        """Resolve master service scope context."""
        from app.application_services import container

        return container.master_service_scope()

    @staticmethod
    def get_ledger_service() -> Any:
        """Resolve ledger service scope context."""
        from app.application_services import container

        return container.ledger_service_scope()

    @staticmethod
    def get_fiscal_year_service() -> Any:
        """Resolve fiscal year service scope context."""
        from app.application_services import container

        return container.fiscal_year_service_scope()

    @staticmethod
    def get_ocr_service() -> Any:
        """Resolve OCR service instance."""
        from app.application_services import container

        return container.get_ocr_service()

    @staticmethod
    def get_file_service() -> Any:
        """Resolve local file service instance."""
        from app.application_services import container

        return container.get_file_service()

    @staticmethod
    def get_backup_service() -> Any:
        """Resolve backup service instance."""
        from app.application_services import container

        return container.get_backup_service()

    @staticmethod
    def get_pdf_service() -> Any:
        """Resolve PDF service instance."""
        from app.application_services import container

        return container.get_pdf_service()


def call_master(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute MasterService coroutine within scoped session."""
    return run_scoped(DI.get_master_service(), fn)


def call_journal(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute JournalService coroutine within scoped session."""
    return run_scoped(DI.get_journal_service(), fn)


def call_ledger(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute LedgerService coroutine within scoped session."""
    return run_scoped(DI.get_ledger_service(), fn)


def call_fiscal_year(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute FiscalYearService coroutine within scoped session."""
    return run_scoped(DI.get_fiscal_year_service(), fn)


def call_backup(fn: Callable[[Any], Awaitable[T]]) -> T:
    """Execute BackupService coroutine within scoped session."""
    return run_scoped(DI.get_backup_service(), fn)


# --- 4. Self-Contained Smoke Harness ---
if __name__ == "__main__":
    assert normalize_amount(" １，２３４円 ") == 0
    assert normalize_amount(" １，２３４ ") == 1234
    assert normalize_amount(500.6) == 501
    assert settings.APP_TITLE == "STEN-F"
    assert settings.APP_DIR.exists()
    assert settings.PROJECT_ROOT.exists()
    configure_logging()
    log.info("smoke_harness_pass", module="core_foundation")
