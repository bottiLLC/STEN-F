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

from typing import List
from pydantic import BaseModel, ConfigDict
from app.domain.models.account import AccountType
# Ideally Domain Entity. Let's define a simple one or use dict for now to save time,
# but for Clean Arch we should have Domain Entity.
# I'll define a minimal FiscalYear in this file or minimal struct.


class FiscalYear(BaseModel):
    id: int
    name: str
    period_number: int
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class TrialBalanceRow(BaseModel):
    account_id: int
    account_code: str
    account_name: str
    account_type: AccountType
    debit_total: int = 0
    credit_total: int = 0
    balance: int = 0
    debit_balance: int = 0
    credit_balance: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FinancialSection(BaseModel):
    title: str
    rows: List[TrialBalanceRow] = []
    total: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class FinancialReport(BaseModel):
    fiscal_year: FiscalYear

    # B/S Sections
    current_assets: FinancialSection
    fixed_assets: FinancialSection
    deferred_assets: FinancialSection

    current_liabilities: FinancialSection
    fixed_liabilities: FinancialSection

    equity: FinancialSection

    # P/L Sections
    revenue: FinancialSection
    cost_of_sales: FinancialSection
    sga: FinancialSection
    non_op_income: FinancialSection
    non_op_expense: FinancialSection
    extra_income: FinancialSection
    extra_loss: FinancialSection

    # KPIs
    total_assets: int = 0
    total_liabilities: int = 0
    total_equity: int = 0
    gross_profit: int = 0
    operating_income: int = 0
    ordinary_income: int = 0
    income_before_tax: int = 0
    net_income: int = 0
    model_config = ConfigDict(from_attributes=True, extra="forbid")
