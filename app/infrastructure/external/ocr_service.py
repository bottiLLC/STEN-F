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

import io
import json
import re
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional
import fitz  # PyMuPDF
from PIL import Image
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.genai.errors import APIError
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.domain.models.receipt import ReceiptData

log = structlog.get_logger()


class ReceiptExtractionSchema(BaseModel):
    """
    Gemini Structured Output 専用の領収書・証憑抽出スキーマ
    """

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
    """
    Gemini Structured Output 専用の勘定科目・摘要推論スキーマ
    """

    debit_account: Optional[str] = Field(
        None, description="借方科目の名前（例: 消耗品費, 会議費, 旅費交通費など）"
    )
    credit_account: Optional[str] = Field(
        None, description="貸方科目の名前（例: 役員借入金, 普通預金など）"
    )
    description: Optional[str] = Field(
        None, description="取引の摘要文（例: 〇〇代として）"
    )


class GeminiOCRService:
    """
    Google Gemini API (gemini-3.5-flash-lite) を利用した領収書・証憑OCRおよび仕訳推論サービス。
    """

    def __init__(self):
        self.log = log.bind(service="GeminiOCRService")

    async def extract_receipt_data(
        self,
        file_bytes: bytes,
        file_type: str,
        account_list: list[str] | None = None,
        counterparty_list: list[str] | None = None,
    ) -> ReceiptData:
        # Include all function input parameters in log context, masking sensitive keys
        local_log = self.log.bind(
            file_type=file_type,
            file_bytes_len=len(file_bytes),
            account_list=account_list,
            counterparty_list=counterparty_list,
        )
        local_log.info("extract_receipt_data_start")

        from app.container import container

        async with container.master_service_scope() as ms:
            system_settings = await ms.get_system_settings()
            api_key = system_settings.ai_api_key

        # Fallback to config settings (which reads from .env)
        if not api_key:
            api_key = settings.GEMINI_API_KEY or settings.OPENAI_API_KEY

        masked_api_key = api_key[:8] + "..." if api_key else None
        local_log = local_log.bind(api_key=masked_api_key)

        if not api_key:
            local_log.error("API Key not configured.")
            raise ValueError(
                "AI連携用のAPIキー（Gemini）が設定されていません。\n"
                "「マスタ・システム管理」画面の「⚙️ AI・システム設定」タブ、または .env ファイルに GEMINI_API_KEY を登録してください。"
            )

        if not file_bytes or len(file_bytes) == 0:
            raise ValueError("アップロードされたファイルが空です。")

        # Determine MIME type and preprocess
        mime_type = "image/jpeg"
        if file_type.lower() == "pdf":
            try:
                # PDFの場合は最初のページをPNG画像にレンダリングする
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=200, alpha=False)
                    file_bytes = pix.tobytes("png")
                    mime_type = "image/png"
                else:
                    raise ValueError("PDFファイルが空（0ページ）です。")
            except Exception as e:
                self.log.error("PDF page rendering failed", error=str(e), exc_info=True)
                raise ValueError(
                    f"PDFファイルの読み込み・レンダリングに失敗しました: {str(e)}"
                ) from e
        elif file_type.lower() in ["png", "jpg", "jpeg", "webp"]:
            mime_type = f"image/{file_type.lower()}"
            if mime_type == "image/jpg":
                mime_type = "image/jpeg"
        else:
            raise ValueError(
                f"サポートされていないファイル形式です: {file_type} (対応形式: PDF, PNG, JPG, JPEG, WEBP)"
            )

        # Optimize image size/DPI
        optimized_bytes, final_mime_type = self._optimize_image(file_bytes, mime_type)

        # Format counterparty list for prompt
        cp_list_str = ""
        if counterparty_list:
            cp_list_str = "\n".join([f"- {cp}" for cp in counterparty_list])

        sys_instruct = f"""
You are an expert OCR assistant. Extract EXACTLY the following fields from the receipt image.
Do not make any accounting inferences.

### Registered Counterparty List
If the merchant name matches or resembles one of these, use the EXACT name from this list for "merchant_name".
{cp_list_str}

Extract the following fields into a valid JSON object matching the requested schema:
1. **merchant_name**: The name of the store or vendor. If illegible, use null.
2. **transaction_date**: The date of the transaction (Format: YYYY-MM-DD). 
3. **total_amount_incl_tax**: The total amount paid including tax (integer).
4. **invoice_registration_number**: The Japanese invoice registration number (Format: T + 13 digits). If not present or illegible, use null.
"""

        client = genai.Client(api_key=api_key)
        try:
            # Step 1: Raw Extraction via Gemini
            response_text = await self._call_gemini_api(
                client, sys_instruct, optimized_bytes, final_mime_type
            )

            if not response_text:
                raise ValueError("Gemini APIから応答が得られませんでした。")

            cleaned_json = self._clean_json_text(response_text)
            try:
                data = json.loads(cleaned_json)
            except json.JSONDecodeError as e:
                self.log.error("JSON decode error", raw=response_text, error=str(e))
                raise ValueError(
                    f"AI解析結果のJSONパースに失敗しました: {str(e)}"
                ) from e

            # Create ReceiptData model
            receipt = ReceiptData(
                merchant_name=data.get("merchant_name"),
                transaction_date=data.get("transaction_date"),
                total_amount_incl_tax=data.get("total_amount_incl_tax"),
                invoice_registration_number=data.get("invoice_registration_number"),
            )

            # カタカナの全角正規化 (NFKC)
            if receipt.merchant_name:
                receipt.merchant_name = unicodedata.normalize(
                    "NFKC", receipt.merchant_name
                ).strip()

            # インボイス番号のクレンジング (T+13桁)
            if receipt.invoice_registration_number:
                match = re.search(r"(T\d{13})", receipt.invoice_registration_number)
                receipt.invoice_registration_number = match.group(1) if match else None

            # Step 2: Journal Template (Dictionary) Matching
            async with container.master_service_scope() as master_service:
                cps = await master_service.get_counterparties()
                matched_template = None

                # 1. インボイス登録番号によるマッチング (T+13桁) を最優先
                if receipt.invoice_registration_number:
                    matched_template = next(
                        (
                            c
                            for c in cps
                            if c.invoice_number == receipt.invoice_registration_number
                        ),
                        None,
                    )

                # 2. 取引先名によるマッチング (インボイス番号で見つからなかった場合)
                if not matched_template and receipt.merchant_name:
                    norm_ocr = self._normalize_name(receipt.merchant_name)
                    for cp in cps:
                        if norm_ocr == self._normalize_name(cp.name):
                            matched_template = cp
                            break

                # マスタと一致した場合、マスタデータを適用する
                if matched_template:
                    receipt.merchant_name = matched_template.name
                    receipt.invoice_registration_number = (
                        matched_template.invoice_number
                    )
                    receipt.inferred_debit_account_id = (
                        str(matched_template.debit_account_id)
                        if matched_template.debit_account_id
                        else None
                    )
                    receipt.inferred_credit_account_id = (
                        str(matched_template.credit_account_id)
                        if matched_template.credit_account_id
                        else None
                    )
                    receipt.description = matched_template.description_template
                    receipt.is_registered_merchant = True
                    receipt.is_dictionary_matched = True
                    return self._validate_receipt(receipt)

                # Step 3: LLM Fallback Inference for unknown counterparties (Fault-tolerant)
                try:
                    acc_list_str = (
                        chr(10).join(account_list) if account_list else "一覧なし"
                    )
                    sys_instruct_fallback = f"""
あなたは免税事業者の経理担当です。
先ほど、取引先『{receipt.merchant_name or "不明"}』で『{receipt.total_amount_incl_tax or 0}円』支払った。
以下の【勘定科目一覧】の中から、適切な借方科目と貸方科目を推論し、JSON形式で返答してください。

【貸方の推論ルール（極めて重要）】
- 当社は法人名義の口座引き落とし以外は、ほぼ全て代表個人のポケットマネーからの立替払いである。
- そのため、貸方科目はデフォルトで「役員借入金」を優先的に推論すること。

【借方の推論ルール（極めて重要）】
- 当社の自家用車は法人に賃貸しているため、法人の固定資産にはならない。
- 車用・車関係であっても、「車両運搬具」などの科目は推論結果に絶対に含めないこと。

【勘定科目一覧】
{acc_list_str}

出力形式 (JSON):
{{
  "debit_account": "借方科目の名前",
  "credit_account": "貸方科目の名前（迷ったら役員借入金）",
  "description": "摘要文（例：〇〇代として）"
}}
"""
                    fallback_response_text = await self._call_gemini_fallback(
                        client, sys_instruct_fallback
                    )

                    if fallback_response_text:
                        fallback_clean = self._clean_json_text(fallback_response_text)
                        fallback_data = json.loads(fallback_clean)
                        accounts_db = await master_service.get_accounts()

                        def find_acc_id(name):
                            if not name:
                                return None
                            # Try exact match or find in code: name string
                            for acc in accounts_db:
                                if (
                                    acc.name == name
                                    or name in f"{acc.code}: {acc.name}"
                                ):
                                    return str(acc.id)
                            return None

                        receipt.inferred_debit_account_id = find_acc_id(
                            fallback_data.get("debit_account")
                        )
                        receipt.inferred_credit_account_id = find_acc_id(
                            fallback_data.get("credit_account")
                        )
                        receipt.description = fallback_data.get(
                            "description", receipt.merchant_name
                        )
                except Exception as fb_err:
                    self.log.warning(
                        "Fallback account inference failed (continuing with raw OCR)",
                        error=str(fb_err),
                    )

            return self._validate_receipt(receipt)

        except APIError as e:
            self.log.error("Gemini API Error", error=str(e))
            err_msg = getattr(e, "message", None) or str(e)
            raise ValueError(f"Gemini API エラーが発生しました: {err_msg}") from e
        except ValueError as e:
            self.log.error("Validation/Config Error", error=str(e))
            raise e
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
        self.log.info("call_gemini_api_start", model=model)

        contents: list[Any] = [
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            types.Part.from_text(text=sys_instruct),
        ]

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ReceiptExtractionSchema,
            temperature=0.0,
        )

        response = await client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )
        result = response.text or ""
        self.log.info("call_gemini_api_success")
        return result

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_gemini_fallback(
        self, client: genai.Client, sys_instruct_fallback: str
    ) -> str:
        model = settings.GEMINI_DEFAULT_MODEL
        self.log.info("call_gemini_fallback_start", model=model)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=AccountInferenceSchema,
            temperature=0.0,
        )

        response = await client.aio.models.generate_content(
            model=model,
            contents=sys_instruct_fallback,
            config=config,
        )
        result = response.text or ""
        self.log.info("call_gemini_fallback_success")
        return result

    def _clean_json_text(self, text: str) -> str:
        """Markdownコードブロックなどを安全に除去してJSON文字列を取り出す"""
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def _normalize_name(self, name: str) -> str:
        """
        Normalize company name for fuzzy matching.
        1. Convert to NFKC (converts half-width Katakana to full-width Katakana).
        2. Remove spaces (full/half).
        3. Remove corporate status (株式会社, etc).
        """
        if not name:
            return ""

        name = unicodedata.normalize("NFKC", name)

        # 2. Remove spaces
        name = name.replace(" ", "").replace("　", "")

        # 3. Remove corporate statuses (Common ones)
        statuses = [
            "株式会社",
            "有限会社",
            "合同会社",
            "合名会社",
            "合資会社",
            "一般社団法人",
            "公益社団法人",
            "一般財団法人",
            "公益財団法人",
            "医療法人",
            "学校法人",
            "宗教法人",
            "社会福祉法人",
            "特定非営利活動法人",
            "NPO法人",
            "(株)",
            "(有)",
            "(同)",
            "(名)",
            "(資)",
            "(財)",
            "(社)",
            "㈱",
            "㈲",
            "㈇",
            "㈆",
            "㈅",
            "㈄",
            "㈃",
            "㈂",
            "㈁",
        ]

        for status in statuses:
            name = name.replace(status, "")

        return name

    def _validate_receipt(self, data: ReceiptData) -> ReceiptData:
        messages = []

        # 1. Math Validation
        calc_total_tax = 0
        calc_total_excl = 0

        if data.tax_breakdown:
            for item in data.tax_breakdown:
                tax_amt = item.tax_amount or 0
                excl_amt = item.amount_excl_tax or 0

                calc_total_tax += tax_amt
                calc_total_excl += excl_amt

                # Check rate consistency per item
                rate_str = (
                    "0.10"
                    if "10" in item.tax_rate
                    else "0.08"
                    if "8" in item.tax_rate
                    else "0.00"
                )
                if rate_str != "0.00" and excl_amt > 0:
                    excl_dec = Decimal(str(excl_amt))
                    rate_dec = Decimal(rate_str)
                    expected_tax = int(
                        (excl_dec * rate_dec).quantize(
                            Decimal("1"), rounding=ROUND_HALF_UP
                        )
                    )
                    # Allow +/- 1 mismatch
                    if abs(expected_tax - tax_amt) > 1:
                        messages.append(
                            f"消費税計算不整合 ({item.tax_rate}: 対象{excl_amt}, 税額{tax_amt})"
                        )

        # Check Aggregated Totals
        if (
            data.total_tax_amount is not None
            and abs(calc_total_tax - data.total_tax_amount) > 1
        ):
            messages.append(
                f"消費税合計不整合 (計算値:{calc_total_tax}, OCR値:{data.total_tax_amount})"
            )

        if (
            data.total_amount_excl_tax is not None
            and abs(calc_total_excl - data.total_amount_excl_tax) > 1
        ):
            messages.append(
                f"税抜合計不整合 (計算値:{calc_total_excl}, OCR値:{data.total_amount_excl_tax})"
            )

        # Check Grand Total
        if data.total_amount_incl_tax:
            calc_grand_total = (data.total_amount_excl_tax or 0) + (
                data.total_tax_amount or 0
            )
            if abs(calc_grand_total - data.total_amount_incl_tax) > 1:
                # Only flag if components are present
                if (data.total_amount_excl_tax or 0) > 0:
                    messages.append(
                        f"支払合計不整合 (計算値:{calc_grand_total}, OCR値:{data.total_amount_incl_tax})"
                    )

        # 2. Date Validation
        if data.transaction_date:
            try:
                from datetime import date

                date.fromisoformat(data.transaction_date)
            except ValueError:
                messages.append(f"日付フォーマット不正: {data.transaction_date}")
                data.transaction_date = None

        # 3. Invoice Number Validation
        if data.invoice_registration_number:
            # Extract pattern T + 13 digits from the string
            match = re.search(r"(T\d{13})", data.invoice_registration_number)
            if match:
                data.invoice_registration_number = match.group(1)
            else:
                messages.append(
                    f"インボイス番号の形式が不正です: {data.invoice_registration_number}"
                )

        # 4. Aggregation works
        if messages:
            data.needs_manual_review = True
            existing_err = data.error_message or ""
            data.error_message = f"{existing_err} | ".strip(" | ") + "; ".join(messages)

        return data

    def _optimize_image(self, file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
        """
        画像の長辺が大きすぎる場合やPNGを高効率なJPEGに圧縮して軽量化する。
        """
        try:
            with Image.open(io.BytesIO(file_bytes)) as img:
                current_dpi = img.info.get("dpi")
                max_pixels = 2000

                needs_compression = False
                if current_dpi and current_dpi[0] > 200:
                    needs_compression = True
                elif max(img.size) > max_pixels:
                    needs_compression = True
                elif mime_type == "image/png":
                    # PNGはバイト数が膨らみやすいためJPEG変換で軽量化
                    needs_compression = True

                if needs_compression:
                    img.thumbnail((max_pixels, max_pixels), Image.Resampling.LANCZOS)
                    processed_img: Any = (
                        img.convert("RGB") if img.mode != "RGB" else img
                    )
                    output = io.BytesIO()
                    processed_img.save(
                        output, format="JPEG", dpi=(200, 200), quality=85
                    )
                    return output.getvalue(), "image/jpeg"

                return file_bytes, mime_type

        except Exception as e:
            self.log.warning(
                "Image optimization failed, sending raw bytes", error=str(e)
            )
            return file_bytes, mime_type


# Backward compatibility alias
OpenAIOCRService = GeminiOCRService
