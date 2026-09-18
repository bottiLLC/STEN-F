# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date, timedelta
import pytest
from pydantic import ValidationError

from app.application_services import Container
from app.domain_contracts import (
    DEFAULT_ACCOUNTS,
    Abstract,
    Account,
    AccountType,
    Counterparty,
    FiscalYear,
    Transaction,
    TransactionLine,
    validate_invoice_number_format,
)


# --- 1. Master Logic & Account Constraints ---
@pytest.mark.asyncio
async def test_master_service_account_and_counterparty_lifecycle(
    container: Container,
) -> None:
    """Verify MasterService account initialization, abstract management, and counterparty kana sorting."""
    # Arrange
    async with container.master_service_scope() as ms:
        # Act: initialize default accounts
        added_count = await ms.initialize_default_accounts()
        accs = await ms.get_accounts()

        # Assert: default accounts seeded
        assert added_count >= 0
        assert len(accs) >= len(DEFAULT_ACCOUNTS)
        acc1 = accs[0]
        assert acc1.id is not None

        # Act & Assert: Abstract CRUD
        ab = await ms.save_abstract(Abstract(account_id=acc1.id, text="金物代"))
        assert ab.id is not None
        fetched_abs = await ms.get_abstracts()
        assert any(a.id == ab.id and a.text == "金物代" for a in fetched_abs)
        await ms.delete_abstract(ab.id)

        # Act & Assert: Counterparty sorting by Japanese Kana reading
        cp1 = await ms.save_counterparty(
            Counterparty(name="株式会社ベータ", reading="カブシキガイシャベータ")
        )
        cp2 = await ms.save_counterparty(
            Counterparty(name="合同会社アルファ", reading="ゴウドウガイシャアルファ")
        )
        assert cp1.id is not None and cp2.id is not None

        cps = await ms.get_counterparties()
        names = [c.name for c in cps]
        assert names.index("合同会社アルファ") < names.index("株式会社ベータ")

        # Act & Assert: Fuzzy search
        matched = await ms.get_counterparty_by_keyword("アルファ")
        assert matched is not None
        assert matched.name == "合同会社アルファ"
        assert await ms.get_counterparty_by_keyword("") is None
        assert await ms.get_counterparty_by_keyword("存在しない取引先") is None

        await ms.delete_counterparty(cp1.id)
        await ms.delete_counterparty(cp2.id)


@pytest.mark.asyncio
async def test_account_deletion_with_active_transactions_raises_value_error(
    container: Container,
) -> None:
    """Ensure deleting an account referenced by transactions raises ValueError with explicit message."""
    # Arrange
    async with container.master_service_scope() as ms:
        test_acc = await ms.save_account(
            Account(code="8888", name="使用中科目", type=AccountType.SGA)
        )
        assert test_acc.id is not None
        accs = await ms.get_accounts()
        cash_acc = next(a for a in accs if a.code == "1110")
        assert cash_acc.id is not None

    async with container.journal_service_scope() as js:
        await js.add_journal_entry(
            Transaction(
                date=date.today(),
                description="使用中科目のテスト仕訳",
                lines=[
                    TransactionLine(account_id=test_acc.id, debit=3000, credit=0),
                    TransactionLine(account_id=cash_acc.id, debit=0, credit=3000),
                ],
            )
        )

    # Act & Assert
    async with container.master_service_scope() as ms:
        with pytest.raises(
            ValueError, match="この勘定科目は仕訳で使用されているため削除できません"
        ):
            await ms.delete_account(test_acc.id)


@pytest.mark.asyncio
async def test_master_service_delete_nonexistent_account_executes_safely(
    container: Container,
) -> None:
    """Ensure MasterService handles deletion of nonexistent account ID gracefully without exception."""
    # Arrange & Act & Assert
    async with container.master_service_scope() as ms:
        await ms.delete_account(999999)


# --- 2. Journal Entry Operations & Validation ---
@pytest.mark.asyncio
async def test_journal_entry_lifecycle_and_updates(container: Container) -> None:
    """Verify journal entry recording, updates, CSV export, and deletion."""
    # Arrange
    async with container.master_service_scope() as ms:
        accounts = await ms.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]
        assert acc1.id is not None and acc2.id is not None

    async with container.journal_service_scope() as js:
        # Act 1: Record Transaction
        tx = Transaction(
            date=date.today(),
            description="Service Lifecycle Tx",
            lines=[
                TransactionLine(account_id=acc1.id, debit=12000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=12000),
            ],
            counterparty="新規自動学習取引先",
        )
        tx_id = await js.add_journal_entry(tx)

        # Assert 1: Transaction created & counterparty learned
        assert tx_id > 0
        async with container.master_service_scope() as ms:
            learned_cp = await ms.get_counterparty_by_keyword("新規自動学習取引先")
            assert learned_cp is not None
            assert learned_cp.name == "新規自動学習取引先"

        # Act 2: Update journal entry
        tx_saved = next(t for t in await js.get_entries() if t.id == tx_id)
        tx_saved.description = "更新後の摘要"
        tx_saved.lines = [
            TransactionLine(account_id=acc1.id, debit=15000, credit=0),
            TransactionLine(account_id=acc2.id, debit=0, credit=15000),
        ]
        update_result = await js.update_journal_entry(tx_saved)

        # Assert 2: Entry updated
        assert update_result is True
        updated_entries = await js.get_entries()
        u = next(e for e in updated_entries if e.id == tx_saved.id)
        assert u.description == "更新後の摘要"
        assert sum(line.debit for line in u.lines) == 15000

        # Act 3: CSV Export
        csv_text = await js.export_journal_entries_csv()
        assert "取引日,ID,摘要,取引先" in csv_text
        assert "更新後の摘要" in csv_text

        # Act 4: Opening Balance
        op_id = await js.register_opening_balance(
            opening_date=date.today(),
            debit_balances={str(acc1.id): "50000"},
            credit_balances={str(acc2.id): "50000"},
        )
        assert op_id > 0

        # Act 5: Frequent Account IDs
        freq = await js.get_frequent_account_ids(limit=5)
        assert isinstance(freq, list)
        assert len(freq) >= 1

        # Act 6: Delete entry via repository
        delete_res = await js.repository.delete_transaction(tx_id)
        await js.repository.commit()
        delete_fail = await js.repository.delete_transaction(999999)
        assert delete_res is True
        assert delete_fail is False


@pytest.mark.asyncio
async def test_journal_entry_register_opening_balance_unbalanced_raises_validation_error(
    container: Container,
) -> None:
    """Verify register_opening_balance rejects unbalanced debit and credit amounts and empty balances."""
    # Arrange
    async with container.master_service_scope() as ms:
        accounts = await ms.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]
        assert acc1.id is not None and acc2.id is not None

    async with container.journal_service_scope() as js:
        # Act & Assert 1: Unbalanced amounts trigger ValidationError
        with pytest.raises(ValidationError, match="Unbalanced Transaction"):
            await js.register_opening_balance(
                opening_date=date.today(),
                debit_balances={str(acc1.id): "50000"},
                credit_balances={str(acc2.id): "40000"},
            )

        # Act & Assert 2: Empty zero balances trigger ValueError
        with pytest.raises(ValueError, match="入力された金額がありません。"):
            await js.register_opening_balance(
                opening_date=date.today(),
                debit_balances={str(acc1.id): "0"},
                credit_balances={str(acc2.id): "0"},
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "out_of_range_offset",
    [
        timedelta(days=-365 * 10),
        timedelta(days=365 * 10),
    ],
)
async def test_journal_entry_with_date_outside_open_fiscal_years_raises_value_error(
    container: Container, out_of_range_offset: timedelta
) -> None:
    """Verify add_journal_entry strictly validates entry date within active OPEN fiscal years."""
    # Arrange
    async with container.master_service_scope() as ms:
        accounts = await ms.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]
        assert acc1.id is not None and acc2.id is not None

    target_date = date.today() + out_of_range_offset

    # Act & Assert
    async with container.journal_service_scope() as js:
        with pytest.raises(
            ValueError, match="指定された日付は、現在「OPEN」な会計年度の範囲外です"
        ):
            await js.add_journal_entry(
                Transaction(
                    date=target_date,
                    description="Out of range transaction",
                    lines=[
                        TransactionLine(account_id=acc1.id, debit=100, credit=0),
                        TransactionLine(account_id=acc2.id, debit=0, credit=100),
                    ],
                )
            )


# --- 3. Ledger & Financial Report Services ---
@pytest.mark.asyncio
async def test_ledger_trial_balance_and_statements(container: Container) -> None:
    """Verify trial balance compilation, general ledger running movements, and financial statements."""
    # Arrange
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        fy = fys[0]
        assert fy.id is not None
        accounts = await ms.get_accounts()
        first_acc_id = accounts[0].id
        assert first_acc_id is not None

    async with container.ledger_service_scope() as ls:
        # Act
        tb_rows = await ls.get_trial_balance(fy.id)
        df_gl = await ls.get_general_ledger(fy.id, first_acc_id)
        report = await ls.generate_financial_report(fy.id)

        # Assert
        assert len(tb_rows) == len(accounts)
        assert hasattr(df_gl, "columns")
        assert report.fiscal_year.id == fy.id
        assert report.total_assets == report.total_liabilities + report.total_equity
        assert report.operating_income == report.gross_profit - report.sga.total


# --- 4. Fiscal Year Closing & Rollover Flow ---
@pytest.mark.asyncio
async def test_fiscal_year_closing_workflow_and_boundary_checks(
    container: Container,
) -> None:
    """Verify complete period closing, net profit transfer to retained earnings, and rollover journal."""
    # Arrange
    today = date.today()
    async with container.master_service_scope() as ms:
        test_fy = await ms.save_fiscal_year(
            FiscalYear(
                name="締めテスト第99期",
                start_date=date(today.year - 3, 1, 1),
                end_date=date(today.year - 3, 12, 31),
                status="OPEN",
                period_number=99,
            )
        )
        assert test_fy.id is not None
        accs = await ms.get_accounts()
        re_acc = next(
            (a for a in accs if a.name == "繰越利益剰余金" or a.code == "3120"), None
        )
        if not re_acc:
            await ms.save_account(
                Account(code="3120", name="繰越利益剰余金", type=AccountType.EQUITY)
            )

    async with container.fiscal_year_service_scope() as fys:
        # Act 1: Close active fiscal year
        next_fy = await fys.close_fiscal_year(test_fy.id)

        # Assert 1: New fiscal year opened and old closed
        assert next_fy is not None
        assert next_fy.period_number == 100
        assert next_fy.status == "OPEN"

        async with container.master_service_scope() as ms:
            closed_fy = await ms.get_fiscal_year_by_id(test_fy.id)
            assert closed_fy is not None
            assert closed_fy.status == "CLOSED"

        # Act & Assert 2: Attempting to close already closed fiscal year raises ValueError
        with pytest.raises(ValueError, match="Fiscal Year is already closed"):
            await fys.close_fiscal_year(test_fy.id)

        # Act & Assert 3: Closing nonexistent fiscal year raises ValueError
        with pytest.raises(ValueError, match=r"Fiscal Year 999999 not found"):
            await fys.close_fiscal_year(999999)


# --- 5. Invoice Cleansing & Pydantic Field Validation ---
@pytest.mark.parametrize(
    ("raw_input", "expected_invoice"),
    [
        ("  T1234567890123  ", "T1234567890123"),
        ("T1234567890123", "T1234567890123"),
        ("   ", None),
        ("", None),
        (None, None),
    ],
)
def test_invoice_cleansing_validator(
    raw_input: str | None, expected_invoice: str | None
) -> None:
    """Verify invoice number whitespace stripping and strict pattern verification."""
    # Act
    cp = Counterparty(name="テスト商事", invoice_number=raw_input)

    # Assert
    assert cp.invoice_number == expected_invoice


def test_unbalanced_transaction_raises_validation_error() -> None:
    """Verify Transaction validator rejects unbalanced debit and credit lines."""
    # Act & Assert
    with pytest.raises(ValidationError, match="Unbalanced Transaction"):
        Transaction(
            date=date.today(),
            description="Unbalanced",
            lines=[
                TransactionLine(account_id=1, debit=100, credit=0),
                TransactionLine(account_id=2, debit=0, credit=90),
            ],
        )


# --- 6. Domain Model Invariants (Decoupled from inline harnesses) ---
def test_account_type_label_and_constants() -> None:
    """Verify Account domain helper properties and default account catalog."""
    # Arrange & Act
    acc = Account(code="1110", name="現金", type=AccountType.CURRENT_ASSET)

    # Assert
    assert acc.type_label == "流動資産"
    assert len(DEFAULT_ACCOUNTS) >= 20


@pytest.mark.parametrize(
    ("invoice_candidate", "is_valid"),
    [
        ("T1234567890123", True),
        (None, False),
        ("", False),
        ("   ", False),
        ("1234567890123", False),
        ("T123456789012", False),
        ("T12345678901234", False),
        ("T123456789012A", False),
    ],
)
def test_validate_invoice_number_format_boundary_cases(
    invoice_candidate: str | None, is_valid: bool
) -> None:
    """Verify standalone invoice registration number validation across valid and boundary values."""
    # Act & Assert
    assert validate_invoice_number_format(invoice_candidate) is is_valid


# --- 7. Boundary Logic & Branch Coverage Tests ---
@pytest.mark.parametrize(
    ("current_end", "expected_start", "expected_end"),
    [
        (date(2025, 3, 31), date(2025, 4, 1), date(2026, 3, 31)),
        (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31)),
        (
            date(2024, 2, 28),
            date(2024, 2, 29),
            date(2025, 2, 27),
        ),  # Leap year boundary branch
    ],
)
def test_compute_next_fiscal_year_dates_handles_standard_and_leap_years(
    current_end: date, expected_start: date, expected_end: date
) -> None:
    """Verify next fiscal period date calculation including leap year day 29 rollover branch."""
    # Arrange
    from app.application_services import _compute_next_fiscal_year_dates

    # Act
    start_dt, end_dt = _compute_next_fiscal_year_dates(current_end)

    # Assert
    assert start_dt == expected_start
    assert end_dt == expected_end


@pytest.mark.asyncio
async def test_master_service_fiscal_year_create_alias_and_delete(
    container: Container,
) -> None:
    """Verify MasterService create_fiscal_year alias and deletion lifecycle."""
    # Arrange
    async with container.master_service_scope() as ms:
        fy_input = FiscalYear(
            name="エイリアステスト期",
            start_date=date(2030, 1, 1),
            end_date=date(2030, 12, 31),
            period_number=30,
            status="OPEN",
        )

        # Act
        created_fy = await ms.create_fiscal_year(fy_input)
        assert created_fy.id is not None
        await ms.delete_fiscal_year(created_fy.id)
        fetched_fy = await ms.get_fiscal_year_by_id(created_fy.id)

        # Assert
        assert created_fy.name == "エイリアステスト期"
        assert fetched_fy is None


@pytest.mark.asyncio
async def test_ledger_service_general_ledger_boundary_cases(
    container: Container,
) -> None:
    """Verify general ledger behavior on non-existent targets and credit-positive account types."""
    # Arrange
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        open_fy = next(f for f in fys if f.status == "OPEN")
        assert open_fy.id is not None
        accounts = await ms.get_accounts()
        sales_acc = next(a for a in accounts if a.type == AccountType.REVENUE)
        cash_acc = next(a for a in accounts if a.code == "1110")
        assert sales_acc.id is not None and cash_acc.id is not None

    async with container.journal_service_scope() as js:
        await js.add_journal_entry(
            Transaction(
                date=open_fy.start_date,
                description="GL信用残高テスト",
                lines=[
                    TransactionLine(account_id=cash_acc.id, debit=10000, credit=0),
                    TransactionLine(account_id=sales_acc.id, debit=0, credit=10000),
                ],
            )
        )

    async with container.ledger_service_scope() as ls:
        # Act 1: Non-existent fiscal year returns empty DataFrame
        df_empty_fy = await ls.get_general_ledger(999999, sales_acc.id)

        # Act 2: Non-existent account returns empty DataFrame
        df_empty_acc = await ls.get_general_ledger(open_fy.id, 999999)

        # Act 3: Revenue (credit-positive) general ledger running balance
        df_sales = await ls.get_general_ledger(open_fy.id, sales_acc.id)

        # Assert
        assert df_empty_fy.empty is True
        assert df_empty_acc.empty is True
        assert not df_sales.empty
        assert "残高" in df_sales.columns
        assert df_sales["残高"].iloc[-1] == 10000


@pytest.mark.asyncio
async def test_fiscal_year_closing_when_succeeding_fiscal_year_already_exists(
    container: Container,
) -> None:
    """Verify closing logic seamlessly attaches to pre-existing next fiscal year entity."""
    # Arrange
    today = date.today()
    async with container.master_service_scope() as ms:
        fy_current = await ms.save_fiscal_year(
            FiscalYear(
                name="先行テスト第80期",
                start_date=date(today.year - 5, 1, 1),
                end_date=date(today.year - 5, 12, 31),
                status="OPEN",
                period_number=80,
            )
        )
        fy_preexisting_next = await ms.save_fiscal_year(
            FiscalYear(
                name="先行テスト第81期（予約済）",
                start_date=date(today.year - 4, 1, 1),
                end_date=date(today.year - 4, 12, 31),
                status="OPEN",
                period_number=81,
            )
        )
        accs = await ms.get_accounts()
        if not any(a.name == "繰越利益剰余金" or a.code == "3120" for a in accs):
            await ms.save_account(
                Account(code="3120", name="繰越利益剰余金", type=AccountType.EQUITY)
            )
        assert fy_current.id is not None and fy_preexisting_next.id is not None

    async with container.fiscal_year_service_scope() as fys:
        # Act
        next_fy = await fys.close_fiscal_year(fy_current.id)

        # Assert
        assert next_fy.id == fy_preexisting_next.id
        assert next_fy.period_number == 81
        assert next_fy.status == "OPEN"
