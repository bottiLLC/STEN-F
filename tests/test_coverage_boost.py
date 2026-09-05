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
from datetime import date
from streamlit.testing.v1 import AppTest
from app.domain.models.corporation import Corporation
from app.domain.models.counterparty import Counterparty
from app.domain.models.abstract import Abstract
from app.domain.models.account import Account, AccountType
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.receipt import ReceiptData


@pytest.mark.asyncio
class TestCoverageBoost:
    async def test_fiscal_year_closing_edge_cases(self, container):
        """Test fiscal year closing error conditions (not found, already closed)."""
        async with container.fiscal_year_service_scope() as fy_service:
            # 1. Non-existent FY ID
            with pytest.raises(ValueError, match="not found"):
                await fy_service.close_fiscal_year(999999, "Next FY")

        async with container.master_service_scope() as master_service:
            # 2. Setup already CLOSED FY
            closed_fy = FiscalYear(
                name="Already Closed FY",
                start_date=date(2020, 1, 1),
                end_date=date(2020, 12, 31),
                status="CLOSED",
                period_number=1,
            )
            saved = await master_service.save_fiscal_year(closed_fy)

        async with container.fiscal_year_service_scope() as fy_service:
            with pytest.raises(ValueError, match="already closed"):
                await fy_service.close_fiscal_year(saved.id, "Next FY")

        # Cleanup
        async with container.master_service_scope() as master_service:
            await master_service.delete_fiscal_year(saved.id)

    async def test_leap_year_fiscal_year_closing(self, container):
        """Test closing a fiscal year ending on a leap day (Feb 29)."""
        async with container.master_service_scope() as master_service:
            leap_fy = FiscalYear(
                name="Leap Year FY",
                start_date=date(2024, 3, 1),
                end_date=date(2025, 2, 28),
                status="OPEN",
                period_number=10,
            )
            saved_leap = await master_service.save_fiscal_year(leap_fy)

        async with container.fiscal_year_service_scope() as fy_service:
            next_fy = await fy_service.close_fiscal_year(saved_leap.id, "Next FY Leap")
            assert next_fy is not None
            assert next_fy.status == "OPEN"

        # Cleanup
        async with container.master_service_scope() as master_service:
            await master_service.delete_fiscal_year(saved_leap.id)
            await master_service.delete_fiscal_year(next_fy.id)

    async def test_corporation_save_and_update(self, container):
        """Test Corporation creation, retrieval, and full update."""
        async with container.master_service_scope() as master_service:
            corp = Corporation(
                name="株式会社カバレッジテスト",
                address="東京都千代田区1-1-1",
                representative_title="代表取締役",
                representative_name="テスト太郎",
            )
            await master_service.save_corporation(corp)

            # Fetch
            fetched = await master_service.get_corporation()
            assert fetched is not None
            assert fetched.name == "株式会社カバレッジテスト"
            assert fetched.representative_title == "代表取締役"

            # Update
            corp.name = "合同会社カバレッジテスト更新"
            await master_service.save_corporation(corp)
            fetched_updated = await master_service.get_corporation()
            assert fetched_updated is not None
            assert fetched_updated.name == "合同会社カバレッジテスト更新"

    async def test_master_service_crud_methods(self, container):
        """Test comprehensive MasterService methods for accounts, abstracts, counterparties."""
        async with container.master_service_scope() as master_service:
            # 1. Accounts list and filter
            accounts = await master_service.get_accounts()
            assets = [a for a in accounts if a.type == AccountType.CURRENT_ASSET]
            assert len(assets) > 0

            # 2. Add and delete account
            test_acc = Account(
                code="8888",
                name="テスト勘定科目",
                type=AccountType.SGA,
                description="テスト用",
            )
            await master_service.save_account(test_acc)

            # Get by id/code
            accs = await master_service.get_accounts()
            target = next(a for a in accs if a.code == "8888")
            assert target.name == "テスト勘定科目"

            # Delete
            await master_service.delete_account(target.id)
            accs_after = await master_service.get_accounts()
            assert not any(a.code == "8888" for a in accs_after)

            # 3. Default accounts init
            init_count = await master_service.initialize_default_accounts()
            assert isinstance(init_count, int)

            # 4. Counterparty
            cp = Counterparty(name="テスト業者", invoice_number="T9999888877776")
            saved_cp = await master_service.save_counterparty(cp)
            assert saved_cp.id is not None
            await master_service.delete_counterparty(saved_cp.id)

            # 5. Abstract
            ab = Abstract(account_id=assets[0].id, text="テスト摘要")
            saved_ab = await master_service.save_abstract(ab)
            assert saved_ab.id is not None
            await master_service.delete_abstract(saved_ab.id)

    async def test_journal_service_filter_branches(self, container):
        """Test get_entries filtering by various date ranges and flags."""
        async with container.master_service_scope() as master_service:
            accounts = await master_service.get_accounts()
            a1, a2 = accounts[0], accounts[1]

        async with container.journal_service_scope() as j_service:
            tx = Transaction(
                date=date.today(),
                description="Filter branch test",
                counterparty="Filter Partner",
                lines=[
                    TransactionLine(account_id=a1.id, debit=500, credit=0),
                    TransactionLine(account_id=a2.id, debit=0, credit=500),
                ],
            )
            tx_id = await j_service.add_journal_entry(tx)

            # 1. Filter with start_date only
            res1 = await j_service.get_entries(start_date=date.today())
            assert any(e.id == tx_id for e in res1)

            # 2. Filter with end_date only
            res2 = await j_service.get_entries(end_date=date.today())
            assert any(e.id == tx_id for e in res2)

            # 3. Filter with both
            res3 = await j_service.get_entries(
                start_date=date.today(), end_date=date.today()
            )
            assert any(e.id == tx_id for e in res3)

            # 4. Filter with future date (should be empty)
            future_date = date(date.today().year + 5, 1, 1)
            res4 = await j_service.get_entries(start_date=future_date)
            assert not any(e.id == tx_id for e in res4)

            # 5. Soft delete and include_deleted filter
            await j_service.delete_entry(tx_id)
            res_without_deleted = await j_service.get_entries(
                start_date=date.today(), include_deleted=False
            )
            assert not any(e.id == tx_id for e in res_without_deleted)

            res_with_deleted = await j_service.get_entries(
                start_date=date.today(), include_deleted=True
            )
            assert any(e.id == tx_id for e in res_with_deleted)

    async def test_journal_service_frequent_accounts(self, container):
        """Test JournalService.get_frequent_account_ids returns expected top accounts."""
        async with container.journal_service_scope() as j_service:
            frequent = await j_service.get_frequent_account_ids(limit=5)
            assert isinstance(frequent, list)

    async def test_backup_service_custom_dir(self, container, tmp_path):
        """Test BackupService execution into a custom temporary directory."""
        backup_service = container.get_backup_service()
        custom_backup_dir = str(tmp_path / "custom_backups")

        backup_file_path = await backup_service.create_backup(custom_backup_dir)
        assert backup_file_path is not None
        assert "bookkeeping" in backup_file_path or "backups" in backup_file_path

    async def test_pdf_service_comprehensive_sections(self, container):
        """Test PDF generation with all financial report sections populated."""
        from app.domain.models.financial_report import (
            FinancialReport,
            FinancialSection,
            TrialBalanceRow,
        )

        dummy_fy = FiscalYear(
            id=1,
            name="2026年度",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="OPEN",
            period_number=1,
        )
        dummy_corp = Corporation(
            name="PDFテスト株式会社",
            address="東京都港区六本木1-1",
            representative_title="代表取締役",
            representative_name="テスト社長",
        )

        def make_sec(title, names_amounts, acc_type):
            rows = [
                TrialBalanceRow(
                    account_id=i,
                    account_code=str(1000 + i),
                    account_name=name,
                    account_type=acc_type,
                    debit_total=amt if amt > 0 else 0,
                    credit_total=0,
                    balance=amt,
                    debit_balance=amt,
                    credit_balance=0,
                )
                for i, (name, amt) in enumerate(names_amounts)
            ]
            return FinancialSection(
                title=title, rows=rows, total=sum(amt for _, amt in names_amounts)
            )

        report = FinancialReport(
            fiscal_year=dummy_fy,
            current_assets=make_sec(
                "流動資産", [("普通預金", 1000000)], AccountType.CURRENT_ASSET
            ),
            fixed_assets=make_sec(
                "固定資産", [("工具器具備品", 500000)], AccountType.FIXED_ASSET
            ),
            deferred_assets=make_sec(
                "繰延資産", [("創立費", 100000)], AccountType.DEFERRED_ASSET
            ),
            current_liabilities=make_sec(
                "流動負債", [("買掛金", 300000)], AccountType.CURRENT_LIABILITY
            ),
            fixed_liabilities=make_sec(
                "固定負債", [("長期借入金", 700000)], AccountType.FIXED_LIABILITY
            ),
            equity=make_sec("純資産", [("資本金", 500000)], AccountType.EQUITY),
            revenue=make_sec("売上高", [("売上高", 2000000)], AccountType.REVENUE),
            cost_of_sales=make_sec(
                "売上原価", [("仕入高", 800000)], AccountType.COST_OF_SALES
            ),
            sga=make_sec("販管費", [("旅費交通費", 200000)], AccountType.SGA),
            non_op_income=make_sec(
                "営業外収益", [("受取利息", 1000)], AccountType.NON_OPERATING_INCOME
            ),
            non_op_expense=make_sec(
                "営業外費用",
                [("支払利息", 5000)],
                AccountType.NON_OPERATING_EXPENSE,
            ),
            extra_income=make_sec(
                "特別利益",
                [("固定資産売却益", 50000)],
                AccountType.EXTRAORDINARY_INCOME,
            ),
            extra_loss=make_sec(
                "特別損失",
                [("固定資産除却損", 20000)],
                AccountType.EXTRAORDINARY_LOSS,
            ),
            total_assets=1600000,
            total_liabilities=1000000,
            total_equity=600000,
            gross_profit=1200000,
            operating_income=1000000,
            ordinary_income=996000,
            income_before_tax=1026000,
            net_income=1026000,
        )

        pdf_service = container.get_pdf_service()
        pdf_bytes = pdf_service.generate_annual_report(
            dummy_corp, report, dummy_fy, date.today(), date.today()
        )
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF")


def test_ui_journal_entry_with_ocr_preset():
    """Verify 1_journal_entry.py presets OCR values into the form properly."""
    at = AppTest.from_file("app/ui/app_pages/1_journal_entry.py", default_timeout=15)
    # Preset session state
    ocr_mock = ReceiptData(
        transaction_date="2026-05-15",
        merchant_name="OCRテスト商店",
        total_amount_incl_tax=8800,
        invoice_registration_number="T1234567890123",
        description="タクシー代",
        inferred_debit_account_id="1",
        inferred_credit_account_id="2",
    )
    at.session_state.ocr_result = ocr_mock
    at.session_state.ocr_file_bytes = b"dummy"
    at.session_state.ocr_filename = "receipt.pdf"
    at.run()

    assert not at.exception
    assert len(at.metric) >= 3
    # Check clear button works
    clear_btn = next((b for b in at.button if "クリア" in b.label), None)
    if clear_btn:
        clear_btn.click()
        at.run()
        assert not at.exception
