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

import csv
from datetime import date
import io
from typing import Dict, List, Optional
import structlog
from app.core.utils import normalize_amount
from app.domain.interfaces.i_ledger_repository import ILedgerRepository
from app.domain.interfaces.i_master_repository import IMasterRepository
from app.domain.models.counterparty import Counterparty
from app.domain.models.transaction import Transaction, TransactionLine

log = structlog.get_logger()


class JournalService:
    def __init__(
        self,
        repository: ILedgerRepository,
        master_repository: Optional[IMasterRepository] = None,
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
        fys = await self._get_fiscal_years()
        open_fys = [fy for fy in fys if fy.status == "OPEN"]
        if not open_fys:
            raise ValueError("現在「OPEN」ステータスの会計年度が存在しません。")

        if not any(fy.start_date <= transaction_date <= fy.end_date for fy in open_fys):
            periods = ", ".join(
                [
                    f"{fy.start_date.strftime('%Y/%m/%d')}〜{fy.end_date.strftime('%Y/%m/%d')}"
                    for fy in open_fys
                ]
            )
            raise ValueError(
                f"指定された日付は、現在「OPEN」な会計年度の範囲外です。\n(入力可能範囲: {periods})"
            )

    async def add_journal_entry(self, transaction: Transaction) -> int:
        await self._validate_transaction_date(transaction.date)
        tx_id = await self.repository.add_transaction(transaction)
        await self.repository.commit()

        if transaction.counterparty:
            try:
                if self.master_repository:
                    existing = await self.master_repository.get_counterparty_by_keyword(
                        transaction.counterparty
                    )
                else:
                    from app.container import container

                    async with container.master_service_scope() as ms:
                        existing = await ms.get_counterparty_by_keyword(
                            transaction.counterparty
                        )

                if not existing:
                    d_acc, c_acc, max_d, max_c = None, None, -1, -1
                    for line in transaction.lines:
                        if line.debit > max_d:
                            max_d, d_acc = line.debit, line.account_id
                        if line.credit > max_c:
                            max_c, c_acc = line.credit, line.account_id

                    new_tmpl = Counterparty(
                        name=transaction.counterparty,
                        debit_account_id=d_acc,
                        credit_account_id=c_acc,
                        description_template=transaction.description,
                    )
                    if self.master_repository:
                        await self.master_repository.save_counterparty(new_tmpl)
                    else:
                        from app.container import container

                        async with container.master_service_scope() as ms:
                            await ms.save_counterparty(new_tmpl)
            except Exception as e:
                self.log.warning(
                    "Failed to auto-learn counterparty rules", error=str(e)
                )

        return tx_id

    async def register_opening_balance(
        self,
        opening_date: date,
        debit_balances: Dict[str, str],
        credit_balances: Dict[str, str],
    ) -> int:
        lines: List[TransactionLine] = []
        for acc_id_str, val_str in debit_balances.items():
            val = normalize_amount(val_str)
            if val > 0:
                lines.append(
                    TransactionLine(account_id=int(acc_id_str), debit=val, credit=0)
                )
        for acc_id_str, val_str in credit_balances.items():
            val = normalize_amount(val_str)
            if val > 0:
                lines.append(
                    TransactionLine(account_id=int(acc_id_str), debit=0, credit=val)
                )

        if not lines:
            raise ValueError("入力された金額がありません。")

        return await self.add_journal_entry(
            Transaction(date=opening_date, description="期首残高", lines=lines)
        )

    async def update_journal_entry(self, transaction: Transaction) -> bool:
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
        return await self.repository.get_transactions(
            start_date, end_date, include_deleted=include_deleted
        )

    async def add_journal_entry_with_evidence(
        self, transaction: Transaction, file_bytes: bytes, file_service
    ) -> int:
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
        await self.repository.delete_transaction(transaction_id)

    async def export_journal_entries_csv(
        self, start_date: Optional[date] = None, end_date: Optional[date] = None
    ) -> str:
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
        try:
            return await self.repository.get_frequent_account_ids(limit)
        except Exception:
            return []
