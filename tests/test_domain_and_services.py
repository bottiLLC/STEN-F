# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from datetime import date, timedelta
import pytest
from app.domain_contracts import (
    Abstract,
    Account,
    AccountType,
    Counterparty,
    FiscalYear,
    Transaction,
    TransactionLine,
)


# --- 1. Master Logic & Account Constraints ---
@pytest.mark.asyncio
async def test_master_service_account_and_counterparty_lifecycle(container):
    """Verify MasterService account deletion constraints and counterparty kana sorting."""
    async with container.master_service_scope() as ms:
        added_count = await ms.initialize_default_accounts()
        assert added_count >= 0

        accs = await ms.get_accounts()
        assert len(accs) >= 2
        acc1 = accs[0]

        # Abstract
        ab = await ms.save_abstract(Abstract(account_id=acc1.id, text="金物代"))
        assert ab.id is not None
        fetched_abs = await ms.get_abstracts()
        assert any(a.id == ab.id for a in fetched_abs)
        await ms.delete_abstract(ab.id)

        # Counterparty sorting & cleaning
        cp1 = await ms.save_counterparty(
            Counterparty(name="株式会社ベータ", reading="カブシキガイシャベータ")
        )
        cp2 = await ms.save_counterparty(
            Counterparty(name="合同会社アルファ", reading="ゴウドウガイシャアルファ")
        )
        cps = await ms.get_counterparties()
        names = [c.name for c in cps]
        assert names.index("合同会社アルファ") < names.index("株式会社ベータ")

        # Fuzzy search
        matched = await ms.get_counterparty_by_keyword("アルファ")
        assert matched is not None
        assert matched.name == "合同会社アルファ"
        assert await ms.get_counterparty_by_keyword("") is None

        await ms.delete_counterparty(cp1.id)
        await ms.delete_counterparty(cp2.id)


@pytest.mark.asyncio
async def test_account_deletion_with_active_transactions(container):
    """Ensure deleting an account referenced by transactions raises ValueError."""
    async with container.master_service_scope() as ms:
        test_acc = await ms.save_account(
            Account(code="8888", name="使用中科目", type=AccountType.SGA)
        )
        accs = await ms.get_accounts()
        cash_acc = next(a for a in accs if a.code == "1110")

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

    async with container.master_service_scope() as ms:
        with pytest.raises(
            ValueError, match="この勘定科目は仕訳で使用されているため削除できません"
        ):
            await ms.delete_account(test_acc.id)


# --- 2. Journal Entry Operations & Validation ---
@pytest.mark.asyncio
async def test_journal_entry_lifecycle_and_updates(container):
    """Verify journal entry recording, validation against OPEN years, and line replacements."""
    async with container.master_service_scope() as ms:
        accounts = await ms.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]

    async with container.journal_service_scope() as js:
        # 1. Successful entry
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
        assert tx_id > 0

        # Verify auto-learn counterparty
        async with container.master_service_scope() as ms:
            learned_cp = await ms.get_counterparty_by_keyword("新規自動学習取引先")
            assert learned_cp is not None

        # 2. Update journal entry
        tx_saved = next(t for t in await js.get_entries() if t.id == tx_id)
        tx_saved.description = "更新後の摘要"
        tx_saved.lines = [
            TransactionLine(account_id=acc1.id, debit=15000, credit=0),
            TransactionLine(account_id=acc2.id, debit=0, credit=15000),
        ]
        assert await js.update_journal_entry(tx_saved) is True

        updated_entries = await js.get_entries()
        u = next(e for e in updated_entries if e.id == tx_saved.id)
        assert u.description == "更新後の摘要"
        assert sum(line.debit for line in u.lines) == 15000

        # 3. CSV Export
        csv_text = await js.export_journal_entries_csv()
        assert "取引日,ID,摘要,取引先" in csv_text
        assert "更新後の摘要" in csv_text

        # 4. Opening Balance
        op_id = await js.register_opening_balance(
            opening_date=date.today(),
            debit_balances={str(acc1.id): "50000"},
            credit_balances={str(acc2.id): "50000"},
        )
        assert op_id > 0

        # 5. Frequent Account IDs
        freq = await js.get_frequent_account_ids(limit=5)
        assert isinstance(freq, list)
        assert len(freq) >= 1

        # 6. Date validation outside open fiscal year
        out_of_range_date = date.today() - timedelta(days=365 * 10)
        with pytest.raises(
            ValueError, match="指定された日付は、現在「OPEN」な会計年度の範囲外です"
        ):
            await js.add_journal_entry(
                Transaction(
                    date=out_of_range_date,
                    description="Out of range",
                    lines=[
                        TransactionLine(account_id=acc1.id, debit=100, credit=0),
                        TransactionLine(account_id=acc2.id, debit=0, credit=100),
                    ],
                )
            )


# --- 3. Ledger & Financial Report Services ---
@pytest.mark.asyncio
async def test_ledger_trial_balance_and_statements(container):
    """Verify trial balance compilation, general ledger running movements, and financial statements."""
    async with container.master_service_scope() as ms:
        fys = await ms.get_fiscal_years()
        fy = fys[0]
        accounts = await ms.get_accounts()

    async with container.ledger_service_scope() as ls:
        # Trial Balance
        tb_rows = await ls.get_trial_balance(fy.id)
        assert isinstance(tb_rows, list)
        assert len(tb_rows) == len(accounts)

        # General Ledger DataFrame
        df_gl = await ls.get_general_ledger(fy.id, accounts[0].id)
        assert hasattr(df_gl, "columns")

        # Financial Report
        report = await ls.generate_financial_report(fy.id)
        assert report.fiscal_year.id == fy.id
        assert isinstance(report.total_assets, int)


# --- 4. Fiscal Year Closing & Rollover Flow ---
@pytest.mark.asyncio
async def test_fiscal_year_closing_workflow(container):
    """Verify complete period closing, net profit transfer to retained earnings, and rollover journal."""
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
        accs = await ms.get_accounts()
        re_acc = next(
            (a for a in accs if a.name == "繰越利益剰余金" or a.code == "3120"), None
        )
        if not re_acc:
            await ms.save_account(
                Account(code="3120", name="繰越利益剰余金", type=AccountType.EQUITY)
            )

    async with container.fiscal_year_service_scope() as fys:
        next_fy = await fys.close_fiscal_year(test_fy.id)
        assert next_fy is not None
        assert next_fy.period_number == 100
        assert next_fy.status == "OPEN"

    async with container.master_service_scope() as ms:
        closed_fy = await ms.get_fiscal_year_by_id(test_fy.id)
        assert closed_fy.status == "CLOSED"


# --- 5. Invoice Cleansing & Pydantic Field Validation ---
def test_invoice_cleansing_validator():
    """Verify invoice number whitespace stripping and strict pattern verification."""
    cp = Counterparty(name="テスト商事", invoice_number="  T1234567890123  ")
    assert cp.invoice_number == "T1234567890123"

    cp_empty = Counterparty(name="空番号", invoice_number="   ")
    assert cp_empty.invoice_number is None

    tx = Transaction(
        date=date.today(),
        description="Invoice Test",
        invoice_number="  T9876543210987  ",
        lines=[
            TransactionLine(account_id=1, debit=100, credit=0),
            TransactionLine(account_id=2, debit=0, credit=100),
        ],
    )
    assert tx.invoice_number == "T9876543210987"

    with pytest.raises(ValueError):
        Transaction(
            date=date.today(),
            description="Unbalanced",
            lines=[
                TransactionLine(account_id=1, debit=100, credit=0),
                TransactionLine(account_id=2, debit=0, credit=90),
            ],
        )
