# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import io
import re
from typing import Final
import unicodedata

from PIL import Image
from rapidfuzz import fuzz

from app.domain_contracts import (
    MatchScoreResult,
    ReceiptData,
    ReceiptRawExtractionSchema,
    VendorMasterRecord,
)

_CORP_STATUS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"株式会社|有限会社|合同会社|合名会社|合資会社|一般社団法人|公益社団法人|"
    r"一般財団法人|公益財団法人|医療法人|学校法人|宗教法人|社会福祉法人|"
    r"特定非営利活動法人|NPO法人|\(株\)|\(有\)|\(同\)|\(名\)|\(資\)|\(財\)|\(社\)|"
    r"㈱|㈲|㈇|㈆|㈅|㈄|㈃|㈂|㈁"
)
_DIGIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\D")

_MIME_FORMAT_MAP: Final[dict[str, str]] = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/pjpeg": "jpeg",
    "image/webp": "webp",
}
_SUPPORTED_FORMATS: Final[frozenset[str]] = frozenset(
    {"pdf", "png", "jpg", "jpeg", "webp"}
)


def clean_json_codeblock(text: str) -> str:
    """Strip markdown fencing and clean extracted JSON raw string.

    Args:
        text: Raw response string potentially containing code blocks.

    Returns:
        Cleaned JSON string without markdown fences.
    """
    c = text.strip()
    if c.startswith("```json"):
        c = c[7:]
    elif c.startswith("```"):
        c = c[3:]
    return c[:-3].strip() if c.endswith("```") else c.strip()


def normalize_merchant_name(name: str) -> str:
    """Normalize legal entities and spacing in merchant title.

    Args:
        name: Raw vendor name.

    Returns:
        Normalized name stripped of corporate prefixes/suffixes.
    """
    if not name:
        return ""
    norm = unicodedata.normalize("NFKC", name).replace(" ", "").replace("　", "")
    return _CORP_STATUS_PATTERN.sub("", norm)


def calculate_match_score(
    extracted: ReceiptRawExtractionSchema,
    vendor: VendorMasterRecord,
) -> tuple[float, dict[str, float]]:
    """Calculate multi-tier composite confidence score against single vendor master record.

    Args:
        extracted: Raw structured fields extracted by Gemini.
        vendor: Registered vendor master entity.

    Returns:
        Tuple of (total_score clamped to 100.0, score_breakdown_dictionary).
    """
    breakdown: dict[str, float] = {
        "invoice": 0.0,
        "tel": 0.0,
        "name_fuzzy": 0.0,
    }

    if extracted.invoice_number and vendor.invoice_number:
        ext_digits = _DIGIT_PATTERN.sub("", extracted.invoice_number)
        mst_digits = _DIGIT_PATTERN.sub("", vendor.invoice_number)
        if len(ext_digits) == 13 and ext_digits == mst_digits:
            breakdown["invoice"] = 100.0
            return 100.0, breakdown
        if len(ext_digits) >= 10 and (
            ext_digits in mst_digits or mst_digits.endswith(ext_digits)
        ):
            breakdown["invoice"] = 70.0

    if extracted.tel and vendor.tel:
        ext_tel = _DIGIT_PATTERN.sub("", extracted.tel)
        mst_tel = _DIGIT_PATTERN.sub("", vendor.tel)
        if ext_tel and mst_tel and ext_tel == mst_tel:
            breakdown["tel"] = 80.0

    if extracted.raw_company_name:
        ext_norm = normalize_merchant_name(extracted.raw_company_name)
        candidates: list[str] = []
        if vendor.name:
            candidates.append(normalize_merchant_name(vendor.name))
        if vendor.trade_name:
            candidates.append(normalize_merchant_name(vendor.trade_name))
        if candidates:
            ratio = max(
                (float(fuzz.partial_ratio(ext_norm, c)) for c in candidates if c),
                default=0.0,
            )
            breakdown["name_fuzzy"] = round(ratio * 0.3, 2)

    total_score = min(
        100.0,
        breakdown["invoice"] + breakdown["tel"] + breakdown["name_fuzzy"],
    )
    return total_score, breakdown


def match_counterparty_master(
    extracted: ReceiptRawExtractionSchema,
    master_records: list[VendorMasterRecord],
    threshold: float = 75.0,
) -> MatchScoreResult:
    """Execute multi-tier composite scoring over vendor master collection.

    Args:
        extracted: Raw structured fields extracted by Gemini.
        master_records: Full collection of registered vendor master records.
        threshold: Score cut-off for definitive entity identification (default: 75.0).

    Returns:
        MatchScoreResult carrying top candidate details, identified flag, and score.
    """
    if not master_records:
        return MatchScoreResult(score=0.0, is_identified=False, matched_vendor=None)

    best_score = 0.0
    best_vendor: VendorMasterRecord | None = None
    best_breakdown: dict[str, float] = {}

    for vendor in master_records:
        score, breakdown = calculate_match_score(extracted, vendor)
        if score >= 100.0:
            return MatchScoreResult(
                score=100.0,
                is_identified=True,
                matched_vendor=vendor,
                breakdown=breakdown,
            )
        if score > best_score:
            best_score = score
            best_vendor = vendor
            best_breakdown = breakdown

    is_identified = best_score >= threshold
    return MatchScoreResult(
        score=best_score,
        is_identified=is_identified,
        matched_vendor=best_vendor if is_identified else None,
        breakdown=best_breakdown,
    )


def map_extraction_to_receipt_data(
    raw: ReceiptRawExtractionSchema,
    match_result: MatchScoreResult,
) -> ReceiptData:
    """Map raw extracted fields and match outcome into ReceiptData domain entity.

    Args:
        raw: Structured fields extracted directly by Gemini.
        match_result: Multi-stage scoring evaluation result.

    Returns:
        Fully populated ReceiptData ready for UI form prefilling and validation.
    """
    matched = match_result.matched_vendor

    merchant_name = matched.name if matched else raw.raw_company_name
    inv_number = (
        matched.invoice_number
        if (matched and matched.invoice_number)
        else raw.invoice_number
    )
    tax_rate = matched.tax_rate if matched else None
    debit_acc = matched.debit_account if matched else None
    credit_acc = matched.credit_account if matched else None
    desc = (
        matched.description_template
        if (matched and matched.description_template)
        else (f"仕入・経費 ({merchant_name})" if merchant_name else None)
    )

    if inv_number:
        m = re.search(r"(T\d{13})", inv_number)
        if m:
            inv_number = m.group(1)

    return ReceiptData(
        merchant_name=merchant_name,
        raw_company_name=raw.raw_company_name,
        transaction_date=raw.date,
        total_amount_incl_tax=raw.total_amount,
        invoice_registration_number=inv_number,
        tel=raw.tel,
        tax_rate=tax_rate,
        match_score=match_result.score,
        needs_manual_review=not match_result.is_identified,
        is_registered_merchant=match_result.is_identified,
        is_dictionary_matched=match_result.is_identified,
        inferred_debit_account_id=debit_acc,
        inferred_credit_account_id=credit_acc,
        description=desc,
    )


def validate_receipt_structure(data: ReceiptData) -> ReceiptData:
    """Perform edge consistency checks on receipt totals, dates, and invoice registration.

    Args:
        data: Candidate ReceiptData model.

    Returns:
        Validated ReceiptData model with manual review flags set if inconsistent.
    """
    msgs: list[str] = []
    c_tax, c_excl = 0, 0
    if data.tax_breakdown:
        for item in data.tax_breakdown:
            t_amt, e_amt = item.tax_amount or 0, item.amount_excl_tax or 0
            c_tax += t_amt
            c_excl += e_amt
            rate_str = (
                "0.10"
                if "10" in item.tax_rate
                else "0.08"
                if "8" in item.tax_rate
                else "0.00"
            )
            if rate_str != "0.00" and e_amt > 0:
                exp_tax = int(
                    (Decimal(str(e_amt)) * Decimal(rate_str)).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
                if abs(exp_tax - t_amt) > 1:
                    msgs.append(
                        f"消費税計算不整合 ({item.tax_rate}: 対象{e_amt}, 税額{t_amt})"
                    )

    if data.total_tax_amount is not None and abs(c_tax - data.total_tax_amount) > 1:
        msgs.append(f"消費税合計不整合 (計算値:{c_tax}, OCR値:{data.total_tax_amount})")
    if (
        data.total_amount_excl_tax is not None
        and abs(c_excl - data.total_amount_excl_tax) > 1
    ):
        msgs.append(
            f"税抜合計不整合 (計算値:{c_excl}, OCR値:{data.total_amount_excl_tax})"
        )
    if data.total_amount_incl_tax:
        c_grand = (data.total_amount_excl_tax or 0) + (data.total_tax_amount or 0)
        if (
            abs(c_grand - data.total_amount_incl_tax) > 1
            and (data.total_amount_excl_tax or 0) > 0
        ):
            msgs.append(
                f"支払合計不整合 (計算値:{c_grand}, OCR値:{data.total_amount_incl_tax})"
            )

    if data.transaction_date:
        try:
            date.fromisoformat(data.transaction_date)
        except ValueError:
            msgs.append(f"日付フォーマット不正: {data.transaction_date}")
            data.transaction_date = None

    if data.invoice_registration_number:
        match = re.search(r"(T\d{13})", data.invoice_registration_number)
        if match:
            data.invoice_registration_number = match.group(1)
        else:
            msgs.append(
                f"インボイス番号の形式が不正です: {data.invoice_registration_number}"
            )

    if msgs:
        data.needs_manual_review = True
        existing = data.error_message or ""
        data.error_message = f"{existing} | ".strip(" | ") + "; ".join(msgs)
    return data


def optimize_receipt_image(file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Resize high-resolution images down to standard OCR processing boundaries.

    Args:
        file_bytes: Raw input binary image data.
        mime_type: MIME content type identifier.

    Returns:
        Tuple of optimized bytes and effective MIME type string.
    """
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            dpi = img.info.get("dpi")
            max_px = 2000
            if (
                (dpi and dpi[0] > 200)
                or max(img.size) > max_px
                or mime_type == "image/png"
            ):
                img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
                proc: Image.Image = img.convert("RGB") if img.mode != "RGB" else img
                out = io.BytesIO()
                proc.save(out, format="JPEG", dpi=(200, 200), quality=85)
                return out.getvalue(), "image/jpeg"
            return file_bytes, mime_type
    except Exception:
        return file_bytes, mime_type


def normalize_receipt_file_format(raw_type: str) -> str:
    """Normalize MIME types, dotted extensions, and filenames into standard formats.

    Args:
        raw_type: MIME type, extension, or filename.

    Returns:
        Canonical format token ('pdf', 'png', 'jpg', 'jpeg', or 'webp').

    Raises:
        ValueError: If raw_type is unsupported or unparseable.
    """
    token = raw_type.strip().lower()

    if token in _MIME_FORMAT_MAP:
        return _MIME_FORMAT_MAP[token]

    if "/" in token:
        _, _, sub = token.partition("/")
        if sub in _SUPPORTED_FORMATS:
            return sub

    if "." in token:
        ext = token.rsplit(".", 1)[-1]
        if ext in _SUPPORTED_FORMATS:
            return ext

    if token in _SUPPORTED_FORMATS:
        return token

    raise ValueError(
        f"サポートされていないファイル形式です: {raw_type} (対応形式: PDF, PNG, JPG, JPEG, WEBP)"
    )
