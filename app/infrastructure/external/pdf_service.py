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

from datetime import date
import io
from typing import Optional
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from app.config import settings
from app.domain.models.corporation import Corporation
from app.domain.models.financial_report import FinancialReport, FinancialSection
from app.domain.models.fiscal_year import FiscalYear


class PDFService:
    @staticmethod
    def _register_font():
        if settings.FONT_PATH and settings.FONT_PATH.exists():
            try:
                pdfmetrics.registerFont(
                    TTFont(settings.FONT_NAME, str(settings.FONT_PATH))
                )
            except Exception:
                pass
        elif settings.FONT_NAME == "HeiseiMin-W3":
            try:
                from reportlab.pdfbase import cidfonts

                pdfmetrics.registerFont(cidfonts.UnicodeCIDFont("HeiseiMin-W3"))
            except Exception:
                pass

    @staticmethod
    def generate_annual_report(
        corp: Corporation,
        rpt: FinancialReport,
        fiscal_year: FiscalYear,
        report_date: date,
        audit_date: date,
    ) -> bytes:
        PDFService._register_font()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4, pdfVersion=(1, 4))
        c.setTitle(f"Annual Report - {corp.name} - {fiscal_year.name}")
        c.setAuthor(corp.name)
        c.setCreator(settings.APP_TITLE)

        w, h = A4
        mx = 20 * mm

        def draw_hdr(title: str, sub: Optional[str] = None):
            c.setFont(settings.FONT_NAME, 14)
            c.drawCentredString(w / 2, h - 20 * mm, title)
            c.setFont(settings.FONT_NAME, 10)
            if sub:
                c.drawCentredString(w / 2, h - 26 * mm, sub)
            c.line(mx, h - 30 * mm, w - mx, h - 30 * mm)

        period = (
            f"第 {fiscal_year.period_number} 期"
            if fiscal_year.period_number
            else fiscal_year.name
        )
        drange = f"自 {fiscal_year.start_date.strftime('%Y年%m月%d日')}　至 {fiscal_year.end_date.strftime('%Y年%m月%d日')}"

        # 1. 表紙
        c.setFont(settings.FONT_NAME, 24)
        c.drawCentredString(w / 2, h / 2 + 40 * mm, "決算報告書")
        c.setFont(settings.FONT_NAME, 16)
        c.drawCentredString(w / 2, h / 2 + 20 * mm, period)
        c.setFont(settings.FONT_NAME, 12)
        c.drawCentredString(
            w / 2,
            h / 2 + 10 * mm,
            f"自　{fiscal_year.start_date.strftime('%Y年%m月%d日')}",
        )
        c.drawCentredString(
            w / 2, h / 2, f"至　{fiscal_year.end_date.strftime('%Y年%m月%d日')}"
        )
        c.setFont(settings.FONT_NAME, 18)
        c.drawCentredString(w / 2, h / 2 - 60 * mm, corp.name)
        if corp.address:
            c.setFont(settings.FONT_NAME, 11)
            c.drawCentredString(w / 2, h / 2 - 80 * mm, corp.address)
        c.showPage()

        # 2. B/S
        draw_hdr("貸借対照表 (Balance Sheet)", drange)
        y = h - 40 * mm

        def draw_bs_sec(sec: FinancialSection, lbl: str, val: int, cy: float) -> float:
            c.setFont(settings.FONT_NAME, 11)
            is_a = "負債" not in sec.title and "純資産" not in sec.title
            xt, xl, xv = (
                (30 * mm, 35 * mm, 100 * mm) if is_a else (110 * mm, 115 * mm, 180 * mm)
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
            return cy - 10 * mm

        yl = draw_bs_sec(
            rpt.current_assets, "流動資産合計", rpt.current_assets.total, y - 6 * mm
        )
        yl = draw_bs_sec(rpt.fixed_assets, "固定資産合計", rpt.fixed_assets.total, yl)
        if rpt.deferred_assets.total > 0:
            yl = draw_bs_sec(
                rpt.deferred_assets, "繰延資産合計", rpt.deferred_assets.total, yl
            )
        c.line(35 * mm, yl + 2, 100 * mm, yl + 2)
        c.drawString(35 * mm, yl - 6 * mm, "資産合計")
        c.drawRightString(100 * mm, yl - 6 * mm, f"{rpt.total_assets:,}")

        yr = draw_bs_sec(
            rpt.current_liabilities,
            "流動負債合計",
            rpt.current_liabilities.total,
            y - 6 * mm,
        )
        yr = draw_bs_sec(
            rpt.fixed_liabilities, "固定負債合計", rpt.fixed_liabilities.total, yr
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
        c.drawString(115 * mm, yr, "当期純利益")
        c.drawRightString(180 * mm, yr, f"{rpt.net_income:,}")
        yr -= 7 * mm
        c.line(115 * mm, yr, 180 * mm, yr)
        c.drawString(115 * mm, yr - 8 * mm, "純資産合計")
        c.drawRightString(180 * mm, yr - 8 * mm, f"{rpt.total_equity:,}")
        yr -= 18 * mm
        c.setFont(settings.FONT_NAME, 11)
        c.drawString(115 * mm, yr, "負債・純資産合計")
        c.drawRightString(180 * mm, yr, f"{rpt.total_liabilities + rpt.total_equity:,}")
        c.showPage()

        # 3. P/L
        draw_hdr("損益計算書 (Profit & Loss)", drange)
        y, xl, xv = h - 40 * mm, 30 * mm, 170 * mm

        def draw_pl_sec(sec: FinancialSection):
            nonlocal y
            c.setFont(settings.FONT_NAME, 11)
            c.drawString(xl - 5 * mm, y, sec.title)
            y -= 6 * mm
            c.setFont(settings.FONT_NAME, 10)
            for r in sec.rows:
                if r.balance != 0:
                    c.drawString(xl + 5 * mm, y, r.account_name)
                    c.drawRightString(xv - 10 * mm, y, f"{r.balance:,}")
                    y -= 5 * mm
            c.drawString(
                xl + 5 * mm, y, f"{sec.title.replace('【', '').replace('】', '')} 合計"
            )
            c.drawRightString(xv, y, f"{sec.total:,}")
            y -= 8 * mm

        def draw_pl_step(title: str, val: int):
            nonlocal y
            c.setFont(settings.FONT_NAME, 11)
            c.drawString(xl, y, title)
            c.drawRightString(xv, y, f"{val:,}")
            y -= 10 * mm

        draw_pl_sec(rpt.revenue)
        draw_pl_sec(rpt.cost_of_sales)
        draw_pl_step("売上総利益", rpt.gross_profit)
        draw_pl_sec(rpt.sga)
        draw_pl_step("営業利益", rpt.operating_income)

        if y < 60 * mm:
            c.showPage()
            draw_hdr("損益計算書 (続)")
            y = h - 40 * mm

        draw_pl_sec(rpt.non_op_income)
        draw_pl_sec(rpt.non_op_expense)
        draw_pl_step("経常利益", rpt.ordinary_income)
        draw_pl_sec(rpt.extra_income)
        draw_pl_sec(rpt.extra_loss)
        draw_pl_step("税引前当期純利益", rpt.income_before_tax)
        c.showPage()

        # 4. 附属明細書
        draw_hdr("附属明細書")
        y = h - 40 * mm

        def draw_dtl(sec: FinancialSection):
            nonlocal y
            c.setFont(settings.FONT_NAME, 11)
            c.drawString(
                30 * mm, y, f"{sec.title.replace('【', '').replace('】', '')} 明細"
            )
            y -= 6 * mm
            c.setFont(settings.FONT_NAME, 10)
            pos_rows = [r for r in sec.rows if r.balance > 0]
            if not pos_rows:
                c.drawString(35 * mm, y, "(該当なし)")
                y -= 8 * mm
                return
            for r in pos_rows:
                c.drawString(35 * mm, y, r.account_name)
                c.drawRightString(150 * mm, y, f"{r.balance:,}")
                y -= 5 * mm
            y -= 2 * mm
            c.line(35 * mm, y, 150 * mm, y)
            c.drawString(35 * mm, y - 6 * mm, "合計")
            c.drawRightString(150 * mm, y - 6 * mm, f"{sec.total:,}")
            y -= 18 * mm

        draw_dtl(rpt.sga)
        draw_dtl(rpt.cost_of_sales)
        c.showPage()

        # 5. 署名
        y = h - 40 * mm
        c.line(mx, y, w - mx, y)
        c.setFont(settings.FONT_NAME, 11)
        c.drawString(30 * mm, y - 10 * mm, "上記の通りご報告申し上げます。")
        c.drawString(
            30 * mm, y - 20 * mm, f"報告日：{report_date.strftime('%Y年%m月%d日')}"
        )
        c.setFont(settings.FONT_NAME, 12)
        c.drawString(30 * mm, y - 30 * mm, corp.name)
        if corp.representative_title and corp.representative_name:
            c.drawString(
                30 * mm,
                y - 38 * mm,
                f"{corp.representative_title}  {corp.representative_name}",
            )
        c.setFont(settings.FONT_NAME, 11)
        c.drawString(
            30 * mm, y - 63 * mm, "監査の結果、適法かつ正確なることを認めます。"
        )
        c.drawString(
            30 * mm, y - 73 * mm, f"監査日：{audit_date.strftime('%Y年%m月%d日')}"
        )

        c.save()
        buffer.seek(0)
        return buffer.getvalue()
