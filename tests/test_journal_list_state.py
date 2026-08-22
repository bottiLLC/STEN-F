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
import os
import tempfile
from datetime import date
from app.ui.view_models.journal.list import JournalListState
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.fiscal_year import FiscalYear
import datetime
import app.ui.view_models.journal.list as list_module


@pytest.mark.asyncio
async def test_journal_list_load_and_filter(container):
    """Test load_entries with date filters and show_deleted toggle."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )
        journal_service = await stack.enter_async_context(
            container.journal_service_scope()
        )

        today = date.today()
        fy = FiscalYear(
            name="List Test FY",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN",
        )
        await master_service.save_fiscal_year(fy)

        accounts = await master_service.get_accounts()

        # Add transaction
        tx = Transaction(
            date=today,
            description="List Test TX",
            lines=[
                TransactionLine(account_id=accounts[0].id, debit=1000, credit=0),
                TransactionLine(account_id=accounts[1].id, debit=0, credit=1000),
            ],
        )
        tx_id = await journal_service.add_journal_entry(tx)

        state = JournalListState()
        await state.load_entries()
        assert any(e.id == tx_id for e in state.journal_entries)

        # Filter by date range that excludes today
        state.set_filter_start_date("2020-01-01")
        state.set_filter_end_date("2020-12-31")
        await state.load_entries()
        assert not any(e.id == tx_id for e in state.journal_entries)

        # Toggle show_deleted
        assert state.show_deleted is False
        await state.toggle_show_deleted()
        assert state.show_deleted is True


@pytest.mark.asyncio
async def test_journal_list_delete_entry(container):
    """Test deleting an entry via JournalListState."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )
        journal_service = await stack.enter_async_context(
            container.journal_service_scope()
        )

        today = date.today()
        fy = FiscalYear(
            name="List Delete FY",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN",
        )
        await master_service.save_fiscal_year(fy)

        accounts = await master_service.get_accounts()

        tx = Transaction(
            date=today,
            description="To be deleted",
            lines=[
                TransactionLine(account_id=accounts[0].id, debit=500, credit=0),
                TransactionLine(account_id=accounts[1].id, debit=0, credit=500),
            ],
        )
        tx_id = await journal_service.add_journal_entry(tx)

        state = JournalListState()
        await state.load_entries()
        assert any(e.id == tx_id for e in state.journal_entries)

        # Delete entry
        result = await state.delete_entry(tx_id)
        assert result is not None

        # Verify not in active entries
        await state.load_entries()
        assert not any(e.id == tx_id for e in state.journal_entries)


@pytest.mark.asyncio
async def test_journal_list_export_csv(container):
    """Test export_csv returns download action with CSV data."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )
        journal_service = await stack.enter_async_context(
            container.journal_service_scope()
        )

        today = date.today()
        fy = FiscalYear(
            name="CSV Export FY",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN",
        )
        await master_service.save_fiscal_year(fy)

        accounts = await master_service.get_accounts()

        tx = Transaction(
            date=today,
            description="CSV Export TX",
            lines=[
                TransactionLine(account_id=accounts[0].id, debit=2000, credit=0),
                TransactionLine(account_id=accounts[1].id, debit=0, credit=2000),
            ],
        )
        await journal_service.add_journal_entry(tx)

        state = JournalListState()
        action = await state.export_csv()
        assert action is not None


@pytest.mark.asyncio
async def test_journal_list_download_evidence(container):
    """Test download_evidence handles missing evidence, missing file, and existing file."""
    state = JournalListState()

    # Entry does not exist
    res = await state.download_evidence(999999)
    assert res is not None

    # Entry exists with temp evidence file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        f.write(b"%PDF-1.4 test content")
        temp_path = f.name

    try:
        tx = Transaction(
            id=10101,
            date=date.today(),
            description="Evidence TX",
            lines=[],
            evidence_path=temp_path,
        )
        state.journal_entries = [tx]

        # Valid file download
        res_valid = await state.download_evidence(10101)
        assert res_valid is not None

        # File does not exist on disk
        tx_ghost = Transaction(
            id=10102,
            date=date.today(),
            description="Ghost Evidence",
            lines=[],
            evidence_path="C:/non_existent_path_12345.pdf",
        )
        state.journal_entries = [tx_ghost]
        res_ghost = await state.download_evidence(10102)
        assert res_ghost is not None
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@pytest.mark.asyncio
async def test_journal_list_check_for_updates():
    """Test check_for_updates detects newer global timestamps and reloads entries."""
    state = JournalListState()
    state._local_last_update = 100.0

    # Newer timestamp
    list_module.GLOBAL_JOURNAL_UPDATE_TIME = 200.0
    await state.check_for_updates()
    assert state._local_last_update == 200.0
