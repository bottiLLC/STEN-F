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

"""
First Stage Golden Master Test: Ledger & Master Repositories
Testing ONLY public API with test SQLite database boundary.
"""

from datetime import date
import pytest

from app.domain.models.abstract import Abstract
from app.domain.models.account import Account, AccountType
from app.domain.models.counterparty import Counterparty
from app.domain.models.transaction import Transaction, TransactionLine

from app.infrastructure.repositories.ledger_repository_impl import SQLAlchemyLedgerRepository
from app.infrastructure.repositories.master_repository_impl import SQLAlchemyMasterRepository


@pytest.mark.asyncio
async def test_golden_master_repository(container):
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)

        # 1. System Settings
        settings = await repo.get_system_settings()
        assert settings is not None
        settings.backup_path = "/tmp/backup"
        saved_s = await repo.save_system_settings(settings)
        assert saved_s.backup_path == "/tmp/backup"

        # 2. Corporation
        corp = await repo.get_corporation()
        assert corp is not None
        corp.name = "合同会社ゴールデン"
        saved_c = await repo.save_corporation(corp)
        assert saved_c.name == "合同会社ゴールデン"

        # 3. Fiscal Year
        fys = await repo.get_fiscal_years()
        assert len(fys) >= 1
        fy = await repo.get_fiscal_year(fys[0].id)
        assert fy is not None

        # 4. Account CRUD
        acc = await repo.save_account(Account(code="9999", name="テスト科目", type=AccountType.SGA))
        assert acc.id is not None
        all_accs = await repo.get_accounts()
        assert any(a.code == "9999" for a in all_accs)
        deleted = await repo.delete_account(acc.id)
        assert deleted is True


        # 5. Counterparty CRUD
        cp = await repo.save_counterparty(Counterparty(name="リポジトリ専用取引先"))
        assert cp.id is not None
        matched_cp = await repo.get_counterparty_by_keyword("専用取引先")
        assert matched_cp is not None
        assert matched_cp.name == "リポジトリ専用取引先"
        del_cp = await repo.delete_counterparty(cp.id)
        assert del_cp is True



        # 6. Abstract CRUD
        first_acc = (await repo.get_accounts())[0]
        ab = await repo.save_abstract(Abstract(account_id=first_acc.id, text="テスト摘要"))
        assert ab.id is not None
        all_abs = await repo.get_abstracts()
        assert any(a.id == ab.id for a in all_abs)
        del_ab = await repo.delete_abstract(ab.id)
        assert del_ab is True



@pytest.mark.asyncio
async def test_golden_ledger_repository(container):
    async with container.session_scope() as session:
        master_repo = SQLAlchemyMasterRepository(session)
        ledger_repo = SQLAlchemyLedgerRepository(session)

        accounts = await master_repo.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]

        tx = Transaction(
            date=date.today(),
            description="Golden Transaction",
            lines=[
                TransactionLine(account_id=acc1.id, debit=5000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=5000),
            ],
            counterparty="ゴールデン顧客",
        )
        tx_id = await ledger_repo.add_transaction(tx)
        await ledger_repo.commit()
        assert tx_id > 0

        # Fetch
        txs = await ledger_repo.get_transactions()
        saved = next((t for t in txs if t.id == tx_id), None)
        assert saved is not None
        assert saved.description == "Golden Transaction"

        # Check has_transactions_for_account
        has_tx = await ledger_repo.has_transactions_for_account(acc1.id)
        assert has_tx is True

        # Update evidence path
        await ledger_repo.update_evidence_path(tx_id, "/storage/receipt.pdf")
        await ledger_repo.commit()
        txs_updated = await ledger_repo.get_transactions()
        updated = next(t for t in txs_updated if t.id == tx_id)
        assert updated.evidence_path == "/storage/receipt.pdf"

        # Delete
        del_res = await ledger_repo.delete_transaction(tx_id)
        await ledger_repo.commit()
        assert del_res is True
