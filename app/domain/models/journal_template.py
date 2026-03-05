from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class JournalTemplate(BaseModel):
    """
    仕訳登録時に自動学習・参照される仕訳辞書モデル
    """
    model_config = ConfigDict(extra='forbid', from_attributes=True)

    id: Optional[int] = Field(None, description="Database ID")
    keyword: str = Field(..., description="The keyword to search for, usually the merchant name")
    debit_account_id: int | None = Field(default=None, description="The default debit account ID for this template")
    credit_account_id: int | None = Field(default=None, description="The default credit account ID for this template")
    description_template: str | None = Field(default=None, description="The default description template")
