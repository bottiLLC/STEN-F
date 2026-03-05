import os
import json
import io 
from typing import Optional
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

from core.logging import logger
from core.resilience import resilient_api_call

# Re-using the Pydantic model for internal data transfer
from domain.models.receipt import ReceiptData



class GoogleOCRService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.log = logger.bind(service="GoogleOCRService")

    async def extract_receipt_data(self, file_bytes: bytes, file_type: str, account_list: list[str] = None, counterparty_list: list[str] = None) -> Optional[ReceiptData]:
        if not self.api_key:
            self.log.error("GOOGLE_API_KEY not found.")
            return None
            
        # Determine Mime Type
        mime_type = "image/jpeg" # Default
        if file_type.lower() == "pdf":
            mime_type = "application/pdf"
        elif file_type.lower() in ["png", "jpg", "jpeg"]:
             mime_type = f"image/{file_type.lower()}"
             if mime_type == "image/jpg": 
                 mime_type = "image/jpeg"

        image_part = None
        
        # Determine basic MIME type first
        mime_type = "image/jpeg" # Default
        if file_type.lower() == "pdf":
            mime_type = "application/pdf"
        elif file_type.lower() in ["png", "jpg", "jpeg"]:
             mime_type = f"image/{file_type.lower()}"
             if mime_type == "image/jpg": 
                 mime_type = "image/jpeg"

        # Optimize image if needed (PDFs are passed through)
        optimized_bytes, final_mime_type = self._optimize_for_gemini(file_bytes, mime_type)
        
        image_part = types.Part.from_bytes(data=optimized_bytes, mime_type=final_mime_type)



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
        
        client = genai.Client(api_key=self.api_key)
        try:
            # Step 1: Raw Extraction
            response = await self._call_gemini_api(client, sys_instruct, image_part)
            
            if not response.text:
                raise ValueError("Empty response from Gemini")

            data = json.loads(response.text)
            # Safely create ReceiptData ignoring extra fields if LLM hallucinates them
            receipt = ReceiptData(**{k: v for k, v in data.items() if k in ReceiptData.model_fields})
            
            # Step 2: Journal Template (Dictionary) Matching
            from app.ui.di import DI
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
                    template = await master_service.get_counterparty_by_keyword(receipt.merchant_name)
                    if template:
                        # Map invoice number from master if available
                        receipt.invoice_registration_number = template.invoice_number if template.invoice_number else None
                        # Map dictionary data
                        receipt.inferred_debit_account_id = str(template.debit_account_id) if template.debit_account_id else None
                        receipt.inferred_credit_account_id = str(template.credit_account_id) if template.credit_account_id else None
                        receipt.description = template.description_template
                        receipt.is_dictionary_matched = True
                        return self._validate_receipt(receipt)

                # Step 3: LLM Fallback Inference for unknown counterparties
                acc_list_str = chr(10).join(account_list) if account_list else '一覧なし'
                sys_instruct_fallback = f"""
お前は免税事業者の経理担当だ。
先ほど、取引先『{receipt.merchant_name or '不明'}』で『{receipt.total_amount_incl_tax or 0}円』支払った。
以下の【勘定科目一覧】の中から、適切な借方科目と貸方科目を推論し、JSON形式で返答しろ。

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
                fallback_response = await client.aio.models.generate_content(
                    model="gemini-3.1-flash-lite-preview",
                    contents=[sys_instruct_fallback],
                    config=types.GenerateContentConfig(
                        temperature=0.0,
                        response_mime_type="application/json",
                    )
                )
                
                if fallback_response.text:
                    fallback_data = json.loads(fallback_response.text)
                    accounts_db = await master_service.get_accounts()
                    
                    def find_acc_id(name):
                        if not name: 
                            return None
                        # Try exact match or find in code: name string
                        for acc in accounts_db:
                            if acc.name == name or name in f"{acc.code}: {acc.name}":
                                return str(acc.id)
                        return None
                        
                    receipt.inferred_debit_account_id = find_acc_id(fallback_data.get("debit_account"))
                    receipt.inferred_credit_account_id = find_acc_id(fallback_data.get("credit_account"))
                    receipt.description = fallback_data.get("description", receipt.merchant_name)
                    
            return self._validate_receipt(receipt)

        except Exception as e:
            self.log.error("Failed to extract receipt data", error=str(e), exc_info=True)
            return None
        finally:
            pass # The new google genai SDK does not require or support explicit closing of the async client.

    @resilient_api_call(max_retries=3, base_delay=0.5)
    async def _call_gemini_api(self, client, sys_instruct, image_part):
        return await client.aio.models.generate_content(
            model="gemini-3.1-flash-lite-preview", 
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=sys_instruct),
                        image_part
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=8192,
                response_mime_type="application/json",
            )
        )


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
            "株式会社", "有限会社", "合同会社", "合名会社", "合資会社",
            "一般社団法人", "公益社団法人", "一般財団法人", "公益財団法人",
            "医療法人", "学校法人", "宗教法人", "社会福祉法人", 
            "特定非営利活動法人", "NPO法人",
            "(株)", "(有)", "(同)", "(名)", "(資)", "(財)", "(社)",
            "㈱", "㈲", "㈇", "㈆", "㈅", "㈄", "㈃", "㈂", "㈁"
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
                rate_val = 0.10 if "10" in item.tax_rate else 0.08 if "8" in item.tax_rate else 0.0
                if rate_val > 0 and excl_amt > 0:
                     expected_tax = int(excl_amt * rate_val)
                     # Allow +/- 1 mismatch
                     if abs(expected_tax - tax_amt) > 1:
                         messages.append(f"消費税計算不整合 ({item.tax_rate}: 対象{excl_amt}, 税額{tax_amt})")

        # Check Aggregated Totals
        if data.total_tax_amount is not None and abs(calc_total_tax - data.total_tax_amount) > 1:
             messages.append(f"消費税合計不整合 (計算値:{calc_total_tax}, OCR値:{data.total_tax_amount})")

        if data.total_amount_excl_tax is not None and abs(calc_total_excl - data.total_amount_excl_tax) > 1:
             messages.append(f"税抜合計不整合 (計算値:{calc_total_excl}, OCR値:{data.total_amount_excl_tax})")

        # Check Grand Total
        if data.total_amount_incl_tax:
            calc_grand_total = (data.total_amount_excl_tax or 0) + (data.total_tax_amount or 0)
            if abs(calc_grand_total - data.total_amount_incl_tax) > 1:
                 # Only flag if components are present
                 if (data.total_amount_excl_tax or 0) > 0:
                     messages.append(f"支払合計不整合 (計算値:{calc_grand_total}, OCR値:{data.total_amount_incl_tax})")

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
            match = re.search(r'(T\d{13})', data.invoice_registration_number)
            if match:
                data.invoice_registration_number = match.group(1)
            else:
                messages.append(f"インボイス番号の形式が不正です: {data.invoice_registration_number}")

        # 4. Aggregation works
        if messages:
            data.needs_manual_review = True
            existing_err = data.error_message or ""
            data.error_message = f"{existing_err} | ".strip(" | ") + "; ".join(messages)

        return data

    def _optimize_for_gemini(self, file_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
        """
        PDFはそのまま、画像はデカすぎたら圧縮して返す最適化処理
        """
        # PDFなら即パス
        if mime_type == "application/pdf":
            return file_bytes, mime_type

        # ここから画像処理
        try:
            # The original code used io.BytesIO and PIL.Image without local imports.
            # Assuming these are imported globally or the instruction implies removing their usage.
            # As per the instruction to "Remove the local imports", and since no local import statements exist,
            # no changes are made to the usage of io.BytesIO and Image.open within this method.
            # If the intent was to remove their usage, the code would break.
            # Therefore, faithfully interpreting "remove local imports" means no lines are removed here.
            with Image.open(io.BytesIO(file_bytes)) as img:
                # 現在のDPIを取得（無い場合はNoneになる）
                current_dpi = img.info.get('dpi')
                
                # APIに投げる時の限界サイズ（長辺2000pxあればレシートの文字は余裕で読める）
                max_pixels = 2000 
                
                # 「DPIが200より大きい」または「長辺が2000pxを超えている」なら圧縮発動
                needs_compression = False
                if current_dpi and current_dpi[0] > 200:
                    needs_compression = True
                elif max(img.size) > max_pixels:
                    needs_compression = True

                if needs_compression:
                    # アスペクト比を保ったまま縮小（サムネイル化）
                    img.thumbnail((max_pixels, max_pixels), Image.Resampling.LANCZOS)
                    
                    # JPEG保存のためにRGBモードに変換（透過PNGなどを防ぐ）
                    if img.mode in ("RGBA", "P"):
                        img = img.convert("RGB")
                        
                    output = io.BytesIO()
                    # ここでDPIを200に上書きし、画質85%で圧縮してバイナリ化
                    img.save(output, format="JPEG", dpi=(200, 200), quality=85)
                    
                    # 圧縮成功。MIMEタイプもJPEGに更新して返す
                    return output.getvalue(), "image/jpeg"
                
                # 圧縮条件に引っかからなかった（小さくて軽い）場合はそのまま返す
                return file_bytes, mime_type

        except Exception as e:
            # 万が一Pillowで開けない変なファイルが来たら、元のデータをそのまま投げる（フェイルセーフ）
            self.log.warning("Image optimization failed", error=str(e))
            return file_bytes, mime_type
