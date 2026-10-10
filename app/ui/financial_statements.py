"""Financial statement UI components for Streamlit.

Renders Balance Sheet (B/S) and Profit & Loss (P/L) statements as high-precision,
accessible, and tabular accounting documents using scoped HTML/CSS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import html
from typing import Any

import streamlit as st

from app.domain_contracts import FinancialReport, FinancialSection


@dataclass(frozen=True)
class StatementRow:
    """Individual account line within a financial section."""

    account_name: str
    balance: int


@dataclass(frozen=True)
class StatementSectionData:
    """Aggregated financial category section."""

    title: str
    rows: list[StatementRow] = field(default_factory=list)
    total: int = 0


@dataclass(frozen=True)
class NormalizedFinancialReport:
    """Normalized payload enabling unified rendering from Pydantic models or dicts."""

    current_assets: StatementSectionData
    fixed_assets: StatementSectionData
    deferred_assets: StatementSectionData
    current_liabilities: StatementSectionData
    fixed_liabilities: StatementSectionData
    equity: StatementSectionData
    revenue: StatementSectionData
    cost_of_sales: StatementSectionData
    sga: StatementSectionData
    non_op_income: StatementSectionData
    non_op_expense: StatementSectionData
    extra_income: StatementSectionData
    extra_loss: StatementSectionData
    total_assets: int
    total_liabilities: int
    total_equity: int
    gross_profit: int
    operating_income: int
    ordinary_income: int
    income_before_tax: int
    net_income: int


def _format_currency(val: int) -> str:
    """Format integer monetary amount into standard Japanese currency notation."""
    if val < 0:
        return f"-¥{abs(val):,}"
    return f"¥{val:,}"


def _normalize_section(raw: Any, default_title: str) -> StatementSectionData:
    """Normalize raw section input (FinancialSection, dict, or None) into StatementSectionData."""
    if isinstance(raw, FinancialSection):
        clean_title = raw.title.strip("【】 ")
        rows = [
            StatementRow(account_name=r.account_name, balance=r.balance)
            for r in raw.rows
        ]
        return StatementSectionData(
            title=clean_title or default_title, rows=rows, total=raw.total
        )

    if isinstance(raw, dict):
        clean_title = str(raw.get("title", default_title)).strip("【】 ")
        raw_rows = raw.get("rows", [])
        parsed_rows: list[StatementRow] = []
        for item in raw_rows:
            if isinstance(item, dict):
                name = str(item.get("account_name") or item.get("name") or "未分類科目")
                bal = int(item.get("balance") or item.get("amount") or 0)
                parsed_rows.append(StatementRow(account_name=name, balance=bal))
            elif hasattr(item, "account_name") and hasattr(item, "balance"):
                parsed_rows.append(
                    StatementRow(
                        account_name=str(item.account_name), balance=int(item.balance)
                    )
                )
            elif isinstance(item, (tuple, list)) and len(item) >= 2:
                parsed_rows.append(
                    StatementRow(account_name=str(item[0]), balance=int(item[1]))
                )

        calc_total = sum(r.balance for r in parsed_rows)
        total = int(raw.get("total", calc_total))
        return StatementSectionData(
            title=clean_title or default_title, rows=parsed_rows, total=total
        )

    return StatementSectionData(title=default_title, rows=[], total=0)


def _normalize_report_data(
    data: FinancialReport | dict[str, Any],
) -> NormalizedFinancialReport:
    """Extract and normalize all balance sheet and income statement metrics."""
    if isinstance(data, FinancialReport):
        return NormalizedFinancialReport(
            current_assets=_normalize_section(data.current_assets, "流動資産"),
            fixed_assets=_normalize_section(data.fixed_assets, "固定資産"),
            deferred_assets=_normalize_section(data.deferred_assets, "繰延資産"),
            current_liabilities=_normalize_section(
                data.current_liabilities, "流動負債"
            ),
            fixed_liabilities=_normalize_section(data.fixed_liabilities, "固定負債"),
            equity=_normalize_section(data.equity, "純資産の部"),
            revenue=_normalize_section(data.revenue, "売上高"),
            cost_of_sales=_normalize_section(data.cost_of_sales, "売上原価"),
            sga=_normalize_section(data.sga, "販売費及び一般管理費"),
            non_op_income=_normalize_section(data.non_op_income, "営業外収益"),
            non_op_expense=_normalize_section(data.non_op_expense, "営業外費用"),
            extra_income=_normalize_section(data.extra_income, "特別利益"),
            extra_loss=_normalize_section(data.extra_loss, "特別損失"),
            total_assets=data.total_assets,
            total_liabilities=data.total_liabilities,
            total_equity=data.total_equity,
            gross_profit=data.gross_profit,
            operating_income=data.operating_income,
            ordinary_income=data.ordinary_income,
            income_before_tax=data.income_before_tax,
            net_income=data.net_income,
        )

    # Dictionary input processing
    cur_a = _normalize_section(data.get("current_assets"), "流動資産")
    fix_a = _normalize_section(data.get("fixed_assets"), "固定資産")
    def_a = _normalize_section(data.get("deferred_assets"), "繰延資産")
    cur_l = _normalize_section(data.get("current_liabilities"), "流動負債")
    fix_l = _normalize_section(data.get("fixed_liabilities"), "固定負債")
    eq = _normalize_section(data.get("equity"), "純資産の部")

    rev = _normalize_section(data.get("revenue"), "売上高")
    cos = _normalize_section(data.get("cost_of_sales"), "売上原価")
    sga = _normalize_section(data.get("sga"), "販売費及び一般管理費")
    no_inc = _normalize_section(data.get("non_op_income"), "営業外収益")
    no_exp = _normalize_section(data.get("non_op_expense"), "営業外費用")
    ex_inc = _normalize_section(data.get("extra_income"), "特別利益")
    ex_loss = _normalize_section(data.get("extra_loss"), "特別損失")

    gross_profit = int(data.get("gross_profit", rev.total - cos.total))
    operating_income = int(data.get("operating_income", gross_profit - sga.total))
    ordinary_income = int(
        data.get("ordinary_income", operating_income + no_inc.total - no_exp.total)
    )
    income_before_tax = int(
        data.get("income_before_tax", ordinary_income + ex_inc.total - ex_loss.total)
    )
    net_income = int(data.get("net_income", income_before_tax))

    tot_assets = int(data.get("total_assets", cur_a.total + fix_a.total + def_a.total))
    tot_liabs = int(data.get("total_liabilities", cur_l.total + fix_l.total))
    tot_equity = int(data.get("total_equity", eq.total + net_income))

    return NormalizedFinancialReport(
        current_assets=cur_a,
        fixed_assets=fix_a,
        deferred_assets=def_a,
        current_liabilities=cur_l,
        fixed_liabilities=fix_l,
        equity=eq,
        revenue=rev,
        cost_of_sales=cos,
        sga=sga,
        non_op_income=no_inc,
        non_op_expense=no_exp,
        extra_income=ex_inc,
        extra_loss=ex_loss,
        total_assets=tot_assets,
        total_liabilities=tot_liabs,
        total_equity=tot_equity,
        gross_profit=gross_profit,
        operating_income=operating_income,
        ordinary_income=ordinary_income,
        income_before_tax=income_before_tax,
        net_income=net_income,
    )


_COMMON_CSS = """
<style>
.fs-scope {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    color: #1f2937;
    margin: 16px 0 24px 0;
    width: 100%;
}
.fs-card {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    padding: 20px 24px;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.fs-heading {
    font-size: 1.15rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid #374151;
    letter-spacing: 0.02em;
}
.fs-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 8px;
    font-size: 0.90rem;
    line-height: 1.5;
}
.fs-name {
    text-align: left;
    color: #374151;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.fs-amount {
    text-align: right;
    font-variant-numeric: tabular-nums;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    color: #111827;
    white-space: nowrap;
    margin-left: 12px;
}
.fs-subtotal {
    border-top: 1px solid #e5e7eb;
    font-weight: 600;
    background-color: #fafafa;
    margin-top: 2px;
    margin-bottom: 6px;
}
.fs-part-total {
    border-top: 1px solid #9ca3af;
    border-bottom: 1px solid #9ca3af;
    font-weight: 700;
    background-color: #f3f4f6;
    margin-top: 8px;
    margin-bottom: 12px;
    padding: 7px 8px;
}
.fs-grand-total {
    margin-top: auto;
    background-color: #f8f9fa;
    border-top: 1px solid #374151;
    border-bottom: 3px double #1f2937;
    font-weight: 700;
    font-size: 0.98rem;
    padding: 10px 12px;
    min-height: 46px;
    box-sizing: border-box;
}

/* B/S Specific Layout */
.fs-bs-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    align-items: stretch;
}
@media (max-width: 768px) {
    .fs-bs-grid {
        grid-template-columns: 1fr;
    }
}
.fs-bs-col {
    display: flex;
    flex-direction: column;
    height: 100%;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    background-color: #ffffff;
}
.fs-bs-body {
    flex: 1 1 auto;
    padding: 14px 16px;
}
.fs-bs-part-title {
    font-size: 1.05rem;
    font-weight: 700;
    color: #1f2937;
    padding: 4px 0 8px 0;
    border-bottom: 2px solid #4b5563;
    margin-bottom: 8px;
}
.fs-bs-sec-title {
    font-size: 0.93rem;
    font-weight: 700;
    color: #374151;
    padding: 8px 4px 4px 4px;
    border-bottom: 1px solid #e5e7eb;
    margin-top: 6px;
}
.fs-bs-item:hover {
    background-color: #f9fafb;
}

/* P/L Specific Layout */
.fs-pl-sec-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #1f2937;
    padding: 10px 8px 4px 8px;
    border-bottom: 1px solid #e5e7eb;
    margin-top: 8px;
}
.fs-pl-item {
    padding-left: 28px;
}
.fs-pl-item:hover {
    background-color: #f9fafb;
}
.fs-pl-subtotal {
    padding-left: 16px;
}
.fs-pl-stage {
    background-color: #f1f5f9;
    font-weight: 700;
    font-size: 0.95rem;
    border-top: 1px solid #cbd5e1;
    border-bottom: 1px solid #cbd5e1;
    margin: 8px 0;
    padding: 8px 12px;
}
.fs-pl-net-income {
    background-color: #f8f9fa;
    border-top: 1px solid #374151;
    border-bottom: 3px double #1f2937;
    font-weight: 700;
    font-size: 1.02rem;
    margin-top: 12px;
    padding: 10px 12px;
    min-height: 46px;
    box-sizing: border-box;
}
</style>
"""


def _render_bs_section_html(sec: StatementSectionData, hide_zero: bool) -> str:
    """Render inner HTML for a single B/S section and its items."""
    out: list[str] = [
        f'<div class="fs-bs-sec-title">{html.escape(sec.title)}</div>',
    ]
    for r in sec.rows:
        if hide_zero and r.balance == 0:
            continue
        out.append(
            f'<div class="fs-row fs-bs-item">'
            f'<span class="fs-name">{html.escape(r.account_name)}</span>'
            f'<span class="fs-amount">{_format_currency(r.balance)}</span>'
            f"</div>"
        )
    out.append(
        f'<div class="fs-row fs-subtotal">'
        f'<span class="fs-name">{html.escape(sec.title)}合計</span>'
        f'<span class="fs-amount">{_format_currency(sec.total)}</span>'
        f"</div>"
    )
    return "".join(out)


def build_balance_sheet_html(
    data: FinancialReport | dict[str, Any],
    hide_zero: bool = True,
) -> str:
    """Construct complete, deterministic HTML for Balance Sheet (B/S)."""
    rpt = _normalize_report_data(data)

    # Left Column: Assets
    left_body: list[str] = [
        '<div class="fs-bs-part-title">【 資産の部 】</div>',
        _render_bs_section_html(rpt.current_assets, hide_zero),
        _render_bs_section_html(rpt.fixed_assets, hide_zero),
    ]
    if rpt.deferred_assets.total != 0 or (not hide_zero and rpt.deferred_assets.rows):
        left_body.append(_render_bs_section_html(rpt.deferred_assets, hide_zero))

    left_col = (
        '<div class="fs-bs-col">'
        f'<div class="fs-bs-body">{"".join(left_body)}</div>'
        '<div class="fs-row fs-grand-total">'
        '<span class="fs-name">資産の部 合計</span>'
        f'<span class="fs-amount">{_format_currency(rpt.total_assets)}</span>'
        "</div>"
        "</div>"
    )

    # Right Column: Liabilities & Equity
    right_body: list[str] = [
        '<div class="fs-bs-part-title">【 負債・純資産の部 】</div>',
        _render_bs_section_html(rpt.current_liabilities, hide_zero),
        _render_bs_section_html(rpt.fixed_liabilities, hide_zero),
        # Mandatory total liabilities row per requirements
        '<div class="fs-row fs-part-total">'
        '<span class="fs-name">負債の部合計</span>'
        f'<span class="fs-amount">{_format_currency(rpt.total_liabilities)}</span>'
        "</div>",
        '<div class="fs-bs-sec-title">純資産の部</div>',
    ]

    for r in rpt.equity.rows:
        if hide_zero and r.balance == 0:
            continue
        right_body.append(
            f'<div class="fs-row fs-bs-item">'
            f'<span class="fs-name">{html.escape(r.account_name)}</span>'
            f'<span class="fs-amount">{_format_currency(r.balance)}</span>'
            f"</div>"
        )

    # Display Net Income row under equity if non-zero or explicitly tracked
    if rpt.net_income != 0:
        income_label = "当期純利益" if rpt.net_income >= 0 else "当期純損失"
        right_body.append(
            f'<div class="fs-row fs-bs-item">'
            f'<span class="fs-name">{income_label}</span>'
            f'<span class="fs-amount">{_format_currency(rpt.net_income)}</span>'
            f"</div>"
        )

    right_body.append(
        f'<div class="fs-row fs-subtotal">'
        f'<span class="fs-name">純資産合計</span>'
        f'<span class="fs-amount">{_format_currency(rpt.total_equity)}</span>'
        f"</div>"
    )

    tot_liab_eq = rpt.total_liabilities + rpt.total_equity
    right_col = (
        '<div class="fs-bs-col">'
        f'<div class="fs-bs-body">{"".join(right_body)}</div>'
        '<div class="fs-row fs-grand-total">'
        '<span class="fs-name">負債・純資産の部 合計</span>'
        f'<span class="fs-amount">{_format_currency(tot_liab_eq)}</span>'
        "</div>"
        "</div>"
    )

    return (
        f"{_COMMON_CSS}"
        f'<div class="fs-scope">'
        f'<div class="fs-card">'
        f'<div class="fs-heading">貸借対照表 (Balance Sheet)</div>'
        f'<div class="fs-bs-grid">{left_col}{right_col}</div>'
        f"</div>"
        f"</div>"
    )


def _render_pl_section_html(
    sec: StatementSectionData, sec_number_label: str, hide_zero: bool
) -> str:
    """Render 1-column waterfall rows for an individual P/L section."""
    out: list[str] = [
        f'<div class="fs-pl-sec-title">{sec_number_label}</div>',
    ]
    for r in sec.rows:
        if hide_zero and r.balance == 0:
            continue
        out.append(
            f'<div class="fs-row fs-pl-item">'
            f'<span class="fs-name">{html.escape(r.account_name)}</span>'
            f'<span class="fs-amount">{_format_currency(r.balance)}</span>'
            f"</div>"
        )
    out.append(
        f'<div class="fs-row fs-subtotal fs-pl-subtotal">'
        f'<span class="fs-name">{html.escape(sec.title)}合計</span>'
        f'<span class="fs-amount">{_format_currency(sec.total)}</span>'
        f"</div>"
    )
    return "".join(out)


def build_profit_and_loss_html(
    data: FinancialReport | dict[str, Any],
    hide_zero: bool = True,
) -> str:
    """Construct complete, deterministic HTML for Profit & Loss Statement (P/L) in waterfall format."""
    rpt = _normalize_report_data(data)

    body: list[str] = [
        # 1. Revenue & 2. Cost of sales
        _render_pl_section_html(rpt.revenue, "I. 売上高", hide_zero),
        _render_pl_section_html(rpt.cost_of_sales, "II. 売上原価", hide_zero),
        # Stage Profit 1: Gross Profit
        f'<div class="fs-row fs-pl-stage">'
        f'<span class="fs-name">{"売上総利益" if rpt.gross_profit >= 0 else "売上総損失"}</span>'
        f'<span class="fs-amount">{_format_currency(rpt.gross_profit)}</span>'
        f"</div>",
        # 3. SG&A
        _render_pl_section_html(rpt.sga, "III. 販売費及び一般管理費", hide_zero),
        # Stage Profit 2: Operating Income
        f'<div class="fs-row fs-pl-stage">'
        f'<span class="fs-name">{"営業利益" if rpt.operating_income >= 0 else "営業損失"}</span>'
        f'<span class="fs-amount">{_format_currency(rpt.operating_income)}</span>'
        f"</div>",
        # 4. Non-operating Income & 5. Non-operating Expense
        _render_pl_section_html(rpt.non_op_income, "IV. 営業外収益", hide_zero),
        _render_pl_section_html(rpt.non_op_expense, "V. 営業外費用", hide_zero),
        # Stage Profit 3: Ordinary Income
        f'<div class="fs-row fs-pl-stage">'
        f'<span class="fs-name">{"経常利益" if rpt.ordinary_income >= 0 else "経常損失"}</span>'
        f'<span class="fs-amount">{_format_currency(rpt.ordinary_income)}</span>'
        f"</div>",
        # 6. Extraordinary Income & 7. Extraordinary Loss
        _render_pl_section_html(rpt.extra_income, "VI. 特別利益", hide_zero),
        _render_pl_section_html(rpt.extra_loss, "VII. 特別損失", hide_zero),
        # Stage Profit 4: Income before income taxes
        f'<div class="fs-row fs-pl-stage">'
        f'<span class="fs-name">{"税引前当期純利益" if rpt.income_before_tax >= 0 else "税引前当期純損失"}</span>'
        f'<span class="fs-amount">{_format_currency(rpt.income_before_tax)}</span>'
        f"</div>",
        # Stage Profit 5: Net Income (Final Double-Underline)
        f'<div class="fs-row fs-pl-net-income">'
        f'<span class="fs-name">{"当期純利益" if rpt.net_income >= 0 else "当期純損失"}</span>'
        f'<span class="fs-amount">{_format_currency(rpt.net_income)}</span>'
        f"</div>",
    ]

    return (
        f"{_COMMON_CSS}"
        f'<div class="fs-scope">'
        f'<div class="fs-card">'
        f'<div class="fs-heading">損益計算書 (Profit & Loss Statement)</div>'
        f'<div class="fs-pl-table">{"".join(body)}</div>'
        f"</div>"
        f"</div>"
    )


def render_balance_sheet(
    report: FinancialReport | dict[str, Any],
    hide_zero: bool = True,
) -> None:
    """Render Balance Sheet (B/S) component directly in Streamlit."""
    html_content = build_balance_sheet_html(report, hide_zero=hide_zero)
    st.markdown(html_content, unsafe_allow_html=True)


def render_profit_and_loss(
    report: FinancialReport | dict[str, Any],
    hide_zero: bool = True,
) -> None:
    """Render Profit and Loss (P/L) component in vertical waterfall format directly in Streamlit."""
    html_content = build_profit_and_loss_html(report, hide_zero=hide_zero)
    st.markdown(html_content, unsafe_allow_html=True)
