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

    model_config = ConfigDict(from_attributes=True, extra="forbid")
