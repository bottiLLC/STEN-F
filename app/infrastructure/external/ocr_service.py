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

import asyncio
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import io
import json
import re
from typing import Any, List, Optional, Tuple
import unicodedata
import fitz
from google import genai
from google.genai import types
from google.genai.errors import APIError
from PIL import Image
from pydantic import BaseModel, Field
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.domain.models.receipt import ReceiptData

log = structlog.get_logger()

_CORP_STATUS_PATTERN = re.compile(
    r"株式会社|有限会社|合同会社|合名会社|合資会社|一般社団法人|公益社団法人|"
    r"一般財団法人|公益財団法人|医療法人|学校法人|宗教法人|社会福祉法人|"
    r"特定非営利活動法人|NPO法人|\(株\)|\(有\)|\(同\)|\(名\)|\(資\)|\(財\)|\(社\)|"
    r"㈱|㈲|㈇|㈆|㈅|㈄|㈃|㈂|㈁"
)


class ReceiptExtractionSchema(BaseModel):
    merchant_name: Optional[str] = Field(
        None, description="The name of the store or vendor. If illegible, use null."
    )
    transaction_date: Optional[str] = Field(
        None,
        description="The date of the transaction (Format: YYYY-MM-DD). If illegible, use null.",
    )
    total_amount_incl_tax: Optional[int] = Field(
        None,
        description="The total amount paid including tax (integer). If illegible, use null.",
    )
    invoice_registration_number: Optional[str] = Field(
        None,
        description="The Japanese invoice registration number (Format: T + 13 digits). If not present or illegible, use null.",
    )


class AccountInferenceSchema(BaseModel):
    debit_account: Optional[str] = Field(
        None, description="借方科目の名前（例: 消耗品費, 会議費, 旅費交通費など）"
    )
    credit_account: Optional[str] = Field(
        None, description="貸方科目の名前（例: 役員借入金, 普通預金など）"
    )
    description: Optional[str] = Field(
        None, description="取引の摘要文（例: 〇〇代として）"
    )


_API_ERROR_RULES = [
    (
        lambda c, m: any(k in m for k in ("API_KEY_INVALID", "API KEY NOT VALID", "AUTHENTICATION", "UNAUTHENTICATED")) or c == 401 or (c == 400 and "API KEY" in m),
        lambda msg: f"⚠️ **Gemini API キーが無効または未設定です**\n\nGoogle AI Studio で取得した有効な API キーが登録されているかご確認ください。\n「マスタ・システム管理」画面の「⚙️ AI・システム設定」タブ、または `.env` ファイルから再設定できます。\n(詳細エラー: `{msg}`)",
    ),
    (lambda c, m: "PERMISSION_DENIED" in m or c == 403, lambda msg: f"⚠️ **Gemini API へのアクセス権限が拒否されました (403 Forbidden)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: any(k in m for k in ("NOT_FOUND", "MODEL_NOT_FOUND")) or c == 404, lambda msg: f"⚠️ **指定されたAIモデル（`{settings.GEMINI_DEFAULT_MODEL}`）が見つかりません (404 Not Found)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: any(k in m for k in ("RESOURCE_EXHAUSTED", "RATE_LIMIT", "QUOTA_EXCEEDED", "TOO_MANY_REQUESTS")) or c == 429, lambda msg: f"⚠️ **Gemini API の利用上限（クォータ／レート制限）に達しました (429 Too Many Requests)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "FAILED_PRECONDITION" in m, lambda msg: f"⚠️ **API リクエストの前提条件が満たされていません (400 Failed Precondition)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "OUT_OF_RANGE" in m or c == 416, lambda msg: f"⚠️ **リクエストパラメータが許容範囲外です (416 Out of Range)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "SAFETY" in m or "IMAGE_SAFETY" in m, lambda msg: f"⚠️ **コンテンツ安全フィルターによりリクエストがブロックされました (Safety Blocked)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "RECITATION" in m or "IMAGE_RECITATION" in m, lambda msg: f"⚠️ **著作権・引用制限（Recitation）によりリクエストがブロックされました**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: any(k in m for k in ("INVALID_REQUEST", "PARAMETER_UNKNOWN")) or (c == 400 and "INVALID_ARGUMENT" in m), lambda msg: f"⚠️ **API リクエストの形式またはパラメータが不正です (400 Bad Request)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "DEADLINE_EXCEEDED" in m or c == 504, lambda msg: f"⚠️ **Gemini API 通信がタイムアウトしました (504 Gateway Timeout)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: c in (500, 502, 503) or any(k in m for k in ("INTERNAL", "SERVICE_UNAVAILABLE", "UNAVAILABLE")), lambda msg: f"⚠️ **Google Gemini サーバー側で一時的な障害が発生しています (500/503 Service Unavailable)**\n\n(詳細エラー: `{msg}`)"),
    (lambda c, m: "CANCELLED" in m or c == 499, lambda msg: f"⚠️ **リクエストがクライアント側で中断されました (499 Cancelled)**\n\n(詳細エラー: `{msg}`)"),
]


class GeminiOCRService:

    def __init__(self):
        self.log = log.bind(service="GeminiOCRService")

    async def extract_receipt_data(
        self,
        file_bytes: bytes,
        file_type: str,
        account_list: Optional[List[str]] = None,
        counterparty_list: Optional[List[str]] = None,
    ) -> ReceiptData:
        from app.container import container

        async with container.master_service_scope() as ms:
            settings_obj = await ms.get_system_settings()
            api_key = (
                settings_obj.ai_api_key
                or settings.GEMINI_API_KEY
                or settings.OPENAI_API_KEY
            )

        if not api_key:
            raise ValueError(
                "AI連携用のAPIキー（Gemini）が設定されていません。\n"
                "「マスタ・システム管理」画面の「⚙️ AI・システム設定」タブ、または .env ファイルに GEMINI_API_KEY を登録してください。"
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

        opt_bytes, opt_mime = self._optimize_image(file_bytes, mime_type)
        cp_str = (
            "\n".join([f"- {cp}" for cp in counterparty_list])
            if counterparty_list
            else ""
        )
        sys_instruct = f"""You are an expert OCR assistant. Extract EXACTLY the following fields from the receipt image.
Do not make any accounting inferences.

### Registered Counterparty List
If the merchant name matches or resembles one of these, use the EXACT name from this list for "merchant_name".
{cp_str}

Extract the following fields into a valid JSON object matching the requested schema:
1. **merchant_name**: The name of the store or vendor. If illegible, use null.
2. **transaction_date**: The date of the transaction (Format: YYYY-MM-DD).
3. **total_amount_incl_tax**: The total amount paid including tax (integer).
4. **invoice_registration_number**: The Japanese invoice registration number (Format: T + 13 digits). If not present or illegible, use null.
"""
        client = genai.Client(api_key=api_key)
        try:
            resp = await self._call_gemini_api(
                client, sys_instruct, opt_bytes, opt_mime
            )
            if not resp:
                raise ValueError("Gemini APIから応答が得られませんでした。")

            try:
                data = json.loads(self._clean_json_text(resp))
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"AI解析結果のJSONパースに失敗しました: {str(e)}"
                ) from e

            receipt = ReceiptData(
                merchant_name=data.get("merchant_name"),
                transaction_date=data.get("transaction_date"),
                total_amount_incl_tax=data.get("total_amount_incl_tax"),
                invoice_registration_number=data.get("invoice_registration_number"),
            )
            if receipt.merchant_name:
                receipt.merchant_name = unicodedata.normalize(
                    "NFKC", receipt.merchant_name
                ).strip()
            if receipt.invoice_registration_number:
                m = re.search(r"(T\d{13})", receipt.invoice_registration_number)
                receipt.invoice_registration_number = m.group(1) if m else None

            async with container.master_service_scope() as master_service:
                cps = await master_service.get_counterparties()
                matched = None
                if receipt.invoice_registration_number:
                    matched = next(
                        (
                            c
                            for c in cps
                            if c.invoice_number == receipt.invoice_registration_number
                        ),
                        None,
                    )
                if not matched and receipt.merchant_name:
                    norm = self._normalize_name(receipt.merchant_name)
                    matched = next(
                        (c for c in cps if norm == self._normalize_name(c.name)), None
                    )

                if matched:
                    receipt.merchant_name = matched.name
                    receipt.invoice_registration_number = matched.invoice_number
                    receipt.inferred_debit_account_id = (
                        str(matched.debit_account_id)
                        if matched.debit_account_id
                        else None
                    )
                    receipt.inferred_credit_account_id = (
                        str(matched.credit_account_id)
                        if matched.credit_account_id
                        else None
                    )
                    receipt.description = matched.description_template
                    receipt.is_registered_merchant = True
                    receipt.is_dictionary_matched = True
                    return self._validate_receipt(receipt)

                try:
                    acc_str = "\n".join(account_list) if account_list else "一覧なし"
                    sys_fb = f"""あなたは免税事業者の経理担当です。
取引先『{receipt.merchant_name or "不明"}』で『{receipt.total_amount_incl_tax or 0}円』支払った。
適切な借方科目と貸方科目を推論しJSON形式で返答してください。
【貸方推論ルール】当社はほぼ全て代表個人のポケットマネーからの立替払いであるため「役員借入金」を優先推論すること。
【借方推論ルール】当社の自家用車は法人賃貸のため「車両運搬具」は絶対に含めないこと。
【勘定科目一覧】\n{acc_str}
出力形式 (JSON): {{"debit_account": "借方科目名", "credit_account": "貸方科目名", "description": "摘要文"}}"""
                    fb_text = await self._call_gemini_fallback(client, sys_fb)
                    if fb_text:
                        fb_data = json.loads(self._clean_json_text(fb_text))
                        accounts_db = await master_service.get_accounts()

                        def find_id(name: Optional[str]) -> Optional[str]:
                            if not name:
                                return None
                            for a in accounts_db:
                                if a.name == name or name in f"{a.code}: {a.name}":
                                    return str(a.id)
                            return None

                        receipt.inferred_debit_account_id = find_id(
                            fb_data.get("debit_account")
                        )
                        receipt.inferred_credit_account_id = find_id(
                            fb_data.get("credit_account")
                        )
                        receipt.description = fb_data.get(
                            "description", receipt.merchant_name
                        )
                except Exception as fb_err:
                    self.log.warning(
                        "Fallback account inference failed", error=str(fb_err)
                    )

            return self._validate_receipt(receipt)
        except APIError as e:
            self.log.error(
                "Gemini API Error", error=str(e), code=getattr(e, "code", None)
            )
            raise ValueError(self._format_api_error_message(e)) from e
        except ValueError:
            raise
        except Exception as e:
            self.log.exception("Unexpected OCR extraction failure", error=str(e))
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
    ) -> str:
        model = settings.GEMINI_DEFAULT_MODEL
        contents: list[Any] = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=sys_instruct),
        ]
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptExtractionSchema,
            temperature=0.0,
        )
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=model, contents=contents, config=config
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

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_gemini_fallback(
        self, client: genai.Client, sys_instruct_fallback: str
    ) -> str:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AccountInferenceSchema,
            temperature=0.0,
        )
        response = await asyncio.to_thread(
            lambda: client.models.generate_content(
                model=settings.GEMINI_DEFAULT_MODEL,
                contents=sys_instruct_fallback,
                config=config,
            )
        )
        return response.text or ""

    def _format_api_error_message(self, e: APIError) -> str:

        code, raw_msg = getattr(e, "code", None), getattr(e, "message", None) or str(e)
        msg_u = raw_msg.upper()
        for matcher, formatter in _API_ERROR_RULES:
            if matcher(code, msg_u):
                return formatter(raw_msg)
        return f"⚠️ **Gemini API エラー (Code: {code or '不明'})**\n\n{raw_msg}"

    def _clean_json_text(self, text: str) -> str:
        c = text.strip()
        if c.startswith("```json"):
            c = c[7:]
        elif c.startswith("```"):
            c = c[3:]
        return c[:-3].strip() if c.endswith("```") else c.strip()

    def _normalize_name(self, name: str) -> str:
        if not name:
            return ""
        norm = unicodedata.normalize("NFKC", name).replace(" ", "").replace("　", "")
        return _CORP_STATUS_PATTERN.sub("", norm)


    def _validate_receipt(self, data: ReceiptData) -> ReceiptData:
        msgs: List[str] = []
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
            msgs.append(
                f"消費税合計不整合 (計算値:{c_tax}, OCR値:{data.total_tax_amount})"
            )
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

    def _optimize_image(self, file_bytes: bytes, mime_type: str) -> Tuple[bytes, str]:
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
                    proc: Any = img.convert("RGB") if img.mode != "RGB" else img
                    out = io.BytesIO()
                    proc.save(out, format="JPEG", dpi=(200, 200), quality=85)
                    return out.getvalue(), "image/jpeg"
                return file_bytes, mime_type
        except Exception:
            return file_bytes, mime_type


    # Compatibility alias for UI
    analyze_receipt = extract_receipt_data


# Backward compatibility alias
OpenAIOCRService = GeminiOCRService

