# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Unit tests for pure UI helpers, alphanumeric account sorting, and PDF alignment."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch
import pandas as pd
import pytest

from app.application_services import Container
from app.domain_contracts import (
    Abstract,
    Account,
    AccountType,
    Corporation,
    Counterparty,
    FinancialReport,
    FinancialSection,
    FiscalYear,
    ReceiptData,
    Transaction,
    TransactionLine,
    TrialBalanceRow,
    account_code_sort_key,
)
from app.external_services import PDFService
from app.ui.editor import clean_editor_text
from app.ui.journal_helpers import (
    build_detail_line_rows,
    build_journal_display_rows,
    filter_journal_entries,
    identify_cancelled_transaction_ids,
    is_red_slip_transaction,
    parse_voucher_editor_lines,
    resolve_ocr_initial_accounts,
)
from app.ui.master_helpers import (
    build_abstract_commit_plan,
    build_abstract_df,
    build_account_commit_plan,
    build_account_df,
    build_counterparty_commit_plan,
    build_counterparty_df,
    extract_selected_pk_ids,
)


def test_account_code_sort_key_orders_numeric_then_alphanumeric() -> None:
    """Verify alphanumeric account codes sort numerically first, then lexicographically."""
    codes = ["A10", "1000", "200", "B01", "1110", "A02"]
    assert sorted(codes, key=account_code_sort_key) == [
        "200",
        "1000",
        "1110",
        "A02",
        "A10",
        "B01",
    ]


@pytest.mark.parametrize(
    ("raw_val", "expected"),
    [
        (None, None),
        (float("nan"), None),
        ("", None),
        ("   ", None),
        ("  テスト  ", "テスト"),
    ],
)
def test_clean_editor_text_handles_nan_and_whitespace(
    raw_val: object, expected: str | None
) -> None:
    """Verify clean_editor_text converts None, NaN, and blank strings to None."""
    assert clean_editor_text(raw_val) == expected


def test_journal_helpers_filter_and_legacy_red_slip_pairing() -> None:
    """Verify cancellation detection handles both explicit FK and legacy description pairing."""
    tx_valid = Transaction(
        id=1,
        occurred_at=date(2026, 4, 5),
        description="通常売上",
        evidence_path="receipt.pdf",
        lines=[
            TransactionLine(account_id=1, debit=1000, credit=0),
            TransactionLine(account_id=2, debit=0, credit=1000),
        ],
    )
    tx_legacy_orig = Transaction(
        id=2,
        occurred_at=date(2026, 4, 6),
        description="誤謬仕訳",
        lines=[
            TransactionLine(account_id=1, debit=500, credit=0),
            TransactionLine(account_id=2, debit=0, credit=500),
        ],
    )
    tx_legacy_red = Transaction(
        id=3,
        occurred_at=date(2026, 4, 6),
        description="[取消: 誤り] 誤謬仕訳",
        lines=[
            TransactionLine(account_id=1, debit=0, credit=500),
            TransactionLine(account_id=2, debit=500, credit=0),
        ],
    )
    assert is_red_slip_transaction(tx_legacy_red) is True
    assert is_red_slip_transaction(tx_valid) is False

    cancelled_ids = identify_cancelled_transaction_ids(
        [tx_valid, tx_legacy_orig, tx_legacy_red]
    )
    assert cancelled_ids == {2}

    filtered, _ = filter_journal_entries(
        [tx_valid, tx_legacy_orig, tx_legacy_red],
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        exclude_cancelled=True,
        evidence_only=True,
    )
    assert [t.id for t in filtered] == [1]


def test_journal_helpers_row_builders_and_voucher_parsing() -> None:
    """Verify display row flattening, OCR account resolution, and voucher DataFrame parsing."""
    tx = Transaction(
        id=10,
        occurred_at=date(2026, 5, 1),
        description="複合仕訳",
        evidence_path="ev.png",
        lines=[
            TransactionLine(account_id=1, debit=600, credit=0),
            TransactionLine(account_id=2, debit=400, credit=0),
            TransactionLine(account_id=3, debit=0, credit=1000),
        ],
    )
    id_to_lbl: dict[int | None, str] = {
        1: "1110: 現金",
        2: "6170: 消耗品費",
        3: "2110: 買掛金",
    }
    lbl_to_id: dict[str, int | None] = {v: k for k, v in id_to_lbl.items()}

    display_rows = build_journal_display_rows([tx], id_to_lbl)
    assert len(display_rows) == 2
    assert display_rows[0]["証憑"] == "あり"
    assert display_rows[1]["証憑"] == ""
    assert display_rows[1]["借方金額"] == 400

    detail_rows = build_detail_line_rows(tx, id_to_lbl)
    assert len(detail_rows) == 2
    assert detail_rows[0]["貸方科目"] == "2110: 買掛金"

    ocr = ReceiptData(
        total_amount_incl_tax=2500,
        inferred_debit_account_id="2",
        inferred_credit_account_id="現金",
    )
    d_lbl, c_lbl, amt = resolve_ocr_initial_accounts(
        ocr, id_to_lbl, ["", *id_to_lbl.values()]
    )
    assert (d_lbl, c_lbl, amt) == ("6170: 消耗品費", "1110: 現金", 2500)

    edited_df = pd.DataFrame(
        [
            {
                "debit_account": "6170: 消耗品費",
                "debit_amount": "１，５００",
                "credit_account": "1110: 現金",
                "credit_amount": float("nan"),
            },
            {
                "debit_account": "",
                "debit_amount": 0,
                "credit_account": "1110: 現金",
                "credit_amount": 1500,
            },
        ]
    )
    lines = parse_voucher_editor_lines(edited_df, lbl_to_id)
    assert len(lines) == 2
    assert lines[0].debit == 1500
    assert lines[1].credit == 1500


def test_master_helpers_counterparty_preserves_tel_and_tax_rate() -> None:
    """Verify Counterparty edit planning preserves hidden tel and tax_rate attributes under Rule 6."""
    existing_cp = Counterparty(
        id=7,
        name="テスト商事",
        name_kana="テストショウジ",
        trade_name="テスト屋号",
        invoice_number="T1234567890123",
        tel="03-1111-2222",
        tax_rate=0.08,
        debit_account_id=10,
        credit_account_id=20,
        description_template="定例仕入",
    )
    id_to_lbl: dict[int | None, str] = {10: "6170: 消耗品費", 20: "1110: 現金"}
    lbl_to_id: dict[str, int | None] = {v: k for k, v in id_to_lbl.items()}

    cp_df = build_counterparty_df([existing_cp], id_to_lbl)
    assert list(cp_df.columns) == [
        "selected",
        "id",
        "name",
        "name_kana",
        "trade_name",
        "invoice_number",
        "debit_account",
        "credit_account",
        "description_template",
    ]

    plan = build_counterparty_commit_plan(
        added=[{"name": "新規取引先", "invoice_number": "999"}],
        edited={7: {"trade_name": "新屋号"}},
        deleted=[99],
        existing_cps=[existing_cp],
        acc_label_to_id=lbl_to_id,
        acc_id_to_label=id_to_lbl,
    )
    assert len(plan.errors) == 1
    assert len(plan.to_save) == 1
    updated = plan.to_save[0]
    assert updated.trade_name == "新屋号"
    assert updated.tel == "03-1111-2222"
    assert updated.tax_rate == 0.08
    assert plan.to_delete == [99]


def test_master_helpers_account_abstract_and_pk_extraction() -> None:
    """Verify Account/Abstract commit planners sanitize NaN and extract selected IDs safely."""
    acc = Account(id=1, code="1110", name="現金", type=AccountType.CURRENT_ASSET)
    acc_df = build_account_df([acc])
    assert acc_df.iloc[0]["code"] == "1110"

    acc_plan = build_account_commit_plan(
        added=[
            {
                "code": "9901",
                "name": "テスト科目",
                "type": "流動資産",
                "description": float("nan"),
            },
            {"code": "", "name": "欠損行", "type": float("nan")},
        ],
        edited={1: {"description": "更新メモ"}},
        deleted=[2],
        existing_accounts=[acc],
    )
    assert len(acc_plan.errors) == 1
    assert len(acc_plan.to_save) == 2
    assert acc_plan.to_save[0].description is None
    assert acc_plan.to_save[1].description == "更新メモ"
    assert acc_plan.to_delete == [2]

    abs_item = Abstract(id=5, account_id=1, text="旅費精算")
    abs_df = build_abstract_df([abs_item], {1: "1110: 現金"})
    assert abs_df.iloc[0]["account"] == "1110: 現金"
    abs_plan = build_abstract_commit_plan(
        added=[{"text": "会議費", "account": "1110: 現金"}],
        edited={5: {"text": "出張旅費"}},
        deleted=[6],
        existing_abs=[abs_item],
        acc_label_to_id={"1110: 現金": 1},
    )
    assert [a.text for a in abs_plan.to_save] == ["会議費", "出張旅費"]
    assert abs_plan.to_delete == [6]

    sel_df = pd.DataFrame(
        [
            {"selected": True, "id": 10},
            {"selected": True, "id": float("nan")},
            {"selected": False, "id": 20},
        ]
    )
    assert extract_selected_pk_ids(sel_df) == [10]


@pytest.mark.asyncio
async def test_trial_balance_uses_alphanumeric_account_code_sorting(
    container: Container,
) -> None:
    """Verify LedgerService.get_trial_balance sorts numeric codes before alphanumeric codes."""
    async with container.master_service_scope() as ms:
        fy = (await ms.get_fiscal_years())[0]
        await ms.save_account(
            Account(code="A01", name="特殊科目", type=AccountType.SGA)
        )
        await ms.save_account(
            Account(code="200", name="数値200", type=AccountType.CURRENT_ASSET)
        )

    async with container.ledger_service_scope() as ls:
        rows = await ls.get_trial_balance(fy.id or 0)
    codes = [r.account_code for r in rows]
    assert codes.index("200") < codes.index("1110") < codes.index("A01")


def test_pdf_service_liabilities_equity_total_baseline_aligned() -> None:
    """Verify PDFService renders 負債・純資産合計 label and amount on identical Y baseline."""
    fy = FiscalYear(
        id=1,
        name="FY2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status="OPEN",
        period_number=1,
    )
    rpt = FinancialReport(
        fiscal_year=fy,
        current_assets=FinancialSection(
            title="【流動資産】",
            rows=[
                TrialBalanceRow(
                    account_id=1,
                    account_code="1110",
                    account_name="現金",
                    account_type=AccountType.CURRENT_ASSET,
                    balance=1000,
                )
            ],
            total=1000,
        ),
        fixed_assets=FinancialSection(title="【固定資産】"),
        deferred_assets=FinancialSection(title="【繰延資産】"),
        current_liabilities=FinancialSection(title="【流動負債】"),
        fixed_liabilities=FinancialSection(title="【固定負債】"),
        equity=FinancialSection(
            title="【純資産の部】",
            rows=[
                TrialBalanceRow(
                    account_id=2,
                    account_code="3110",
                    account_name="資本金",
                    account_type=AccountType.EQUITY,
                    balance=1000,
                )
            ],
            total=1000,
        ),
        revenue=FinancialSection(title="【売上高】"),
        cost_of_sales=FinancialSection(title="【売上原価】"),
        sga=FinancialSection(title="【販売費及び一般管理費】"),
        non_op_income=FinancialSection(title="【営業外収益】"),
        non_op_expense=FinancialSection(title="【営業外費用】"),
        extra_income=FinancialSection(title="【特別利益】"),
        extra_loss=FinancialSection(title="【特別損失】"),
        total_assets=1000,
        total_liabilities=0,
        total_equity=1000,
        net_income=0,
    )

    drawn_labels: list[tuple[float, str]] = []
    drawn_amounts: list[tuple[float, str]] = []

    from reportlab.pdfgen.canvas import Canvas

    orig_draw_string = Canvas.drawString
    orig_draw_right_string = Canvas.drawRightString

    def spy_draw_string(self: Canvas, x: float, y: float, text: str) -> None:
        drawn_labels.append((y, text))
        orig_draw_string(self, x, y, text)

    def spy_draw_right_string(self: Canvas, x: float, y: float, text: str) -> None:
        drawn_amounts.append((y, text))
        orig_draw_right_string(self, x, y, text)

    with (
        patch.object(Canvas, "drawString", spy_draw_string),
        patch.object(Canvas, "drawRightString", spy_draw_right_string),
    ):
        pdf_bytes = PDFService.generate_annual_report(
            Corporation(name="テスト株式会社"), rpt, fy
        )

    assert pdf_bytes.startswith(b"%PDF")
    label_y = next(y for y, txt in drawn_labels if txt == "負債・純資産合計")
    amount_y = next(
        y for y, txt in drawn_amounts if txt == "1,000" and abs(y - label_y) < 1.0
    )
    assert label_y == pytest.approx(amount_y)
