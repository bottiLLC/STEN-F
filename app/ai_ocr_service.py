# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import io
import json
import re
from typing import Final
import unicodedata

import fitz
from google import genai
from google.genai import types
from google.genai.errors import APIError
from PIL import Image
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core_foundation import log, settings
from app.domain_contracts import (
    MatchScoreResult,
    ReceiptData,
    ReceiptRawExtractionSchema,
    VendorMasterRecord,
)

# Backwards compatibility alias
ReceiptExtractionSchema = ReceiptRawExtractionSchema


# --- 1. Datum Plane (Schemas & Patterns) ---
_CORP_STATUS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"株式会社|有限会社|合同会社|合名会社|合資会社|一般社団法人|公益社団法人|"
    r"一般財団法人|公益財団法人|医療法人|学校法人|宗教法人|社会福祉法人|"
    r"特定非営利活動法人|NPO法人|\(株\)|\(有\)|\(同\)|\(名\)|\(資\)|\(財\)|\(社\)|"
    r"㈱|㈲|㈇|㈆|㈅|㈄|㈃|㈂|㈁"
)
_DIGIT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\D")

MatcherFunc = Callable[[int | None, str], bool]
FormatterFunc = Callable[[str], str]

_API_ERROR_RULES: Final[tuple[tuple[MatcherFunc, FormatterFunc], ...]] = (
    (
        lambda c, m: (
            any(
                k in m
                for k in (
                    "API_KEY_INVALID",
                    "API KEY NOT VALID",
                    "AUTHENTICATION",
                    "UNAUTHENTICATED",
                )
            )
            or c == 401
            or (c == 400 and "API KEY" in m)
        ),
        lambda msg: (
            f"**Gemini API キーが無効または未設定です**\n\nGoogle AI Studio で取得した有効な API キーが登録されているかご確認ください。\n「マスタ・システム管理」画面の「AI・システム設定」タブ、または `.env` ファイルから再設定できます。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "PERMISSION_DENIED" in m or c == 403,
        lambda msg: (
            f"⚠️ **Gemini API へのアクセス権限が拒否されました (403 Forbidden)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: any(k in m for k in ("NOT_FOUND", "MODEL_NOT_FOUND")) or c == 404,
        lambda msg: (
            f"⚠️ **指定されたAIモデル（`{settings.GEMINI_DEFAULT_MODEL}`）が見つかりません (404 Not Found)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: (
            any(
                k in m
                for k in (
                    "RESOURCE_EXHAUSTED",
                    "RATE_LIMIT",
                    "QUOTA_EXCEEDED",
                    "TOO_MANY_REQUESTS",
                )
            )
            or c == 429
        ),
        lambda msg: (
            f"⚠️ **Gemini API の利用上限（クォータ／レート制限）に達しました (429 Too Many Requests)**\n\nしばらく時間をおいてから再試行してください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "FAILED_PRECONDITION" in m,
        lambda msg: (
            f"⚠️ **API リクエストの前提条件が満たされていません (400 Failed Precondition)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "OUT_OF_RANGE" in m or c == 416,
        lambda msg: (
            f"⚠️ **リクエストパラメータが許容範囲外です (416 Out of Range)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "SAFETY" in m or "IMAGE_SAFETY" in m,
        lambda msg: (
            f"⚠️ **コンテンツ安全フィルターによりリクエストがブロックされました (Safety Blocked)**\n\n画像内容をご確認の上、鮮明な別の画像でお試しください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "RECITATION" in m or "IMAGE_RECITATION" in m,
        lambda msg: (
            f"⚠️ **著作権・引用制限（Recitation）によりリクエストがブロックされました**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: (
            any(k in m for k in ("INVALID_REQUEST", "PARAMETER_UNKNOWN"))
            or (c == 400 and "INVALID_ARGUMENT" in m)
        ),
        lambda msg: (
            f"⚠️ **API リクエストの形式またはパラメータが不正です (400 Bad Request)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "DEADLINE_EXCEEDED" in m or c == 504,
        lambda msg: (
            f"⚠️ **Gemini API 通信がタイムアウトしました (504 Gateway Timeout)**\n\nネットワーク接続をご確認の上、再試行してください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: (
            c in (500, 502, 503)
            or any(
                k in m
                for k in (
                    "INTERNAL",
                    "SERVICE_UNAVAILABLE",
                    "UNAVAILABLE",
                )
            )
        ),
        lambda msg: (
            f"⚠️ **Google Gemini サーバー側で一時的な障害が発生しています (500/503 Service Unavailable)**\n\n時間をおいて再試行してください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "CANCELLED" in m or c == 499,
        lambda msg: (
            f"⚠️ **リクエストがクライアント側で中断されました (499 Cancelled)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
)


# --- 2. Internal Pure Transformations & Scoring Engine ---
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

    Scoring rules (100-point scale):
      1. Invoice registration number:
         - 13 digits exact match: Immediate 100.0 (short-circuit).
         - Partial match (>=10 digits or substring in master): +70.0.
      2. Telephone number:
         - Digits-only normalized exact match: +80.0.
      3. Company name fuzzy matching:
         - rapidfuzz partial ratio (0-100) scaled by 0.3 (up to 30.0).

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

    # 1. Invoice registration number matching
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

    # 2. Telephone number matching
    if extracted.tel and vendor.tel:
        ext_tel = _DIGIT_PATTERN.sub("", extracted.tel)
        mst_tel = _DIGIT_PATTERN.sub("", vendor.tel)
        if ext_tel and mst_tel and ext_tel == mst_tel:
            breakdown["tel"] = 80.0

    # 3. Fuzzy company name matching
    if extracted.raw_company_name and vendor.name:
        ext_norm = normalize_merchant_name(extracted.raw_company_name)
        mst_norm = normalize_merchant_name(vendor.name)
        ratio = float(fuzz.partial_ratio(ext_norm, mst_norm))
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

    Guarantees preservation and automatic prefilling of all successfully extracted
    text fields (date, total_amount, raw_company_name, invoice_number, tel) even when
    the composite score falls below the 75-point identification threshold.

    Args:
        raw: Structured fields extracted directly by Gemini.
        match_result: Multi-stage scoring evaluation result.

    Returns:
        Fully populated ReceiptData ready for UI form prefilling and validation.
    """
    matched = match_result.matched_vendor

    # If identified, bind master's canonical metadata; otherwise fallback to raw readings
    merchant_name = matched.name if matched else raw.raw_company_name
    inv_number = (
        matched.invoice_number
        if (matched and matched.invoice_number)
        else raw.invoice_number
    )
    tax_rate = matched.tax_rate if matched else None
    debit_acc = matched.debit_account if matched else None

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
        description=f"仕入・経費 ({merchant_name})" if merchant_name else None,
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


# --- 3. Public Orchestration Layer ---
class GeminiOCRService:
    """Multimodal OCR extraction engine utilizing Google Gemini models."""

    def __init__(self) -> None:
        """Bind structured logger."""
        self.log = log.bind(service="GeminiOCRService")

    async def extract_receipt_data(
        self,
        file_bytes: bytes,
        file_type: str,
        model_id: str = "gemini-3.5-flash-lite",
        account_list: list[str] | None = None,
        counterparty_list: list[str] | None = None,
    ) -> ReceiptData:
        """Extract structured receipt metadata and execute Python composite master matching.

        Args:
            file_bytes: Raw binary file payload.
            file_type: File extension or format type.
            model_id: Gemini model identifier (e.g. gemini-3.5-flash-lite or gemini-3.8-flash).
            account_list: Optional legacy parameter for backward compatibility.
            counterparty_list: Optional legacy parameter for backward compatibility.

        Returns:
            Extracted, matched, and validated ReceiptData domain model.

        Raises:
            ValueError: If API key missing, file invalid, or parsing fails.
        """
        from app.application_services import container

        async with container.master_service_scope() as ms:
            settings_obj = await ms.get_system_settings()
            api_key = settings_obj.ai_api_key or settings.GEMINI_API_KEY

        if not api_key:
            raise ValueError(
                "AI連携用のAPIキー（Gemini）が設定されていません。\n"
                "「マスタ・システム管理」画面の「AI・システム設定」タブ、または .env ファイルに GEMINI_API_KEY を登録してください。"
            )
        if not file_bytes:
            raise ValueError("アップロードされたファイルが空です。")

        ft = file_type.lower()
        if ft == "pdf":
            try:
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) == 0:
                    raise ValueError("PDFファイルが空（0ページ）です。")
                pix = doc.load_page(0).get_pixmap(dpi=200, alpha=False)
                file_bytes, mime_type = pix.tobytes("png"), "image/png"
            except Exception as e:
                raise ValueError(
                    f"PDFファイルの読み込み・レンダリングに失敗しました: {str(e)}"
                ) from e
        elif ft in ("png", "jpg", "jpeg", "webp"):
            mime_type = "image/jpeg" if ft == "jpg" else f"image/{ft}"
        else:
            raise ValueError(
                f"サポートされていないファイル形式です: {file_type} (対応形式: PDF, PNG, JPG, JPEG, WEBP)"
            )

        opt_bytes, opt_mime = optimize_receipt_image(file_bytes, mime_type)
        sys_instruct = (
            "You are an expert OCR assistant. Extract text accurately from the receipt or invoice image into the structured JSON schema.\n"
            "Do not make any accounting inferences, assumptions, or translations.\n\n"
            "Extract the following fields:\n"
            "1. date: Transaction date formatted as YYYY-MM-DD. If illegible or missing, return null.\n"
            "2. total_amount: Total paid amount including tax as an integer. If illegible, return null.\n"
            "3. invoice_number: Japanese invoice registration number (T+13 digits or partial digits exactly as visible). Return raw string without alteration. If absent, null.\n"
            "4. raw_company_name: Store, merchant, or company name exactly as visible on the receipt. If illegible, return null.\n"
            "5. tel: Telephone number as printed on the receipt (with or without hyphens). If illegible, return null."
        )

        client = genai.Client(api_key=api_key)
        try:
            resp = await self._call_gemini_api(
                client, sys_instruct, opt_bytes, opt_mime, model_id=model_id
            )
            if not resp:
                raise ValueError("Gemini APIから応答が得られませんでした。")

            try:
                data = json.loads(clean_json_codeblock(resp))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"AI解析結果のJSONパースに失敗しました: {str(e)}"
                ) from e

            raw_extracted = ReceiptRawExtractionSchema.model_validate(data)

            # Retrieve master records for deterministic Python-side matching
            async with container.master_service_scope() as master_service:
                cps = await master_service.get_counterparties()
                accounts = await master_service.get_accounts()
                acc_id_to_name: dict[str, str] = {
                    str(a.id): a.name for a in accounts if a.id is not None
                }
                master_records: list[VendorMasterRecord] = [
                    VendorMasterRecord(
                        vendor_id=cp.id or 0,
                        name=cp.name,
                        invoice_number=cp.invoice_number,
                        tel=cp.tel,
                        debit_account=(
                            acc_id_to_name.get(str(cp.debit_account_id))
                            if cp.debit_account_id
                            else None
                        ),
                        tax_rate=cp.tax_rate if cp.tax_rate is not None else 0.10,
                    )
                    for cp in cps
                ]

            match_result = match_counterparty_master(raw_extracted, master_records)
            receipt = map_extraction_to_receipt_data(raw_extracted, match_result)
            return validate_receipt_structure(receipt)

        except APIError as e:
            self.log.error(
                "gemini_api_error", error=str(e), code=getattr(e, "code", None)
            )
            raise ValueError(self._format_api_error_message(e)) from e
        except ValueError:
            raise
        except Exception as e:
            self.log.exception("ocr_unexpected_failure", error=str(e))
            raise ValueError(
                f"AI証憑解析処理中に予期せぬエラーが発生しました: {str(e)}"
            ) from e

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_gemini_api(
        self,
        client: genai.Client,
        sys_instruct: str,
        image_bytes: bytes,
        mime_type: str,
        model_id: str = "gemini-3.5-flash-lite",
    ) -> str:
        """Call Gemini multimodal API under retry clamping.

        Args:
            client: Authenticated genai.Client instance.
            sys_instruct: System instructions prompt.
            image_bytes: Optimized receipt image binary.
            mime_type: Image MIME type.
            model_id: Target Gemini model identifier.

        Returns:
            JSON text payload returned by Gemini.

        Raises:
            ValueError: If response is empty or blocked by safety filters.
        """
        contents: list[types.ContentUnionDict] = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=sys_instruct),
        ]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptRawExtractionSchema,
            temperature=0.0,
        )
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=model_id,
                contents=contents,
                config=config,
            )
        )
        result = response.text or ""
        if not result:
            if hasattr(response, "candidates") and response.candidates:
                fr = getattr(response.candidates[0], "finish_reason", None)
                fr_str = str(fr).upper() if fr else ""
                if "SAFETY" in fr_str:
                    raise ValueError(
                        "⚠️ **コンテンツ安全フィルターにより生成がブロックされました**\n\n画像内容をご確認の上、鮮明な別の画像でお試しください。"
                    )
                if "RECITATION" in fr_str:
                    raise ValueError(
                        "⚠️ **著作権・引用制限（Recitation）により生成がブロックされました**"
                    )
                if fr:
                    raise ValueError(
                        f"⚠️ **AIモデルの出力が中断されました (理由: {fr})**"
                    )
            raise ValueError("Gemini APIから空の応答が返されました。")
        return result

    def _format_api_error_message(self, e: APIError) -> str:
        """Transform low-level Gemini API exception into user-friendly error string.

        Args:
            e: Captured APIError instance.

        Returns:
            Formatted Japanese error message string.
        """
        code = getattr(e, "code", None)
        raw_msg = getattr(e, "message", None) or str(e)
        msg_u = raw_msg.upper()
        for matcher, formatter in _API_ERROR_RULES:
            if matcher(code, msg_u):
                return formatter(raw_msg)
        return f"⚠️ **Gemini API エラー (Code: {code or '不明'})**\n\n{raw_msg}"

    _validate_receipt = staticmethod(validate_receipt_structure)
