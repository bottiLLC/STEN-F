# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.application_services import Container
from app.core_foundation import (
    call_backup,
    call_fiscal_year,
    normalize_amount,
    settings,
)
from app.domain_contracts import (
    Abstract,
    Account,
    AccountType,
    Corporation,
    Counterparty,
    FiscalYear,
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
@pytest.mark.parametrize(
    ("input_val", "expected"),
    [
        (None, 0),
        ("", 0),
        ("   ", 0),
        (1000, 1000),
        (-500, -500),
        (1234.56, 1235),
        (1234.4, 1234),
        ("１２，３４５円", 0),
        ("１２，３４５", 12345),
        (" 1,000,000 ", 1000000),
        ("　５００　", 500),
        ("invalid_string", 0),
        ("¥1000", 0),
        ("1,234.5", 1235),
    ],
)
def test_normalize_amount_with_various_inputs_returns_expected_integer(
    input_val: object, expected: int
) -> None:
    """Verify amount cleansing, Zenkaku conversion, and rounding invariants."""
    # Arrange & Act
    actual = normalize_amount(input_val)

    # Assert
    assert actual == expected
    assert isinstance(actual, int)


# --- 2. Storage & Backup External Services Tests ---
@pytest.mark.asyncio
async def test_local_file_service_save_evidence_creates_file_with_sanitized_name_and_content(
    tmp_path: Path,
) -> None:
    """Verify local evidence storage creates valid file with sanitized name and content."""
    # Arrange
    service = LocalFileService(base_dir=tmp_path)
    raw_data = b"%PDF-1.4 dummy file content"
    target_date = date(2026, 4, 1)

    # Act
    saved_path_str = await service.save_evidence(
        file_bytes=raw_data,
        original_filename="receipt.pdf",
        date_obj=target_date,
        description="Office Supplies / PC",
        amount=15000,
    )
    saved_path = Path(saved_path_str)

    # Assert
    assert (tmp_path / "storage").is_dir()
    assert saved_path.is_file()
    assert saved_path.read_bytes() == raw_data
    assert "2026-04-01" in saved_path.name
    assert "15000.pdf" in saved_path.name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("corp_input", "expected_suffix"),
    [
        ("株式会社テスト商事", "テスト商事"),
        ("合同会社サンプル", "サンプル"),
        ("有限会社オメガ", "オメガ"),
        ("単独商店", "単独商店"),
    ],
)
async def test_local_file_service_save_evidence_for_transaction_strips_corporate_prefixes(
    tmp_path: Path, corp_input: str, expected_suffix: str
) -> None:
    """Verify corporate prefixes are properly stripped from transaction evidence filename."""
    # Arrange
    service = LocalFileService(base_dir=tmp_path)
    raw_data = b"%PDF-1.4 sample content"
    tx_id = 42

    # Act
    saved_tx_path_str = await service.save_evidence_for_transaction(
        file_bytes=raw_data,
        transaction_id=tx_id,
        date_obj=date(2026, 4, 1),
        amount=25000,
        corp_name=corp_input,
    )
    saved_tx_path = Path(saved_tx_path_str)

    # Assert
    assert saved_tx_path.is_file()
    assert saved_tx_path.read_bytes() == raw_data
    assert f"20260401_25000_{expected_suffix}_{tx_id}.pdf" in saved_tx_path.name


@pytest.mark.asyncio
async def test_backup_service_create_backup_with_empty_target_dir_raises_value_error() -> (
    None
):
    """Ensure BackupService raises ValueError with expected message when target directory is empty."""
    # Arrange
    service = BackupService()

    # Act & Assert
    with pytest.raises(
        ValueError, match="バックアップ先ディレクトリが指定されていません。"
    ):
        await service.create_backup("")


@pytest.mark.asyncio
async def test_backup_service_create_backup_copies_db_wal_shm_and_env_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify SQLite database and environment backup snapshot generation including WAL and SHM."""
    # Arrange
    service = BackupService()
    db_file = tmp_path / "sten_f.db"
    db_file.write_bytes(b"SQLite format 3\x00dummy-db-content")
    wal_file = tmp_path / "sten_f.db-wal"
    wal_file.write_bytes(b"wal-sample-content")
    shm_file = tmp_path / "sten_f.db-shm"
    shm_file.write_bytes(b"shm-sample-content")
    env_file = tmp_path / ".env"
    env_file.write_text("DUMMY_KEY=12345", encoding="utf-8")

    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(settings, "PROJECT_ROOT", tmp_path)
    target_backup_dir = tmp_path / "backups"

    # Act
    backup_result_path_str = await service.create_backup(str(target_backup_dir))
    backup_result_dir = Path(backup_result_path_str)

    # Assert
    assert backup_result_dir.is_dir()
    assert (
        backup_result_dir / "sten_f.db"
    ).read_bytes() == b"SQLite format 3\x00dummy-db-content"
    assert (backup_result_dir / "sten_f.db-wal").read_bytes() == b"wal-sample-content"
    assert (backup_result_dir / "sten_f.db-shm").read_bytes() == b"shm-sample-content"
    assert (backup_result_dir / ".env").read_text(encoding="utf-8") == "DUMMY_KEY=12345"


# --- 3. Persistence Repository Tests ---
@pytest.mark.asyncio
async def test_master_repository_system_settings_crud_lifecycle(
    container: Container,
) -> None:
    """Verify CRUD lifecycle of system settings in SQLAlchemyMasterRepository."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)

        # Act
        settings_record = await repo.get_system_settings()
        settings_record.backup_path = "/tmp/custom_backup"
        saved_s = await repo.save_system_settings(settings_record)
        fetched_s = await repo.get_system_settings()

        # Assert
        assert saved_s.backup_path == "/tmp/custom_backup"
        assert fetched_s.backup_path == "/tmp/custom_backup"


@pytest.mark.asyncio
async def test_master_repository_corporation_crud_lifecycle(
    container: Container,
) -> None:
    """Verify Corporation persistence lifecycle in SQLAlchemyMasterRepository."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)

        # Act
        corp = await repo.get_corporation()
        if corp is None:
            corp = Corporation(name="初期法人名")
        corp.name = "合同会社ゴールデン"
        saved_c = await repo.save_corporation(corp)
        refetched = await repo.get_corporation()

        # Assert
        assert saved_c.name == "合同会社ゴールデン"
        assert isinstance(refetched, Corporation)
        assert refetched.name == "合同会社ゴールデン"


@pytest.mark.asyncio
async def test_master_repository_fiscal_year_crud_and_nonexistent_lookups(
    container: Container,
) -> None:
    """Verify FiscalYear CRUD and boundary checks on nonexistent IDs in SQLAlchemyMasterRepository."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)
        test_fy = FiscalYear(
            name="リポジトリテスト期",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 12, 31),
            period_number=10,
            status="OPEN",
        )

        # Act
        saved_fy = await repo.save_fiscal_year(test_fy)
        assert saved_fy.id is not None
        fetched_fy = await repo.get_fiscal_year(saved_fy.id)
        non_existent_fy = await repo.get_fiscal_year(999999)
        delete_success = await repo.delete_fiscal_year(saved_fy.id)
        delete_non_existent = await repo.delete_fiscal_year(999999)

        # Assert
        assert isinstance(fetched_fy, FiscalYear)
        assert fetched_fy.id == saved_fy.id
        assert fetched_fy.name == "リポジトリテスト期"
        assert fetched_fy.period_number == 10
        assert fetched_fy.status == "OPEN"
        assert fetched_fy.start_date == date(2025, 1, 1)
        assert fetched_fy.end_date == date(2025, 12, 31)
        assert non_existent_fy is None
        assert delete_success is True
        assert delete_non_existent is False


@pytest.mark.asyncio
async def test_master_repository_account_crud_and_nonexistent_deletion(
    container: Container,
) -> None:
    """Verify Account CRUD operations and nonexistent deletion contract."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)
        new_account = Account(code="9999", name="テスト科目", type=AccountType.SGA)

        # Act
        saved_acc = await repo.save_account(new_account)
        assert saved_acc.id is not None
        all_accs = await repo.get_accounts()
        delete_success = await repo.delete_account(saved_acc.id)
        delete_fail = await repo.delete_account(999999)

        # Assert
        assert any(a.code == "9999" and a.name == "テスト科目" for a in all_accs)
        assert delete_success is True
        assert delete_fail is False


@pytest.mark.asyncio
async def test_master_repository_counterparty_and_abstract_crud(
    container: Container,
) -> None:
    """Verify Counterparty and Abstract entity persistence and keyword searches."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)
        first_acc = (await repo.get_accounts())[0]
        assert first_acc.id is not None

        # Act
        cp = await repo.save_counterparty(Counterparty(name="リポジトリ専用取引先"))
        assert cp.id is not None
        matched_cp = await repo.get_counterparty_by_keyword("専用取引先")
        unmatched_cp = await repo.get_counterparty_by_keyword("存在しない取引先名XYZ")

        ab = await repo.save_abstract(
            Abstract(account_id=first_acc.id, text="テスト摘要")
        )
        assert ab.id is not None
        all_abs = await repo.get_abstracts()

        delete_cp_res = await repo.delete_counterparty(cp.id)
        delete_cp_nonexistent = await repo.delete_counterparty(999999)
        delete_ab_res = await repo.delete_abstract(ab.id)
        delete_ab_nonexistent = await repo.delete_abstract(999999)

        # Assert
        assert isinstance(matched_cp, Counterparty)
        assert matched_cp.id == cp.id
        assert matched_cp.name == "リポジトリ専用取引先"
        assert unmatched_cp is None
        assert any(a.id == ab.id and a.text == "テスト摘要" for a in all_abs)
        assert delete_cp_res is True
        assert delete_cp_nonexistent is False
        assert delete_ab_res is True
        assert delete_ab_nonexistent is False


@pytest.mark.asyncio
async def test_ledger_repository_operations(container: Container) -> None:
    """Verify CRUD, evidence path updates, and query aggregation in ledger repository."""
    # Arrange
    async with container.session_scope() as session:
        master_repo = SQLAlchemyMasterRepository(session)
        ledger_repo = SQLAlchemyLedgerRepository(session)

        accounts = await master_repo.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]
        assert acc1.id is not None and acc2.id is not None

        tx = Transaction(
            date=date.today(),
            description="Golden Transaction",
            lines=[
                TransactionLine(account_id=acc1.id, debit=5000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=5000),
            ],
            counterparty="ゴールデン顧客",
        )

        # Act
        tx_id = await ledger_repo.add_transaction(tx)
        await ledger_repo.commit()
        txs = await ledger_repo.get_transactions()
        saved = next((t for t in txs if t.id == tx_id), None)
        has_tx = await ledger_repo.has_transactions_for_account(acc1.id)

        update_ev_success = await ledger_repo.update_evidence_path(
            tx_id, "/storage/receipt.pdf"
        )
        update_ev_fail = await ledger_repo.update_evidence_path(
            999999, "/storage/receipt.pdf"
        )
        await ledger_repo.commit()

        txs_updated = await ledger_repo.get_transactions()
        updated = next(t for t in txs_updated if t.id == tx_id)

        delete_success = await ledger_repo.delete_transaction(tx_id)
        delete_fail = await ledger_repo.delete_transaction(999999)
        await ledger_repo.commit()

        # Assert
        assert tx_id > 0
        assert isinstance(saved, Transaction)
        assert saved.id == tx_id
        assert saved.description == "Golden Transaction"
        assert saved.counterparty == "ゴールデン顧客"
        assert len(saved.lines) == 2
        assert has_tx is True
        assert update_ev_success is True
        assert update_ev_fail is False
        assert updated.evidence_path == "/storage/receipt.pdf"
        assert delete_success is True
        assert delete_fail is False


@pytest.mark.asyncio
async def test_ledger_repository_get_transactions_filtered_by_date_range(
    container: Container,
) -> None:
    """Verify transaction querying with date boundary filters."""
    # Arrange
    async with container.session_scope() as session:
        master_repo = SQLAlchemyMasterRepository(session)
        ledger_repo = SQLAlchemyLedgerRepository(session)
        accounts = await master_repo.get_accounts()
        acc1, acc2 = accounts[0], accounts[1]
        assert acc1.id is not None and acc2.id is not None

        target_date = date.today()
        tx_today = Transaction(
            date=target_date,
            description="日付フィルタテスト（本日）",
            lines=[
                TransactionLine(account_id=acc1.id, debit=1000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=1000),
            ],
        )
        tx_past = Transaction(
            date=target_date - timedelta(days=10),
            description="日付フィルタテスト（過去）",
            lines=[
                TransactionLine(account_id=acc1.id, debit=2000, credit=0),
                TransactionLine(account_id=acc2.id, debit=0, credit=2000),
            ],
        )

        id_today = await ledger_repo.add_transaction(tx_today)
        id_past = await ledger_repo.add_transaction(tx_past)
        await ledger_repo.commit()

        # Act
        filtered_txs = await ledger_repo.get_transactions(
            start_date=target_date, end_date=target_date
        )

        # Clean up
        await ledger_repo.delete_transaction(id_today)
        await ledger_repo.delete_transaction(id_past)
        await ledger_repo.commit()

        # Assert
        filtered_ids = [t.id for t in filtered_txs]
        assert id_today in filtered_ids
        assert id_past not in filtered_ids


# --- 4. Database Schema Auto-Migration Test ---
@pytest.mark.asyncio
async def test_database_auto_migration_backup_path_injects_missing_column(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify auto-migration script safely injects missing backup_path column on legacy schema."""
    # Arrange
    temp_db_file = tmp_path / "test_migration.db"
    temp_db_url = f"sqlite+aiosqlite:///{temp_db_file}"
    temp_engine = create_async_engine(temp_db_url)

    monkeypatch.setattr(settings, "DATABASE_URL", temp_db_url)

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

        # Act
        await init_db(temp_engine)

        # Assert
        async with temp_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT backup_path FROM system_config LIMIT 1")
            )
            row = result.fetchone()
            assert row is not None
            assert tuple(row) == (None,)
    finally:
        await temp_engine.dispose()


@pytest.mark.asyncio
async def test_seed_accounts_with_service_populates_defaults_idempotently(
    container: Container,
) -> None:
    """Verify seed_accounts_with_service seeds DEFAULT_ACCOUNTS and subsequent runs are no-ops."""
    # Arrange
    from app.storage_repository import seed_accounts_with_service

    async with container.master_service_scope() as service:
        # Act 1: Seed accounts into database
        await seed_accounts_with_service(service.repository)
        first_run_accounts = await service.get_accounts()

        # Assert 1: All default accounts populated
        assert len(first_run_accounts) >= 47

        # Act 2: Re-run seed on already populated database
        await seed_accounts_with_service(service.repository)
        second_run_accounts = await service.get_accounts()

        # Assert 2: No duplicate accounts inserted
        assert len(second_run_accounts) == len(first_run_accounts)


@pytest.mark.asyncio
async def test_call_fiscal_year_and_call_backup_helper_functions(
    container: Container, tmp_path: Path
) -> None:
    """Verify call_fiscal_year and call_backup helper functions execute under active scopes."""
    # Arrange & Act: call_fiscal_year
    fys = call_fiscal_year(lambda s: s.master_service.get_fiscal_years())

    # Assert
    assert isinstance(fys, list)
    assert len(fys) > 0

    # Arrange & Act: call_backup
    backup_target = tmp_path / "backups_test"
    backup_dir = call_backup(lambda b: b.create_backup(str(backup_target)))

    # Assert
    assert isinstance(backup_dir, str)
    assert Path(backup_dir).exists()


@pytest.mark.asyncio
async def test_master_repository_save_counterparty_merges_on_matching_invoice_or_name(
    container: Container,
) -> None:
    """Verify save_counterparty updates existing record when ID is None but invoice_number or name matches."""
    # Arrange
    async with container.session_scope() as session:
        repo = SQLAlchemyMasterRepository(session)
        cp_initial = await repo.save_counterparty(
            Counterparty(
                name="インボイス名寄せテスト商事",
                invoice_number="T1111111111111",
            )
        )
        assert cp_initial.id is not None

        # Act 1: Same invoice_number, ID=None, updated name
        cp_updated_by_inv = await repo.save_counterparty(
            Counterparty(
                id=None,
                name="インボイス名寄せテスト商事（改名）",
                invoice_number="T1111111111111",
            )
        )

        # Assert 1: Same ID retained, name updated
        assert cp_updated_by_inv.id == cp_initial.id
        assert cp_updated_by_inv.name == "インボイス名寄せテスト商事（改名）"

        # Act 2: Same name, ID=None, new invoice_number
        cp_updated_by_name = await repo.save_counterparty(
            Counterparty(
                id=None,
                name="インボイス名寄せテスト商事（改名）",
                invoice_number="T2222222222222",
            )
        )

        # Assert 2: Same ID retained, invoice_number updated
        assert cp_updated_by_name.id == cp_initial.id
        assert cp_updated_by_name.invoice_number == "T2222222222222"
