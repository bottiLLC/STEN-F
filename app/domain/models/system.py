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

class SystemSettings(BaseModel):
    """
    アプリケーション全体のシステム設定を管理するドメインモデル
    """
    id: Optional[int] = Field(None, description="Database ID")
    ai_api_key: Optional[str] = Field(None, description="OpenAI API Key for AI operations")
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
