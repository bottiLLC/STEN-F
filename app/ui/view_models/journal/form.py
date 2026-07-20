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

import reflex as rx
from typing import List, Dict, Any
from datetime import date
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.models.counterparty import Counterparty
from app.domain.models.abstract import Abstract
from app.ui.di import DI
import structlog
from app.core.utils import normalize_amount
from .base import JournalState

log = structlog.get_logger()


class JournalFormState(JournalState):
    """Handles the journal entry input form."""

    transaction_date: str = date.today().isoformat()
    description: str = ""
    counterparty: str = ""
    invoice_number: str = ""

    lines: List[Dict[str, Any]] = [{"account_id": "", "debit": "", "credit": ""}]

    # Master data copies needed for UI logic
    abstracts: List[Abstract] = []

    # Flags
    register_master: bool = False
    continuous_entry: bool = False
    is_processing: bool = False
    form_key: str = "initial"

    def _reset_form_state(self):
        """Reset all input fields to their default clean values."""
        self.description = ""
        self.counterparty = ""
        self.invoice_number = ""
        self.lines = [{"account_id": "", "debit": "", "credit": ""}]
        self.register_master = False
        import uuid

        self.form_key = str(uuid.uuid4())

    def set_register_master(self, value: bool):
        self.register_master = value

    def set_continuous_entry(self, value: bool):
        self.continuous_entry = value

    def set_transaction_date(self, value: str):
        if self.is_processing:
            return
        self.transaction_date = value

    def set_description(self, value: str):
        if self.is_processing:
            return
        self.description = value

    async def set_counterparty(self, value: str):
        if self.is_processing:
            return
        self.counterparty = value

        if value:
            async with DI.get_master_service() as service:
                cps = await service.get_counterparties()
                matched = next((c for c in cps if c.name == value), None)
                if matched:
                    if matched.invoice_number:
                        self.invoice_number = matched.invoice_number
                    if self.lines and matched.debit_account_id:
                        self.update_line_account(0, str(matched.debit_account_id))

    def set_invoice_number(self, value: str):
        if self.is_processing:
            return
        self.invoice_number = value.upper()

    def add_line(self):
        if self.is_processing:
            return
        self.lines.append({"account_id": "", "debit": "", "credit": ""})

    def remove_line(self, index: int):
        if self.is_processing:
            return
        if len(self.lines) > 1:
            self.lines.pop(index)

    def update_line_account(self, index: int, value: str):
        if self.is_processing:
            return
        new_lines = self.lines[:]
        new_lines[index]["account_id"] = value
        self.lines = new_lines

    def update_line(self, index: int, field: str, value: Any):
        if self.is_processing:
            return
        if field in ["debit", "credit"]:
            # ユーザーが入力値を消した場合は、0にならず空欄（空文字）のまま保持する
            if value is None or str(value).strip() == "":
                self.lines[index][field] = ""
            else:
                val = normalize_amount(value)
                self.lines[index][field] = val
        else:
            self.lines[index][field] = value

    @rx.var
    def abstract_suggestions(self) -> List[str]:
        """Generate abstract suggestions based on selected accounts."""
        selected_account_ids = set()
        for line in self.lines:
            aid = line.get("account_id")
            if aid:
                try:
                    selected_account_ids.add(int(aid))
                except ValueError, TypeError:
                    pass

        suggestions = []
        if not selected_account_ids:
            suggestions = [a.text for a in self.abstracts]
        else:
            suggestions = [
                a.text for a in self.abstracts if a.account_id in selected_account_ids
            ]
            if not suggestions:
                suggestions = [a.text for a in self.abstracts]

        return sorted(list(set(s for s in suggestions if s)))

    async def submit(self):
        """Submit the journal entry."""
        if self.is_processing:
            return

        from .ocr import JournalOCRState

        ocr_state = await self.get_state(JournalOCRState)
        if ocr_state.is_analyzing:
            return

        self.is_processing = True
        yield

        try:
            valid_lines = []
            for line in self.lines:
                debit_val = normalize_amount(line.get("debit"))
                credit_val = normalize_amount(line.get("credit"))
                if line["account_id"] and (debit_val > 0 or credit_val > 0):
                    valid_lines.append(
                        TransactionLine(
                            account_id=line["account_id"],
                            debit=debit_val,
                            credit=credit_val,
                        )
                    )

            if not valid_lines:
                self.is_processing = False
                yield rx.toast("有効な仕訳明細がありません。")
                return

            total_debit = sum(line.debit for line in valid_lines)
            total_credit = sum(line.credit for line in valid_lines)

            if total_debit != total_credit:
                self.is_processing = False
                yield rx.toast(f"貸借不一致: 借方 {total_debit} / 貸方 {total_credit}")
                return

            try:
                transaction = Transaction(
                    date=date.fromisoformat(self.transaction_date),
                    description=self.description,
                    counterparty=self.counterparty,
                    invoice_number=self.invoice_number
                    if self.invoice_number.strip()
                    else None,
                    lines=valid_lines,
                    evidence_path=None,
                )
            except ValueError as e:
                self.is_processing = False
                if "invoice_number" in str(e):
                    yield rx.toast(
                        "登録番号は「T + 13桁の半角数字」で入力してください。"
                    )
                else:
                    yield rx.toast(f"入力内容にエラーがあります: {str(e)}")
                return

            try:
                # Retrieve OCR state to check if there is an uploaded evidence file
                from .ocr import JournalOCRState

                ocr_state = await self.get_state(JournalOCRState)

                async with DI.get_journal_service() as service:
                    if ocr_state._uploaded_file_data:
                        file_service = DI.get_file_service()
                        await service.add_journal_entry_with_evidence(
                            transaction, ocr_state._uploaded_file_data, file_service
                        )
                    else:
                        await service.add_journal_entry(transaction)

                if self.register_master and (self.counterparty or self.invoice_number):
                    cp = Counterparty(
                        name=self.counterparty or "Unknown",
                        invoice_number=self.invoice_number
                        if self.invoice_number.strip()
                        else None,
                    )
                    async with DI.get_master_service() as master_service:
                        await master_service.save_counterparty(cp)

                if not self.continuous_entry:
                    self._reset_form_state()
                    yield rx.set_value("form_description", "")
                    yield rx.set_value("form_counterparty", "")
                    yield rx.set_value("form_invoice_number", "")
                    yield rx.set_value(f"{self.form_key}_debit_0", "")
                    yield rx.set_value(f"{self.form_key}_credit_0", "")

                # 即時でフロントエンドにクリア状態を送信し、画面をリセットする
                yield

                # Clear OCR state
                yield await ocr_state.clear_upload_state()

                # Trigger list reload locally
                from .list import JournalListState

                list_state = await self.get_state(JournalListState)
                await list_state.load_entries()

                # Trigger global cross-session reload for other tabs
                import time
                import app.ui.view_models.journal.list as list_module

                list_module.GLOBAL_JOURNAL_UPDATE_TIME = time.time()
                list_state._local_last_update = list_module.GLOBAL_JOURNAL_UPDATE_TIME

                self.is_processing = False
                yield rx.toast("登録しました！")

            except Exception as e:
                log.error("Error submitting journal entry", error=str(e), exc_info=True)
                self.is_processing = False
                yield rx.toast(f"エラーが発生しました: {str(e)}")
                return

        except Exception as e:
            log.error("Unexpected error in submit", error=str(e), exc_info=True)
            self.is_processing = False
            yield rx.toast(f"予期せぬエラーが発生しました: {str(e)}")

    async def clear_form(self):
        """Clear all inputs in the journal entry form."""
        from .ocr import JournalOCRState

        ocr_state = await self.get_state(JournalOCRState)
        if ocr_state.is_analyzing:
            return

        self.is_processing = False
        self.transaction_date = date.today().isoformat()
        self._reset_form_state()
        yield rx.set_value("form_description", "")
        yield rx.set_value("form_counterparty", "")
        yield rx.set_value("form_invoice_number", "")
        yield rx.set_value(f"{self.form_key}_debit_0", "")
        yield rx.set_value(f"{self.form_key}_credit_0", "")

        # 即時でフロントエンドにクリア状態を送信し、画面をリセットする
        yield

        # Clear OCR State
        from .ocr import JournalOCRState

        ocr_state = await self.get_state(JournalOCRState)
        yield await ocr_state.clear_upload_state()
