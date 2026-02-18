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
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")

    async def extract_receipt_data(self, file_bytes: bytes, file_type: str, account_list: list[str] = None) -> Optional[ReceiptData]:
        if not self.api_key:
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
            
        sys_instruct = """
You are an expert AI assistant specialized in accounting and OCR data extraction. Your task is to extract specific financial information from the provided image of a receipt.

Please analyze the receipt and extract the following information into a valid JSON object. Do not include any markdown formatting (like ```json) in your response, just the raw JSON string.

Extract the following fields:
1. **merchant_name**: The name of the store or vendor.
2. **transaction_date**: The date of the transaction (Format: YYYY-MM-DD). If the year is omitted, assume the current year or infer from context if possible.
3. **total_amount_incl_tax**: The total amount paid including tax (integer).
4. **invoice_registration_number**: The qualified invoice issuer registration number (e.g., T1234567890123). If not found, return null.
5. **tax_breakdown**: An array of objects detailing tax amounts per tax rate. Each object should contain:
    - "tax_rate": The tax rate (e.g., "10%" or "8%").
    - "tax_amount": The amount of consumption tax for this rate.
    - "amount_excl_tax": The taxable amount (price excluding tax) for this rate.
6. **total_tax_amount**: The sum of all consumption tax amounts.
7. **total_amount_excl_tax**: The total price excluding tax.

Notes:
- If a specific field is not found or is illegible, use null for that field.
- Ensure the 'invoice_registration_number' follows the format 'T' followed by 13 digits if it exists.
- Correct any obvious OCR errors based on context, but prioritize accuracy.
- Return ONLY the JSON object.
"""
        
        import asyncio
        import random

        max_retries = 3
        base_delay = 1.0

        client = genai.Client(api_key=self.api_key)
        try:
            for attempt in range(max_retries):
                try:
                    # Run async
                    response = await client.aio.models.generate_content(
                        model="gemini-3-flash-preview", 
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
                    
                    # Check for empty response or error
                    if not response.text:
                        raise ValueError("Empty response from Gemini")

                    data = json.loads(response.text)
                    receipt = ReceiptData(**data)
                    return self._validate_receipt(receipt)

                except Exception as e:
                    # Check for 503 or 429
                    error_str = str(e)
                    if "503" in error_str or "429" in error_str:
                        if attempt < max_retries - 1:
                            delay = (base_delay * (2 ** attempt)) + (random.uniform(0, 1))
                            print(f"Gemini API Busy (Attempt {attempt+1}/{max_retries}). Retrying in {delay:.2f}s...")
                            await asyncio.sleep(delay)
                            continue
                    
                    print(f"Gemini API Error (Final): {e}")
                    return None
            return None
        finally:
            client.close()

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
