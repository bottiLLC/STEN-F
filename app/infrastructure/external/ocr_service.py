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
            You are an expert accountant assistant. 
            Analyze the provided receipt image and extract the following information in JSON format:
            - date (YYYY-MM-DD)
            - store_name
            - total_amount (integer, no symbols)
            - suggested_account_type (Choose one from: '消耗品費', '旅費交通費', '交際費', '新聞図書費', '未分類')
            
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
