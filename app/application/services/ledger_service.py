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

from datetime import date
from typing import List
import pandas as pd
import structlog
from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.models.account import AccountType
from app.domain.models.financial_report import (
    FinancialReport,
    FinancialSection,
    TrialBalanceRow,
)
from app.domain.models.fiscal_year import FiscalYear

log = structlog.get_logger()

_DEBIT_POSITIVE_TYPES = {
    AccountType.CURRENT_ASSET,
    AccountType.FIXED_ASSET,
    AccountType.DEFERRED_ASSET,
    AccountType.COST_OF_SALES,
    AccountType.SGA,
    AccountType.NON_OPERATING_EXPENSE,
    AccountType.EXTRAORDINARY_LOSS,
}


class LedgerService:
    def __init__(self, repository: ILedgerRepository):
        self.repository = repository
        self.log = log.bind(service="LedgerService")

    async def get_trial_balance(self, fiscal_year_id: int) -> List[TrialBalanceRow]:
        accounts = await self.repository.get_accounts()
        tb_data = await self.repository.get_trial_balance_data(fiscal_year_id)
        tb_map = {row["account_id"]: row for row in tb_data}

        rows: List[TrialBalanceRow] = []
        for acc in accounts:
            data = tb_map.get(acc.id, {"total_debit": 0, "total_credit": 0})
            debit, credit = data["total_debit"], data["total_credit"]
            balance = (debit - credit) if acc.type in _DEBIT_POSITIVE_TYPES else (credit - debit)
            net_raw = debit - credit
            rows.append(
                TrialBalanceRow(
                    account_id=acc.id,
                    account_code=acc.code,
                    account_name=acc.name,
                    account_type=acc.type,
                    debit_total=debit,
                    credit_total=credit,
                    balance=balance,
                    debit_balance=net_raw if net_raw > 0 else 0,
                    credit_balance=abs(net_raw) if net_raw < 0 else 0,
                )
            )
        rows.sort(key=lambda x: x.account_code)
        return rows

    async def get_general_ledger(
        self, fiscal_year_id: int, account_id: int
    ) -> pd.DataFrame:
        target_fy = await self.repository.get_fiscal_year(fiscal_year_id)
        if not target_fy:
            return pd.DataFrame()

        transactions = await self.repository.get_transactions_by_account(
            account_id, start_date=target_fy.start_date, end_date=target_fy.end_date
        )
        accounts = await self.repository.get_accounts()
        target_acc = next((a for a in accounts if a.id == account_id), None)
        if not target_acc:
            return pd.DataFrame()

        is_debit_positive = target_acc.type in _DEBIT_POSITIVE_TYPES
        gl_lines = []
        running_balance = 0
        transactions.sort(key=lambda x: x.date)

        for tx in transactions:
            line = next((ln for ln in tx.lines if ln.account_id == account_id), None)
            if not line:
                continue
            debit, credit = line.debit, line.credit
            running_balance += (debit - credit) if is_debit_positive else (credit - debit)
            gl_lines.append({
                "日付": tx.date,
                "摘要": tx.description,
                "借方": debit if debit > 0 else 0,
                "貸方": credit if credit > 0 else 0,
                "残高": running_balance,
                "TransactionID": tx.id,
            })
        return pd.DataFrame(gl_lines)

    async def generate_financial_report(self, fiscal_year_id: int) -> FinancialReport:
        rows = await self.get_trial_balance(fiscal_year_id)

        def sec(title: str, t: AccountType) -> FinancialSection:
            s_rows = [r for r in rows if r.account_type == t]
            return FinancialSection(title=title, rows=s_rows, total=sum(r.balance for r in s_rows))

        cur_assets = sec("【流動資産】", AccountType.CURRENT_ASSET)
        fix_assets = sec("【固定資産】", AccountType.FIXED_ASSET)
        def_assets = sec("【繰延資産】", AccountType.DEFERRED_ASSET)
        cur_liabs = sec("【流動負債】", AccountType.CURRENT_LIABILITY)
        fix_liabs = sec("【固定負債】", AccountType.FIXED_LIABILITY)
        equity = sec("【純資産の部】", AccountType.EQUITY)

        rev = sec("【売上高】", AccountType.REVENUE)
        cost = sec("【売上原価】", AccountType.COST_OF_SALES)
        sga = sec("【販売費及び一般管理費】", AccountType.SGA)
        no_inc = sec("【営業外収益】", AccountType.NON_OPERATING_INCOME)
        no_exp = sec("【営業外費用】", AccountType.NON_OPERATING_EXPENSE)
        ex_inc = sec("【特別利益】", AccountType.EXTRAORDINARY_INCOME)
        ex_loss = sec("【特別損失】", AccountType.EXTRAORDINARY_LOSS)

        gross_profit = rev.total - cost.total
        operating_income = gross_profit - sga.total
        ordinary_income = operating_income + no_inc.total - no_exp.total
        income_before_tax = ordinary_income + ex_inc.total - ex_loss.total
        net_income = income_before_tax

        fy_obj = await self.repository.get_fiscal_year(fiscal_year_id) or FiscalYear(
            id=fiscal_year_id,
            name="Current FY",
            start_date=date(date.today().year, 1, 1),
            end_date=date(date.today().year, 12, 31),
            status="OPEN",
            period_number=1,
        )

        return FinancialReport(
            fiscal_year=fy_obj,
            current_assets=cur_assets,
            fixed_assets=fix_assets,
            deferred_assets=def_assets,
            current_liabilities=cur_liabs,
            fixed_liabilities=fix_liabs,
            equity=equity,
            revenue=rev,
            cost_of_sales=cost,
            sga=sga,
            non_op_income=no_inc,
            non_op_expense=no_exp,
            extra_income=ex_inc,
            extra_loss=ex_loss,
            total_assets=cur_assets.total + fix_assets.total + def_assets.total,
            total_liabilities=cur_liabs.total + fix_liabs.total,
            total_equity=equity.total + net_income,
            gross_profit=gross_profit,
            operating_income=operating_income,
            ordinary_income=ordinary_income,
            income_before_tax=income_before_tax,
            net_income=net_income,
        )
