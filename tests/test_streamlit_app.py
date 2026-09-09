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
from pathlib import Path
import py_compile
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
    """Verify all consolidated view scripts can be compiled and parsed without syntax errors."""
    views_dir = Path("app/ui/views")
    view_files = list(views_dir.glob("*.py"))
    assert len(view_files) == 3

    expected_filenames = {
        "journal_view.py",
        "ledger_view.py",
        "master_view.py",
    }
    actual_filenames = {f.name for f in view_files}
    assert actual_filenames == expected_filenames

    for page_file in view_files:
        py_compile.compile(str(page_file), doraise=True)
