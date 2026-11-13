# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Pure transformation and commit-planning helpers for master management UI views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import pandas as pd
from pydantic import ValidationError

from app.domain_contracts import (
    Abstract,
    Account,
    AccountType,
    Counterparty,
    FiscalYear,
    account_code_sort_key,
)
from app.ui.editor import clean_editor_text, format_counterparty_validation_error


@dataclass(frozen=True)
class CommitPlan[T]:
    """Validated persistence operations and error messages derived from editor deltas."""

    to_save: list[T]
    to_delete: list[int]
    errors: list[str]


def build_account_df(accounts: list[Account]) -> pd.DataFrame:
    """Construct sorted account master DataFrame preserving expected UI column schema."""
    return pd.DataFrame(
        [
            {
                "selected": False,
                "id": a.id,
                "code": a.code,
                "name": a.name,
                "type": a.type.label,
                "description": a.description or "",
            }
            for a in sorted(accounts, key=lambda x: account_code_sort_key(x.code))
        ],
        columns=["selected", "id", "code", "name", "type", "description"],
    )


def build_counterparty_df(
    counterparties: list[Counterparty],
    acc_id_to_label: dict[int | None, str],
) -> pd.DataFrame:
    """Construct counterparty master DataFrame preserving expected UI column schema."""
    return pd.DataFrame(
        [
            {
                "selected": False,
                "id": c.id,
                "name": c.name,
                "name_kana": c.name_kana or "",
                "trade_name": c.trade_name or "",
                "invoice_number": c.invoice_number or "",
                "debit_account": acc_id_to_label.get(c.debit_account_id, ""),
                "credit_account": acc_id_to_label.get(c.credit_account_id, ""),
                "description_template": c.description_template or "",
            }
            for c in counterparties
        ],
        columns=[
            "selected",
            "id",
            "name",
            "name_kana",
            "trade_name",
            "invoice_number",
            "debit_account",
            "credit_account",
            "description_template",
        ],
    )


def build_abstract_df(
    abstracts: list[Abstract],
    acc_id_to_label: dict[int | None, str],
) -> pd.DataFrame:
    """Construct frequent abstract master DataFrame preserving expected UI column schema."""
    return pd.DataFrame(
        [
            {
                "selected": False,
                "id": a.id,
                "text": a.text,
                "account": acc_id_to_label.get(a.account_id, ""),
            }
            for a in abstracts
        ],
        columns=["selected", "id", "text", "account"],
    )


def build_account_commit_plan(
    added: list[dict[str, Any]],
    edited: dict[Any, dict[str, Any]],
    deleted: list[Any],
    existing_accounts: list[Account],
) -> CommitPlan[Account]:
    """Validate and compile Account add/edit/delete operations from editor deltas."""
    to_save: list[Account] = []
    errors: list[str] = []

    for idx, row in enumerate(added):
        clean_code = clean_editor_text(row.get("code")) or ""
        clean_name = clean_editor_text(row.get("name")) or ""
        raw_type = row.get("type")
        if (
            not clean_code
            or not clean_name
            or raw_type is None
            or bool(pd.isna(raw_type))
            or not raw_type
        ):
            errors.append(
                f"追加行 {idx + 1}: 科目コード・科目名・勘定区分をすべて入力してください。"
            )
            continue
        try:
            acc_type = AccountType.from_any(raw_type)
        except ValueError as err:
            errors.append(f"勘定科目「{clean_name}」の勘定区分が不正です: {err}")
            continue
        to_save.append(
            Account(
                code=clean_code,
                name=clean_name,
                type=acc_type,
                description=clean_editor_text(row.get("description")),
            )
        )

    account_by_id = {a.id: a for a in existing_accounts if a.id is not None}
    for pk, chg in edited.items():
        cur = account_by_id.get(pk)
        if not cur:
            continue
        raw_type = chg.get("type", cur.type)
        try:
            acc_type = AccountType.from_any(raw_type)
        except ValueError as err:
            errors.append(f"勘定科目「{cur.name}」の勘定区分が不正です: {err}")
            continue
        clean_code = clean_editor_text(chg.get("code", cur.code)) or ""
        clean_name = clean_editor_text(chg.get("name", cur.name)) or ""
        clean_desc = clean_editor_text(chg.get("description", cur.description))
        try:
            to_save.append(
                Account(
                    id=pk,
                    code=clean_code,
                    name=clean_name,
                    type=acc_type,
                    description=clean_desc,
                )
            )
        except (ValidationError, ValueError) as err:
            errors.append(f"勘定科目「{cur.name}」の更新内容が不正です: {err}")

    return CommitPlan(
        to_save=to_save,
        to_delete=[int(pk) for pk in deleted],
        errors=errors,
    )


def build_counterparty_commit_plan(
    added: list[dict[str, Any]],
    edited: dict[Any, dict[str, Any]],
    deleted: list[Any],
    existing_cps: list[Counterparty],
    acc_label_to_id: dict[str, int | None],
    acc_id_to_label: dict[int | None, str],
) -> CommitPlan[Counterparty]:
    """Validate and compile Counterparty deltas while preserving tel and tax_rate metadata."""
    to_save: list[Counterparty] = []
    errors: list[str] = []

    for row in added:
        cp_name = clean_editor_text(row.get("name"))
        if not cp_name:
            continue
        deb_label = clean_editor_text(row.get("debit_account"))
        cred_label = clean_editor_text(row.get("credit_account"))
        raw_inv = clean_editor_text(row.get("invoice_number"))
        try:
            to_save.append(
                Counterparty(
                    name=cp_name,
                    name_kana=clean_editor_text(row.get("name_kana")),
                    trade_name=clean_editor_text(row.get("trade_name")),
                    invoice_number=raw_inv,
                    debit_account_id=acc_label_to_id.get(deb_label)
                    if deb_label
                    else None,
                    credit_account_id=acc_label_to_id.get(cred_label)
                    if cred_label
                    else None,
                    description_template=clean_editor_text(
                        row.get("description_template")
                    ),
                )
            )
        except (ValidationError, ValueError) as err:
            errors.append(format_counterparty_validation_error(err, cp_name, raw_inv))

    cp_by_id = {c.id: c for c in existing_cps if c.id is not None}
    for pk, chg in edited.items():
        cur = cp_by_id.get(pk)
        if not cur:
            continue
        deb_label = clean_editor_text(
            chg.get("debit_account", acc_id_to_label.get(cur.debit_account_id, ""))
        )
        cred_label = clean_editor_text(
            chg.get("credit_account", acc_id_to_label.get(cur.credit_account_id, ""))
        )
        raw_inv = clean_editor_text(chg.get("invoice_number", cur.invoice_number))
        cp_name = clean_editor_text(chg.get("name", cur.name)) or cur.name
        try:
            to_save.append(
                Counterparty(
                    id=pk,
                    name=cp_name,
                    name_kana=clean_editor_text(chg.get("name_kana", cur.name_kana)),
                    trade_name=clean_editor_text(chg.get("trade_name", cur.trade_name)),
                    invoice_number=raw_inv,
                    tel=cur.tel,
                    tax_rate=cur.tax_rate,
                    debit_account_id=acc_label_to_id.get(deb_label)
                    if deb_label
                    else None,
                    credit_account_id=acc_label_to_id.get(cred_label)
                    if cred_label
                    else None,
                    description_template=clean_editor_text(
                        chg.get("description_template", cur.description_template)
                    ),
                )
            )
        except (ValidationError, ValueError) as err:
            errors.append(format_counterparty_validation_error(err, cp_name, raw_inv))

    return CommitPlan(
        to_save=to_save,
        to_delete=[int(pk) for pk in deleted],
        errors=errors,
    )


def build_abstract_commit_plan(
    added: list[dict[str, Any]],
    edited: dict[Any, dict[str, Any]],
    deleted: list[Any],
    existing_abs: list[Abstract],
    acc_label_to_id: dict[str, int | None],
) -> CommitPlan[Abstract]:
    """Validate and compile Abstract add/edit/delete operations from editor deltas."""
    to_save: list[Abstract] = []
    errors: list[str] = []

    for row in added:
        raw_text = clean_editor_text(row.get("text"))
        acc_label = clean_editor_text(row.get("account"))
        acc_id = acc_label_to_id.get(acc_label) if acc_label else None
        if raw_text and acc_id:
            to_save.append(Abstract(text=raw_text, account_id=acc_id))

    abs_by_id = {a.id: a for a in existing_abs if a.id is not None}
    for pk, chg in edited.items():
        cur = abs_by_id.get(pk)
        if not cur:
            continue
        new_text = clean_editor_text(chg.get("text", cur.text))
        acc_label = clean_editor_text(chg.get("account"))
        acc_id = acc_label_to_id.get(acc_label) if acc_label else cur.account_id
        if new_text and acc_id:
            to_save.append(Abstract(id=pk, text=new_text, account_id=acc_id))

    return CommitPlan(
        to_save=to_save,
        to_delete=[int(pk) for pk in deleted],
        errors=errors,
    )


def extract_selected_pk_ids(df: pd.DataFrame) -> list[int]:
    """Extract non-null integer primary keys for rows marked as selected."""
    if df.empty or "selected" not in df.columns or "id" not in df.columns:
        return []
    selected_df = df[df["selected"].astype(bool)]
    ids: list[int] = []
    for _, row in selected_df.iterrows():
        raw_id = row.get("id")
        if raw_id is not None and not bool(pd.isna(raw_id)):
            ids.append(int(raw_id))
    return ids


def partition_opening_balance_accounts(
    all_accounts: list[Account],
) -> tuple[list[Account], list[Account]]:
    """Split accounts into balance-sheet debit (asset) and credit (liability/equity) lists."""
    debit_types = {
        AccountType.CURRENT_ASSET,
        AccountType.FIXED_ASSET,
        AccountType.DEFERRED_ASSET,
    }
    credit_types = {
        AccountType.CURRENT_LIABILITY,
        AccountType.FIXED_LIABILITY,
        AccountType.EQUITY,
    }
    debit_accs = [a for a in all_accounts if a.type in debit_types]
    credit_accs = [a for a in all_accounts if a.type in credit_types]
    return debit_accs, credit_accs


def build_fiscal_year_rows(fys: list[FiscalYear]) -> list[dict[str, object]]:
    """Build sorted table rows for fiscal year overview DataFrame."""
    return [
        {
            "ID": f.id,
            "年度名称": f.name,
            "期数": f"第{f.period_number}期" if f.period_number else "-",
            "開始日": str(f.start_date),
            "終了日": str(f.end_date),
            "状態": "進行中 (OPEN)" if f.status == "OPEN" else "締切済 (CLOSED)",
        }
        for f in sorted(fys, key=lambda x: x.start_date, reverse=True)
    ]
