import pytest
from datetime import date
from pathlib import Path
from app.infrastructure.external.file_service import LocalFileService

@pytest.mark.asyncio
async def test_save_evidence_success(tmp_path):
    # 1. Initialize LocalFileService with temporary path
    service = LocalFileService(base_dir=tmp_path)
    
    # Check that storage directory is created
    storage_dir = tmp_path / "storage"
    assert storage_dir.exists()
    assert storage_dir.is_dir()
    
    # 2. Prepare dummy arguments
    dummy_bytes = b"Dummy PDF Bytes content"
    orig_filename = "receipt.pdf"
    tx_date = date(2026, 7, 19)
    description = "コンビニ（消耗品）"
    amount = 540
    
    # 3. Execute
    saved_path_str = await service.save_evidence(
        file_bytes=dummy_bytes,
        original_filename=orig_filename,
        date_obj=tx_date,
        description=description,
        amount=amount
    )
    
    saved_path = Path(saved_path_str)
    
    # 4. Assertions
    assert saved_path.exists()
    assert saved_path.is_file()
    assert saved_path.parent == storage_dir
    
    # Check standardized filename format: YYYY-MM-DD_Store_Amount.pdf
    # "コンビニ（消耗品）" -> non-alphanumeric removed except spaces, underscores, hyphens
    # isalnum() of "コンビニ" is True for Japanese characters in Python.
    expected_filename = "2026-07-19_コンビニ消耗品_540.pdf"
    assert saved_path.name == expected_filename
    
    # Check file content
    with open(saved_path, "rb") as f:
        assert f.read() == dummy_bytes

@pytest.mark.asyncio
async def test_save_evidence_for_transaction_success(tmp_path):
    service = LocalFileService(base_dir=tmp_path)
    
    dummy_bytes = b"Evidence for Tx"
    tx_id = 99
    tx_date = date(2026, 7, 19)
    amount = 12960
    corp_name = "テスト株式会社（合同会社ぼっち）"
    
    # Execute
    saved_path_str = await service.save_evidence_for_transaction(
        file_bytes=dummy_bytes,
        transaction_id=tx_id,
        date_obj=tx_date,
        amount=amount,
        corp_name=corp_name
    )
    
    saved_path = Path(saved_path_str)
    
    # Assertions
    assert saved_path.exists()
    assert saved_path.is_file()
    
    # Expected format: YYYYMMDD_{Amount}_{NormalizedCorp}_{ID}.pdf
    # "テスト株式会社（合同会社ぼっち）" -> normalized to "テスト（ぼっち）" roughly,
    # non-alphanumeric stripped, leading to "テストぼっち"
    expected_name = "20260719_12960_テストぼっち_99.pdf"
    assert saved_path.name == expected_name
    
    with open(saved_path, "rb") as f:
        assert f.read() == dummy_bytes
