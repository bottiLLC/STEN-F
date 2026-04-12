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
from pydantic import BaseModel, ConfigDict, Field

class Abstract(BaseModel):
    id: Optional[int] = Field(None, description="ID")
    account_id: int = Field(..., description="紐づく勘定科目ID")
    text: str = Field(..., description="摘要内容")
    
    # Optional denormalized field
    account_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')
