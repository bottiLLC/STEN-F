"""Unit tests for financial statement UI components (B/S & P/L)."""

from __future__ import annotations

from datetime import date

from app.domain_contracts import (
    AccountType,
    FinancialReport,
    FinancialSection,
    FiscalYear,
    TrialBalanceRow,
)
from app.ui.financial_statements import (
    build_balance_sheet_html,
    build_profit_and_loss_html,
)


def _make_sample_report(net_income: int = 50000) -> FinancialReport:
    """Construct deterministic sample FinancialReport for rendering tests."""
    fy = FiscalYear(
        id=1,
        name="第1期",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="OPEN",
        period_number=1,
    )

    def _sec(
        title: str, acc_type: AccountType, items: list[tuple[str, int]]
    ) -> FinancialSection:
        rows = [
            TrialBalanceRow(
                account_id=i + 1,
                account_code=f"{100 + i}",
                account_name=name,
                account_type=acc_type,
                balance=bal,
            )
            for i, (name, bal) in enumerate(items)
        ]
        return FinancialSection(title=title, rows=rows, total=sum(b for _, b in items))

    cur_assets = _sec(
        "【流動資産】",
        AccountType.CURRENT_ASSET,
        [("現金預金", 1000000), ("売掛金", 500000), ("前払費用", 0)],
    )
    fix_assets = _sec(
        "【固定資産】",
        AccountType.FIXED_ASSET,
        [("工具器具備品", 300000)],
    )
    def_assets = _sec("【繰延資産】", AccountType.DEFERRED_ASSET, [])

    cur_liabs = _sec(
        "【流動負債】",
        AccountType.CURRENT_LIABILITY,
        [("買掛金", 200000), ("未払金", 0)],
    )
    fix_liabs = _sec(
        "【固定負債】",
        AccountType.FIXED_LIABILITY,
        [("長期借入金", 600000)],
    )
    equity = _sec(
        "【純資産の部】",
        AccountType.EQUITY,
        [("資本金", 950000)],
    )

    revenue = _sec("【売上高】", AccountType.REVENUE, [("売上高", 2000000)])
    cost = _sec("【売上原価】", AccountType.COST_OF_SALES, [("仕入高", 1200000)])
    sga = _sec(
        "【販売費及び一般管理費】",
        AccountType.SGA,
        [("役員報酬", 500000), ("旅費交通費", 100000)],
    )
    no_inc = _sec(
        "【営業外収益】", AccountType.NON_OPERATING_INCOME, [("受取利息", 1000)]
    )
    no_exp = _sec(
        "【営業外費用】", AccountType.NON_OPERATING_EXPENSE, [("支払利息", 51000)]
    )
    ex_inc = _sec("【特別利益】", AccountType.EXTRAORDINARY_INCOME, [])
    ex_loss = _sec(
        "【特別損失】", AccountType.EXTRAORDINARY_LOSS, [("固定資産除却損", 100000)]
    )

    gross_profit = 2000000 - 1200000  # 800,000
    operating_income = gross_profit - 600000  # 200,000
    ordinary_income = operating_income + 1000 - 51000  # 150,000
    income_before_tax = ordinary_income + 0 - 100000  # 50,000

    return FinancialReport(
        fiscal_year=fy,
        current_assets=cur_assets,
        fixed_assets=fix_assets,
        deferred_assets=def_assets,
        current_liabilities=cur_liabs,
        fixed_liabilities=fix_liabs,
        equity=equity,
        revenue=revenue,
        cost_of_sales=cost,
        sga=sga,
        non_op_income=no_inc,
        non_op_expense=no_exp,
        extra_income=ex_inc,
        extra_loss=ex_loss,
        total_assets=cur_assets.total + fix_assets.total,  # 1,800,000
        total_liabilities=cur_liabs.total + fix_liabs.total,  # 800,000
        total_equity=equity.total + net_income,  # 950,000 + 50,000 = 1,000,000
        gross_profit=gross_profit,
        operating_income=operating_income,
        ordinary_income=ordinary_income,
        income_before_tax=income_before_tax,
        net_income=net_income,
    )


def test_build_balance_sheet_html_with_financial_report() -> None:
    """Verify Balance Sheet HTML incorporates layout, subtotal, and alignment requirements."""
    # Arrange
    rpt = _make_sample_report()

    # Act
    html_output = build_balance_sheet_html(rpt, hide_zero=True)

    # Assert
    assert "貸借対照表 (Balance Sheet)" in html_output
    assert "負債の部合計" in html_output
    assert "¥800,000" in html_output
    assert "資産の部 合計" in html_output
    assert "負債・純資産の部 合計" in html_output
    assert "¥1,800,000" in html_output
    assert "tabular-nums" in html_output
    assert "border-bottom: 3px double #1f2937" in html_output
    assert "margin-top: auto" in html_output  # Flush horizontal alignment requirement
    # Zero balance filtering verification
    assert "前払費用" not in html_output
    assert "未払金" not in html_output


def test_build_balance_sheet_html_shows_zero_when_hide_zero_is_false() -> None:
    """Verify zero balance accounts are retained when hide_zero is disabled."""
    # Arrange
    rpt = _make_sample_report()

    # Act
    html_output = build_balance_sheet_html(rpt, hide_zero=False)

    # Assert
    assert "前払費用" in html_output
    assert "未払金" in html_output


def test_build_balance_sheet_html_with_dict_payload() -> None:
    """Verify dynamic dict payload can be normalized and rendered directly."""
    # Arrange
    dict_payload = {
        "current_assets": {
            "title": "流動資産",
            "rows": [{"name": "普通預金", "amount": 500000}],
            "total": 500000,
        },
        "fixed_assets": {"rows": []},
        "current_liabilities": {
            "title": "流動負債",
            "rows": [{"account_name": "短期借入金", "balance": 100000}],
            "total": 100000,
        },
        "fixed_liabilities": {"rows": []},
        "equity": {
            "title": "純資産",
            "rows": [("資本金", 400000)],
            "total": 400000,
        },
        "total_assets": 500000,
        "total_liabilities": 100000,
        "total_equity": 400000,
        "net_income": 0,
    }

    # Act
    html_output = build_balance_sheet_html(dict_payload)

    # Assert
    assert "普通預金" in html_output
    assert "¥500,000" in html_output
    assert "負債の部合計" in html_output
    assert "¥100,000" in html_output
    assert "負債・純資産の部 合計" in html_output


def test_build_profit_and_loss_html_waterfall_structure() -> None:
    """Verify Profit and Loss statement adheres to 1-column waterfall hierarchy."""
    # Arrange
    rpt = _make_sample_report(net_income=50000)

    # Act
    html_output = build_profit_and_loss_html(rpt, hide_zero=True)

    # Assert
    assert "損益計算書 (Profit & Loss Statement)" in html_output
    assert "I. 売上高" in html_output
    assert "II. 売上原価" in html_output
    assert "売上総利益" in html_output
    assert "III. 販売費及び一般管理費" in html_output
    assert "営業利益" in html_output
    assert "IV. 営業外収益" in html_output
    assert "V. 営業外費用" in html_output
    assert "経常利益" in html_output
    assert "VI. 特別利益" in html_output
    assert "VII. 特別損失" in html_output
    assert "税引前当期純利益" in html_output
    assert "当期純利益" in html_output
    assert "¥50,000" in html_output

    # No emoji icons in tabular rows
    assert "🏛️" not in html_output
    assert "📈" not in html_output
    assert "🌟" not in html_output

    # Check indentation and double border classes
    assert "fs-pl-item" in html_output
    assert "fs-pl-stage" in html_output
    assert "fs-pl-net-income" in html_output


def test_build_profit_and_loss_html_deficit_labels() -> None:
    """Verify net deficit and operating loss are labeled with accurate financial loss terms."""
    # Arrange
    dict_payload = {
        "revenue": {"rows": [("売上高", 100000)], "total": 100000},
        "cost_of_sales": {"rows": [("仕入高", 150000)], "total": 150000},
        "sga": {"rows": [("消耗品費", 20000)], "total": 20000},
        "gross_profit": -50000,
        "operating_income": -70000,
        "ordinary_income": -70000,
        "income_before_tax": -70000,
        "net_income": -70000,
    }

    # Act
    html_output = build_profit_and_loss_html(dict_payload)

    # Assert
    assert "売上総損失" in html_output
    assert "-¥50,000" in html_output
    assert "営業損失" in html_output
    assert "-¥70,000" in html_output
    assert "当期純損失" in html_output
