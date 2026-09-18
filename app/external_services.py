# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import asyncio
from datetime import date, datetime
import io
from pathlib import Path
import shutil
import aiofiles
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core_foundation import log, settings
from app.domain_contracts import (
    Corporation,
    FinancialReport,
    FinancialSection,
    FiscalYear,
)


# --- 1. Datum Plane & Pure Transformations ---
def _sanitize_file_name(text: str) -> str:
    """Sanitize filename to alphanumeric and safe delimiter characters.

    Args:
        text: Raw filename or description string.

    Returns:
        Cleaned filename string.
    """
    return "".join(c for c in text if c.isalnum() or c in " _-").strip()


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


# --- 2. Public Orchestration Layer ---
class LocalFileService:
    """Service persisting local evidence documents with statutory naming standards."""

    def __init__(self, base_dir: Path = settings.PROJECT_ROOT) -> None:
        """Initialize and verify local storage directory.

        Args:
            base_dir: Base directory path anchoring storage directory.
        """
        self.storage_dir = base_dir / "storage"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def save_evidence(
        self,
        file_bytes: bytes,
        original_filename: str,
        date_obj: date,
        description: str,
        amount: int,
    ) -> str:
        """Persist evidence file with date, description, and amount tags.

        Args:
            file_bytes: Raw binary file payload.
            original_filename: Name of source document uploaded.
            date_obj: Transaction date.
            description: Summary of transaction.
            amount: Integer total amount.

        Returns:
            Saved absolute or anchored filesystem path string.
        """
        ext = Path(original_filename).suffix or ".pdf"
        save_path = (
            self.storage_dir
            / f"{date_obj}_{_sanitize_file_name(description)}_{amount}{ext}"
        )
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
        return str(save_path)

    async def save_evidence_for_transaction(
        self,
        file_bytes: bytes,
        transaction_id: int,
        date_obj: date,
        amount: int,
        corp_name: str,
    ) -> str:
        """Persist evidence file bound to transaction id under legal standard naming.

        Args:
            file_bytes: Raw binary file payload.
            transaction_id: Associated transaction ID.
            date_obj: Transaction date.
            amount: Transaction absolute amount.
            corp_name: Vendor or counterparty name.

        Returns:
            Saved filesystem path string.
        """
        clean_name = corp_name
        for prefix in ("株式会社", "合同会社", "有限会社"):
            clean_name = clean_name.replace(prefix, "")
        save_path = (
            self.storage_dir
            / f"{date_obj.strftime('%Y%m%d')}_{amount}_{_sanitize_file_name(clean_name)}_{transaction_id}.pdf"
        )
        async with aiofiles.open(save_path, "wb") as f:
            await f.write(file_bytes)
        return str(save_path)


class BackupService:
    """Service performing scheduled or on-demand SQLite and environment snapshots."""

    async def create_backup(self, target_dir_str: str) -> str:
        """Execute filesystem snapshot of SQLite database and environment variables.

        Args:
            target_dir_str: Target root directory for backup repository.

        Returns:
            Created backup directory path string.

        Raises:
            ValueError: If target_dir_str is empty.
        """
        if not target_dir_str:
            raise ValueError("バックアップ先ディレクトリが指定されていません。")

        target_base = Path(target_dir_str)
        target_base.mkdir(parents=True, exist_ok=True)

        backup_sub = target_base / datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_sub.mkdir(parents=True, exist_ok=True)

        db_file: Path | None = None
        db_url = settings.DATABASE_URL
        if db_url is not None and ":///" in db_url:
            candidate = Path(db_url.split(":///", 1)[-1])
            if candidate.exists():
                db_file = candidate
        if db_file is None:
            for cand in (
                settings.PROJECT_ROOT / "data" / settings.DB_NAME,
                settings.PROJECT_ROOT / settings.DB_NAME,
            ):
                if cand.exists():
                    db_file = cand
                    break
        if db_file is None:
            db_file = settings.PROJECT_ROOT / "data" / settings.DB_NAME

        copied_files: list[str] = []

        def _copy_sync() -> list[str]:
            results: list[str] = []
            if db_file.exists():
                shutil.copy2(db_file, backup_sub / db_file.name)
                results.append(db_file.name)
                for ext in ("-wal", "-shm"):
                    extra = db_file.parent / f"{db_file.name}{ext}"
                    if extra.exists():
                        shutil.copy2(extra, backup_sub / extra.name)
                        results.append(extra.name)

            env_file = settings.PROJECT_ROOT / ".env"
            if env_file.exists():
                shutil.copy2(env_file, backup_sub / ".env")
                results.append(".env")
            return results

        copied_files = await asyncio.to_thread(_copy_sync)
        log.info(
            "backup_created", directory=str(backup_sub), file_count=len(copied_files)
        )
        return str(backup_sub)


class PDFService:
    """Service rendering statutory Japanese financial statements using ReportLab."""

    @staticmethod
    def generate_annual_report(
        corp: Corporation,
        rpt: FinancialReport,
        fy: FiscalYear | None = None,
        report_date: date | None = None,
        audit_date: date | None = None,
        *,
        fiscal_year: FiscalYear | None = None,
    ) -> bytes:
        """Synthesize A4 PDF annual financial statements.

        Args:
            corp: Legal entity corporation metadata.
            rpt: Computed financial statement totals and sections.
            fy: Active fiscal period metadata.
            report_date: Report issuance date.
            audit_date: Statutory audit completion date.
            fiscal_year: Keyword alias for active fiscal period metadata.

        Returns:
            Raw PDF bytes stream.
        """
        target_fy: FiscalYear = (
            fy
            if fy is not None
            else (fiscal_year if fiscal_year is not None else rpt.fiscal_year)
        )
        rep_date: date = report_date if report_date is not None else date.today()
        aud_date: date = audit_date if audit_date is not None else rep_date

        _register_reportlab_fonts()
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        w, h = A4
        mx = 20 * mm

        def draw_hdr(subtitle: str, drange: str = "") -> None:
            c.setFont(settings.FONT_NAME, 16)
            c.drawCentredString(
                w / 2, h - 25 * mm, f"第{target_fy.period_number or 1}期 決算報告書"
            )
            c.setFont(settings.FONT_NAME, 12)
            c.drawCentredString(w / 2, h - 32 * mm, subtitle)
            if drange:
                c.setFont(settings.FONT_NAME, 9)
                c.drawRightString(w - mx, h - 33 * mm, drange)
            c.setLineWidth(0.5)
            c.line(mx, h - 35 * mm, w - mx, h - 35 * mm)

        drange = f"自 {target_fy.start_date.strftime('%Y年%m月%d日')}  至 {target_fy.end_date.strftime('%Y年%m月%d日')}"

        # 1. 表紙
        c.setFont(settings.FONT_NAME, 24)
        c.drawCentredString(
            w / 2, h - 90 * mm, f"第{target_fy.period_number or 1}期 決算報告書"
        )
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

        # 2. 貸借対照表
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
            return float(cy - 10 * mm)

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
        c.drawRightString(
            180 * mm, yr - 8 * mm, f"{rpt.total_liabilities + rpt.total_equity:,}"
        )
        c.showPage()

        # 3. 損益計算書
        draw_hdr("損益計算書 (Profit & Loss)", drange)
        y, xl, xv = h - 40 * mm, 30 * mm, 170 * mm

        def draw_pl_sec(sec: FinancialSection) -> None:
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

        def draw_pl_step(title: str, val: int) -> None:
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

        def draw_dtl(sec: FinancialSection) -> None:
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
            30 * mm, y - 20 * mm, f"報告日：{rep_date.strftime('%Y年%m月%d日')}"
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
            30 * mm, y - 73 * mm, f"監査日：{aud_date.strftime('%Y年%m月%d日')}"
        )

        c.save()
        buffer.seek(0)
        return buffer.getvalue()
