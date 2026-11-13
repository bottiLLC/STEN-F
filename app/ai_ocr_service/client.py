# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
import json
from typing import Final

import fitz
from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.ai_ocr_service.matching import (
    clean_json_codeblock,
    map_extraction_to_receipt_data,
    match_counterparty_master,
    normalize_receipt_file_format,
    optimize_receipt_image,
    validate_receipt_structure,
)
from app.core_foundation import log, settings
from app.domain_contracts import (
    ReceiptData,
    ReceiptRawExtractionSchema,
    VendorMasterRecord,
)

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
            f"**Gemini API へのアクセス権限が拒否されました (403 Forbidden)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: any(k in m for k in ("NOT_FOUND", "MODEL_NOT_FOUND")) or c == 404,
        lambda msg: (
            f"**指定されたAIモデル（`{settings.GEMINI_DEFAULT_MODEL}`）が見つかりません (404 Not Found)**\n\n(詳細エラー: `{msg}`)"
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
            f"**Gemini API の利用上限（クォータ／レート制限）に達しました (429 Too Many Requests)**\n\nしばらく時間をおいてから再試行してください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "FAILED_PRECONDITION" in m,
        lambda msg: (
            f"**API リクエストの前提条件が満たされていません (400 Failed Precondition)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "OUT_OF_RANGE" in m or c == 416,
        lambda msg: (
            f"**リクエストパラメータが許容範囲外です (416 Out of Range)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "SAFETY" in m or "IMAGE_SAFETY" in m,
        lambda msg: (
            f"**コンテンツ安全フィルターによりリクエストがブロックされました (Safety Blocked)**\n\n画像内容をご確認の上、鮮明な別の画像でお試しください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "RECITATION" in m or "IMAGE_RECITATION" in m,
        lambda msg: (
            f"**著作権・引用制限（Recitation）によりリクエストがブロックされました**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: (
            any(k in m for k in ("INVALID_REQUEST", "PARAMETER_UNKNOWN"))
            or (c == 400 and "INVALID_ARGUMENT" in m)
        ),
        lambda msg: (
            f"**API リクエストの形式またはパラメータが不正です (400 Bad Request)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "DEADLINE_EXCEEDED" in m or c == 504,
        lambda msg: (
            f"**Gemini API 通信がタイムアウトしました (504 Gateway Timeout)**\n\nネットワーク接続をご確認の上、再試行してください。\n(詳細エラー: `{msg}`)"
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
            f"**Google Gemini サーバー側で一時的な障害が発生しています (500/503 Service Unavailable)**\n\n時間をおいて再試行してください。\n(詳細エラー: `{msg}`)"
        ),
    ),
    (
        lambda c, m: "CANCELLED" in m or c == 499,
        lambda msg: (
            f"**リクエストがクライアント側で中断されました (499 Cancelled)**\n\n(詳細エラー: `{msg}`)"
        ),
    ),
)


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
    ) -> ReceiptData:
        """Extract structured receipt metadata and execute Python composite master matching.

        Args:
            file_bytes: Raw binary file payload.
            file_type: File extension or format type.
            model_id: Gemini model identifier (e.g. gemini-3.5-flash-lite or gemini-3.8-flash).

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

        fmt = normalize_receipt_file_format(file_type)
        if fmt == "pdf":
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
        else:
            mime_type = "image/jpeg" if fmt in ("jpg", "jpeg") else f"image/{fmt}"

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
                        trade_name=cp.trade_name,
                        invoice_number=cp.invoice_number,
                        tel=cp.tel,
                        debit_account=(
                            acc_id_to_name.get(str(cp.debit_account_id))
                            if cp.debit_account_id
                            else None
                        ),
                        credit_account=(
                            acc_id_to_name.get(str(cp.credit_account_id))
                            if cp.credit_account_id
                            else None
                        ),
                        description_template=cp.description_template,
                        tax_rate=cp.tax_rate
                        if cp.tax_rate is not None
                        else Decimal("0.10"),
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
        """Call Gemini multimodal API under retry clamping."""
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
                        "**コンテンツ安全フィルターにより生成がブロックされました**\n\n画像内容をご確認の上、鮮明な別の画像でお試しください。"
                    )
                if "RECITATION" in fr_str:
                    raise ValueError(
                        "**著作権・引用制限（Recitation）により生成がブロックされました**"
                    )
                if fr:
                    raise ValueError(f"**AIモデルの出力が中断されました (理由: {fr})**")
            raise ValueError("Gemini APIから空の応答が返されました。")
        return result

    def _format_api_error_message(self, e: APIError) -> str:
        """Transform low-level Gemini API exception into user-friendly error string."""
        code = getattr(e, "code", None)
        raw_msg = getattr(e, "message", None) or str(e)
        msg_u = raw_msg.upper()
        for matcher, formatter in _API_ERROR_RULES:
            if matcher(code, msg_u):
                return formatter(raw_msg)
        return f"**Gemini API エラー (Code: {code or '不明'})**\n\n{raw_msg}"

    _validate_receipt = staticmethod(validate_receipt_structure)
