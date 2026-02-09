from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

class FiscalYear(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    name: str = Field(..., description="年度名 (例: 第10期)")
    start_date: date = Field(..., description="開始日")
    end_date: date = Field(..., description="終了日")
    status: str = Field("OPEN", description="ステータス (OPEN/CLOSED)")
    period_number: Optional[int] = Field(None, description="期数 (数値)")
    created_at: Optional[datetime] = Field(None, description="作成日時")

    model_config = ConfigDict(from_attributes=True)
