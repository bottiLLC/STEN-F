# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core_foundation import normalize_amount, settings
from app.domain_contracts import (
    Abstract,
    Account,
    AccountType,
    Counterparty,
    Transaction,
    TransactionLine,
)
from app.external_services import BackupService, LocalFileService
from app.storage_repository import (
    SQLAlchemyLedgerRepository,
    SQLAlchemyMasterRepository,
    init_db,
)


# --- 1. Core Foundation & Utility Tests ---
def test_normalize_amount_various_inputs():
    """Verify amount cleansing, Zenkaku conversion, and rounding invariants."""
    assert normalize_amount(None) == 0
    assert normalize_amount("") == 0
    assert normalize_amount("   ") == 0
    assert normalize_amount(1000) == 1000
    assert normalize_amount(1234.56) == 1235
    assert normalize_amount(1234.4) == 1234
    assert normalize_amount("１２，３４５円") == 0
    assert normalize_amount("１２，３４５") == 12345
    assert normalize_amount(" 1,000,000 ") == 1000000
    assert normalize_amount("　５００　") == 500
    assert normalize_amount("invalid_string") == 0


# --- 2. Storage & Backup External Services Tests ---
@pytest.mark.asyncio
async def test_local_file_service_lifecycle(tmp_path: Path):
    """Verify local evidence storage and naming conventions."""
    service = LocalFileService(base_dir=tmp_path)
    assert (tmp_path / "storage").exists()

    raw_data = b"%PDF-1.4 dummy file content"
    saved_path_str = await service.save_evidence(
        file_bytes=raw_data,
        original_filename="receipt.pdf",
        date_obj=date(2026, 4, 1),
        description="Office Supplies / PC",
        amount=15000,
    )
    saved_path = Path(saved_path_str)
    assert saved_path.exists()
    assert saved_path.read_bytes() == raw_data
    assert "2026-04-01" in saved_path.name
    assert "15000.pdf" in saved_path.name

    saved_tx_path_str = await service.save_evidence_for_transaction(
        file_bytes=raw_data,
        transaction_id=42,
        date_obj=date(2026, 4, 1),
        amount=25000,
        corp_name="株式会社テスト商事",
    )
    saved_tx_path = Path(saved_tx_path_str)
    assert saved_tx_path.exists()
    assert saved_tx_path.read_bytes() == raw_data
    assert "20260401_25000_テスト商事_42.pdf" in saved_tx_path.name


@pytest.mark.asyncio
async def test_backup_service_lifecycle(tmp_path: Path, monkeypatch):
    """Verify SQLite database and environment backup snapshot generation."""
    service = BackupService()

    with pytest.raises(
        ValueError, match="バックアップ先ディレクトリが指定されていません"
    ):
        await service.create_backup("")

    db_file = tmp_path / "sten_f.db"
    db_file.write_bytes(b"SQLite format 3\x00dummy-db-content")
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY_KEY=12345", encoding="utf-8")

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)

    target_backup_dir = tmp_path / "backups"
    backup_result_path_str = await service.create_backup(str(target_backup_dir))

    backup_result_dir = Path(backup_result_path_str)
    assert backup_result_dir.exists()
    assert backup_result_dir.is_dir()
    assert (backup_result_dir / "sten_f.db").exists()
    assert (
        backup_result_dir / "sten_f.db"
    ).read_bytes() == b"SQLite format 3\x00dummy-db-content"
    assert (backup_result_dir / ".env").exists()
    assert (backup_result_dir / ".env").read_text(encoding="utf-8") == "DUMMY_KEY=12345"


# --- 3. Persistence Repository Tests ---
@pytest.mark.asyncio
async def test_master_repository_operations(container):
    """Verify CRUD lifecycle across master repository entities."""
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)

        # System Settings
        settings_record = await repo.get_system_settings()
        assert settings_record is not None
        settings_record.backup_path = "/tmp/backup"
        saved_s = await repo.save_system_settings(settings_record)
        assert saved_s.backup_path == "/tmp/backup"

        # Corporation
        corp = await repo.get_corporation()
        assert corp is not None
        corp.name = "合同会社ゴールデン"
        saved_c = await repo.save_corporation(corp)
        assert saved_c.name == "合同会社ゴールデン"

        # Fiscal Year
        fys = await repo.get_fiscal_years()
        assert len(fys) >= 1
        fy = await repo.get_fiscal_year(fys[0].id)
        assert fy is not None

        # Account CRUD
        acc = await repo.save_account(
            Account(code="9999", name="テスト科目", type=AccountType.SGA)
        )
        assert acc.id is not None
        all_accs = await repo.get_accounts()
        assert any(a.code == "9999" for a in all_accs)
        assert await repo.delete_account(acc.id) is True

        # Counterparty CRUD
        cp = await repo.save_counterparty(Counterparty(name="リポジトリ専用取引先"))
        assert cp.id is not None
        matched_cp = await repo.get_counterparty_by_keyword("専用取引先")
        assert matched_cp is not None
        assert matched_cp.name == "リポジトリ専用取引先"
        assert await repo.delete_counterparty(cp.id) is True

        # Abstract CRUD
        first_acc = (await repo.get_accounts())[0]
        ab = await repo.save_abstract(
            Abstract(account_id=first_acc.id, text="テスト摘要")
        )
        assert ab.id is not None
        all_abs = await repo.get_abstracts()
        assert any(a.id == ab.id for a in all_abs)
        assert await repo.delete_abstract(ab.id) is True


@pytest.mark.asyncio
async def test_ledger_repository_operations(container):
    """Verify CRUD and query aggregation in ledger repository."""
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

        txs = await ledger_repo.get_transactions()
        saved = next((t for t in txs if t.id == tx_id), None)
        assert saved is not None
        assert saved.description == "Golden Transaction"

        assert await ledger_repo.has_transactions_for_account(acc1.id) is True

        assert (
            await ledger_repo.update_evidence_path(tx_id, "/storage/receipt.pdf")
            is True
        )
        await ledger_repo.commit()
        txs_updated = await ledger_repo.get_transactions()
        updated = next(t for t in txs_updated if t.id == tx_id)
        assert updated.evidence_path == "/storage/receipt.pdf"

        assert await ledger_repo.delete_transaction(tx_id) is True
        await ledger_repo.commit()


# --- 4. Database Schema Auto-Migration Test ---
@pytest.mark.asyncio
async def test_database_auto_migration_backup_path(tmp_path: Path):
    """Verify auto-migration script safely injects missing columns on legacy schema."""
    import app.infrastructure.db.session as session_mod

    original_db_url = settings.DATABASE_URL
    original_engine = session_mod.engine

    temp_db_file = tmp_path / "test_migration.db"
    temp_db_url = f"sqlite+aiosqlite:///{temp_db_file}"
    settings.DATABASE_URL = temp_db_url

    temp_engine = create_async_engine(temp_db_url)
    session_mod.engine = temp_engine

    try:
        async with temp_engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE TABLE system_config (id INTEGER PRIMARY KEY AUTOINCREMENT, ai_api_key TEXT)"
                )
            )
            await conn.execute(
                text("INSERT INTO system_config (ai_api_key) VALUES ('test-key')")
            )

        await init_db(temp_engine)

        async with temp_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT backup_path FROM system_config LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            assert row[0] is None
    finally:
        settings.DATABASE_URL = original_db_url
        session_mod.engine = original_engine
        await temp_engine.dispose()
