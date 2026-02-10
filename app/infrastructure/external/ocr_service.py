import os
import json
from typing import Optional
from pydantic import BaseModel, ConfigDict
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Re-using the Pydantic model for internal data transfer
class ReceiptData(BaseModel):
    date: Optional[str] = None
    store_name: Optional[str] = None
    total_amount: Optional[int] = None
    suggested_account_type: Optional[str] = None
    invoice_number: Optional[str] = None 
    
    model_config = ConfigDict(extra='ignore')

class GoogleOCRService:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def extract_receipt_data(self, file_bytes: bytes, file_type: str) -> Optional[ReceiptData]:
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
            
        sys_instruct = """
            You are an expert accountant assistant specializing in Japanese receipts. 
            Analyze the provided receipt image and extract the following information in JSON format:
            
            - date (YYYY-MM-DD): The transaction date.
            - store_name: The name of the store/vendor. 
              Prioritize the name that includes legal entity designations but ALWAYS abbreviate them.
              - Convert '株式会社' to '(株)'
              - Convert '有限会社' to '(有)'
              - Convert '合同会社' to '(同)'
              - Convert '合資会社' to '(資)'
              - Convert '合名会社' to '(名)'
              - Convert '一般社団法人' to '(一社)'
              - Convert '公益社団法人' to '(公社)'
              - Convert '一般財団法人' to '(一財)'
              - Convert '公益財団法人' to '(公財)'
              - Convert '特定非営利活動法人' to '(NPO)'
              - Convert '社会福祉法人' to '(社福)'
              - Convert '医療法人' to '(医)'
              - Convert '学校法人' to '(学)'
              - Convert '宗教法人' to '(宗)'
              Example: if receipt says '株式会社セブンイレブン', return '(株)セブンイレブン'.
            - total_amount (integer): The total amount paid (tax included). Remove commas and symbols.
            - suggested_account_type: Choose best one from ['消耗品費', '旅費交通費', '交際費', '新聞図書費', '未分類'].
            - invoice_number: The Qualified Invoice Issuers Registration Number (適格請求書発行事業者登録番号). 
              It always starts with 'T' followed by 13 digits (e.g., T1234567890123).
              Look for labels like "登録番号", "法人番号", or just "T". 
              If not found, return null.
            
            If the image is not a receipt, return null values.
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
                    temperature=0.1,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                    system_instruction=sys_instruct
                )
            )
            data = json.loads(response.text)
            return ReceiptData(**data)
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return None
