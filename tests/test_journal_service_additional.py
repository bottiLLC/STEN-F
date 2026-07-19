import pytest
from datetime import date
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.fiscal_year import FiscalYear
from pathlib import Path
from app.infrastructure.external.file_service import LocalFileService


@pytest.mark.asyncio
async def test_validate_transaction_date_no_open_fy(container):
    async with container.master_service_scope() as master_service:
        # Delete any seeded fiscal years to trigger "no OPEN fiscal years" exception
        fys = await master_service.get_fiscal_years()
        for fy in fys:
            await master_service.delete_fiscal_year(fy.id)

    async with container.journal_service_scope() as journal_service:
        tx = Transaction(
            date=date.today(),
            description="No Open FY Test",
            lines=[
                TransactionLine(account_id=1, debit=100, credit=0),
                TransactionLine(account_id=2, debit=0, credit=100),
            ],
        )
        with pytest.raises(
            ValueError, match="現在「OPEN」ステータスの会計年度が存在しません。"
        ):
            await journal_service.add_journal_entry(tx)


@pytest.mark.asyncio
async def test_validate_transaction_date_out_of_range(container):
    async with container.master_service_scope() as master_service:
        # Ensure there is an open fiscal year for today
        fys = await master_service.get_fiscal_years()
        if not fys:
            today = date.today()
            await master_service.save_fiscal_year(
                FiscalYear(
                    name="FY_Test",
                    start_date=date(today.year, 1, 1),
                    end_date=date(today.year, 12, 31),
                    status="OPEN",
                )
            )

    async with container.journal_service_scope() as journal_service:
        # Pass a date 10 years ago, which is out of range of today's OPEN fiscal year
        out_of_range_date = date(date.today().year - 10, 1, 1)
        tx = Transaction(
            date=out_of_range_date,
            description="Out of range date test",
            lines=[
                TransactionLine(account_id=1, debit=100, credit=0),
                TransactionLine(account_id=2, debit=0, credit=100),
            ],
        )
        with pytest.raises(
            ValueError, match="指定された日付は、現在「OPEN」な会計年度の範囲外です"
        ):
            await journal_service.add_journal_entry(tx)


@pytest.mark.asyncio
async def test_register_opening_balance(container):
    async with container.master_service_scope() as master_service:
        # Need accounts in DB. Get seeded accounts.
        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]

    async with container.journal_service_scope() as journal_service:
        # 1. Normal case
        debit_balances = {str(acc1.id): "1,000,000"}
        credit_balances = {str(acc2.id): "1,000,000"}

        tx_id = await journal_service.register_opening_balance(
            opening_date=date.today(),
            debit_balances=debit_balances,
            credit_balances=credit_balances,
        )
        assert tx_id is not None

        # Verify
        entries = await journal_service.get_entries()
        saved = next(e for e in entries if e.id == tx_id)
        assert saved.description == "期首残高"
        assert len(saved.lines) == 2

        # 2. Empty balance case
        with pytest.raises(ValueError, match="入力された金額がありません"):
            await journal_service.register_opening_balance(
                opening_date=date.today(), debit_balances={}, credit_balances={}
            )


@pytest.mark.asyncio
async def test_export_journal_entries_csv(container):
    async with container.master_service_scope() as master_service:
        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]

    async with container.journal_service_scope() as journal_service:
        # Create a transactions to export
        tx = Transaction(
            date=date.today(),
            description="CSV Export Test Tx",
            counterparty="CSV Partner",
            lines=[
                TransactionLine(account_id=acc1.id, debit=3000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=3000),
            ],
            invoice_number="T1234567890123",
        )
        await journal_service.add_journal_entry(tx)

        # Export CSV
        csv_str = await journal_service.export_journal_entries_csv()

        # Assertions
        assert csv_str is not None
        assert (
            "取引日,ID,摘要,取引先,登録番号,勘定科目コード,勘定科目,借方金額,貸方金額"
            in csv_str
        )
        assert "CSV Export Test Tx" in csv_str
        assert "CSV Partner" in csv_str
        assert "T1234567890123" in csv_str


@pytest.mark.asyncio
async def test_add_journal_entry_with_evidence(container, tmp_path):
    async with container.master_service_scope() as master_service:
        accounts = await master_service.get_accounts()
        acc1 = accounts[0]
        acc2 = accounts[1]

    file_service = LocalFileService(base_dir=tmp_path)
    dummy_pdf_bytes = b"%PDF-1.4 mock pdf data"

    async with container.journal_service_scope() as journal_service:
        tx = Transaction(
            date=date.today(),
            description="Evidence upload test",
            counterparty="Evidence Corp",
            lines=[
                TransactionLine(account_id=acc1.id, debit=25000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=25000),
            ],
        )

        tx_id = await journal_service.add_journal_entry_with_evidence(
            transaction=tx, file_bytes=dummy_pdf_bytes, file_service=file_service
        )

        assert tx_id is not None

        # Verify from DB that the path was saved
        entries = await journal_service.get_entries()
        saved = next(e for e in entries if e.id == tx_id)

        assert saved.evidence_path is not None
        assert "25000_Evidence Corp" in saved.evidence_path

        # Verify file exists physically
        assert saved.evidence_path.endswith(".pdf")
        saved_file = Path(saved.evidence_path)
        assert saved_file.exists()
        assert saved_file.read_bytes() == dummy_pdf_bytes
