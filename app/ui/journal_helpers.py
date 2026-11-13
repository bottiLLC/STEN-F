# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Pure transformation helpers for journal entry and general journal UI views."""

from __future__ import annotations

from datetime import date
import pandas as pd

from app.core_foundation import normalize_amount
from app.domain_contracts import ReceiptData, Transaction, TransactionLine


def is_red_slip_transaction(tx: Transaction) -> bool:
    """Return True when transaction is a reversing (red slip) journal entry."""
    return tx.reversed_transaction_id is not None or (
        bool(tx.description) and tx.description.startswith("[取消:")
    )


def identify_cancelled_transaction_ids(transactions: list[Transaction]) -> set[int]:
    """Identify original transaction IDs cancelled by reversing entries, including legacy rows."""
    cancelled_orig_ids: set[int] = {
        tx.reversed_transaction_id
        for tx in transactions
        if tx.reversed_transaction_id is not None
    }

    for tx in transactions:
        if (
            tx.reversed_transaction_id is None
            and tx.description
            and tx.description.startswith("[取消:")
        ):
            target_desc = (
                tx.description.split("]", 1)[-1].strip()
                if "]" in tx.description
                else ""
            )
            for cand in transactions:
                if (
                    cand.id is not None
                    and tx.id is not None
                    and cand.id < tx.id
                    and cand.id not in cancelled_orig_ids
                    and not is_red_slip_transaction(cand)
                    and (cand.description or "").strip() == target_desc
                ):
                    cancelled_orig_ids.add(cand.id)
                    break

    return cancelled_orig_ids


def filter_journal_entries(
    transactions: list[Transaction],
    start_date: date,
    end_date: date,
    exclude_cancelled: bool,
    evidence_only: bool,
) -> tuple[list[Transaction], set[int]]:
    """Filter transactions by date bounds, cancellation pair exclusion, and evidence presence."""
    cancelled_orig_ids = identify_cancelled_transaction_ids(transactions)
    entries = [
        tx
        for tx in transactions
        if tx.occurred_at is not None and start_date <= tx.occurred_at <= end_date
    ]
    if exclude_cancelled:
        entries = [
            tx
            for tx in entries
            if tx.id not in cancelled_orig_ids and not is_red_slip_transaction(tx)
        ]
    if evidence_only:
        entries = [tx for tx in entries if tx.evidence_path]
    return entries, cancelled_orig_ids


def build_journal_display_rows(
    entries: list[Transaction],
    account_id_to_label: dict[int | None, str],
) -> list[dict[str, object]]:
    """Flatten balanced journal transactions into display rows for history table and CSV export."""
    rows: list[dict[str, object]] = []
    for tx in entries:
        d_lines = [line for line in tx.lines if line.debit > 0]
        c_lines = [line for line in tx.lines if line.credit > 0]
        for i in range(max(len(d_lines), len(c_lines), 1)):
            d = d_lines[i] if i < len(d_lines) else None
            c = c_lines[i] if i < len(c_lines) else None
            rows.append(
                {
                    "選択": False,
                    "id": tx.id,
                    "発生日": str(tx.occurred_at),
                    "記録日時(UTC)": tx.recorded_at.strftime("%Y-%m-%d %H:%M:%S")
                    if tx.recorded_at
                    else "-",
                    "証憑": ("あり" if tx.evidence_path else "-") if i == 0 else "",
                    "借方科目": account_id_to_label.get(d.account_id, "") if d else "",
                    "借方金額": d.debit if d else 0,
                    "貸方科目": account_id_to_label.get(c.account_id, "") if c else "",
                    "貸方金額": c.credit if c else 0,
                    "摘要": tx.description or "",
                    "取引先": tx.counterparty or "",
                    "インボイス番号": tx.invoice_number or "",
                }
            )
    return rows


def build_detail_line_rows(
    tx: Transaction,
    account_id_to_label: dict[int | None, str],
) -> list[dict[str, object]]:
    """Build line-item table rows for a single selected transaction detail card."""
    d_lines = [line for line in tx.lines if line.debit > 0]
    c_lines = [line for line in tx.lines if line.credit > 0]
    detail_rows: list[dict[str, object]] = []
    for i in range(max(len(d_lines), len(c_lines), 1)):
        d = d_lines[i] if i < len(d_lines) else None
        c = c_lines[i] if i < len(c_lines) else None
        detail_rows.append(
            {
                "借方科目": account_id_to_label.get(d.account_id, "") if d else "",
                "借方金額 (¥)": d.debit if d else 0,
                "貸方科目": account_id_to_label.get(c.account_id, "") if c else "",
                "貸方金額 (¥)": c.credit if c else 0,
                "行摘要": tx.description or "",
            }
        )
    return detail_rows


def _resolve_account_label(
    raw_account_ref: str | None,
    account_id_to_label: dict[int | None, str],
    account_labels: list[str],
) -> str:
    """Resolve inferred OCR account ID or name fragment to UI selectbox label."""
    if not raw_account_ref:
        return ""
    val = str(raw_account_ref)
    if val.isdigit():
        return account_id_to_label.get(int(val), "")
    for lbl in account_labels:
        if val in lbl:
            return lbl
    return ""


def resolve_ocr_initial_accounts(
    ocr: ReceiptData | None,
    account_id_to_label: dict[int | None, str],
    account_labels: list[str],
) -> tuple[str, str, int]:
    """Derive initial debit label, credit label, and gross amount from OCR result."""
    if ocr is None:
        return "", "", 0
    d_init = _resolve_account_label(
        ocr.inferred_debit_account_id, account_id_to_label, account_labels
    )
    c_init = _resolve_account_label(
        ocr.inferred_credit_account_id, account_id_to_label, account_labels
    )
    init_amt = ocr.total_amount_incl_tax or 0
    return d_init, c_init, init_amt


def parse_voucher_editor_lines(
    edited_df: pd.DataFrame,
    account_code_to_id: dict[str, int | None],
) -> list[TransactionLine]:
    """Parse sanitized single-sided TransactionLine entries from voucher editor DataFrame."""
    tx_lines: list[TransactionLine] = []
    for _, row in edited_df.iterrows():
        d_val = row.get("debit_amount")
        c_val = row.get("credit_amount")
        d_amt = 0 if d_val is None or bool(pd.isna(d_val)) else normalize_amount(d_val)
        c_amt = 0 if c_val is None or bool(pd.isna(c_val)) else normalize_amount(c_val)

        if (d_acc := row.get("debit_account")) and d_amt > 0:
            if aid := account_code_to_id.get(str(d_acc)):
                tx_lines.append(TransactionLine(account_id=aid, debit=d_amt, credit=0))
        if (c_acc := row.get("credit_account")) and c_amt > 0:
            if aid := account_code_to_id.get(str(c_acc)):
                tx_lines.append(TransactionLine(account_id=aid, debit=0, credit=c_amt))
    return tx_lines
