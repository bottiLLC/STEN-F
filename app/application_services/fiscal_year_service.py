# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from typing import Final

from app.application_services.journal_service import JournalService
from app.application_services.ledger_service import LedgerService
from app.application_services.master_service import MasterService
from app.domain_contracts import (
    AccountType,
    FiscalYear,
    Transaction,
    TransactionLine,
    compute_next_fiscal_year_dates,
)

_EXPENSE_TYPES: Final[frozenset[AccountType]] = frozenset(
    {
        AccountType.COST_OF_SALES,
        AccountType.SGA,
        AccountType.NON_OPERATING_EXPENSE,
        AccountType.EXTRAORDINARY_LOSS,
        AccountType.TAXES,
    }
)

_INCOME_TYPES: Final[frozenset[AccountType]] = frozenset(
    {
        AccountType.REVENUE,
        AccountType.NON_OPERATING_INCOME,
        AccountType.EXTRAORDINARY_INCOME,
    }
)


class FiscalYearService:
    """Service governing fiscal year closing calculations and opening balance rollover."""

    def __init__(
        self,
        master_service: MasterService,
        ledger_service: LedgerService,
        journal_service: JournalService,
    ) -> None:
        """Bind cooperating domain services.

        Args:
            master_service: MasterService instance.
            ledger_service: LedgerService instance.
            journal_service: JournalService instance.
        """
        self.master_service = master_service
        self.ledger_service = ledger_service
        self.journal_service = journal_service

    async def close_fiscal_year(
        self, fiscal_year_id: int, next_fy_name: str | None = None
    ) -> FiscalYear:
        """Execute period closing, transfer net income to retained earnings, and rollover.

        Args:
            fiscal_year_id: Target fiscal year identifier to close.
            next_fy_name: Optional custom label for succeeding fiscal year.

        Returns:
            Created or updated succeeding FiscalYear domain instance.

        Raises:
            ValueError: If fiscal year not found, already closed, or required account missing.
        """
        current_fy = await self.master_service.get_fiscal_year_by_id(fiscal_year_id)
        if not current_fy:
            raise ValueError(f"Fiscal Year {fiscal_year_id} not found")
        if current_fy.status != "OPEN":
            raise ValueError("Fiscal Year is already closed")

        tb_rows = await self.ledger_service.get_trial_balance(fiscal_year_id)
        expenses = (
            sum(r.balance for r in tb_rows if r.account_type in _EXPENSE_TYPES) or 0
        )
        income = sum(r.balance for r in tb_rows if r.account_type in _INCOME_TYPES) or 0
        net_income = income - expenses

        next_start, next_end = compute_next_fiscal_year_dates(current_fy.end_date)
        all_fys = await self.master_service.get_fiscal_years()
        next_period = (current_fy.period_number or 0) + 1
        next_fy = next((f for f in all_fys if f.period_number == next_period), None)

        if next_fy:
            if next_fy.status != "OPEN":
                raise ValueError(
                    f"次期会計年度「{next_fy.name}」が既にクローズされているため繰り越しできません。"
                )
            existing_next_entries = await self.journal_service.get_entries(
                start_date=next_fy.start_date, end_date=next_fy.start_date
            )
            if any(
                tx.description in ("前期繰越", "期首残高")
                for tx in existing_next_entries
            ):
                raise ValueError(
                    f"次期会計年度「{next_fy.name}」には既に期首繰越仕訳が登録されています。"
                )
        else:
            next_fy = await self.master_service.save_fiscal_year(
                FiscalYear(
                    name=next_fy_name or f"第{next_period}期",
                    start_date=next_start,
                    end_date=next_end,
                    status="OPEN",
                    period_number=next_period,
                )
            )

        lines: list[TransactionLine] = []
        asset_types = {
            AccountType.CURRENT_ASSET,
            AccountType.FIXED_ASSET,
            AccountType.DEFERRED_ASSET,
        }
        liab_eq_types = {
            AccountType.CURRENT_LIABILITY,
            AccountType.FIXED_LIABILITY,
            AccountType.EQUITY,
        }

        re_row = next(
            (r for r in tb_rows if r.account_name == "繰越利益剰余金"), None
        ) or next((r for r in tb_rows if r.account_code == "3120"), None)
        if not re_row:
            raise ValueError(
                "期末処理に必要な必須勘定科目「繰越利益剰余金」が見つかりませんでした。"
            )
        re_id = re_row.account_id

        for r in tb_rows:
            if r.account_type in asset_types and r.balance != 0:
                lines.append(
                    TransactionLine(
                        account_id=r.account_id,
                        debit=r.balance if r.balance > 0 else 0,
                        credit=abs(r.balance) if r.balance < 0 else 0,
                    )
                )
            elif (
                r.account_type in liab_eq_types
                and r.account_id != re_id
                and r.balance != 0
            ):
                lines.append(
                    TransactionLine(
                        account_id=r.account_id,
                        debit=abs(r.balance) if r.balance < 0 else 0,
                        credit=r.balance if r.balance > 0 else 0,
                    )
                )

        tot_re = sum(r.balance for r in tb_rows if r.account_id == re_id) + net_income
        if tot_re > 0:
            lines.append(TransactionLine(account_id=re_id, debit=0, credit=tot_re))
        elif tot_re < 0:
            lines.append(TransactionLine(account_id=re_id, debit=abs(tot_re), credit=0))

        total_d = sum(line.debit for line in lines)
        total_c = sum(line.credit for line in lines)
        if total_d != total_c:
            raise ValueError(
                f"Opening Balance unbalanced: Dr {total_d} != Cr {total_c}"
            )

        if lines:
            await self.journal_service.add_journal_entry(
                Transaction(
                    occurred_at=next_fy.start_date,
                    description="前期繰越",
                    lines=lines,
                )
            )
        current_fy.status = "CLOSED"
        await self.master_service.save_fiscal_year(current_fy)
        return next_fy
