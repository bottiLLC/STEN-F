# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from contextlib import asynccontextmanager
import csv
from datetime import date, timedelta
import io
from typing import Any, AsyncGenerator, Dict, List, Optional
import pandas as pd
from app.core_foundation import log, normalize_amount
from app.domain_contracts import (
    DEFAULT_ACCOUNTS,
    Abstract,
    Account,
    AccountType,
    Corporation,
    Counterparty,
    FinancialReport,
    FinancialSection,
    FiscalYear,
    ILedgerRepository,
    IMasterRepository,
    SystemSettings,
    Transaction,
    TransactionLine,
    TrialBalanceRow,
)
from app.storage_repository import (
    AsyncSessionLocal,
    SQLAlchemyLedgerRepository,
    SQLAlchemyMasterRepository,
)

# --- 1. Datum Plane (Constants & Types) ---
_DEBIT_POSITIVE_TYPES = {
    AccountType.CURRENT_ASSET,
    AccountType.FIXED_ASSET,
    AccountType.DEFERRED_ASSET,
    AccountType.COST_OF_SALES,
    AccountType.SGA,
    AccountType.NON_OPERATING_EXPENSE,
    AccountType.EXTRAORDINARY_LOSS,
}

_EXPENSE_TYPES = {
    AccountType.COST_OF_SALES,
    AccountType.SGA,
    AccountType.NON_OPERATING_EXPENSE,
    AccountType.EXTRAORDINARY_LOSS,
    AccountType.TAXES,
}

_INCOME_TYPES = {
    AccountType.REVENUE,
    AccountType.NON_OPERATING_INCOME,
    AccountType.EXTRAORDINARY_INCOME,
}

_LEGAL_ENTITY_KANA = [
    "カブシキガイシャ",
    "カブシキカイシャ",
    "カ）",
    "（カ",
    "ユウゲンガイシャ",
    "ユウゲンカイシャ",
    "ユ）",
    "（ユ",
    "ゴウドウガイシャ",
    "ド）",
    "（ド",
    "イッパンシャダンホウジン",
    "コウエキシャダンホウジン",
    "ガッコウホウジン",
    "シュウキョウホウジン",
    "イリョウホウジン",
    "シャカイフクシホウジン",
    "トクテイヒエイリカツドウホウジン",
    "　",
    " ",
]


# --- 2. Internal Pure Transformations ---
def _clean_counterparty_sort_key(cp: Counterparty) -> str:
    """Normalize corporate legal suffix kana to derive alphabetical sorting key."""
    key = (
        cp.reading
        if getattr(cp, "reading", None)
        else getattr(cp, "name_kana", None) or cp.name
    )
    for token in _LEGAL_ENTITY_KANA:
        key = key.replace(token, "")
    return key


def _compute_next_fiscal_year_dates(current_end: date) -> tuple[date, date]:
    """Calculate start and end boundary dates for succeeding fiscal period."""
    next_start = current_end + timedelta(days=1)
    try:
        target = next_start.replace(year=next_start.year + 1)
    except ValueError:
        target = next_start.replace(year=next_start.year + 1, month=2, day=28)
    return next_start, target - timedelta(days=1)


# --- 3. Public Orchestration Layer ---
class MasterService:
    """Business service governing master catalog entities and configurations."""

    def __init__(
        self,
        repository: IMasterRepository,
        ledger_repository: Optional[ILedgerRepository] = None,
    ) -> None:
        """Initialize service dependencies."""
        self.repository = repository
        self.ledger_repository = ledger_repository

    async def get_system_settings(self) -> SystemSettings:
        """Fetch system-wide settings."""
        return await self.repository.get_system_settings()

    async def save_system_settings(self, settings: SystemSettings) -> SystemSettings:
        """Persist modified system settings."""
        return await self.repository.save_system_settings(settings)

    async def get_corporation(self) -> Optional[Corporation]:
        """Fetch corporate identification details."""
        return await self.repository.get_corporation()

    async def save_corporation(self, corp: Corporation) -> None:
        """Persist corporate identification details."""
        await self.repository.save_corporation(corp)

    async def get_fiscal_years(self) -> List[FiscalYear]:
        """Fetch all fiscal year periods."""
        return await self.repository.get_fiscal_years()

    async def get_fiscal_year_by_id(self, fy_id: int) -> Optional[FiscalYear]:
        """Fetch single fiscal year period by identifier."""
        return await self.repository.get_fiscal_year(fy_id)

    async def save_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        """Save fiscal year period boundary."""
        return await self.repository.save_fiscal_year(fy)

    async def create_fiscal_year(self, fy: FiscalYear) -> FiscalYear:
        """Alias for creating fiscal year boundary."""
        return await self.save_fiscal_year(fy)

    async def delete_fiscal_year(self, fy_id: int) -> None:
        """Remove fiscal year record."""
        await self.repository.delete_fiscal_year(fy_id)

    async def get_accounts(self) -> List[Account]:
        """Retrieve full account catalog."""
        return await self.repository.get_accounts()

    async def save_account(self, account: Account) -> Account:
        """Save account definition."""
        return await self.repository.save_account(account)

    async def delete_account(self, account_id: int) -> None:
        """Delete unused account with transaction usage check."""
        if (
            self.ledger_repository
            and await self.ledger_repository.has_transactions_for_account(account_id)
        ):
            raise ValueError("この勘定科目は仕訳で使用されているため削除できません。")
        await self.repository.delete_account(account_id)

    async def initialize_default_accounts(self) -> int:
        """Seed missing standard default accounts into active ledger."""
        existing = {a.code for a in await self.get_accounts()}
        to_add = [d for d in DEFAULT_ACCOUNTS if d["code"] not in existing]
        for data in to_add:
            await self.save_account(
                Account(
                    code=data["code"],
                    name=data["name"],
                    type=data["type"],
                    description=data.get("description"),
                )
            )
        return len(to_add)

    async def get_abstracts(self) -> List[Abstract]:
        """Fetch all predefined transaction abstracts."""
        return await self.repository.get_abstracts()

    async def save_abstract(self, abstract: Abstract) -> Abstract:
        """Persist transaction abstract template."""
        return await self.repository.save_abstract(abstract)

    async def delete_abstract(self, abstract_id: int) -> None:
        """Delete transaction abstract template."""
        await self.repository.delete_abstract(abstract_id)

    async def get_counterparties(self) -> List[Counterparty]:
        """Retrieve sorted list of registered business counterparties."""
        cps = await self.repository.get_counterparties()
        cps.sort(key=_clean_counterparty_sort_key)
        return cps

    async def save_counterparty(self, counterparty: Counterparty) -> Counterparty:
        """Save counterparty record."""
        return await self.repository.save_counterparty(counterparty)

    async def delete_counterparty(self, counterparty_id: int) -> None:
        """Delete counterparty record."""
        await self.repository.delete_counterparty(counterparty_id)

    async def get_counterparty_by_keyword(self, keyword: str) -> Optional[Counterparty]:
        """Find counterparty matching substring."""
        if not keyword:
            return None
        return await self.repository.get_counterparty_by_keyword(keyword)


class LedgerService:
    """Service generating trial balance, general ledger, and financial statements."""

    def __init__(self, repository: ILedgerRepository) -> None:
        """Bind repository dependency."""
        self.repository = repository

    async def get_trial_balance(self, fiscal_year_id: int) -> List[TrialBalanceRow]:
        """Calculate trial balance summary for specified fiscal period."""
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

        return sorted([make_row(acc) for acc in accounts], key=lambda x: x.account_code)

    async def get_general_ledger(
        self, fiscal_year_id: int, account_id: int
    ) -> pd.DataFrame:
        """Build running general ledger movements for specified account."""
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
        gl_lines: List[Dict[str, Any]] = []
        running_balance = 0
        transactions.sort(key=lambda x: x.date)

        for tx in transactions:
            line = next((ln for ln in tx.lines if ln.account_id == account_id), None)
            if not line:
                continue
            debit, credit = line.debit, line.credit
            running_balance += (
                (debit - credit) if is_debit_positive else (credit - debit)
            )
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
        return pd.DataFrame(gl_lines)

    async def generate_financial_report(self, fiscal_year_id: int) -> FinancialReport:
        """Compile complete corporate balance sheet and income statement."""
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


class JournalService:
    """Service governing journal entries, fiscal validation, and exports."""

    def __init__(
        self,
        repository: ILedgerRepository,
        master_repository: Optional[IMasterRepository] = None,
    ) -> None:
        """Bind repository dependencies."""
        self.repository = repository
        self.master_repository = master_repository

    @asynccontextmanager
    async def _master_scope(self) -> AsyncGenerator[Any, None]:
        """Resolve master repository boundary."""
        if self.master_repository:
            yield self.master_repository
        else:
            async with container.master_service_scope() as ms:
                yield ms

    async def _validate_transaction_date(self, transaction_date: date) -> None:
        """Validate transaction date falls within an open fiscal year."""
        async with self._master_scope() as m:
            fys = await m.get_fiscal_years()
        open_fys = [fy for fy in fys if fy.status == "OPEN"]
        if not open_fys:
            raise ValueError("現在「OPEN」ステータスの会計年度が存在しません。")

        if not any(fy.start_date <= transaction_date <= fy.end_date for fy in open_fys):
            periods = ", ".join(
                f"{fy.start_date.strftime('%Y/%m/%d')}〜{fy.end_date.strftime('%Y/%m/%d')}"
                for fy in open_fys
            )
            raise ValueError(
                f"指定された日付は、現在「OPEN」な会計年度の範囲外です。\n(入力可能範囲: {periods})"
            )

    async def add_journal_entry(self, transaction: Transaction) -> int:
        """Validate and record double-entry journal transaction."""
        await self._validate_transaction_date(transaction.date)
        tx_id = await self.repository.add_transaction(transaction)
        await self.repository.commit()

        if transaction.counterparty:
            try:
                async with self._master_scope() as m:
                    if not await m.get_counterparty_by_keyword(
                        transaction.counterparty
                    ):
                        d_line = max(
                            transaction.lines, key=lambda ln: ln.debit, default=None
                        )
                        c_line = max(
                            transaction.lines, key=lambda ln: ln.credit, default=None
                        )
                        await m.save_counterparty(
                            Counterparty(
                                name=transaction.counterparty,
                                debit_account_id=d_line.account_id
                                if d_line and d_line.debit > 0
                                else None,
                                credit_account_id=c_line.account_id
                                if c_line and c_line.credit > 0
                                else None,
                                description_template=transaction.description,
                            )
                        )
            except Exception as e:
                log.warning("counterparty_autolearn_fail", error=str(e))
        return tx_id

    async def register_opening_balance(
        self,
        opening_date: date,
        debit_balances: Dict[str, str],
        credit_balances: Dict[str, str],
    ) -> int:
        """Record opening balance journal entries from mapped inputs."""
        lines = [
            TransactionLine(
                account_id=int(acc_id), debit=normalize_amount(val), credit=0
            )
            for acc_id, val in debit_balances.items()
            if normalize_amount(val) > 0
        ] + [
            TransactionLine(
                account_id=int(acc_id), debit=0, credit=normalize_amount(val)
            )
            for acc_id, val in credit_balances.items()
            if normalize_amount(val) > 0
        ]
        if not lines:
            raise ValueError("入力された金額がありません。")
        return await self.add_journal_entry(
            Transaction(date=opening_date, description="期首残高", lines=lines)
        )

    async def update_journal_entry(self, transaction: Transaction) -> bool:
        """Update existing journal entry within open fiscal boundary."""
        await self._validate_transaction_date(transaction.date)
        success = await self.repository.update_transaction(transaction)
        if success:
            await self.repository.commit()
            return True
        return False

    async def get_entries(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_deleted: bool = False,
    ) -> List[Transaction]:
        """Fetch transactions within optional date range."""
        return await self.repository.get_transactions(
            start_date, end_date, include_deleted=include_deleted
        )

    async def add_journal_entry_with_evidence(
        self, transaction: Transaction, file_bytes: bytes, file_service: Any
    ) -> int:
        """Persist journal entry and link stored electronic evidence file."""
        tx_id = await self.repository.add_transaction(transaction)
        total_amt = sum(line.debit for line in transaction.lines)
        corp = transaction.counterparty or "Unknown"

        path = await file_service.save_evidence_for_transaction(
            file_bytes=file_bytes,
            transaction_id=tx_id,
            date_obj=transaction.date,
            amount=total_amt,
            corp_name=corp,
        )
        await self.repository.update_evidence_path(tx_id, path)
        await self.repository.commit()
        return tx_id

    async def delete_entry(self, transaction_id: int) -> None:
        """Soft delete journal entry."""
        await self.repository.delete_transaction(transaction_id)

    async def export_journal_entries_csv(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> str:
        """Export filtered journal entries to RFC 4180 CSV string."""
        txs = await self.repository.get_transactions(
            start_date=start_date,
            end_date=end_date,
            include_deleted=False,
            include_relationships=True,
        )
        output = io.StringIO()
        w = csv.writer(output)
        w.writerow(
            [
                "取引日",
                "ID",
                "摘要",
                "取引先",
                "登録番号",
                "勘定科目コード",
                "勘定科目",
                "借方金額",
                "貸方金額",
            ]
        )

        for t in txs:
            common = [
                t.date.isoformat(),
                t.id,
                t.description,
                t.counterparty or "",
                t.invoice_number or "",
            ]
            for line in t.lines:
                code = line.account.code if line.account else ""
                name = line.account.name if line.account else f"ID:{line.account_id}"
                w.writerow(
                    common
                    + [
                        code,
                        name,
                        line.debit if line.debit > 0 else 0,
                        line.credit if line.credit > 0 else 0,
                    ]
                )
        return output.getvalue()

    async def get_frequent_account_ids(self, limit: int = 5) -> List[int]:
        """Fetch most frequently utilized account identifiers."""
        try:
            return await self.repository.get_frequent_account_ids(limit)
        except Exception:
            return []


class FiscalYearService:
    """Service governing fiscal year closing calculations and opening balance rollover."""

    def __init__(
        self,
        master_service: MasterService,
        ledger_service: LedgerService,
        journal_service: JournalService,
    ) -> None:
        """Bind cooperating domain services."""
        self.master_service = master_service
        self.ledger_service = ledger_service
        self.journal_service = journal_service

    async def close_fiscal_year(
        self, fiscal_year_id: int, next_fy_name: Optional[str] = None
    ) -> FiscalYear:
        """Execute period closing, transfer net income to retained earnings, and rollover."""
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

        next_start, next_end = _compute_next_fiscal_year_dates(current_fy.end_date)
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

        await self.journal_service.add_journal_entry(
            Transaction(date=next_fy.start_date, description="前期繰越", lines=lines)
        )
        current_fy.status = "CLOSED"
        await self.master_service.save_fiscal_year(current_fy)
        return next_fy


class Container:
    """Dependency injection container managing session-scoped service lifetimes."""

    @asynccontextmanager
    async def session_scope(self) -> AsyncGenerator[Any, None]:
        """Provide managed async session scope."""
        session = AsyncSessionLocal()
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def journal_service_scope(self) -> AsyncGenerator[JournalService, None]:
        """Yield JournalService bound to dedicated session scope."""
        async with self.session_scope() as s:
            yield JournalService(
                SQLAlchemyLedgerRepository(s),
                master_repository=SQLAlchemyMasterRepository(s),
            )

    @asynccontextmanager
    async def master_service_scope(self) -> AsyncGenerator[MasterService, None]:
        """Yield MasterService bound to dedicated session scope."""
        async with self.session_scope() as s:
            yield MasterService(
                SQLAlchemyMasterRepository(s),
                ledger_repository=SQLAlchemyLedgerRepository(s),
            )

    @asynccontextmanager
    async def ledger_service_scope(self) -> AsyncGenerator[LedgerService, None]:
        """Yield LedgerService bound to dedicated session scope."""
        async with self.session_scope() as s:
            yield LedgerService(SQLAlchemyLedgerRepository(s))

    @asynccontextmanager
    async def fiscal_year_service_scope(
        self,
    ) -> AsyncGenerator[FiscalYearService, None]:
        """Yield FiscalYearService bound to dedicated session scope."""
        async with self.session_scope() as s:
            master_repo = SQLAlchemyMasterRepository(s)
            ledger_repo = SQLAlchemyLedgerRepository(s)
            ms = MasterService(master_repo, ledger_repository=ledger_repo)
            ls = LedgerService(ledger_repo)
            js = JournalService(ledger_repo, master_repository=master_repo)
            yield FiscalYearService(ms, ls, js)

    def get_ocr_service(self) -> Any:
        """Instantiate OCR external service."""
        from app.ai_ocr_service import GeminiOCRService

        return GeminiOCRService()

    def get_file_service(self) -> Any:
        """Instantiate local file storage service."""
        from app.external_services import LocalFileService

        return LocalFileService()

    def get_pdf_service(self) -> Any:
        """Instantiate PDF report generation service."""
        from app.external_services import PDFService

        return PDFService()

    def get_backup_service(self) -> Any:
        """Instantiate backup service."""
        from app.external_services import BackupService

        return BackupService()


container = Container()

# --- 4. Self-Contained Smoke Harness ---
if __name__ == "__main__":
    import asyncio

    async def _smoke_harness():
        c = Container()
        async with c.master_service_scope() as ms:
            assert ms.repository is not None
        log.info("smoke_harness_pass", module="application_services")

    asyncio.run(_smoke_harness())
