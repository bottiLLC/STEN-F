# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from typing import TYPE_CHECKING

from app.application_services.master_service import MasterService
from app.core_foundation import log, normalize_amount
from app.domain_contracts import (
    Counterparty,
    ILedgerRepository,
    IMasterRepository,
    Transaction,
    TransactionLine,
    identify_cancelled_transaction_ids,
    is_red_slip_transaction,
)

if TYPE_CHECKING:
    from app.external_services import LocalFileService


class JournalService:
    """Service governing journal entries, fiscal validation, and exports."""

    def __init__(
        self,
        repository: ILedgerRepository,
        master_repository: IMasterRepository | None = None,
    ) -> None:
        """Bind repository dependencies.

        Args:
            repository: Implementation of ILedgerRepository.
            master_repository: Optional implementation of IMasterRepository.
        """
        self.repository = repository
        self.master_repository = master_repository

    @asynccontextmanager
    async def _master_scope(
        self,
    ) -> AsyncGenerator[IMasterRepository | MasterService, None]:
        """Resolve master repository boundary.

        Yields:
            IMasterRepository or MasterService instance.
        """
        if self.master_repository:
            yield self.master_repository
        else:
            from app.application_services.container import container

            async with container.master_service_scope() as ms:
                yield ms

    async def _validate_transaction_date(self, transaction_date: date) -> None:
        """Validate transaction date falls within an open fiscal year.

        Args:
            transaction_date: Transaction date to validate.

        Raises:
            ValueError: If no open fiscal period exists or date is out of range.
        """
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
        """Validate and record double-entry journal transaction.

        Args:
            transaction: Balanced Transaction domain model.

        Returns:
            Database primary key ID of created transaction.
        """
        tx_date = transaction.occurred_at or transaction.date
        if not tx_date:
            raise ValueError("Transaction requires occurred_at or date")
        await self._validate_transaction_date(tx_date)
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
        debit_balances: dict[str, str],
        credit_balances: dict[str, str],
    ) -> int:
        """Record opening balance journal entries from mapped inputs.

        Args:
            opening_date: Transaction date for opening balance.
            debit_balances: Map of account ID string to debit monetary string.
            credit_balances: Map of account ID string to credit monetary string.

        Returns:
            Created Transaction ID.

        Raises:
            ValueError: If no non-zero amounts provided or already registered.
        """
        existing_entries = await self.get_entries(
            start_date=opening_date, end_date=opening_date
        )
        if any(tx.description in ("期首残高", "前期繰越") for tx in existing_entries):
            raise ValueError(
                "指定日の会計年度には既に「期首残高」または「前期繰越」が登録されています。"
                "訂正が必要な場合は、過去仕訳に対し赤伝（反対仕訳）を起票してください。"
            )

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
            Transaction(occurred_at=opening_date, description="期首残高", lines=lines)
        )

    async def reverse_journal_entry(
        self,
        transaction_id: int,
        reason: str = "誤謬取消",
        cancel_date: date | None = None,
    ) -> int:
        """Rectify journal entry solely by inserting a reversing entry under Rule 1.

        Args:
            transaction_id: Target transaction ID to reverse.
            reason: Cancellation explanation or memo.
            cancel_date: Reversing entry occurrence date (defaults to original occurrence date).

        Returns:
            Newly created reversing transaction ID.

        Raises:
            ValueError: If original transaction not found, already reversed/cancelling, or date outside open fiscal year.
        """
        all_txs = await self.repository.get_transactions(include_deleted=True)
        orig = next((t for t in all_txs if t.id == transaction_id), None)
        if not orig:
            raise ValueError(f"仕訳ID {transaction_id} が見つかりません。")

        if is_red_slip_transaction(orig):
            raise ValueError("取消仕訳（赤伝）自体を再度取り消すことはできません。")

        already_reversed_ids = identify_cancelled_transaction_ids(all_txs)
        if transaction_id in already_reversed_ids:
            raise ValueError(
                f"仕訳ID {transaction_id} は既に取消（赤伝）処理済みです。"
            )

        target_date = cancel_date or orig.occurred_at or orig.date
        if not target_date:
            raise ValueError("Transaction requires occurred_at or date")
        await self._validate_transaction_date(target_date)

        rev_id = await self.repository.reverse_transaction(
            original_tx_id=transaction_id,
            reason=reason,
            occurred_at=cancel_date,
        )
        await self.repository.commit()
        return rev_id

    async def update_journal_entry(self, transaction: Transaction) -> bool:
        """Prohibited by Rule 1 (Absolute Immutability). Use reverse_journal_entry."""
        raise NotImplementedError(
            "UPDATE operations on Journal Entries are strictly prohibited by Rule 1 (Absolute Immutability). "
            "Rectify transactions solely by inserting reversing entries via reverse_journal_entry."
        )

    async def get_entries(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        include_deleted: bool = False,
    ) -> list[Transaction]:
        """Fetch transactions within optional date range.

        Args:
            start_date: Optional inclusive start date.
            end_date: Optional inclusive end date.
            include_deleted: Whether to include logically deleted entries.

        Returns:
            List of Transaction domain models.
        """
        return await self.repository.get_transactions(
            start_date, end_date, include_deleted=include_deleted
        )

    async def add_journal_entry_with_evidence(
        self,
        transaction: Transaction,
        file_bytes: bytes,
        file_service: LocalFileService,
        extension: str = ".pdf",
    ) -> int:
        """Persist journal entry and link stored electronic evidence file.

        Args:
            transaction: Balanced Transaction domain model.
            file_bytes: Raw binary content of receipt/invoice file.
            file_service: LocalFileService instance for file saving.
            extension: File extension suffix (defaults to .pdf).

        Returns:
            Created Transaction ID.
        """
        total_amt = sum(line.debit for line in transaction.lines)
        corp = transaction.counterparty or "Unknown"

        tx_date = transaction.occurred_at or transaction.date
        if not tx_date:
            raise ValueError("Transaction requires occurred_at or date")
        # Validate open fiscal period before persisting evidence bytes to avoid orphaned files
        await self._validate_transaction_date(tx_date)
        path = await file_service.save_evidence_for_transaction(
            file_bytes=file_bytes,
            transaction_id=None,
            date_obj=tx_date,
            amount=total_amt,
            corp_name=corp,
            extension=extension,
        )
        transaction.evidence_path = path
        return await self.add_journal_entry(transaction)

    async def delete_entry(self, transaction_id: int) -> None:
        """Prohibited by Rule 1 (Absolute Immutability). Use reverse_journal_entry."""
        raise NotImplementedError(
            "DELETE operations on Journal Entries are strictly prohibited by Rule 1 (Absolute Immutability). "
            "Rectify transactions solely by inserting reversing entries via reverse_journal_entry."
        )
