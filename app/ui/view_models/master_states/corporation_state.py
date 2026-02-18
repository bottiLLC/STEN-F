import reflex as rx
from typing import Optional
from app.domain.models.corporation import Corporation
from app.ui.di import DI

class CorporationState(rx.State):
    corporation: Optional[Corporation] = None
    
    # Form State
    corp_name: str = ""
    corp_address: str = ""
    corp_rep_title: str = ""
    corp_rep_name: str = ""
    
    def set_corp_name(self, v: str): self.corp_name = v
    def set_corp_address(self, v: str): self.corp_address = v
    def set_corp_rep_title(self, v: str): self.corp_rep_title = v
    def set_corp_rep_name(self, v: str): self.corp_rep_name = v

    async def save_corporation(self):
        async with DI.get_master_service() as service:
            try:
                # Use existing ID if available
                corp_id = self.corporation.id if self.corporation else None
                new_corp = Corporation(
                    id=corp_id,
                    name=self.corp_name,
                    address=self.corp_address,
                    representative_title=self.corp_rep_title,
                    representative_name=self.corp_rep_name
                )
                await service.save_corporation(new_corp)
                self.corporation = await service.get_corporation()
                return rx.toast("法人情報を保存しました。")
            except Exception as e:
                return rx.window_alert(f"エラー: {e}")

    def init_corporation_form(self):
        """Initialize form with loaded data."""
        if self.corporation:
            self.corp_name = self.corporation.name
            self.corp_address = self.corporation.address or ""
            self.corp_rep_title = self.corporation.representative_title or ""
            self.corp_rep_name = self.corporation.representative_name or ""
