import pytest
import io
from PIL import Image
from reportlab.pdfgen import canvas
from openai import APIError
from app.infrastructure.external.ocr_service import OpenAIOCRService


def get_dummy_image_bytes(width=100, height=100):
    img = Image.new("RGB", (width, height), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_dummy_pdf_bytes():
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 100, "Hello OCR PDF Test")
    c.showPage()
    c.save()
    return buf.getvalue()


@pytest.mark.asyncio
async def test_extract_receipt_data_image_success(mocker):
    # Mock master_service and DI
    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )
    mock_master_service.get_counterparty_by_keyword = mocker.AsyncMock(
        return_value=None
    )
    mock_master_service.get_accounts = mocker.AsyncMock(return_value=[])
    mock_master_service.get_counterparties = mocker.AsyncMock(
        return_value=[]
    )

    # Context manager return value mock
    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    # Mock chat completions
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = '{"merchant_name": "Mock Store", "transaction_date": "2026-07-19", "total_amount_incl_tax": 1500}'
    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        return_value=mock_response,
    )

    # Run
    service = OpenAIOCRService()
    img_bytes = get_dummy_image_bytes()
    res = await service.extract_receipt_data(img_bytes, "png")

    assert res is not None
    assert res.merchant_name == "Mock Store"
    assert res.total_amount_incl_tax == 1500
    assert res.transaction_date == "2026-07-19"


@pytest.mark.asyncio
async def test_extract_receipt_data_pdf_success(mocker):
    # Mock master_service and DI
    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )
    mock_master_service.get_counterparty_by_keyword = mocker.AsyncMock(
        return_value=None
    )
    mock_master_service.get_accounts = mocker.AsyncMock(return_value=[])
    mock_master_service.get_counterparties = mocker.AsyncMock(
        return_value=[]
    )

    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    # Mock chat completions
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = '{"merchant_name": "PDF Vendor", "transaction_date": "2026-07-19", "total_amount_incl_tax": 9800}'
    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        return_value=mock_response,
    )

    # Run
    service = OpenAIOCRService()
    pdf_bytes = get_dummy_pdf_bytes()
    res = await service.extract_receipt_data(pdf_bytes, "pdf")

    assert res is not None
    assert res.merchant_name == "PDF Vendor"
    assert res.total_amount_incl_tax == 9800
    assert res.transaction_date == "2026-07-19"


@pytest.mark.asyncio
async def test_extract_receipt_data_large_image_resize(mocker):
    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )
    mock_master_service.get_counterparty_by_keyword = mocker.AsyncMock(
        return_value=None
    )
    mock_master_service.get_accounts = mocker.AsyncMock(return_value=[])
    mock_master_service.get_counterparties = mocker.AsyncMock(
        return_value=[]
    )

    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    mock_choice = mocker.MagicMock()
    mock_choice.message.content = '{"merchant_name": "Large Img Vendor", "transaction_date": "2026-07-19", "total_amount_incl_tax": 3000}'
    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        return_value=mock_response,
    )

    # Generate 2200x2200 large image to trigger resize/compression branch
    large_img_bytes = get_dummy_image_bytes(2200, 2200)

    service = OpenAIOCRService()
    res = await service.extract_receipt_data(large_img_bytes, "jpg")

    assert res is not None
    assert res.merchant_name == "Large Img Vendor"


@pytest.mark.asyncio
async def test_extract_receipt_data_api_error(mocker):
    # Mock master_service and DI
    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )

    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    # Mock chat completions to throw APIError
    # APIError constructor parameters: message, request, body
    mock_request = mocker.MagicMock()
    err = APIError("API Rate Limit Exceeded", mock_request, body=None)

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        side_effect=err,
    )

    service = OpenAIOCRService()
    img_bytes = get_dummy_image_bytes()

    with pytest.raises(ValueError, match="OpenAI API エラーが発生しました"):
        await service.extract_receipt_data(img_bytes, "png")


@pytest.mark.asyncio
async def test_extract_receipt_data_invoice_match(mocker):
    """Ensure that the master data is used when matching by invoice_registration_number."""
    from app.domain.models.counterparty import Counterparty

    # Mock counterparty list in master
    mock_cp = Counterparty(
        id=10,
        name="Invoice Matched Vendor",
        invoice_number="T1234567890123",
        debit_account_id=101,
        credit_account_id=102,
        description_template="Description from Master",
    )

    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )
    mock_master_service.get_counterparties = mocker.AsyncMock(return_value=[mock_cp])
    mock_master_service.get_accounts = mocker.AsyncMock(return_value=[])

    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    # OCR returns matched invoice number but a different merchant name
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = (
        '{"merchant_name": "OCR Vendor", "transaction_date": "2026-07-19", '
        '"total_amount_incl_tax": 1500, "invoice_registration_number": "T1234567890123"}'
    )
    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        return_value=mock_response,
    )

    service = OpenAIOCRService()
    img_bytes = get_dummy_image_bytes()
    res = await service.extract_receipt_data(img_bytes, "png")

    assert res is not None
    # Merchant name should be mapped to Master's name (Invoice Matched Vendor)
    assert res.merchant_name == "Invoice Matched Vendor"
    assert res.invoice_registration_number == "T1234567890123"
    assert res.inferred_debit_account_id == "101"
    assert res.inferred_credit_account_id == "102"
    assert res.description == "Description from Master"
    assert res.is_registered_merchant is True
    assert res.is_dictionary_matched is True


@pytest.mark.asyncio
async def test_extract_receipt_data_katakana_normalization_and_name_match(
    mocker,
):
    """Ensure that half-width Katakana is normalized to full-width and fuzzy matched."""
    from app.domain.models.counterparty import Counterparty

    # Master has full-width Katakana name
    mock_cp = Counterparty(
        id=20,
        name="スーパーテスト",
        invoice_number="T9999999999999",
        debit_account_id=201,
        credit_account_id=202,
        description_template="Katakana Master",
    )

    mock_system_settings = mocker.MagicMock()
    mock_system_settings.ai_api_key = "test-api-key"

    mock_master_service = mocker.MagicMock()
    mock_master_service.get_system_settings = mocker.AsyncMock(
        return_value=mock_system_settings
    )
    mock_master_service.get_counterparties = mocker.AsyncMock(return_value=[mock_cp])
    mock_master_service.get_accounts = mocker.AsyncMock(return_value=[])

    class AsyncContextMock:
        async def __aenter__(self):
            return mock_master_service

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    from app.ui.di import DI

    mocker.patch.object(DI, "get_master_service", return_value=AsyncContextMock())

    # OCR returns half-width Katakana name
    mock_choice = mocker.MagicMock()
    mock_choice.message.content = (
        '{"merchant_name": "ｽｰﾊﾟｰﾃｽﾄ", "transaction_date": "2026-07-19", '
        '"total_amount_incl_tax": 1200}'
    )
    mock_response = mocker.MagicMock()
    mock_response.choices = [mock_choice]

    mocker.patch(
        "openai.resources.chat.completions.AsyncCompletions.create",
        new_callable=mocker.AsyncMock,
        return_value=mock_response,
    )

    service = OpenAIOCRService()
    img_bytes = get_dummy_image_bytes()
    res = await service.extract_receipt_data(img_bytes, "png")

    assert res is not None
    # Merchant name should be normalized to full-width and matched with Master (スーパーテスト)
    assert res.merchant_name == "スーパーテスト"
    assert res.invoice_registration_number == "T9999999999999"
    assert res.inferred_debit_account_id == "201"
    assert res.inferred_credit_account_id == "202"
    assert res.description == "Katakana Master"
    assert res.is_registered_merchant is True
    assert res.is_dictionary_matched is True
