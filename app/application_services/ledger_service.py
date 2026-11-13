# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date
from typing import Final, TypedDict

import pandas as pd

from app.domain_contracts import (
    Account,
    AccountType,
    FinancialReport,
    FinancialSection,
    FiscalYear,
    ILedgerRepository,
    TrialBalanceRow,
    account_code_sort_key,
)

_DEBIT_POSITIVE_TYPES: Final[frozenset[AccountType]] = frozenset(
    {
        AccountType.CURRENT_ASSET,
        AccountType.FIXED_ASSET,
        AccountType.DEFERRED_ASSET,
        AccountType.COST_OF_SALES,
        AccountType.SGA,
        AccountType.NON_OPERATING_EXPENSE,
        AccountType.EXTRAORDINARY_LOSS,
        AccountType.TAXES,
    }
)


class GeneralLedgerLine(TypedDict):
    """General ledger line representation for account ledger display."""

    日付: date
    摘要: str
    借方: int
    貸方: int
    残高: int
    TransactionID: int | None


class LedgerService:
    """Service generating trial balance, general ledger, and financial statements."""

    def __init__(self, repository: ILedgerRepository) -> None:
        """Bind repository dependency.

        Args:
            repository: Implementation of ILedgerRepository.
        """
        self.repository = repository

    async def get_trial_balance(self, fiscal_year_id: int) -> list[TrialBalanceRow]:
        """Calculate trial balance summary for specified fiscal period.

        Args:
            fiscal_year_id: Target fiscal year identifier.

        Returns:
            List of TrialBalanceRow models.
        """
        accounts = await self.repository.get_accounts()
        tb_map = {
            row["account_id"]: row
            for row in await self.repository.get_trial_balance_data(fiscal_year_id)
        }

        def make_row(acc: Account) -> TrialBalanceRow:
            data = tb_map.get(acc.id or 0, {"total_debit": 0, "total_credit": 0})
            debit, credit = data["total_debit"], data["total_credit"]
            net = debit - credit
            balance = net if acc.type in _DEBIT_POSITIVE_TYPES else -net
            return TrialBalanceRow(
                account_id=acc.id or 0,
                account_code=acc.code,
                account_name=acc.name,
                account_type=acc.type,
                debit_total=debit,
                credit_total=credit,
                balance=balance,
                debit_balance=max(net, 0),
                credit_balance=abs(net) if net < 0 else 0,
            )

        return sorted(
            [make_row(acc) for acc in accounts],
            key=lambda x: account_code_sort_key(x.account_code),
        )

    async def get_general_ledger(
        self, fiscal_year_id: int, account_id: int
    ) -> pd.DataFrame:
        """Build running general ledger movements for specified account.

        Args:
            fiscal_year_id: Fiscal period identifier.
            account_id: Account identifier.

        Returns:
            Pandas DataFrame containing running movements and balance.
        """
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
        gl_lines: list[GeneralLedgerLine] = []
        running_balance = 0
        transactions.sort(
            key=lambda x: (
                x.occurred_at or x.date or target_fy.start_date,
                x.recorded_at,
                x.id or 0,
            )
        )

        for tx in transactions:
            matching_lines = [ln for ln in tx.lines if ln.account_id == account_id]
            if not matching_lines:
                continue
            tx_date = tx.occurred_at or tx.date or target_fy.start_date
            for line in matching_lines:
                debit, credit = line.debit, line.credit
                running_balance += (
                    (debit - credit) if is_debit_positive else (credit - debit)
                )
                gl_lines.append(
                    {
                        "日付": tx_date,
                        "摘要": tx.description,
                        "借方": debit if debit > 0 else 0,
                        "貸方": credit if credit > 0 else 0,
                        "残高": running_balance,
                        "TransactionID": tx.id,
                    }
                )
        return pd.DataFrame(gl_lines)

    async def generate_financial_report(self, fiscal_year_id: int) -> FinancialReport:
        """Compile complete corporate balance sheet and income statement.

        Args:
            fiscal_year_id: Fiscal period identifier.

        Returns:
            FinancialReport containing B/S, P/L, and sectional totals.
        """
        rows = await self.get_trial_balance(fiscal_year_id)

        def sec(title: str, t: AccountType) -> FinancialSection:
            s_rows = [r for r in rows if r.account_type == t]
            return FinancialSection(
                title=title, rows=s_rows, total=sum(r.balance for r in s_rows)
            )

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
        taxes_sec = sec("【法人税等】", AccountType.TAXES)

        gross_profit = rev.total - cost.total
        operating_income = gross_profit - sga.total
        ordinary_income = operating_income + no_inc.total - no_exp.total
        income_before_tax = ordinary_income + ex_inc.total - ex_loss.total
        net_income = income_before_tax - taxes_sec.total

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
            taxes=taxes_sec,
            total_assets=cur_assets.total + fix_assets.total + def_assets.total,
            total_liabilities=cur_liabs.total + fix_liabs.total,
            total_equity=equity.total + net_income,
            gross_profit=gross_profit,
            operating_income=operating_income,
            ordinary_income=ordinary_income,
            income_before_tax=income_before_tax,
            net_income=net_income,
        )
