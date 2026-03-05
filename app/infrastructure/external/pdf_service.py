from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from datetime import date
import io

from config import FONT_PATH, FONT_NAME, APP_TITLE
from domain.models.corporation import Corporation
from domain.models.financial_report import FinancialReport

class PDFService:
    @staticmethod
    def _register_font():
        if FONT_PATH and FONT_PATH.exists():
            try:
                # Use a unique name to avoid registration errors if called multiple times in some contexts
                # or just try/except
                pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))
            except Exception:
                pass # Already registered or error
        elif FONT_NAME == "HeiseiMin-W3":
            try:
                from reportlab.pdfbase import cidfonts
                pdfmetrics.registerFont(cidfonts.UnicodeCIDFont("HeiseiMin-W3"))
            except Exception:
                pass # Fallback or already registered

 

    @staticmethod
    def generate_annual_report(corp: Corporation, rpt: FinancialReport, fy_full_obj, report_date: date, audit_date: date) -> bytes:
        PDFService._register_font()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4, pdfVersion=(1, 4))
        
        # PDF/A Metadata
        c.setTitle(f"Annual Report - {corp.name} - {fy_full_obj.name}")
        c.setAuthor(corp.name)
        c.setCreator(APP_TITLE)
        
        width, height = A4
        margin_x = 20 * mm
        
        def draw_header(title, subtitle=None):
            c.setFont(FONT_NAME, 14)
            c.drawCentredString(width / 2, height - 20 * mm, title)
            c.setFont(FONT_NAME, 10)
            if subtitle:
                c.drawCentredString(width / 2, height - 26 * mm, subtitle)
            c.line(margin_x, height - 30 * mm, width - margin_x, height - 30 * mm)

        # --- COVER ---
        c.setFont(FONT_NAME, 24)
        c.drawCentredString(width / 2, height / 2 + 40 * mm, "決算報告書")
        
        c.setFont(FONT_NAME, 16)
        period_text = f"第 {fy_full_obj.period_number} 期" if fy_full_obj.period_number else fy_full_obj.name
        c.drawCentredString(width / 2, height / 2 + 20 * mm, period_text)
        
        c.setFont(FONT_NAME, 12)
        date_range = f"自 {fy_full_obj.start_date.strftime('%Y年%m月%d日')}　至 {fy_full_obj.end_date.strftime('%Y年%m月%d日')}"
        
        c.drawCentredString(width / 2, height / 2 + 10 * mm, f"自　{fy_full_obj.start_date.strftime('%Y年%m月%d日')}")
        c.drawCentredString(width / 2, height / 2 + 0 * mm, f"至　{fy_full_obj.end_date.strftime('%Y年%m月%d日')}")
        
        c.setFont(FONT_NAME, 18)
        c.drawCentredString(width / 2, height / 2 - 60 * mm, corp.name)
        
        if corp.address:
            c.setFont(FONT_NAME, 11)
            c.drawCentredString(width / 2, height / 2 - 80 * mm, corp.address)
            
        c.showPage()
        
        # --- BS ---
        draw_header("貸借対照表 (Balance Sheet)", date_range)
        y = height - 40 * mm
        
        def draw_bs_section(section, total_label, total_val, current_y):
            c.setFont(FONT_NAME, 11)
            # Assets vs Liabilities layout logic
            is_assets = "負債" not in section.title and "純資産" not in section.title
            x_title = 30 * mm if is_assets else 110 * mm
            c.drawString(x_title, current_y, section.title)
            current_y -= 8 * mm
            
            x_label = 35 * mm if is_assets else 115 * mm
            x_val = 100 * mm if is_assets else 180 * mm
            
            c.setFont(FONT_NAME, 10)
            for r in section.rows:
                if r.balance != 0:
                    c.drawString(x_label, current_y, r.account_name)
                    c.drawRightString(x_val, current_y, f"{r.balance:,}")
                    current_y -= 5 * mm
            
            current_y -= 2 * mm
            c.line(x_label, current_y, x_val, current_y)
            current_y -= 8 * mm
            c.drawString(x_label, current_y, total_label)
            c.drawRightString(x_val, current_y, f"{total_val:,}")
            
            return current_y - 10 * mm

        # Assets
        y_left = y
        c.setFont(FONT_NAME, 11)
        c.drawString(30 * mm, y_left, "【資産の部】")
        y_left -= 6 * mm
        
        y_left = draw_bs_section(rpt.current_assets, "流動資産合計", rpt.current_assets.total, y_left)
        y_left = draw_bs_section(rpt.fixed_assets, "固定資産合計", rpt.fixed_assets.total, y_left)
        if rpt.deferred_assets.total > 0:
             y_left = draw_bs_section(rpt.deferred_assets, "繰延資産合計", rpt.deferred_assets.total, y_left)
             
        c.line(35 * mm, y_left+2, 100 * mm, y_left+2)
        y_left -= 6 * mm
        c.drawString(35 * mm, y_left, "資産合計")
        c.drawRightString(100 * mm, y_left, f"{rpt.total_assets:,}")
        
        # Liabilities
        y_right = y
        c.setFont(FONT_NAME, 11)
        c.drawString(110 * mm, y_right, "【負債の部】")
        y_right -= 6 * mm
        
        y_right = draw_bs_section(rpt.current_liabilities, "流動負債合計", rpt.current_liabilities.total, y_right)
        y_right = draw_bs_section(rpt.fixed_liabilities, "固定負債合計", rpt.fixed_liabilities.total, y_right)
        
        c.line(115 * mm, y_right+2, 180 * mm, y_right+2)
        y_right -= 6 * mm
        c.drawString(115 * mm, y_right, "負債合計")
        c.drawRightString(180 * mm, y_right, f"{rpt.total_liabilities:,}")
        y_right -= 12 * mm
        
        # Equity
        c.setFont(FONT_NAME, 11)
        c.drawString(110 * mm, y_right, "【純資産の部】")
        y_right -= 6 * mm
        
        c.setFont(FONT_NAME, 10)
        for r in rpt.equity.rows:
             if r.balance != 0:
                c.drawString(115 * mm, y_right, r.account_name)
                c.drawRightString(180 * mm, y_right, f"{r.balance:,}")
                y_right -= 5 * mm
        
        c.drawString(115 * mm, y_right, "当期純利益")
        c.drawRightString(180 * mm, y_right, f"{rpt.net_income:,}")
        y_right -= 5 * mm
        
        y_right -= 2 * mm
        c.line(115 * mm, y_right, 180 * mm, y_right)
        y_right -= 8 * mm
        c.drawString(115 * mm, y_right, "純資産合計")
        c.drawRightString(180 * mm, y_right, f"{rpt.total_equity:,}")
        y_right -= 10 * mm
        
        c.setFont(FONT_NAME, 11)
        c.drawString(115 * mm, y_right, "負債・純資産合計")
        c.drawRightString(180 * mm, y_right, f"{rpt.total_liabilities + rpt.total_equity:,}")
        
        c.showPage()
        
        # --- PL ---
        draw_header("損益計算書 (Profit & Loss)", date_range)
        y = height - 40 * mm
        x_label = 30 * mm
        x_val = 170 * mm
        
        def draw_pl_section_obj(section):
            nonlocal y
            c.setFont(FONT_NAME, 11)
            c.drawString(x_label - 5*mm, y, section.title)
            y -= 6 * mm
            
            c.setFont(FONT_NAME, 10)
            for r in section.rows:
                if r.balance != 0:
                    c.drawString(x_label + 5*mm, y, r.account_name)
                    c.drawRightString(x_val - 10*mm, y, f"{r.balance:,}")
                    y -= 5 * mm
            
            c.drawString(x_label + 5*mm, y, f"{section.title.replace('【','').replace('】','')} 合計")
            c.drawRightString(x_val, y, f"{section.total:,}")
            y -= 8 * mm

        draw_pl_section_obj(rpt.revenue)
        draw_pl_section_obj(rpt.cost_of_sales)
        
        c.setFont(FONT_NAME, 11)
        c.drawString(x_label, y, "売上総利益")
        c.drawRightString(x_val, y, f"{rpt.gross_profit:,}")
        y -= 10 * mm
        
        draw_pl_section_obj(rpt.sga)
        
        c.setFont(FONT_NAME, 11)
        c.drawString(x_label, y, "営業利益")
        c.drawRightString(x_val, y, f"{rpt.operating_income:,}")
        y -= 10 * mm
        
        if y < 60 * mm: 
            c.showPage()
            draw_header("損益計算書 (続)")
            y = height - 40 * mm

        draw_pl_section_obj(rpt.non_op_income)
        draw_pl_section_obj(rpt.non_op_expense)
        
        c.setFont(FONT_NAME, 11)
        c.drawString(x_label, y, "経常利益")
        c.drawRightString(x_val, y, f"{rpt.ordinary_income:,}")
        y -= 10 * mm
        
        draw_pl_section_obj(rpt.extra_income)
        draw_pl_section_obj(rpt.extra_loss)
        
        c.setFont(FONT_NAME, 11)
        c.drawString(x_label, y, "税引前当期純利益")
        c.drawRightString(x_val, y, f"{rpt.income_before_tax:,}")
        
        c.showPage()
        
        # --- DETAILS ---
        draw_header("附属明細書")
        y = height - 40 * mm
        
        def draw_detail_table(section):
            nonlocal y
            c.setFont(FONT_NAME, 11)
            c.drawString(30 * mm, y, f"{section.title.replace('【','').replace('】','')} 明細")
            y -= 6 * mm
            
            has_rows = any(r.balance > 0 for r in section.rows)
            
            if not has_rows:
                c.setFont(FONT_NAME, 10)
                c.drawString(35 * mm, y, "(該当なし)")
                y -= 8 * mm
                return

            c.setFont(FONT_NAME, 10)
            for r in section.rows:
                if r.balance > 0:
                    c.drawString(35 * mm, y, r.account_name)
                    c.drawRightString(150 * mm, y, f"{r.balance:,}")
                    y -= 5 * mm
            
            y -= 2 * mm
            c.line(35*mm, y, 150*mm, y)
            y -= 6 * mm
            c.drawString(35 * mm, y, "合計")
            c.drawRightString(150 * mm, y, f"{section.total:,}")
            y -= 12 * mm

        draw_detail_table(rpt.sga)
        draw_detail_table(rpt.cost_of_sales)
        
        c.showPage()
        
        # --- SIGNATURES ---
        y = height - 40 * mm
        
        c.line(margin_x, y, width - margin_x, y)
        y -= 10 * mm
        
        c.setFont(FONT_NAME, 11)
        c.drawString(30 * mm, y, "上記の通りご報告申し上げます。")
        y -= 10 * mm
        
        c.drawString(30 * mm, y, f"報告日：{report_date.strftime('%Y年%m月%d日')}")
        y -= 10 * mm
        
        c.setFont(FONT_NAME, 12)
        c.drawString(30 * mm, y, corp.name)
        y -= 8 * mm
        
        if corp.representative_title and corp.representative_name:
             c.drawString(30 * mm, y, f"{corp.representative_title}  {corp.representative_name}")
             
        y -= 25 * mm
        c.setFont(FONT_NAME, 11)
        c.drawString(30 * mm, y, "監査の結果、適法かつ正確なることを認めます。")
        y -= 10 * mm
        c.drawString(30 * mm, y, f"監査日：{audit_date.strftime('%Y年%m月%d日')}")
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
