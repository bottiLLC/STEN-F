# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Gemini AI OCR and vendor matching package facade."""

from __future__ import annotations

from app.ai_ocr_service.client import GeminiOCRService
from app.ai_ocr_service.matching import (
    calculate_match_score,
    clean_json_codeblock,
    map_extraction_to_receipt_data,
    match_counterparty_master,
    normalize_merchant_name,
    normalize_receipt_file_format,
    optimize_receipt_image,
    validate_receipt_structure,
)

__all__ = [
    "GeminiOCRService",
    "calculate_match_score",
    "clean_json_codeblock",
    "map_extraction_to_receipt_data",
    "match_counterparty_master",
    "normalize_merchant_name",
    "normalize_receipt_file_format",
    "optimize_receipt_image",
    "validate_receipt_structure",
]
