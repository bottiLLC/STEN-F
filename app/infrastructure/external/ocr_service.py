import os
import json
from typing import Optional
from pydantic import BaseModel, ConfigDict
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Re-using the Pydantic model for internal data transfer
from domain.models.receipt import ReceiptData



class GoogleOCRService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def extract_receipt_data(self, file_bytes: bytes, file_type: str, account_list: list[str] = None) -> Optional[ReceiptData]:
        if not self.client:
            print("ERROR: GOOGLE_API_KEY not found.")
            return None
            
        # Determine Mime Type
        mime_type = "image/jpeg" # Default
        if file_type.lower() == "pdf":
            mime_type = "application/pdf"
        elif file_type.lower() in ["png", "jpg", "jpeg"]:
             mime_type = f"image/{file_type.lower()}"
             if mime_type == "image/jpg": mime_type = "image/jpeg"

        image_part = None
        
        if file_type.lower() == "pdf":
            try:
                import fitz # PyMuPDF
                doc = fitz.open(stream=file_bytes, filetype="pdf")
                page = doc.load_page(0) 
                pix = page.get_pixmap(dpi=300)
                img_bytes = pix.tobytes("png")
                image_part = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
            except ImportError:
                print("PyMuPDF not installed")
                return None
            except Exception as e:
                print(f"PDF Conversion Error: {e}")
                return None
        else:
            image_part = types.Part.from_bytes(data=file_bytes, mime_type=mime_type)
            
        accounts_str = ", ".join(account_list) if account_list else "未分類, 消耗品費, 旅費交通費, 交際費, 新聞図書費"

        sys_instruct = f"""
            # Core Philosophy: "Sten-gun"
            - Minimalist over complex. 
            - Logic over inference. 
            - Reliability over versatility.
            - This is for professional use; assume the user expects zero mathematical errors.

            # Task
            Analyze the provided receipt image and extract data into STRICT JSON format.

            # JSON Schema
            {{
              "vendor_name": "string (The name of the vendor. ALWAYS abbreviate legal entities: e.g. 株式会社->(株), 有限会社->(有), 合同会社->(同), 合資会社->(資), etc.)",
              "date": "YYYY-MM-DD",
              "account_item": "string (MUST be one of: {accounts_str})",
              "tax_8_base": number (integer, 0 if null),
              "tax_8_amount": number (integer, 0 if null),
              "tax_10_base": number (integer, 0 if null),
              "tax_10_amount": number (integer, 0 if null),
              "total_amount": number (integer),
              "invoice_number": "string (T+13 digits, e.g. T1234567890123. If not found, null)",
              "confidence_score": number (0.0 - 1.0),
              "needs_manual_review": boolean,
              "error_message": "string | null"
            }}

            # Business Rules
            1. Master Data Mapping: Select the most appropriate 'account_item' from the provided list based on the receipt content.
            2. Tax Logic: 
               - Separate 8% (reduced tax) and 10% (standard tax) items if possible.
               - If no tax breakdown is visible, assume 10% or apply simple logic, but check total.
            3. Values: JPY only. Integer only (no decimals). No negative values.
            4. Error Handling:
               - If image is blurry/illegible: confidence_score < 0.5, needs_manual_review = true.
               - If "First-time Vendor" (you cannot know this, but if name is unclear), flag review.

            # Validation Logic (CRITICAL)
            Before outputting, you MUST internally verify:
            1. Suggest valid 'account_item' from list.
            2. Check: tax_8_base * 0.08 approx equals tax_8_amount (+- 1)
            3. Check: tax_10_base * 0.10 equals tax_10_amount
            4. Check: (tax_8_base + tax_8_amount) + (tax_10_base + tax_10_amount) == total_amount
            
            If any math check fails materially, set "needs_manual_review": true and "error_message": "Math mismatch".
            If the image is not a receipt, return null fields.
        """
        
        try:
            # Run async
            response = await self.client.aio.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text="Extract receipt data"),
                            image_part
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0, # Cold, technical
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    system_instruction=sys_instruct
                )
            )
            data = json.loads(response.text)
            receipt = ReceiptData(**data)
            return self._validate_receipt(receipt, account_list)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return None

    def _validate_receipt(self, data: ReceiptData, account_list: list[str] = None) -> ReceiptData:
        messages = []
        
        # 1. Tax Math Validation (Allow slight rounding errors of +/- 1 JPY)
        tax_8_base = data.tax_8_base or 0
        tax_8_amount = data.tax_8_amount or 0
        tax_10_base = data.tax_10_base or 0
        tax_10_amount = data.tax_10_amount or 0
        total_amount = data.total_amount or 0

        # Check 8%
        if abs(tax_8_base * 0.08 - tax_8_amount) > 1:
             messages.append(f"8%消費税不整合 (対象:{tax_8_base}, 税額:{tax_8_amount})")

        # Check 10%
        if abs(tax_10_base * 0.10 - tax_10_amount) > 1:
             messages.append(f"10%消費税不整合 (対象:{tax_10_base}, 税額:{tax_10_amount})")

        # Check Total (Base + Tax = Total)
        calc_total = (tax_8_base + tax_8_amount) + (tax_10_base + tax_10_amount)
        if total_amount > 0 and abs(calc_total - total_amount) > 1:
             if calc_total > 0:
                 messages.append(f"合計金額不整合 (計算値:{calc_total}, OCR値:{total_amount})")

        # 2. Date Validation
        if data.date:
            try:
                from datetime import date
                date.fromisoformat(data.date)
            except ValueError:
                messages.append(f"日付フォーマット不正: {data.date}")
                data.date = None

        # 3. Account Item Validation
        if account_list and data.account_item:
            if data.account_item not in account_list:
                # If exact match fails, it might be a valid guess but not in list style
                messages.append(f"勘定科目 '{data.account_item}' はマスタに存在しません")

        # 4. Invoice Number Validation
        if data.invoice_number:
            import re
            # Extract pattern T + 13 digits from the string
            match = re.search(r'(T\d{13})', data.invoice_number)
            if match:
                data.invoice_number = match.group(1)
            else:
                messages.append(f"インボイス番号の形式が不正です: {data.invoice_number}")

        # 5. Aggregation works
        if messages:
            data.needs_manual_review = True
            existing_err = data.error_message or ""
            data.error_message = f"{existing_err} | ".strip(" | ") + "; ".join(messages)

        return data
