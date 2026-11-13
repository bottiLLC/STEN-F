# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Statutory Japanese financial statement PDF generation service using ReportLab."""

from __future__ import annotations

from datetime import date
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core_foundation import settings
from app.domain_contracts import (
    Corporation,
    FinancialReport,
    FinancialSection,
    FiscalYear,
)


def _register_reportlab_fonts() -> None:
    """Register Japanese font glyph metrics with ReportLab."""
    if settings.FONT_PATH and settings.FONT_PATH.exists():
        try:
            pdfmetrics.registerFont(TTFont(settings.FONT_NAME, str(settings.FONT_PATH)))
        except Exception:
            pass
    elif settings.FONT_NAME == "HeiseiMin-W3":
        try:
            from reportlab.pdfbase import cidfonts

            pdfmetrics.registerFont(cidfonts.UnicodeCIDFont("HeiseiMin-W3"))
        except Exception:
            pass


def _draw_pdf_header(
    c: canvas.Canvas,
    w: float,
    h: float,
    mx: float,
    period_number: int,
    subtitle: str,
    drange: str = "",
) -> None:
    """Draw shared statutory header and divider line on an A4 PDF page."""
    c.setFont(settings.FONT_NAME, 16)
    c.drawCentredString(w / 2, h - 25 * mm, f"第{period_number}期 決算報告書")
    c.setFont(settings.FONT_NAME, 12)
    c.drawCentredString(w / 2, h - 32 * mm, subtitle)
    if drange:
        c.setFont(settings.FONT_NAME, 9)
        c.drawRightString(w - mx, h - 33 * mm, drange)
    c.setLineWidth(0.5)
    c.line(mx, h - 35 * mm, w - mx, h - 35 * mm)


def _draw_cover_page(
    c: canvas.Canvas,
    w: float,
    h: float,
    period_number: int,
    drange: str,
    corp: Corporation,
) -> None:
    """Render report cover page with period range and corporate signatory."""
    c.setFont(settings.FONT_NAME, 24)
    c.drawCentredString(w / 2, h - 90 * mm, f"第{period_number}期 決算報告書")
    c.setFont(settings.FONT_NAME, 12)
    c.drawCentredString(w / 2, h - 105 * mm, drange)
    c.setFont(settings.FONT_NAME, 16)
    c.drawCentredString(w / 2, h - 150 * mm, corp.name)
    if corp.representative_title and corp.representative_name:
        c.setFont(settings.FONT_NAME, 12)
        c.drawCentredString(
            w / 2,
            h - 160 * mm,
            f"{corp.representative_title}  {corp.representative_name}",
        )
    c.showPage()


def _draw_bs_section(
    c: canvas.Canvas,
    sec: FinancialSection,
    lbl: str,
    val: int,
    cy: float,
) -> float:
    """Draw one Balance Sheet section block and return updated Y cursor."""
    c.setFont(settings.FONT_NAME, 11)
    is_asset = "負債" not in sec.title and "純資産" not in sec.title
    xt, xl, xv = (
        (30 * mm, 35 * mm, 100 * mm) if is_asset else (110 * mm, 115 * mm, 180 * mm)
    )
    c.drawString(xt, cy, sec.title)
    cy -= 8 * mm
    c.setFont(settings.FONT_NAME, 10)
    for r in sec.rows:
        if r.balance != 0:
            c.drawString(xl, cy, r.account_name)
            c.drawRightString(xv, cy, f"{r.balance:,}")
            cy -= 5 * mm
    cy -= 2 * mm
    c.line(xl, cy, xv, cy)
    cy -= 8 * mm
    c.drawString(xl, cy, lbl)
    c.drawRightString(xv, cy, f"{val:,}")
    return float(cy - 10 * mm)


def _draw_balance_sheet_page(
    c: canvas.Canvas,
    w: float,
    h: float,
    mx: float,
    rpt: FinancialReport,
    period_number: int,
    drange: str,
) -> None:
    """Render side-by-side Balance Sheet page with aligned liability-equity total."""
    _draw_pdf_header(c, w, h, mx, period_number, "貸借対照表 (Balance Sheet)", drange)
    y = h - 40 * mm

    yl = _draw_bs_section(
        c, rpt.current_assets, "流動資産合計", rpt.current_assets.total, y - 6 * mm
    )
    yl = _draw_bs_section(
        c, rpt.fixed_assets, "固定資産合計", rpt.fixed_assets.total, yl
    )
    if rpt.deferred_assets.total != 0:
        yl = _draw_bs_section(
            c, rpt.deferred_assets, "繰延資産合計", rpt.deferred_assets.total, yl
        )

    yr = _draw_bs_section(
        c,
        rpt.current_liabilities,
        "流動負債合計",
        rpt.current_liabilities.total,
        y - 6 * mm,
    )
    yr = _draw_bs_section(
        c, rpt.fixed_liabilities, "固定負債合計", rpt.fixed_liabilities.total, yr
    )
    c.line(115 * mm, yr + 2, 180 * mm, yr + 2)
    c.drawString(115 * mm, yr - 6 * mm, "負債合計")
    c.drawRightString(180 * mm, yr - 6 * mm, f"{rpt.total_liabilities:,}")
    yr -= 18 * mm

    c.setFont(settings.FONT_NAME, 11)
    c.drawString(110 * mm, yr, "【純資産の部】")
    yr -= 6 * mm
    c.setFont(settings.FONT_NAME, 10)
    for r in rpt.equity.rows:
        if r.balance != 0:
            c.drawString(115 * mm, yr, r.account_name)
            c.drawRightString(180 * mm, yr, f"{r.balance:,}")
            yr -= 5 * mm
    income_label = "当期純利益" if rpt.net_income >= 0 else "当期純損失"
    c.drawString(115 * mm, yr, income_label)
    c.drawRightString(180 * mm, yr, f"{rpt.net_income:,}")
    yr -= 7 * mm
    c.line(115 * mm, yr, 180 * mm, yr)
    c.drawString(115 * mm, yr - 8 * mm, "純資産合計")
    c.drawRightString(180 * mm, yr - 8 * mm, f"{rpt.total_equity:,}")

    # Enforce bottom alignment (equal visual height) between Assets and Liabilities/Equity
    grand_total_y = min(yl - 6 * mm, yr - 26 * mm)
    rule_y = grand_total_y + 6 * mm
    c.setFont(settings.FONT_NAME, 11)
    c.line(35 * mm, rule_y, 100 * mm, rule_y)
    c.drawString(35 * mm, grand_total_y, "資産合計")
    c.drawRightString(100 * mm, grand_total_y, f"{rpt.total_assets:,}")
    c.line(115 * mm, rule_y, 180 * mm, rule_y)
    c.drawString(115 * mm, grand_total_y, "負債・純資産合計")
    c.drawRightString(
        180 * mm, grand_total_y, f"{rpt.total_liabilities + rpt.total_equity:,}"
    )
    c.showPage()


def _draw_profit_and_loss_pages(
    c: canvas.Canvas,
    w: float,
    h: float,
    mx: float,
    rpt: FinancialReport,
    period_number: int,
    drange: str,
) -> None:
    """Render vertical waterfall Profit and Loss pages with automatic page breaks."""
    _draw_pdf_header(c, w, h, mx, period_number, "損益計算書 (Profit & Loss)", drange)
    y, xl, xv = h - 32 * mm, 30 * mm, 170 * mm

    def ensure_space(required_mm: float) -> None:
        nonlocal y
        if y - required_mm < 22 * mm:
            c.showPage()
            _draw_pdf_header(c, w, h, mx, period_number, "損益計算書 (続)", drange)
            y = h - 32 * mm

    def draw_pl_sec(sec: FinancialSection) -> None:
        nonlocal y
        active_rows = [r for r in sec.rows if r.balance != 0]
        sec_height = 5 * mm + (len(active_rows) * 4.2 * mm) + 5.5 * mm
        ensure_space(sec_height)

        c.setFont(settings.FONT_NAME, 10.5)
        c.drawString(xl - 5 * mm, y, sec.title)
        y -= 5 * mm
        c.setFont(settings.FONT_NAME, 9.5)
        for r in active_rows:
            c.drawString(xl + 5 * mm, y, r.account_name)
            c.drawRightString(xv - 10 * mm, y, f"{r.balance:,}")
            y -= 4.2 * mm
        c.drawString(
            xl + 5 * mm, y, f"{sec.title.replace('【', '').replace('】', '')} 合計"
        )
        c.drawRightString(xv, y, f"{sec.total:,}")
        y -= 5.5 * mm

    def draw_pl_step(title: str, val: int) -> None:
        nonlocal y
        ensure_space(7.5 * mm)
        c.setFont(settings.FONT_NAME, 10.5)
        c.drawString(xl, y, title)
        c.drawRightString(xv, y, f"{val:,}")
        y -= 6.5 * mm

    draw_pl_sec(rpt.revenue)
    draw_pl_sec(rpt.cost_of_sales)
    draw_pl_step(
        "売上総利益" if rpt.gross_profit >= 0 else "売上総損失",
        rpt.gross_profit,
    )
    draw_pl_sec(rpt.sga)
    draw_pl_step(
        "営業利益" if rpt.operating_income >= 0 else "営業損失",
        rpt.operating_income,
    )
    draw_pl_sec(rpt.non_op_income)
    draw_pl_sec(rpt.non_op_expense)
    draw_pl_step(
        "経常利益" if rpt.ordinary_income >= 0 else "経常損失",
        rpt.ordinary_income,
    )
    draw_pl_sec(rpt.extra_income)
    draw_pl_sec(rpt.extra_loss)
    draw_pl_step(
        "税引前当期純利益" if rpt.income_before_tax >= 0 else "税引前当期純損失",
        rpt.income_before_tax,
    )
    draw_pl_sec(rpt.taxes)
    draw_pl_step(
        "当期純利益" if rpt.net_income >= 0 else "当期純損失",
        rpt.net_income,
    )
    c.showPage()


def _draw_supporting_schedules_page(
    c: canvas.Canvas,
    w: float,
    h: float,
    mx: float,
    rpt: FinancialReport,
    period_number: int,
) -> None:
    """Render supporting schedules for SG&A and Cost of Sales."""
    _draw_pdf_header(c, w, h, mx, period_number, "附属明細書")
    y = h - 40 * mm

    for sec in (rpt.sga, rpt.cost_of_sales):
        c.setFont(settings.FONT_NAME, 11)
        c.drawString(
            30 * mm, y, f"{sec.title.replace('【', '').replace('】', '')} 明細"
        )
        y -= 6 * mm
        c.setFont(settings.FONT_NAME, 10)
        active_rows = [r for r in sec.rows if r.balance != 0]
        if not active_rows:
            c.drawString(35 * mm, y, "(該当なし)")
            y -= 8 * mm
            continue
        for r in active_rows:
            c.drawString(35 * mm, y, r.account_name)
            c.drawRightString(150 * mm, y, f"{r.balance:,}")
            y -= 5 * mm
        y -= 2 * mm
        c.line(35 * mm, y, 150 * mm, y)
        c.drawString(35 * mm, y - 6 * mm, "合計")
        c.drawRightString(150 * mm, y - 6 * mm, f"{sec.total:,}")
        y -= 18 * mm
    c.showPage()


def _draw_signature_page(
    c: canvas.Canvas,
    w: float,
    mx: float,
    h: float,
    corp: Corporation,
    rep_date: date,
    aud_date: date,
) -> None:
    """Render corporate report attestation and audit signature page."""
    y = h - 40 * mm
    c.line(mx, y, w - mx, y)
    c.setFont(settings.FONT_NAME, 11)
    c.drawString(30 * mm, y - 10 * mm, "上記の通りご報告申し上げます。")
    c.drawString(30 * mm, y - 20 * mm, f"報告日：{rep_date.strftime('%Y年%m月%d日')}")
    c.setFont(settings.FONT_NAME, 12)
    c.drawString(30 * mm, y - 30 * mm, corp.name)
    if corp.representative_title and corp.representative_name:
        c.drawString(
            30 * mm,
            y - 38 * mm,
            f"{corp.representative_title}  {corp.representative_name}",
        )
    c.setFont(settings.FONT_NAME, 11)
    c.drawString(30 * mm, y - 63 * mm, "監査の結果、適法かつ正確なることを認めます。")
    c.drawString(30 * mm, y - 73 * mm, f"監査日：{aud_date.strftime('%Y年%m月%d日')}")


class PDFService:
    """Service rendering statutory Japanese financial statements using ReportLab."""

    @staticmethod
    def generate_annual_report(
        corp: Corporation,
        rpt: FinancialReport,
        fy: FiscalYear | None = None,
        report_date: date | None = None,
        audit_date: date | None = None,
    ) -> bytes:
        """Synthesize A4 PDF annual financial statements.

        Args:
            corp: Legal entity corporation metadata.
            rpt: Computed financial statement totals and sections.
            fy: Active fiscal period metadata.
            report_date: Report issuance date.
            audit_date: Statutory audit completion date.

        Returns:
            Raw PDF bytes stream.
        """
        target_fy: FiscalYear = fy if fy is not None else rpt.fiscal_year
        rep_date: date = report_date if report_date is not None else date.today()
        aud_date: date = audit_date if audit_date is not None else rep_date
        period_number = target_fy.period_number or 1
        drange = f"自 {target_fy.start_date.strftime('%Y年%m月%d日')}  至 {target_fy.end_date.strftime('%Y年%m月%d日')}"

        _register_reportlab_fonts()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        w, h = A4
        mx = 20 * mm

        _draw_cover_page(c, w, h, period_number, drange, corp)
        _draw_balance_sheet_page(c, w, h, mx, rpt, period_number, drange)
        _draw_profit_and_loss_pages(c, w, h, mx, rpt, period_number, drange)
        _draw_supporting_schedules_page(c, w, h, mx, rpt, period_number)
        _draw_signature_page(c, w, mx, h, corp, rep_date, aud_date)

        c.save()
        buffer.seek(0)
        return buffer.getvalue()
