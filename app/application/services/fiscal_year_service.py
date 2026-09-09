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

from datetime import timedelta
from typing import List, Optional
import structlog
from app.domain.models.account import AccountType
from app.domain.models.fiscal_year import FiscalYear
from app.domain.models.transaction import Transaction, TransactionLine

log = structlog.get_logger()


class FiscalYearService:
    def __init__(self, master_service, ledger_service, journal_service):
        self.master_service = master_service
        self.ledger_service = ledger_service
        self.journal_service = journal_service
        self.log = log.bind(service="FiscalYearService")

    async def close_fiscal_year(
        self, fiscal_year_id: int, next_fy_name: Optional[str] = None
    ) -> FiscalYear:
        current_fy = await self.master_service.get_fiscal_year_by_id(fiscal_year_id)
        if not current_fy:
            raise ValueError(f"Fiscal Year {fiscal_year_id} not found")
        if current_fy.status != "OPEN":
            raise ValueError("Fiscal Year is already closed")

        tb_rows = await self.ledger_service.get_trial_balance(fiscal_year_id)
        exp_types = {
            AccountType.COST_OF_SALES,
            AccountType.SGA,
            AccountType.NON_OPERATING_EXPENSE,
            AccountType.EXTRAORDINARY_LOSS,
            AccountType.TAXES,
        }
        inc_types = {
            AccountType.REVENUE,
            AccountType.NON_OPERATING_INCOME,
            AccountType.EXTRAORDINARY_INCOME,
        }

        expenses = sum(r.balance for r in tb_rows if r.account_type in exp_types) or 0
        income = sum(r.balance for r in tb_rows if r.account_type in inc_types) or 0
        net_income = income - expenses

        next_start = current_fy.end_date + timedelta(days=1)
        try:
            next_end_target = next_start.replace(year=next_start.year + 1)
        except ValueError:
            next_end_target = next_start.replace(
                year=next_start.year + 1, month=2, day=28
            )
        next_end = next_end_target - timedelta(days=1)

        all_fys = await self.master_service.get_fiscal_years()
        next_period = (current_fy.period_number or 0) + 1
        next_fy = next((f for f in all_fys if f.period_number == next_period), None)

        if not next_fy:
            next_fy = await self.master_service.save_fiscal_year(
                FiscalYear(
                    name=next_fy_name or f"第{next_period}期",
                    start_date=next_start,
                    end_date=next_end,
                    status="OPEN",
                    period_number=next_period,
                )
            )

        lines: List[TransactionLine] = []
        asset_types = {
            AccountType.CURRENT_ASSET,
            AccountType.FIXED_ASSET,
            AccountType.DEFERRED_ASSET,
        }
        for r in tb_rows:
            if r.account_type in asset_types:
                if r.balance > 0:
                    lines.append(
                        TransactionLine(
                            account_id=r.account_id, debit=r.balance, credit=0
                        )
                    )
                elif r.balance < 0:
                    lines.append(
                        TransactionLine(
                            account_id=r.account_id, debit=0, credit=abs(r.balance)
                        )
                    )

        re_row = next(
            (r for r in tb_rows if r.account_name == "繰越利益剰余金"), None
        ) or next((r for r in tb_rows if r.account_code == "3120"), None)
        if not re_row:
            raise ValueError(
                "期末処理に必要な必須勘定科目「繰越利益剰余金」が見つかりませんでした。マスタの科目名をご確認ください。"
            )

        re_id, re_sum = re_row.account_id, 0
        liab_eq_types = {
            AccountType.CURRENT_LIABILITY,
            AccountType.FIXED_LIABILITY,
            AccountType.EQUITY,
        }
        for r in tb_rows:
            if r.account_type in liab_eq_types:
                if r.account_id == re_id:
                    re_sum += r.balance
                elif r.balance > 0:
                    lines.append(
                        TransactionLine(
                            account_id=r.account_id, debit=0, credit=r.balance
                        )
                    )
                elif r.balance < 0:
                    lines.append(
                        TransactionLine(
                            account_id=r.account_id, debit=abs(r.balance), credit=0
                        )
                    )

        tot_re = re_sum + net_income
        if tot_re > 0:
            lines.append(TransactionLine(account_id=re_id, debit=0, credit=tot_re))
        elif tot_re < 0:
            lines.append(TransactionLine(account_id=re_id, debit=abs(tot_re), credit=0))

        total_d, total_c = (
            sum(line.debit for line in lines),
            sum(line.credit for line in lines),
        )
        if total_d != total_c:
            raise ValueError(
                f"Opening Balance unbalanced: Dr {total_d} != Cr {total_c}"
            )

        await self.journal_service.add_journal_entry(
            Transaction(date=next_fy.start_date, description="前期繰越", lines=lines)
        )
        current_fy.status = "CLOSED"
        await self.master_service.save_fiscal_year(current_fy)
        return next_fy
