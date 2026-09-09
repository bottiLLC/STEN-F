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
from typing import List, Dict
import structlog
from app.core.utils import normalize_amount
from app.domain.models.transaction import Transaction, TransactionLine
from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.interfaces.i_master_repository import IMasterRepository
from app.domain.models.counterparty import Counterparty

log = structlog.get_logger()


class JournalService:
    def __init__(
        self,
        repository: ILedgerRepository,
        master_repository: IMasterRepository | None = None,
    ):
        self.repository = repository
        self.master_repository = master_repository
        self.log = log.bind(service="JournalService")

    async def _get_fiscal_years(self):
        if self.master_repository:
            return await self.master_repository.get_fiscal_years()
        from app.container import container

        async with container.master_service_scope() as ms:
            return await ms.get_fiscal_years()

    async def _validate_transaction_date(self, transaction_date: date):
        """
        取引日付が現在OPENな会計年度の範囲内か検証する。
        """
        fys = await self._get_fiscal_years()
        open_fys = [fy for fy in fys if fy.status == "OPEN"]

        if not open_fys:
            raise ValueError("現在「OPEN」ステータスの会計年度が存在しません。")

        # Check if the date falls in ANY of the completely OPEN years
        is_valid = False
        for fy in open_fys:
            if fy.start_date <= transaction_date <= fy.end_date:
                is_valid = True
                break

        if not is_valid:
            # For a better error message, list the open periods
            periods = ", ".join(
                [
                    f"{fy.start_date.strftime('%Y/%m/%d')}〜{fy.end_date.strftime('%Y/%m/%d')}"
                    for fy in open_fys
                ]
            )
            raise ValueError(
                f"指定された日付は、現在「OPEN」な会計年度の範囲外です。\n(入力可能範囲: {periods})"
            )

    async def add_journal_entry(self, transaction: Transaction):
        context_log = self.log.bind(
            date=transaction.date.isoformat(),
            description=transaction.description,
            line_count=len(transaction.lines),
        )

        try:
            await self._validate_transaction_date(transaction.date)

            context_log.info("Adding new journal entry")
            tx_id = await self.repository.add_transaction(transaction)
            await self.repository.commit()  # Unit of Work Commit
            context_log.info("Journal entry added successfully", transaction_id=tx_id)

            # --- Auto-Learning for Counterparty Dictionary ---
            if transaction.counterparty:
                try:
                    if self.master_repository:
                        existing_template = (
                            await self.master_repository.get_counterparty_by_keyword(
                                transaction.counterparty
                            )
                        )
                    else:
                        from app.container import container

                        async with container.master_service_scope() as ms:
                            existing_template = await ms.get_counterparty_by_keyword(
                                transaction.counterparty
                            )

                    if not existing_template:
                        # Extract primary debit and primary credit from lines
                        debit_account_id = None
                        credit_account_id = None
                        max_debit = -1
                        max_credit = -1
                        for line in transaction.lines:
                            if line.debit > max_debit:
                                max_debit = line.debit
                                debit_account_id = line.account_id
                            if line.credit > max_credit:
                                max_credit = line.credit
                                credit_account_id = line.account_id

                        new_template = Counterparty(
                            name=transaction.counterparty,
                            debit_account_id=debit_account_id,
                            credit_account_id=credit_account_id,
                            description_template=transaction.description,
                        )
                        if self.master_repository:
                            await self.master_repository.save_counterparty(new_template)
                        else:
                            from app.container import container

                            async with container.master_service_scope() as ms:
                                await ms.save_counterparty(new_template)

                        context_log.info(
                            "Auto-learned new counterparty rules",
                            keyword=transaction.counterparty,
                        )
                except Exception as e:
                    context_log.warning(
                        "Failed to auto-learn counterparty rules", error=str(e)
                    )

            return tx_id
        except Exception as e:
            context_log.error("Failed to add journal entry", error=str(e))
            raise

    async def register_opening_balance(
        self,
        opening_date: date,
        debit_balances: Dict[str, str],
        credit_balances: Dict[str, str],
    ) -> int:
        """
        期首残高の登録処理（UIから受け取った生辞書データからトランザクションエンティティを構築して保存する）
        """
        lines: List[TransactionLine] = []

        # 借方入力分の処理
        for acc_id_str, val_str in debit_balances.items():
            val = normalize_amount(val_str)
            if val > 0:
                lines.append(
                    TransactionLine(account_id=int(acc_id_str), debit=val, credit=0)
                )

        # 貸方入力分の処理
        for acc_id_str, val_str in credit_balances.items():
            val = normalize_amount(val_str)
            if val > 0:
                lines.append(
                    TransactionLine(account_id=int(acc_id_str), debit=0, credit=val)
                )

        if not lines:
            raise ValueError("入力された金額がありません。")

        transaction = Transaction(
            date=opening_date, description="期首残高", lines=lines
        )

        return await self.add_journal_entry(transaction)

    async def update_journal_entry(self, transaction: Transaction) -> bool:
        context_log = self.log.bind(
            transaction_id=transaction.id, description=transaction.description
        )
        try:
            await self._validate_transaction_date(transaction.date)

            context_log.info("Updating journal entry")
            success = await self.repository.update_transaction(transaction)
            if success:
                await self.repository.commit()
                context_log.info("Journal entry updated successfully")
                return True
            else:
                context_log.warning("Journal entry not found for update")
                return False
        except Exception as e:
            context_log.error("Failed to update journal entry", error=str(e))
            raise

    async def get_entries(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        include_deleted: bool = False,
    ) -> List[Transaction]:
        """指定された期間・条件に基づいて仕訳データを取得する。"""
        try:
            self.log.debug("Fetching journal entries")
            entries = await self.repository.get_transactions(
                start_date, end_date, include_deleted=include_deleted
            )
            self.log.info("Fetched journal entries", count=len(entries))
            return entries
        except Exception as e:
            self.log.error("Failed to fetch journal entries", error=str(e))
            raise

    async def add_journal_entry_with_evidence(
        self, transaction: Transaction, file_bytes: bytes, file_service
    ) -> int:
        """証憑ファイルを保存し、そのパスを紐づけて仕訳を新規登録する。"""
        context_log = self.log.bind(
            date=transaction.date.isoformat(),
            description=transaction.description,
            counterparty=transaction.counterparty,
        )
        try:
            context_log.info("Adding journal entry with evidence")

            # 1. 仕訳を追加（IDを採番）
            tx_id = await self.repository.add_transaction(transaction)

            # 2. 証憑ファイルをストレージに保存
            total_amount = sum(line.debit for line in transaction.lines)
            corp_name = transaction.counterparty or "Unknown"

            evidence_path = await file_service.save_evidence_for_transaction(
                file_bytes=file_bytes,
                transaction_id=tx_id,
                date_obj=transaction.date,
                amount=total_amount,
                corp_name=corp_name,
            )

            # 3. 証憑パスを更新してコミット
            await self.repository.update_evidence_path(tx_id, evidence_path)
            await self.repository.commit()

            context_log.info(
                "Journal entry with evidence added",
                transaction_id=tx_id,
                path=evidence_path,
            )
            return tx_id

        except Exception as e:
            context_log.error("Failed to add entry with evidence", error=str(e))
            # Rollback is handled by session context usually, or explicit?
            # We should probably rollback if we could.
            # self.repository.rollback() ? (Not in interface yet, but maybe session auto-rolls back on close/error?)
            raise

    async def delete_entry(self, transaction_id: int):
        context_log = self.log.bind(transaction_id=transaction_id)
        try:
            context_log.info("Deleting journal entry")
            await self.repository.delete_transaction(transaction_id)
            context_log.info("Journal entry deleted successfully")
        except Exception as e:
            context_log.error("Failed to delete journal entry", error=str(e))
            raise

    async def export_journal_entries_csv(self, start_date=None, end_date=None) -> str:
        """
        Exports journal entries to CSV string.
        """
        import csv
        import io

        try:
            # Fetch transactions with relationships
            transactions = await self.repository.get_transactions(
                start_date=start_date,
                end_date=end_date,
                include_deleted=False,
                include_relationships=True,
            )

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
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

            for t in transactions:
                # Common fields for all lines in this transaction
                common = [
                    t.date.isoformat(),
                    t.id,
                    t.description,
                    t.counterparty or "",
                    t.invoice_number or "",
                ]

                for line in t.lines:
                    # Account might be loaded
                    account_code = line.account.code if line.account else ""
                    account_name = (
                        line.account.name if line.account else f"ID:{line.account_id}"
                    )

                    row = common + [
                        account_code,
                        account_name,
                        line.debit if line.debit > 0 else 0,
                        line.credit if line.credit > 0 else 0,
                    ]
                    writer.writerow(row)

            return output.getvalue()

        except Exception as e:
            self.log.error("Failed to export CSV", error=str(e))
            raise

    async def get_frequent_account_ids(self, limit: int = 5) -> list[int]:
        """
        Get the defined number of frequently used account IDs.
        """
        try:
            return await self.repository.get_frequent_account_ids(limit)
        except Exception as e:
            self.log.error("Failed to fetch frequent accounts", error=str(e))
            return []
