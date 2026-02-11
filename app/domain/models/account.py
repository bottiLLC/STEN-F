from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

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

class Account(BaseModel):
    id: Optional[int] = Field(None, description="Database ID")
    code: str = Field(..., min_length=1, max_length=10)
    name: str = Field(..., min_length=1)
    type: AccountType
    description: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
