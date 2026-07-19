from datetime import date
from app.infrastructure.external.pdf_service import PDFService
from app.domain.models.corporation import Corporation
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.account import AccountType
from app.domain.models.financial_report import (
    FinancialReport,
    FinancialSection,
    TrialBalanceRow,
    FiscalYear as ReportFiscalYear
)

def test_generate_annual_report_success():
    # 1. Prepare Mock Data
    corp = Corporation(
        id=1,
        name="テスト株式会社",
        address="東京都渋谷区1-1-1",
        representative_title="代表取締役",
        representative_name="テスト太郎"
    )
    
    fy_model = FiscalYear(
        id=1,
        name="FY2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="OPEN",
        period_number=10
    )
    
    # FinancialReport internally references a simplified FiscalYear model
    report_fy = ReportFiscalYear(
        id=1,
        name="FY2026",
        period_number=10
    )
    
    # Helper to generate typical section
    def create_dummy_section(title, balance=1000):
        return FinancialSection(
            title=title,
            rows=[
                TrialBalanceRow(
                    account_id=101,
                    account_code="1110",
                    account_name="普通預金",
                    account_type=AccountType.CURRENT_ASSET,
                    debit_total=balance,
                    credit_total=0,
                    balance=balance,
                    debit_balance=balance,
                    credit_balance=0
                )
            ],
            total=balance
        )

    rpt = FinancialReport(
        fiscal_year=report_fy,
        current_assets=create_dummy_section("【流動資産】"),
        fixed_assets=create_dummy_section("【固定資産】"),
        deferred_assets=create_dummy_section("【繰延資産】", balance=0), # deferred total 0 to cover condition
        current_liabilities=create_dummy_section("【流動負債】"),
        fixed_liabilities=create_dummy_section("【固定負債】"),
        equity=create_dummy_section("【株主資本】"),
        revenue=create_dummy_section("【売上高】", balance=5000),
        cost_of_sales=create_dummy_section("【売上原価】", balance=2000),
        sga=create_dummy_section("【販売費及び一般管理費】", balance=1500),
        non_op_income=create_dummy_section("【営業外収益】", balance=100),
        non_op_expense=create_dummy_section("【営業外費用】", balance=50),
        extra_income=create_dummy_section("【特別利益】", balance=0),
        extra_loss=create_dummy_section("【特別損失】", balance=0),
        total_assets=2000,
        total_liabilities=1000,
        total_equity=1000,
        gross_profit=3000,
        operating_income=1500,
        ordinary_income=1550,
        income_before_tax=1550,
        net_income=1550
    )
    
    # 2. Execute
    pdf_bytes = PDFService.generate_annual_report(
        corp=corp,
        rpt=rpt,
        fy_full_obj=fy_model,
        report_date=date(2027, 2, 28),
        audit_date=date(2027, 3, 10)
    )
    
    # 3. Assertions
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # PDF specification header check
    assert pdf_bytes.startswith(b"%PDF-1.4")
