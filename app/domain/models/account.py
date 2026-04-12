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

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

class AccountType(str, Enum):
    CURRENT_ASSET = "CurrentAsset"       # 流動資産

    FIXED_ASSET = "FixedAsset"           # 固定資産
    DEFERRED_ASSET = "DeferredAsset"     # 繰延資産
    
    CURRENT_LIABILITY = "CurrentLiability" # 流動負債
    FIXED_LIABILITY = "FixedLiability"     # 固定負債
    
    EQUITY = "Equity"       # 純資産
    REVENUE = "Revenue"     # 収益
    COST_OF_SALES = "CostOfSales" # 売上原価
    SGA = "SGA"             # 販管費
    NON_OPERATING_INCOME = "NonOperatingIncome" # 営業外収益
    NON_OPERATING_EXPENSE = "NonOperatingExpense" # 営業外費用
    EXTRAORDINARY_INCOME = "ExtraordinaryIncome" # 特別利益
    EXTRAORDINARY_LOSS = "ExtraordinaryLoss" # 特別損失
    TAXES = "Taxes" # 法人税等
    @property
    def label(self) -> str:
        labels = {
            "CurrentAsset": "流動資産",
            "FixedAsset": "固定資産",
            "DeferredAsset": "繰延資産",
            "CurrentLiability": "流動負債",
            "FixedLiability": "固定負債",
            "Equity": "純資産",
            "Revenue": "売上高",
            "CostOfSales": "売上原価",
            "SGA": "販管費",
            "NonOperatingIncome": "営業外収益",
            "NonOperatingExpense": "営業外費用",
            "ExtraordinaryIncome": "特別利益",
            "ExtraordinaryLoss": "特別損失",
            "Taxes": "法人税等"
        }
        return labels.get(self.value, self.value)

    @classmethod
    def from_label(cls, label: str) -> "AccountType":
        for t in cls:
            if t.label == label:
                return t
        raise ValueError(f"Unknown label: {label}")

class Account(BaseModel):
    id: Optional[int] = Field(None, description="Database ID")
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1)
    type: AccountType
    description: Optional[str] = None
    
    @computed_field
    def type_label(self) -> str:
        return self.type.label
    
    model_config = ConfigDict(from_attributes=True, extra='forbid')
