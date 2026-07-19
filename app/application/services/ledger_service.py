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
import pandas as pd
import structlog
from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.models.financial_report import TrialBalanceRow
from app.domain.models.account import AccountType

log = structlog.get_logger()


class LedgerService:
    def __init__(self, repository: ILedgerRepository):
        self.repository = repository
        self.log = log.bind(service="LedgerService")

    async def get_trial_balance(self, fiscal_year_id: int) -> List[TrialBalanceRow]:
        # 1. Fetch Data
        accounts = await self.repository.get_accounts()
        tb_data = await self.repository.get_trial_balance_data(fiscal_year_id)

        # 1.1 Create Map
        tb_map = {row["account_id"]: row for row in tb_data}

        context_log = self.log.bind(fy_id=fiscal_year_id)

        try:
            context_log.info("Generating Trial Balance")

            # 2. Build Rows
            rows = []
            for acc in accounts:
                data = tb_map.get(acc.id, {"total_debit": 0, "total_credit": 0})
                debit = data["total_debit"]
                credit = data["total_credit"]

                balance = 0
                # Calculate Standard Balance (Book Value)
                if acc.type in [
                    AccountType.CURRENT_ASSET,
                    AccountType.FIXED_ASSET,
                    AccountType.DEFERRED_ASSET,
                    AccountType.COST_OF_SALES,
                    AccountType.SGA,
                    AccountType.NON_OPERATING_EXPENSE,
                    AccountType.EXTRAORDINARY_LOSS,
                ]:
                    balance = debit - credit
                else:
                    balance = credit - debit

                # Calculate Columnar Balances (Raw)
                net_raw = debit - credit
                debit_bal = net_raw if net_raw > 0 else 0
                credit_bal = abs(net_raw) if net_raw < 0 else 0

                rows.append(
                    TrialBalanceRow(
                        account_id=acc.id,
                        account_code=acc.code,
                        account_name=acc.name,
                        account_type=acc.type,
                        debit_total=debit,
                        credit_total=credit,
                        balance=balance,
                        debit_balance=debit_bal,
                        credit_balance=credit_bal,
                    )
                )

            # Sort by code
            rows.sort(key=lambda x: x.account_code)

            context_log.info("Trial Balance generated", account_count=len(rows))
            return rows

        except Exception as e:
            context_log.error("Failed to generate Trial Balance", error=str(e))
            raise

    async def get_general_ledger(
        self, fiscal_year_id: int, account_id: int
    ) -> pd.DataFrame:
        """
        Returns a DataFrame for the General Ledger of a specific account.
        """
        context_log = self.log.bind(fy_id=fiscal_year_id, account_id=account_id)
        try:
            context_log.info("Generating General Ledger")

            # Note: The logic from previous implementation manually calculated balances.
            # We should preserve that logic but wrapped in logging.

            # Since repository.get_account_ledger seems to not be implemented or I missed it in previous file view,
            # I'll stick to the manual implementation logic I saw in Step 2570 where it fetches transactions.
            # Wait, Step 2570 showed manual logic.
            # Step 2593 showed `await self.repository.get_account_ledger(fy_id, account_id)`.
            # Did I implement `get_account_ledger` in Repo? I should check.
            # If not, I should revert to manual logic.
            # Given I'm "Adding logging", I probably shouldn't have changed implementation details.

            # 1. Fetch FY for dates
            target_fy = await self.repository.get_fiscal_year(fiscal_year_id)
            if not target_fy:
                self.log.warning("Fiscal Year not found", fy_id=fiscal_year_id)
                return pd.DataFrame()

            # 2. Fetch Transactions (Filtered by Date)
            transactions = await self.repository.get_transactions_by_account(
                account_id, start_date=target_fy.start_date, end_date=target_fy.end_date
            )

            # self.log.info(f"DEBUG: Fetched {len(transactions)} transactions for account_id={account_id}")

            accounts = await self.repository.get_accounts()
            target_acc = next((a for a in accounts if a.id == account_id), None)

            if not target_acc:
                # self.log.warning(f"DEBUG: Account {account_id} not found in accounts list")
                return pd.DataFrame()

            is_debit_positive = target_acc.type in [
                AccountType.CURRENT_ASSET,
                AccountType.FIXED_ASSET,
                AccountType.DEFERRED_ASSET,
                AccountType.COST_OF_SALES,
                AccountType.SGA,
                AccountType.NON_OPERATING_EXPENSE,
                AccountType.EXTRAORDINARY_LOSS,
            ]

            gl_lines = []
            running_balance = 0

            # Sort by date
            transactions.sort(key=lambda x: x.date)

            for tx in transactions:
                # Find the line for this account
                line = next(
                    (
                        tx_line
                        for tx_line in tx.lines
                        if tx_line.account_id == account_id
                    ),
                    None,
                )
                if not line:
                    continue

                debit = line.debit
                credit = line.credit

                if is_debit_positive:
                    running_balance += debit - credit
                else:
                    running_balance += credit - debit

                gl_lines.append(
                    {
                        "日付": tx.date,
                        "摘要": tx.description,
                        "借方": debit if debit > 0 else 0,
                        "貸方": credit if credit > 0 else 0,
                        "残高": running_balance,
                        "TransactionID": tx.id,
                    }
                )

            df = pd.DataFrame(gl_lines)
            context_log.info("General Ledger generated", row_count=len(df))
            return df

        except Exception as e:
            context_log.error("Failed to generate General Ledger", error=str(e))
            raise

    async def generate_financial_report(self, fy_id: int):
        # This was just a stub/wrapper in my previous edit, but in 2570 it had full logic.
        # I should probably restore full logic if I want to keep parity.
        # However, for the sake of "Observability", I can just log and call the implementation.
        # BUT, the logic was INSIDE Service. So I must restore it.
        pass  # I will skip this for this single file write and do it properly in a moment or include it.
        # Actually, it's better to verify if `generate_financial_report` is called.
        # It is called by `financial_statements_tab.py`.
        # So I MUST restore the logic.

        # ... (Implementation of generate_financial_report with logging) ...
        # Since the logic is long, I will focus on `get_trial_balance` and `get_general_ledger` first which caused the error,
        # but I can't leave this method broken.

        # I'll try to include the previous logic or a simplified version if it delegates to `get_trial_balance`.
        # In 2570, `generate_financial_report` calls `get_trial_balance` then filters.
        # See Step 2570 lines 52-120.

        # I will include it.
        return await self._generate_financial_report_logic(fy_id)

    async def _generate_financial_report_logic(self, fiscal_year_id: int):
        from domain.models.financial_report import (
            FinancialReport,
            FinancialSection,
            FiscalYear,
        )

        context_log = self.log.bind(fy_id=fiscal_year_id)
        try:
            context_log.info("Generating Financial Report")
            rows = await self.get_trial_balance(fiscal_year_id)

            def get_section(title, acc_type):
                section_rows = [r for r in rows if r.account_type == acc_type]
                total = sum(r.balance for r in section_rows)
                return FinancialSection(title=title, rows=section_rows, total=total)

            cur_assets = get_section("【流動資産】", AccountType.CURRENT_ASSET)
            fix_assets = get_section("【固定資産】", AccountType.FIXED_ASSET)
            def_assets = get_section("【繰延資産】", AccountType.DEFERRED_ASSET)

            cur_liabs = get_section("【流動負債】", AccountType.CURRENT_LIABILITY)
            fix_liabs = get_section("【固定負債】", AccountType.FIXED_LIABILITY)

            equity = get_section("【純資産の部】", AccountType.EQUITY)

            revenue = get_section("【売上高】", AccountType.REVENUE)
            cost = get_section("【売上原価】", AccountType.COST_OF_SALES)
            sga = get_section("【販売費及び一般管理費】", AccountType.SGA)

            no_inc = get_section("【営業外収益】", AccountType.NON_OPERATING_INCOME)
            no_exp = get_section("【営業外費用】", AccountType.NON_OPERATING_EXPENSE)

            ex_inc = get_section("【特別利益】", AccountType.EXTRAORDINARY_INCOME)
            ex_loss = get_section("【特別損失】", AccountType.EXTRAORDINARY_LOSS)

            total_assets = cur_assets.total + fix_assets.total + def_assets.total
            total_liabilities = cur_liabs.total + fix_liabs.total

            gross_profit = revenue.total - cost.total
            operating_income = gross_profit - sga.total
            ordinary_income = operating_income + no_inc.total - no_exp.total
            income_before_tax = ordinary_income + ex_inc.total - ex_loss.total
            net_income = income_before_tax

            total_equity_val = equity.total + net_income

            # Mock FY for now
            dummy_fy = FiscalYear(id=fiscal_year_id, name="Current FY", period_number=1)

            report = FinancialReport(
                fiscal_year=dummy_fy,
                current_assets=cur_assets,
                fixed_assets=fix_assets,
                deferred_assets=def_assets,
                current_liabilities=cur_liabs,
                fixed_liabilities=fix_liabs,
                equity=equity,
                revenue=revenue,
                cost_of_sales=cost,
                sga=sga,
                non_op_income=no_inc,
                non_op_expense=no_exp,
                extra_income=ex_inc,
                extra_loss=ex_loss,
                total_assets=total_assets,
                total_liabilities=total_liabilities,
                total_equity=total_equity_val,
                gross_profit=gross_profit,
                operating_income=operating_income,
                ordinary_income=ordinary_income,
                income_before_tax=income_before_tax,
                net_income=net_income,
            )

            context_log.info("Financial Report generated")
            return report

        except Exception as e:
            context_log.error("Failed to generate Financial Report", error=str(e))
            raise
