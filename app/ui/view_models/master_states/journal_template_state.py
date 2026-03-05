import reflex as rx
from typing import List, Optional
from app.domain.models.journal_template import JournalTemplate
from app.ui.di import DI

class JournalTemplateState(rx.State):
    templates: List[JournalTemplate] = []
    
    # Form State
    jt_id: Optional[int] = None
    jt_keyword: str = ""
    jt_debit_account_id: str = ""
    jt_credit_account_id: str = ""
    jt_description_template: str = ""
    
    jt_account_options: List[List[str]] = [] # [[value, label]]

    def set_jt_keyword(self, v: str): self.jt_keyword = v
    def set_jt_debit_account_id(self, v: str): self.jt_debit_account_id = v
    def set_jt_credit_account_id(self, v: str): self.jt_credit_account_id = v
    def set_jt_description_template(self, v: str): self.jt_description_template = v

    def toggle_template_selection(self, jt: JournalTemplate, checked: bool):
        if checked:
            self.select_template(jt)
        else:
            if self.jt_id == jt.id:
                self.clear_template_form()

    def select_template(self, jt: JournalTemplate):
        self.jt_id = jt.id
        self.jt_keyword = jt.keyword
        self.jt_debit_account_id = str(jt.debit_account_id) if jt.debit_account_id else ""
        self.jt_credit_account_id = str(jt.credit_account_id) if jt.credit_account_id else ""
        self.jt_description_template = jt.description_template or ""

    def clear_template_form(self):
        self.jt_id = None
        self.jt_keyword = ""
        self.jt_debit_account_id = ""
        self.jt_credit_account_id = ""
        self.jt_description_template = ""

    async def save_template_data(self):
        if not self.jt_keyword:
            return rx.window_alert("キーワード（取引先名等）は必須です。")
        if not self.jt_debit_account_id:
            return rx.window_alert("借方科目は必須です。")
        if not self.jt_credit_account_id:
            return rx.window_alert("貸方科目は必須です。")

        async with DI.get_master_service() as service:
            try:
                jt = JournalTemplate(
                    id=self.jt_id,
                    keyword=self.jt_keyword,
                    debit_account_id=int(self.jt_debit_account_id),
                    credit_account_id=int(self.jt_credit_account_id),
                    description_template=self.jt_description_template
                )
                await service.save_journal_template(jt)
                await self.load_templates()
                self.clear_template_form()
                return rx.toast("仕訳辞書を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def delete_template_data(self):
        if not self.jt_id: 
            return
        async with DI.get_master_service() as service:
            try:
                await service.delete_journal_template(self.jt_id)
                await self.load_templates()
                self.clear_template_form()
                return rx.toast("削除しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    async def load_templates(self):
        async with DI.get_master_service() as service:
            self.templates = await service.get_journal_templates()
            accounts = await service.get_accounts()
            # [[value, label]]
            self.jt_account_options = [[str(a.id), f"{a.code}: {a.name}"] for a in accounts]
