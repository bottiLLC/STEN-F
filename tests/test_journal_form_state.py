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
from datetime import date
from unittest.mock import AsyncMock, patch
from app.ui.view_models.journal.form import JournalFormState
from app.domain.models.counterparty import Counterparty
from app.domain.models.fiscal_year import FiscalYear
import datetime


@pytest.mark.asyncio
async def test_form_state_reset_and_versioning():
    """Verify that _reset_form_state cleans all fields and increments form_version."""
    state = JournalFormState()
    state.description = "Test Description"
    state.counterparty = "Test CP"
    state.invoice_number = "T1234567890123"
    state.selected_abstract = "Selected Abstract"
    state.lines = [{"account_id": "1", "debit": 1000, "credit": 0}]
    initial_version = state.form_version
    initial_key = state.form_key

    state._reset_form_state()

    assert state.description == ""
    assert state.counterparty == ""
    assert state.invoice_number == ""
    assert state.selected_abstract == ""
    assert state.lines == [{"account_id": "", "debit": "", "credit": ""}]
    assert state.form_version == initial_version + 1
    assert state.form_key != initial_key


@pytest.mark.asyncio
async def test_select_abstract_and_set_description():
    """Verify select_abstract sets both selected_abstract and description, and manual edit resets selected_abstract."""
    state = JournalFormState()

    state.select_abstract("会議費（飲食）")
    assert state.selected_abstract == "会議費（飲食）"
    assert state.description == "会議費（飲食）"

    # Manual edit to different text resets selected_abstract
    state.set_description("手入力の摘要")
    assert state.description == "手入力の摘要"
    assert state.selected_abstract == ""


@pytest.mark.asyncio
async def test_set_counterparty_race_condition_protection(container):
    """Verify that if form is reset while set_counterparty is querying DB, stale result is dropped."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )

        # Save test counterparty
        cp = Counterparty(
            name="AsyncTest CP",
            invoice_number="T9876543210987",
            debit_account_id=1,
        )
        await master_service.save_counterparty(cp)

        state = JournalFormState()
        state.lines = [{"account_id": "", "debit": "", "credit": ""}]

        # Scenario: set_counterparty starts, but form is cleared before DB query returns
        orig_get_cps = master_service.get_counterparties

        async def delayed_get_counterparties():
            await asyncio.sleep(0.05)
            return await orig_get_cps()

        with patch("app.ui.di.DI.get_master_service") as mock_di:
            mock_ctx = AsyncMock()
            mock_service = AsyncMock()
            mock_service.get_counterparties = delayed_get_counterparties
            mock_ctx.__aenter__.return_value = mock_service
            mock_di.return_value = mock_ctx

            # Start set_counterparty task
            task = asyncio.create_task(state.set_counterparty("AsyncTest CP"))

            # Simultaneously reset the form (e.g. submit or clear_form happens)
            await asyncio.sleep(0.01)
            state._reset_form_state()

            # Wait for set_counterparty task to complete
            await task

            # Ensure stale invoice_number and account_id were NOT applied to the clean state
            assert state.invoice_number == ""
            assert state.lines == [{"account_id": "", "debit": "", "credit": ""}]


@pytest.mark.asyncio
async def test_submit_flow_clears_form_on_success(container):
    """Verify submit adds entry to DB and resets form state."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )
        journal_service = await stack.enter_async_context(
            container.journal_service_scope()
        )

        # Setup Fiscal Year
        today = date.today()
        fy = FiscalYear(
            name="Test FY 2026",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN",
        )
        await master_service.save_fiscal_year(fy)

        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]

        state = JournalFormState()
        state.transaction_date = today.isoformat()
        state.description = "Test Submission"
        state.counterparty = "Test Merchant"
        state.invoice_number = "T1111222233334"
        state.lines = [
            {"account_id": str(acc1.id), "debit": 5000, "credit": ""},
            {"account_id": str(acc2.id), "debit": "", "credit": 5000},
        ]

        # Mock OCR state and other sub-states
        from app.ui.view_models.journal.ocr import JournalOCRState
        from app.ui.view_models.journal.list import JournalListState

        mock_ocr = JournalOCRState()
        mock_list = JournalListState()

        async def mock_get_state(self_ref, state_cls):
            if state_cls == JournalOCRState:
                return mock_ocr
            if state_cls == JournalListState:
                return mock_list
            return self_ref

        with patch.object(JournalFormState, "get_state", mock_get_state):
            # Run submit generator
            events = []
            async for event in state.submit():
                events.append(event)

        # Verify entry in DB
        entries = await journal_service.get_entries(include_deleted=False)
        target = next((e for e in entries if e.description == "Test Submission"), None)
        assert target is not None
        assert target.counterparty == "Test Merchant"

        # Verify FormState is completely clean
        assert state.description == ""
        assert state.counterparty == ""
        assert state.invoice_number == ""
        assert state.selected_abstract == ""
        assert state.lines == [{"account_id": "", "debit": "", "credit": ""}]
        assert state.is_processing is False


@pytest.mark.asyncio
async def test_submit_unbalanced_toast():
    """Verify submit handles debit/credit mismatch by yielding a toast and aborting."""
    state = JournalFormState()
    state.transaction_date = date.today().isoformat()
    state.description = "Unbalanced"
    state.lines = [
        {"account_id": "1", "debit": 1000, "credit": ""},
        {"account_id": "2", "debit": "", "credit": 2000},
    ]

    from app.ui.view_models.journal.ocr import JournalOCRState

    mock_ocr = JournalOCRState()

    async def mock_get_state(self_ref, state_cls):
        if state_cls == JournalOCRState:
            return mock_ocr
        return self_ref

    with patch.object(JournalFormState, "get_state", mock_get_state):
        events = []
        async for event in state.submit():
            events.append(event)

    assert state.is_processing is False
    assert len(events) >= 1
    # Check that toast was yielded
    assert any("貸借不一致" in str(getattr(ev, "title", str(ev))) for ev in events)


@pytest.mark.asyncio
async def test_submit_empty_lines_toast():
    """Verify submit handles empty/zero lines by yielding a toast and aborting."""
    state = JournalFormState()
    state.lines = [{"account_id": "", "debit": "", "credit": ""}]

    from app.ui.view_models.journal.ocr import JournalOCRState

    mock_ocr = JournalOCRState()

    async def mock_get_state(self_ref, state_cls):
        if state_cls == JournalOCRState:
            return mock_ocr
        return self_ref

    with patch.object(JournalFormState, "get_state", mock_get_state):
        events = []
        async for event in state.submit():
            events.append(event)

    assert state.is_processing is False
    assert any(
        "有効な仕訳明細がありません" in str(getattr(ev, "title", str(ev)))
        for ev in events
    )


@pytest.mark.asyncio
async def test_submit_invalid_invoice_number_toast():
    """Verify submit validates invoice format and yields toast on invalid format."""
    state = JournalFormState()
    state.transaction_date = date.today().isoformat()
    state.description = "Bad Invoice"
    state.invoice_number = "INVALID_INV_123"
    state.lines = [
        {"account_id": "1", "debit": 1000, "credit": ""},
        {"account_id": "2", "debit": "", "credit": 1000},
    ]

    from app.ui.view_models.journal.ocr import JournalOCRState

    mock_ocr = JournalOCRState()

    async def mock_get_state(self_ref, state_cls):
        if state_cls == JournalOCRState:
            return mock_ocr
        return self_ref

    with patch.object(JournalFormState, "get_state", mock_get_state):
        events = []
        async for event in state.submit():
            events.append(event)

    assert state.is_processing is False
    assert any(
        "登録番号は「T + 13桁の半角数字」" in str(getattr(ev, "title", str(ev)))
        for ev in events
    )


@pytest.mark.asyncio
async def test_submit_continuous_entry_retains_form(container):
    """Verify continuous_entry=True retains input values in form upon submission."""
    from contextlib import AsyncExitStack

    async with AsyncExitStack() as stack:
        master_service = await stack.enter_async_context(
            container.master_service_scope()
        )

        today = date.today()
        fy = FiscalYear(
            name="Continuous FY",
            start_date=today - datetime.timedelta(days=30),
            end_date=today + datetime.timedelta(days=330),
            status="OPEN",
        )
        await master_service.save_fiscal_year(fy)

        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]

        state = JournalFormState()
        state.transaction_date = today.isoformat()
        state.description = "Continuous Test"
        state.counterparty = "Continuous Merchant"
        state.continuous_entry = True
        state.lines = [
            {"account_id": str(acc1.id), "debit": 3000, "credit": ""},
            {"account_id": str(acc2.id), "debit": "", "credit": 3000},
        ]

        from app.ui.view_models.journal.ocr import JournalOCRState
        from app.ui.view_models.journal.list import JournalListState

        mock_ocr = JournalOCRState()
        mock_list = JournalListState()

        async def mock_get_state(self_ref, state_cls):
            if state_cls == JournalOCRState:
                return mock_ocr
            if state_cls == JournalListState:
                return mock_list
            return self_ref

        with patch.object(JournalFormState, "get_state", mock_get_state):
            async for _ in state.submit():
                pass

        # Values should be retained
        assert state.description == "Continuous Test"
        assert state.counterparty == "Continuous Merchant"
        assert len(state.lines) == 2
        assert state.is_processing is False


@pytest.mark.asyncio
async def test_line_operations_and_amount_normalization():
    """Verify add_line, remove_line, update_line, and update_line_account."""
    state = JournalFormState()
    assert len(state.lines) == 1

    # Add lines
    state.add_line()
    state.add_line()
    assert len(state.lines) == 3

    # Remove line
    state.remove_line(1)
    assert len(state.lines) == 2

    # Cannot remove last line
    state.remove_line(0)
    state.remove_line(0)
    assert len(state.lines) == 1

    # Update line account
    state.update_line_account(0, "42")
    assert state.lines[0]["account_id"] == "42"

    # Update line amounts with normalization
    state.update_line(0, "debit", "１,５００")  # Full-width + comma
    assert state.lines[0]["debit"] == 1500

    state.update_line(0, "credit", "")  # Empty string remains empty string
    assert state.lines[0]["credit"] == ""

    state.update_line(0, "credit", None)
    assert state.lines[0]["credit"] == ""


@pytest.mark.asyncio
async def test_is_processing_guards():
    """Verify that mutation methods are locked when is_processing is True."""
    state = JournalFormState()
    state.is_processing = True

    # None of these should mutate state
    state.set_transaction_date("2099-01-01")
    assert state.transaction_date != "2099-01-01"

    state.set_description("Ignored")
    assert state.description == ""

    state.set_invoice_number("T1111111111111")
    assert state.invoice_number == ""

    state.add_line()
    assert len(state.lines) == 1

    state.update_line_account(0, "999")
    assert state.lines[0]["account_id"] == ""

    state.update_line(0, "debit", 500)
    assert state.lines[0]["debit"] == ""


@pytest.mark.asyncio
async def test_abstract_suggestions_filtering():
    """Verify abstract_suggestions filters correctly by selected account IDs."""
    from app.domain.models.abstract import Abstract

    state = JournalFormState()
    state.abstracts = [
        Abstract(account_id=1, text="現金売上"),
        Abstract(account_id=2, text="仕入高（掛け）"),
        Abstract(account_id=1, text="普通預金預入"),
    ]

    # No lines selected -> all unique abstracts
    state.lines = [{"account_id": "", "debit": "", "credit": ""}]
    suggestions = state.abstract_suggestions
    assert set(suggestions) == {"現金売上", "仕入高（掛け）", "普通預金預入"}

    # Account 1 selected -> only account 1 suggestions
    state.lines = [{"account_id": "1", "debit": "", "credit": ""}]
    suggestions = state.abstract_suggestions
    assert set(suggestions) == {"現金売上", "普通預金預入"}


@pytest.mark.asyncio
async def test_clear_form_manual():
    """Verify clear_form safely resets state and yields OCR cleanup."""
    state = JournalFormState()
    state.description = "Dirty"
    state.counterparty = "Dirty Merchant"
    state.invoice_number = "T1234567890123"
    state.lines = [{"account_id": "1", "debit": 100, "credit": ""}]

    from app.ui.view_models.journal.ocr import JournalOCRState

    mock_ocr = JournalOCRState()

    async def mock_get_state(self_ref, state_cls):
        if state_cls == JournalOCRState:
            return mock_ocr
        return self_ref

    with patch.object(JournalFormState, "get_state", mock_get_state):
        events = []
        async for ev in state.clear_form():
            events.append(ev)

    assert state.description == ""
    assert state.counterparty == ""
    assert state.invoice_number == ""
    assert state.lines == [{"account_id": "", "debit": "", "credit": ""}]
    assert state.is_processing is False
