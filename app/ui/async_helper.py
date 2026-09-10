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

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, TypeVar
import asyncio
import sniffio
from app.ui.di import DI

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    """Safely runs an async coroutine within Streamlit's environment.

    nest_asyncio must be applied prior to calling this function.
    """
    # Ensure sniffio detects asyncio context under Python 3.14+ nest_asyncio
    try:
        sniffio.current_async_library_cvar.set("asyncio")
    except Exception:
        pass

    return asyncio.run(coro)


def run_scoped(scope_ctx: Any, coro_fn: Callable[[Any], Awaitable[T]]) -> T:
    """Executes a coroutine cleanly inside an async context manager."""
    async def _runner() -> T:
        async with scope_ctx as s:
            return await coro_fn(s)

    return run_async(_runner())


def call_master(fn: Callable[[Any], Awaitable[T]]) -> T:
    return run_scoped(DI.get_master_service(), fn)


def call_journal(fn: Callable[[Any], Awaitable[T]]) -> T:
    return run_scoped(DI.get_journal_service(), fn)


def call_ledger(fn: Callable[[Any], Awaitable[T]]) -> T:
    return run_scoped(DI.get_ledger_service(), fn)


def call_fiscal_year(fn: Callable[[Any], Awaitable[T]]) -> T:
    return run_scoped(DI.get_fiscal_year_service(), fn)


def call_backup(fn: Callable[[Any], Awaitable[T]]) -> T:
    return run_scoped(DI.get_backup_service(), fn)



