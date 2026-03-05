import reflex as rx
from typing import List, Dict, Any, Optional
from datetime import date
from domain.models.transaction import Transaction, TransactionLine
from domain.models.account import Account
from domain.models.abstract import Abstract
from domain.models.counterparty import Counterparty
from core.logging import logger
from ..di import DI

class JournalState(rx.State):
    """State for the Journal Entry page."""
    
    # Form Fields
    transaction_date: str = date.today().isoformat()
    description: str = ""
    counterparty: str = ""
    invoice_number: str = ""
    
    # List View
    journal_entries: List[Transaction] = []
    show_deleted: bool = False
    
    # Date Filter
    # Default to empty (will be set by on_mount)
    filter_start_date: str = ""
    filter_end_date: str = ""

    # Master Registration Flag
    register_master: bool = False

    def set_register_master(self, value: bool):
        self.register_master = value

    async def toggle_show_deleted(self):
        self.show_deleted = not self.show_deleted
        await self.load_entries()
    
    async def on_mount_journal_page(self):
        """Called when the journal page is mounted."""
        await self.load_accounts()
        
        # Set default dates if not set
        if not self.filter_start_date or not self.filter_end_date:
            async with DI.get_master_service() as service:
                fys = await service.get_fiscal_years()
                if fys:
                    # Sort by period_number descending (latest first)
                    fys.sort(key=lambda x: x.period_number, reverse=True)
                    latest = fys[0]
                    self.filter_start_date = latest.start_date.isoformat()
                    self.filter_end_date = latest.end_date.isoformat()
        
        await self.load_entries()

    # Line Items
    lines: List[Dict[str, Any]] = [{"account_id": "", "debit": 0, "credit": 0}]
    
    # Master Data
    accounts: List[Account] = []
    abstracts: List[Abstract] = []  # Added abstracts list
    
    # Separation for UI Grouping
    frequent_accounts: List[Account] = []
    other_accounts: List[Account] = []
    
    # Select Items
    frequent_select_items: List[List[str]] = []
    other_select_items: List[List[str]] = []
    
    # Legacy/Fallback (All items flat)
    account_select_items: List[List[str]] = [] 
    
    account_map: Dict[str, str] = {} # Label -> ID
    account_label_map: Dict[int, str] = {} # ID -> Label

    async def load_accounts(self):
        """Load accounts and abstracts from MasterService."""
        async with DI.get_master_service() as service:
            self.accounts = await service.get_accounts()
            self.abstracts = await service.get_abstracts()
            
            # 1. Fetch Frequent IDs
            async with DI.get_journal_service() as j_service:
                f_ids = await j_service.get_frequent_account_ids(5)
            
            # 2. Split Accounts
            self.frequent_accounts = []
            self.other_accounts = []
            
            # Map for O(1) lookup
            account_dict = {a.id: a for a in self.accounts}
            
            # Populate Frequent (preserving order from DB aggregation)
            processed_ids = set()
            for fid in f_ids:
                if fid in account_dict:
                    self.frequent_accounts.append(account_dict[fid])
                    processed_ids.add(fid)
            
            # Populate Others
            for a in self.accounts:
                if a.id not in processed_ids:
                    self.other_accounts.append(a)
                    
            # 3. Build Select Items
            def make_item(a):
                return [str(a.id), f"{a.code}: {a.name}"]

            self.frequent_select_items = [make_item(a) for a in self.frequent_accounts]
            self.other_select_items = [make_item(a) for a in self.other_accounts]
            
            # Legacy/Flat backup
            self.account_select_items = [make_item(a) for a in self.accounts]
            
            self.account_map = {f"{a.code}: {a.name}": str(a.id) for a in self.accounts}
            self.account_label_map = {a.id: f"{a.code}: {a.name}" for a in self.accounts}
            
    def set_transaction_date(self, value: str):
        self.transaction_date = value

    def set_description(self, value: str):
        self.description = value

    async def set_counterparty(self, value: str):
        self.counterparty = value
        
        # Auto-fill Details if exact match found
        if value:
            async with DI.get_master_service() as service:
                cps = await service.get_counterparties()
                # Find exact match
                matched = next((c for c in cps if c.name == value), None)
                if matched:
                     if matched.invoice_number:
                         self.invoice_number = matched.invoice_number
                         
                     # Only update if the user hasn't explicitly set another account yet?
                     # Let's overwrite first line's account for convenience
                     if self.lines and matched.debit_account_id:
                         self.update_line_account(0, str(matched.debit_account_id))

    def set_invoice_number(self, value: str):
        # Auto-uppercase for 't' -> 'T'
        self.invoice_number = value.upper()

    def set_filter_start_date(self, value: str):
        self.filter_start_date = value

    def set_filter_end_date(self, value: str):
        self.filter_end_date = value

    def add_line(self):
        self.lines.append({"account_id": "", "debit": 0, "credit": 0})
        
    def remove_line(self, index: int):
        if len(self.lines) > 1:
            self.lines.pop(index)

    def update_line_account(self, index: int, value: str):
        """Update account_id based on selected value (ID)."""
        # Create a new list to ensure change detection
        new_lines = self.lines[:]
        new_lines[index]["account_id"] = value
        self.lines = new_lines

    def update_line(self, index: int, field: str, value: Any):
        if field in ["debit", "credit"]:
            try:
                val = int(value)
            except (ValueError, TypeError):
                val = 0
            self.lines[index][field] = val
        else:
            self.lines[index][field] = value

    is_processing: bool = False
    
    async def submit(self):
        """Submit the journal entry."""
        self.is_processing = True
        yield
        
        valid_lines = []
        for line in self.lines:
             if line["account_id"] and (line["debit"] > 0 or line["credit"] > 0):
                 valid_lines.append(
                     TransactionLine(
                         account_id=line["account_id"],
                         debit=line["debit"],
                         credit=line["credit"]
                     )
                 )
        
        if not valid_lines:
            yield rx.window_alert("有効な仕訳明細がありません。")
            return

        total_debit = sum(line.debit for line in valid_lines)
        total_credit = sum(line.credit for line in valid_lines)
        
        if total_debit != total_credit:
            yield rx.window_alert(f"貸借不一致: 借方 {total_debit} / 貸方 {total_credit}")
            return

        try:
            transaction = Transaction(
                date=date.fromisoformat(self.transaction_date),
                description=self.description,
                counterparty=self.counterparty,
                invoice_number=self.invoice_number,
                lines=valid_lines,
                evidence_path=None
            )
        except ValueError:
            self.is_processing = False
            yield rx.window_alert("登録番号は「T + 13桁の半角数字」で入力してください。")
            return

        try:
             async with DI.get_journal_service() as service:
                 if self._uploaded_file_data:
                     # Use service with evidence
                     file_service = DI.get_file_service()
                     await service.add_journal_entry_with_evidence(
                         transaction, 
                         self._uploaded_file_data, 
                         file_service
                     )
                 else:
                     await service.add_journal_entry(transaction)
             
             # Handle Master Registration
             if self.register_master and (self.counterparty or self.invoice_number):
                 cp = Counterparty(name=self.counterparty or "Unknown", invoice_number=self.invoice_number)
                 async with DI.get_master_service() as master_service:
                     await master_service.save_counterparty(cp)
                     # Optionally toast? "Updated Master"
                 
             self.description = ""
             self.counterparty = ""
             self.invoice_number = ""
             self.lines = [{"account_id": "", "debit": 0, "credit": 0}]
             self.register_master = False # Reset flag
             # Clear file state
             self._uploaded_file_data = None
             self._uploaded_filename = None
             
             await self.load_entries()
             yield rx.window_alert("登録しました！")
             return
             
        except Exception as e:
            logger.error("Error submitting journal entry", error=str(e), exc_info=True)
            yield rx.window_alert(f"エラーが発生しました: {str(e)}")
            return
        finally:
            self.is_processing = False
            yield

    async def load_entries(self):
        """Load recent journal entries."""
        async with DI.get_journal_service() as service:
             try:
                 # Parse dates from strings
                 start = date.fromisoformat(self.filter_start_date) if self.filter_start_date else None
                 end = date.fromisoformat(self.filter_end_date) if self.filter_end_date else None
                 
                 entries = await service.get_entries(
                     start_date=start, 
                     end_date=end, 
                     include_deleted=self.show_deleted
                 )
                 self.journal_entries = entries
             except Exception as e:
                 logger.error("Error loading entries", error=str(e), exc_info=True)

    async def delete_entry(self, entry_id: int):
        async with DI.get_journal_service() as service:
            try:
                await service.delete_entry(entry_id)
                await self.load_entries()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"削除エラー: {e}")

        # End of file
    async def handle_tab_change(self, val: str):
        if val == "list":
            await self.load_entries()

    async def export_csv(self):
        """Export filtered journal entries to CSV."""
        async with DI.get_journal_service() as service:
            try:
                start = date.fromisoformat(self.filter_start_date) if self.filter_start_date else None
                end = date.fromisoformat(self.filter_end_date) if self.filter_end_date else None
                
                csv_data = await service.export_journal_entries_csv(start_date=start, end_date=end)
                
                # Determine filename
                filename = f"journal_export_{self.filter_start_date or 'begin'}_{self.filter_end_date or 'end'}.csv"
                
                return rx.download(
                    data=csv_data,
                    filename=filename
                )
            except Exception as e:
                return rx.window_alert(f"Export Error: {e}")

    async def download_evidence(self, entry_id: int):
        """Download evidence file for a transaction asynchronously."""
        # Find the entry
        entry = next((e for e in self.journal_entries if e.id == entry_id), None)
        if not entry or not entry.evidence_path:
             return rx.window_alert("証憑ファイルが見つかりません。")
        
        import os
        import aiofiles
        if not os.path.exists(entry.evidence_path):
             return rx.window_alert("指定されたファイルがサーバー上に存在しません。")
             
        try:
            async with aiofiles.open(entry.evidence_path, "rb") as f:
                data = await f.read()
                
            filename = os.path.basename(entry.evidence_path)
            return rx.download(data=data, filename=filename)
        except Exception as e:
            logger.error("Failed to download evidence.", error=str(e), exc_info=True)
            return rx.window_alert(f"ダウンロードエラー: {e}")

    @rx.var
    def abstract_suggestions(self) -> List[str]:
        """Generate abstract suggestions based on selected accounts."""
        selected_account_ids = set()
        for line in self.lines:
            aid = line.get("account_id")
            if aid:
                 try:
                     selected_account_ids.add(int(aid))
                 except (ValueError, TypeError):
                     pass
        
        suggestions = []
        if not selected_account_ids:
            # If no accounts selected, show all (or maybe top frequent? showing all for now)
            suggestions = [a.text for a in self.abstracts]
        else:
            # Show abstracts linked to selected accounts
            suggestions = [a.text for a in self.abstracts if a.account_id in selected_account_ids]
            
            # If nothing found for specific accounts, fallback to all?
            # Or just append unique ones?
            # User wants "Registered Abstract List".
            # Let's return relevant ones first, then maybe others?
            # For now, simple filter is what's expected.
            if not suggestions:
                 suggestions = [a.text for a in self.abstracts]

        # Remove duplicates and empty
        unique_suggestions = sorted(list(set(s for s in suggestions if s)))
        return unique_suggestions

    # --- OCR Functionality ---
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
                
                # Store for later saving
                self._uploaded_file_data = upload_data
                self._uploaded_filename = file.filename
                
                # Get OCR Service
                ocr_service = DI.get_ocr_service()
                
                # Prepare account list for OCR context
                acc_options = [f"{a.code}: {a.name}" for a in self.accounts]
                
                # Prepare counterparty list for OCR context
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
        """Apply OCR result to state."""
        if data.transaction_date:
            self.transaction_date = data.transaction_date
        
        if data.merchant_name:
            self.counterparty = data.merchant_name
            # Auto-set description to merchant name initially, or use inferred description
            self.description = data.description or data.merchant_name
            
        if data.invoice_registration_number:
            self.invoice_number = data.invoice_registration_number
            
        if data.total_amount_incl_tax:
            debit_acc = data.inferred_debit_account_id or ""
            credit_acc = data.inferred_credit_account_id or ""
            
            # Fallback to existing logic if no template/inference matched
            if not debit_acc and self.counterparty:
                 async with DI.get_master_service() as service:
                      cps = await service.get_counterparties()
                      matched = next((c for c in cps if c.name == self.counterparty), None)
                      if matched:
                           if matched.debit_account_id:
                               debit_acc = str(matched.debit_account_id)
                           if matched.credit_account_id and not credit_acc:
                               credit_acc = str(matched.credit_account_id)
                           # Also fallback for invoice number if OCR missed it
                           if matched.invoice_number and not self.invoice_number:
                               self.invoice_number = matched.invoice_number

            self.lines = [
                {"account_id": debit_acc, "debit": data.total_amount_incl_tax, "credit": 0},
                {"account_id": credit_acc, "debit": 0, "credit": data.total_amount_incl_tax} # Basic single-entry mapping
            ]
            
        if data.needs_manual_review:
             return rx.window_alert(f"要確認: {data.error_message}")
