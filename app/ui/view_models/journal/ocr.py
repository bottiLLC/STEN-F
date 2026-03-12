import reflex as rx
from typing import List, Optional
from core.logging import logger
from app.ui.di import DI
from .base import JournalState
from .master import JournalMasterState

class JournalOCRState(JournalState):
    """Handles OCR file uploads and processing."""
    
    is_analyzing: bool = False
    uploaded_files: List[str] = []
    
    # Internal storage for file to be saved on submit
    _uploaded_file_data: Optional[bytes] = None
    _uploaded_filename: Optional[str] = None

    async def handle_upload(self, files: List[rx.UploadFile]):
        """Handle file upload for OCR."""
        self.is_analyzing = True
        yield
        
        try:
            for file in files:
                upload_data = await file.read()
                file_type = file.filename.split('.')[-1]
                
                # Store for later saving by JournalFormState
                self._uploaded_file_data = upload_data
                self._uploaded_filename = file.filename
                
                ocr_service = DI.get_ocr_service()
                master_state = await self.get_state(JournalMasterState)
                
                # Prepare context
                acc_options = [f"{a.code}: {a.name}" for a in master_state.accounts]
                
                cp_options = []
                async with DI.get_master_service() as service:
                     cps = await service.get_counterparties()
                     cp_options = [c.name for c in cps]

                # Call OCR
                receipt_data = await ocr_service.extract_receipt_data(upload_data, file_type, acc_options, cp_options)
                
                if receipt_data:
                    await self._apply_ocr_result(receipt_data)
                    
                    if receipt_data.is_registered_merchant:
                        yield rx.toast(f"登録済みの取引先「{receipt_data.merchant_name}」と一致しました。", duration=5000, close_button=True)
                    else:
                        yield rx.toast("AI読み取り完了（新規取引先の可能性があります）", duration=5000, close_button=True)
                else:
                    yield rx.window_alert("読み取りに失敗しました。")
        except Exception as e:
             yield rx.window_alert(f"アップロードエラー: {e}")
        finally:
             self.is_analyzing = False

    async def _apply_ocr_result(self, data):
        """Apply OCR result to the form state."""
        from .form import JournalFormState
        form_state = await self.get_state(JournalFormState)
        
        if data.transaction_date:
            form_state.transaction_date = data.transaction_date
        
        if data.merchant_name:
            form_state.counterparty = data.merchant_name
            form_state.description = data.description or data.merchant_name
            
        if data.invoice_registration_number:
            form_state.invoice_number = data.invoice_registration_number
            
        if data.total_amount_incl_tax:
            debit_acc = data.inferred_debit_account_id or ""
            credit_acc = data.inferred_credit_account_id or ""
            
            # Fallback to existing logic if no template matched
            if not debit_acc and form_state.counterparty:
                 async with DI.get_master_service() as service:
                      cps = await service.get_counterparties()
                      matched = next((c for c in cps if c.name == form_state.counterparty), None)
                      if matched:
                           if matched.debit_account_id:
                               debit_acc = str(matched.debit_account_id)
                           if matched.credit_account_id and not credit_acc:
                               credit_acc = str(matched.credit_account_id)
                           if matched.invoice_number and not form_state.invoice_number:
                               form_state.invoice_number = matched.invoice_number

            form_state.lines = [
                {"account_id": debit_acc, "debit": data.total_amount_incl_tax, "credit": 0},
                {"account_id": credit_acc, "debit": 0, "credit": data.total_amount_incl_tax}
            ]
            
        if data.needs_manual_review:
             return rx.window_alert(f"要確認: {data.error_message}")
             
    async def clear_upload_state(self):
        """Called by FormState on submit/clear to clear OCR files."""
        self._uploaded_file_data = None
        self._uploaded_filename = None
        yield rx.clear_selected_files("upload_receipt")
