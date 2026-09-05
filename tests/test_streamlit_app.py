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

import pytest
import asyncio
from app.ui.async_helper import run_async
from app.ui.di import DI


def test_run_async_helper():
    """Verify that run_async executes async coroutine synchronously."""

    async def sample_coroutine():
        await asyncio.sleep(0.01)
        return "async_success"

    result = run_async(sample_coroutine())
    assert result == "async_success"


@pytest.mark.asyncio
async def test_di_container_resolution(container):
    """Verify DI static methods return valid service instances."""
    assert DI.get_journal_service() is not None
    assert DI.get_master_service() is not None
    assert DI.get_ledger_service() is not None
    assert DI.get_fiscal_year_service() is not None
    assert DI.get_ocr_service() is not None
    assert DI.get_file_service() is not None
    assert DI.get_backup_service() is not None
    assert DI.get_pdf_service() is not None


def test_page_files_syntax():
    """Verify all Streamlit page scripts can be compiled and parsed without syntax errors."""
    import py_compile
    from pathlib import Path

    pages_dir = Path("app/ui/app_pages")
    page_files = list(pages_dir.glob("*.py"))
    assert len(page_files) == 7

    expected_filenames = {
        "1_journal_entry.py",
        "2_journal_history.py",
        "3_general_ledger.py",
        "4_trial_balance.py",
        "5_financial_statements.py",
        "6_opening_balance.py",
        "7_master_management.py",
    }
    actual_filenames = {pf.name for pf in page_files}
    assert actual_filenames == expected_filenames

    for pf in page_files:
        py_compile.compile(str(pf), doraise=True)

    # Also check app.py and styles.py
    py_compile.compile("app.py", doraise=True)
    py_compile.compile("app/ui/styles.py", doraise=True)
