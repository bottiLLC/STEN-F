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

import json
import io
import base64
from typing import Optional, Any
from PIL import Image
import fitz  # PyMuPDF
from decimal import Decimal, ROUND_HALF_UP
import structlog
from openai import AsyncOpenAI, APIError
from tenacity import retry, wait_exponential, stop_after_attempt

from app.config import settings

# Re-using the Pydantic model for internal data transfer
from app.domain.models.receipt import ReceiptData

log = structlog.get_logger()


class OpenAIOCRService:
    def __init__(self):
        self.log = log.bind(service="OpenAIOCRService")

    async def extract_receipt_data(
        self,
        file_bytes: bytes,
        file_type: str,
        account_list: list[str] | None = None,
        counterparty_list: list[str] | None = None,
    ) -> Optional[ReceiptData]:
        # Include all function input parameters in log context, masking sensitive keys
        local_log = self.log.bind(
            file_type=file_type,
            file_bytes_len=len(file_bytes),
            account_list=account_list,
            counterparty_list=counterparty_list,
        )
        local_log.info("extract_receipt_data_start")

        from app.ui.di import DI

        async with DI.get_master_service() as ms:
            system_settings = await ms.get_system_settings()
            api_key = system_settings.ai_api_key

        # Fallback to config settings (which reads from .env)
        if not api_key:
            api_key = settings.OPENAI_API_KEY

        masked_api_key = api_key[:8] + "..." if api_key else None
        local_log = local_log.bind(api_key=masked_api_key)

        if not api_key:
            local_log.error("API Key not configured.")
            raise ValueError(
                "システム設定画面からAI連携用のAPIキー（OpenAI）を登録してください。"
            )

        # Determine MIME type first
        mime_type = "image/jpeg"  # Default
        if file_type.lower() == "pdf":
            try:
                # PDFの場合は最初のページをPNG画像にレンダリングする
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                if len(doc) > 0:
                    page = doc.load_page(0)
                    pix = page.get_pixmap(dpi=200)
                    file_bytes = pix.tobytes("png")
                    mime_type = "image/png"
                else:
                    raise ValueError("PDF file is empty")
            except Exception as e:
                self.log.error("PDF page rendering failed", error=str(e))
                raise ValueError("PDFファイルの読み込みに失敗しました。") from e
        elif file_type.lower() in ["png", "jpg", "jpeg"]:
            mime_type = f"image/{file_type.lower()}"
            if mime_type == "image/jpg":
                mime_type = "image/jpeg"

        # Optimize image size/DPI
        optimized_bytes, final_mime_type = self._optimize_image(file_bytes, mime_type)
        base64_image = base64.b64encode(optimized_bytes).decode("utf-8")

        # Format counterparty list for prompt
        cp_list_str = ""
        if counterparty_list:
            cp_list_str = "\n".join([f"- {cp}" for cp in counterparty_list])

        sys_instruct = f"""
You are an expert OCR assistant. Extract EXACTLY the following 3 pieces of information from the receipt image.
Do not make any accounting inferences.

### Registered Counterparty List
If the merchant name matches or resembles one of these, use the EXACT name from this list for "merchant_name".
{cp_list_str}

Extract the following fields into a valid JSON object:
1. **merchant_name**: The name of the store or vendor. If illegible, use null.
2. **transaction_date**: The date of the transaction (Format: YYYY-MM-DD). 
3. **total_amount_incl_tax**: The total amount paid including tax (integer).

Return ONLY the raw JSON object without markdown formatting.
"""

        client = AsyncOpenAI(api_key=api_key)
        try:
            # Step 1: Raw Extraction
            response_text = await self._call_openai_api(
                client, sys_instruct, base64_image, final_mime_type
            )

            if not response_text:
                raise ValueError("Empty response from OpenAI")

            data = json.loads(response_text)
            # Safely create ReceiptData ignoring extra fields if LLM hallucinates them
            receipt = ReceiptData(
                **{k: v for k, v in data.items() if k in ReceiptData.model_fields}
            )

            # Step 2: Journal Template (Dictionary) Matching
            async with DI.get_master_service() as master_service:
                # Normalize OCR result and check against counterparty list
                if counterparty_list and receipt.merchant_name:
                    norm_ocr = self._normalize_name(receipt.merchant_name)
                    for registered_name in counterparty_list:
                        if norm_ocr == self._normalize_name(registered_name):
                            receipt.merchant_name = registered_name
                            receipt.is_registered_merchant = True
                            break

                if receipt.merchant_name:
                    template = await master_service.get_counterparty_by_keyword(
                        receipt.merchant_name
                    )
                    if template:
                        # Map invoice number from master if available
                        receipt.invoice_registration_number = (
                            template.invoice_number if template.invoice_number else None
                        )
                        # Map dictionary data
                        receipt.inferred_debit_account_id = (
                            str(template.debit_account_id)
                            if template.debit_account_id
                            else None
                        )
                        receipt.inferred_credit_account_id = (
                            str(template.credit_account_id)
                            if template.credit_account_id
                            else None
                        )
                        receipt.description = template.description_template
                        receipt.is_dictionary_matched = True
                        return self._validate_receipt(receipt)

                # Step 3: LLM Fallback Inference for unknown counterparties
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
                fallback_response_text = await self._call_openai_fallback(
                    client, sys_instruct_fallback
                )

                if fallback_response_text:
                    fallback_data = json.loads(fallback_response_text)
                    accounts_db = await master_service.get_accounts()

                    def find_acc_id(name):
                        if not name:
                            return None
                        # Try exact match or find in code: name string
                        for acc in accounts_db:
                            if acc.name == name or name in f"{acc.code}: {acc.name}":
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

            return self._validate_receipt(receipt)

        except APIError as e:
            self.log.error("OpenAI API Error", error=str(e))
            raise ValueError(f"OpenAI API エラーが発生しました: {e.message}") from e
        except ValueError as e:
            self.log.error("Configuration Error", error=str(e))
            raise e
        except Exception as e:
            self.log.exception("Failed to extract receipt data", error=str(e))
            return None

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_openai_api(
        self, client: AsyncOpenAI, sys_instruct: str, base64_image: str, mime_type: str
    ) -> str:
        from app.config import settings

        model = settings.OPENAI_DEFAULT_MODEL
        effort = settings.OPENAI_REASONING_EFFORT

        self.log.info("call_openai_api_start", model=model, reasoning_effort=effort)

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": sys_instruct},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
        }

        if model.startswith("o") or "5.6" in model:
            payload["reasoning_effort"] = effort
        else:
            payload["temperature"] = 0.0

        response = await client.chat.completions.create(**payload)
        result = response.choices[0].message.content or ""
        self.log.info("call_openai_api_success")
        return result

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_openai_fallback(
        self, client: AsyncOpenAI, sys_instruct_fallback: str
    ) -> str:
        from app.config import settings

        model = settings.OPENAI_DEFAULT_MODEL
        effort = settings.OPENAI_REASONING_EFFORT

        self.log.info(
            "call_openai_fallback_start", model=model, reasoning_effort=effort
        )

        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": sys_instruct_fallback}],
            "response_format": {"type": "json_object"},
        }

        if model.startswith("o") or "5.6" in model:
            payload["reasoning_effort"] = effort
        else:
            payload["temperature"] = 0.0

        response = await client.chat.completions.create(**payload)
        result = response.choices[0].message.content or ""
        self.log.info("call_openai_fallback_success")
        return result

    def _normalize_name(self, name: str) -> str:
        """
        Normalize company name for fuzzy matching.
        1. Remove spaces (full/half).
        2. Remove corporate status (株式会社, etc).
        """
        if not name:
            return ""

        # 1. Remove spaces
        name = name.replace(" ", "").replace("　", "")

        # 2. Remove corporate statuses (Common ones)
        # Order matters: longer strings first to avoid partial replacements
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
        # Check Total Tax vs Breakdown Sum
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
            import re

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
        PDFはすでに変換済みのため画像のみ。長辺2000px以内、DPIが大きすぎる場合はリサイズして軽量化する。
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

                if needs_compression:
                    img.thumbnail((max_pixels, max_pixels), Image.Resampling.LANCZOS)
                    processed_img: Any = (
                        img.convert("RGB") if img.mode in ("RGBA", "P") else img
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
