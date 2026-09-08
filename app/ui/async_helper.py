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

import asyncio
from typing import TypeVar, Coroutine, Any
import sniffio

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
