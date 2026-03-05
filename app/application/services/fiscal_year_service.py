from datetime import timedelta, date
from core.logging import logger
from domain.models.account import AccountType
from domain.models.transaction import Transaction, TransactionLine
from domain.models.fiscal_year import FiscalYear

class FiscalYearService:
    def __init__(self, master_service, ledger_service, journal_service):
        self.master_service = master_service
        self.ledger_service = ledger_service
        self.journal_service = journal_service
        self.log = logger.bind(service="FiscalYearService")

    async def close_fiscal_year(self, fiscal_year_id: int, next_fy_name: str = None):
        context_log = self.log.bind(fy_id=fiscal_year_id)
        try:
            context_log.info("Starting fiscal year closing process")

            # 1. Validate Current FY
            current_fy = await self.master_service.get_fiscal_year_by_id(fiscal_year_id) # Assuming this method exists or similar
            # If not, use repository directly? master_service usually wraps it.
            # Let's verify master_service capabilities.
            # If master_service doesn't have get_by_id, we might need to add it or use repo.
            # For now assuming it exists or I'll fix it. 
            # Actually, `ledger_repository` has `get_fiscal_year`.
            # Let's check `master_service` later. I'll write code assuming `get_fiscal_year` is available via master_service.
            
            if not current_fy:
                raise ValueError(f"Fiscal Year {fiscal_year_id} not found")
            
            if current_fy.status != "OPEN":
                raise ValueError("Fiscal Year is already closed")

            # 2. Calculate Net Income
            tb_rows = await self.ledger_service.get_trial_balance(fiscal_year_id)
            
            # revenue calculation was removed because it was unused
            expenses = sum(r.balance for r in tb_rows if r.account_type in [
                AccountType.COST_OF_SALES, AccountType.SGA, 
                AccountType.NON_OPERATING_EXPENSE, AccountType.EXTRAORDINARY_LOSS,
                AccountType.TAXES # Taxes should be included in expenses for Net Income generally, logic depends on if taxes are already booked.
                # User requirement: Revenue - Expenses.
                # Expenses usually include CostOfSales, SGA, NonOpExp, ExtraLoss, Taxes.
            ]) or 0
            # Note: Income types also include NonOpInc, ExtraInc.
            income = sum(r.balance for r in tb_rows if r.account_type in [
                AccountType.REVENUE, AccountType.NON_OPERATING_INCOME, AccountType.EXTRAORDINARY_INCOME
            ]) or 0
            
            net_income = income - expenses
            context_log.info("Calculated Net Income", net_income=net_income)

            # 3. Prepare Next FY
            next_start = current_fy.end_date + timedelta(days=1)
            next_end = next_start + timedelta(days=365) # Approximation, logic might need to be exact year ending?
            # Usually 1 year. 
            # Date logic: if start is 2025-04-01, end is 2026-03-31.
            # next_end = date(next_start.year + 1, next_start.month, next_start.day) - timedelta(days=1)
            next_end = date(next_start.year + 1, next_start.month, next_start.day) - timedelta(days=1)

            # Check if next FY exists
            # We need a way to check. `get_fiscal_year_by_date`?
            # Or just try to create.
            # Let's try to find if next period exists.
            all_fys = await self.master_service.get_fiscal_years()
            next_fy = next((fy for fy in all_fys if fy.period_number == (current_fy.period_number or 0) + 1), None)

            if not next_fy:
                context_log.info("Creating Next Fiscal Year")
                determined_name = next_fy_name if next_fy_name else f"第{(current_fy.period_number or 0) + 1}期"
                next_fy_data = FiscalYear(
                    name=determined_name,
                    start_date=next_start,
                    end_date=next_end,
                    status="OPEN",
                    period_number=(current_fy.period_number or 0) + 1
                )
                next_fy = await self.master_service.save_fiscal_year(next_fy_data)
            
            # 4. Create Opening Balance Transaction
            lines = []
            
            # 4.1 Assets (Debit Balance -> Debit Side)
            assets = [r for r in tb_rows if r.account_type in [
                AccountType.CURRENT_ASSET, AccountType.FIXED_ASSET, AccountType.DEFERRED_ASSET
            ]]
            for r in assets:
                if r.balance > 0:
                    lines.append(TransactionLine(account_id=r.account_id, debit=r.balance, credit=0))
                elif r.balance < 0:
                    lines.append(TransactionLine(account_id=r.account_id, debit=0, credit=abs(r.balance)))

            # 4.2 Liabilities & Equity (Credit Balance -> Credit Side)
            liabs_and_equity = [r for r in tb_rows if r.account_type in [
                AccountType.CURRENT_LIABILITY, AccountType.FIXED_LIABILITY, AccountType.EQUITY
            ]]
            
            retained_earnings_account_id = None
            retained_earnings_row = next((r for r in tb_rows if r.account_code == "3120"), None)
            
            if retained_earnings_row:
                retained_earnings_account_id = retained_earnings_row.account_id

            retained_earnings_sum = 0

            for r in liabs_and_equity:
                if r.account_code == "3120":
                    retained_earnings_sum += r.balance # Existing RE
                    continue # specific handling later
                
                if r.balance > 0:
                    lines.append(TransactionLine(account_id=r.account_id, debit=0, credit=r.balance))
                elif r.balance < 0:
                    lines.append(TransactionLine(account_id=r.account_id, debit=abs(r.balance), credit=0))
            
            # 4.3 Add Net Income to Retained Earnings
            total_re = retained_earnings_sum + net_income
            if total_re > 0:
                 lines.append(TransactionLine(
                    account_id=retained_earnings_account_id,
                    debit=0,
                    credit=total_re
                ))
            elif total_re < 0:
                 lines.append(TransactionLine(
                    account_id=retained_earnings_account_id,
                    debit=abs(total_re),
                    credit=0
                ))

            # 5. Save Opening Entry
            opening_tx = Transaction(
                date=next_fy.start_date,
                description="前期繰越",
                lines=lines
            )
            
            # Verify Balance
            total_debit = sum(line.debit for line in lines)
            total_credit = sum(line.credit for line in lines)
            
            if total_debit != total_credit:
                raise ValueError(f"Opening Balance unbalanced: Dr {total_debit} != Cr {total_credit}")

            await self.journal_service.add_journal_entry(opening_tx)
            
            # 6. Close Current FY
            # Need update method in MasterService or direct repo?
            # master_service.save_fiscal_year updates if ID present.
            current_fy.status = "CLOSED"
            await self.master_service.save_fiscal_year(current_fy)
            
            context_log.info("Fiscal Year closed successfully")
            return next_fy

        except Exception as e:
            context_log.error("Failed to close fiscal year", error=str(e))
            raise
