# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Catalog master section renderers (accounts, counterparties, abstracts) and batch delete dialog."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pandas as pd
import streamlit as st

from app.application_services import MasterService
from app.core_foundation import DI, call_master, run_async
from app.domain_contracts import Account, AccountType
from app.ui.design_system import (
    destructive_button_container,
    destructive_confirm_container,
)
from app.ui.editor import render_accounting_editor
from app.ui.master_helpers import (
    CommitPlan,
    build_abstract_commit_plan,
    build_abstract_df,
    build_account_commit_plan,
    build_account_df,
    build_counterparty_commit_plan,
    build_counterparty_df,
    extract_selected_pk_ids,
)


def _execute_commit_plan[T](
    plan: CommitPlan[T],
    save_fn: Callable[[MasterService, T], Awaitable[Any]],
    delete_fn: Callable[[MasterService, int], Awaitable[Any]],
    entity_label: str,
) -> bool:
    """Persist validated CommitPlan items inside a scoped MasterService session."""
    if plan.errors:
        for err_msg in plan.errors:
            st.error(err_msg)
        return False

    async def do_commit() -> list[str]:
        runtime_errors: list[str] = []
        async with DI.get_master_service() as s:
            for item in plan.to_save:
                try:
                    await save_fn(s, item)
                except Exception as err:
                    runtime_errors.append(f"{entity_label}の保存に失敗しました: {err}")
            for pk in plan.to_delete:
                try:
                    await delete_fn(s, pk)
                except Exception as err:
                    runtime_errors.append(
                        f"{entity_label} (ID: {pk}) の削除に失敗しました: {err}"
                    )
        return runtime_errors

    runtime_errors = run_async(do_commit())
    if runtime_errors:
        for err_msg in runtime_errors:
            st.error(err_msg)
        return False
    return True


def _open_batch_delete_dialog(
    selected_ids: list[int],
    entity_label: str,
    version_key: str,
    button_key: str,
    delete_handler: Callable[[MasterService, list[int]], Awaitable[str | None]],
) -> None:
    """Open two-step confirmation modal for destructive batch deletion."""
    pending_key = f"{button_key}_pending_ids"

    def _clear_pending() -> None:
        st.session_state.pop(pending_key, None)

    @st.dialog(f"{entity_label}の削除確認", width="small", on_dismiss=_clear_pending)
    def _confirm_dialog() -> None:
        st.warning(
            f"選択中の **{len(selected_ids)} 件** の{entity_label}を削除します。この操作は元に戻せません。"
        )
        with st.container(horizontal=True, horizontal_alignment="right"):
            if st.button(
                "キャンセル",
                type="secondary",
                width="content",
                key=f"{button_key}_cancel",
            ):
                _clear_pending()
                st.rerun()
            with destructive_confirm_container(button_key):
                confirmed = st.button(
                    "削除確定",
                    type="secondary",
                    icon=":material/delete_forever:",
                    width="content",
                    key=f"{button_key}_confirm",
                )
        if not confirmed:
            return

        async def execute_delete() -> str | None:
            async with DI.get_master_service() as ms:
                return await delete_handler(ms, selected_ids)

        err_msg = run_async(execute_delete())
        if err_msg:
            st.error(err_msg)
            return

        _clear_pending()
        st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
        st.toast(
            f"{len(selected_ids)} 件の{entity_label}を正常に削除しました",
            icon=":material/delete:",
        )
        st.rerun()

    _confirm_dialog()


def _render_batch_delete_bar(
    edited_df: pd.DataFrame,
    entity_label: str,
    version_key: str,
    button_key: str,
    delete_handler: Callable[[MasterService, list[int]], Awaitable[str | None]],
) -> None:
    """Render unified warning bar and destructive batch-delete action for selected rows."""
    selected_ids = extract_selected_pk_ids(edited_df)
    if not selected_ids:
        return

    pending_key = f"{button_key}_pending_ids"
    col_del_info, col_del_btn = st.columns([4, 1])
    with col_del_info:
        st.warning(f"{len(selected_ids)} 件の{entity_label}が選択されています。")
    with col_del_btn:
        with st.container(horizontal=True, horizontal_alignment="right"):
            with destructive_button_container(button_key):
                do_delete = st.button(
                    "削除",
                    type="secondary",
                    icon=":material/delete:",
                    width="content",
                    key=button_key,
                )

    if do_delete:
        st.session_state[pending_key] = selected_ids

    pending_ids = st.session_state.get(pending_key)
    if pending_ids:
        _open_batch_delete_dialog(
            pending_ids, entity_label, version_key, button_key, delete_handler
        )


def _render_master_editor_section[T](
    df: pd.DataFrame,
    base_key: str,
    entity_label: str,
    column_config: dict[str, Any],
    column_order: list[str],
    plan_builder: Callable[
        [list[dict[str, Any]], dict[Any, dict[str, Any]], list[Any]], CommitPlan[T]
    ],
    save_fn: Callable[[MasterService, T], Awaitable[Any]],
    delete_fn: Callable[[MasterService, int], Awaitable[Any]],
    batch_delete_button_key: str,
    batch_delete_handler: Callable[[MasterService, list[int]], Awaitable[str | None]],
) -> None:
    """Render shared master editor grid, commit handler, and batch-delete action."""

    def on_commit(
        added: list[dict[str, Any]],
        edited: dict[Any, dict[str, Any]],
        deleted: list[Any],
    ) -> bool:
        plan = plan_builder(added, edited, deleted)
        return _execute_commit_plan(plan, save_fn, delete_fn, entity_label)

    edited_df = render_accounting_editor(
        df,
        pk_column="id",
        base_key=base_key,
        on_commit=on_commit,
        column_config=column_config,
        column_order=column_order,
        num_rows="add",
    )
    _render_batch_delete_bar(
        edited_df,
        entity_label,
        f"{base_key}_version",
        batch_delete_button_key,
        batch_delete_handler,
    )


def _render_add_account_popover() -> None:
    """Render popover form for registering a single new ledger account."""
    with st.popover("新規科目追加", icon=":material/add:"):
        st.markdown("**新規勘定科目の登録**")
        with st.form("form_create_account", border=False):
            c_code, c_type = st.columns([1, 2])
            new_code_in = c_code.text_input(
                "科目コード", placeholder="例: 1195", max_chars=10
            )
            new_type_label = c_type.selectbox(
                "勘定区分", options=[t.label for t in AccountType]
            )
            new_name_in = st.text_input("科目名", placeholder="例: 仮払金")
            new_desc_in = st.text_input(
                "説明・用途（任意）", placeholder="例: 出張等の仮渡金"
            )
            with st.container(horizontal=True, horizontal_alignment="right"):
                add_submitted = st.form_submit_button(
                    "登録", type="primary", width="content"
                )

            if not add_submitted:
                return
            clean_code = new_code_in.strip()
            clean_name = new_name_in.strip()
            clean_desc = new_desc_in.strip() or None
            if not clean_code:
                st.error("科目コードを入力してください。")
                return
            if not clean_name:
                st.error("科目名を入力してください。")
                return
            try:
                target_type = AccountType.from_any(new_type_label)
                call_master(
                    lambda s: s.save_account(
                        Account(
                            code=clean_code,
                            name=clean_name,
                            type=target_type,
                            description=clean_desc,
                        )
                    )
                )
                st.session_state["editor_accounts_version"] = (
                    st.session_state.get("editor_accounts_version", 0) + 1
                )
                st.toast(
                    f"勘定科目「{clean_name}」を登録しました",
                    icon=":material/check:",
                )
                st.rerun()
            except Exception as err:
                st.error(f"登録エラー: {err}")


def render_accounts_section(accounts: list[Account]) -> None:
    """Render chart of accounts master editor, creation popover, and batch delete."""
    col_acc_head, col_acc_add = st.columns([4, 1])
    with col_acc_head:
        st.subheader("勘定科目マスタ一括管理")
        st.caption("勘定科目の登録、編集、および一括削除を管理します。")
    with col_acc_add:
        with st.container(horizontal=True, horizontal_alignment="right"):
            _render_add_account_popover()

    acc_df = build_account_df(accounts)
    col_cfg_acc = {
        "selected": st.column_config.CheckboxColumn(
            "選択",
            help="削除対象の勘定科目を選択してください",
            default=False,
        ),
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "code": st.column_config.TextColumn("科目コード", required=True),
        "name": st.column_config.TextColumn("科目名", required=True),
        "type": st.column_config.SelectboxColumn(
            "勘定区分", options=[t.label for t in AccountType], required=True
        ),
        "description": st.column_config.TextColumn("説明・用途"),
    }
    acc_name_by_id = {a.id: a.name for a in accounts if a.id is not None}

    async def delete_accounts_if_unused(
        ms: MasterService, target_ids: list[int]
    ) -> str | None:
        blocked_names: list[str] = []
        valid_ids: list[int] = []
        for acc_id in target_ids:
            if (
                ms.ledger_repository
                and await ms.ledger_repository.has_transactions_for_account(acc_id)
            ):
                blocked_names.append(acc_name_by_id.get(acc_id, str(acc_id)))
            else:
                valid_ids.append(acc_id)
        if blocked_names:
            return (
                "以下の勘定科目は仕訳データで使用されているため削除できません:\n"
                + "、".join(blocked_names)
            )
        for target_id in valid_ids:
            await ms.delete_account(target_id)
        return None

    _render_master_editor_section(
        df=acc_df,
        base_key="editor_accounts",
        entity_label="勘定科目",
        column_config=col_cfg_acc,
        column_order=["selected", "code", "name", "type", "description"],
        plan_builder=lambda a, e, d: build_account_commit_plan(a, e, d, accounts),
        save_fn=lambda s, item: s.save_account(item),
        delete_fn=lambda s, pk: s.delete_account(pk),
        batch_delete_button_key="btn_delete_selected_accounts",
        batch_delete_handler=delete_accounts_if_unused,
    )


def render_counterparties_section(
    account_options: list[str],
    acc_id_to_label: dict[int | None, str],
    acc_label_to_id: dict[str, int | None],
) -> None:
    """Render counterparty master editor and batch delete controls."""
    st.subheader("取引先マスタ一括管理")
    st.caption(
        "インボイス番号は13桁の数字を入力すると「T」が自動付与されます（例: 1234567890123 → T1234567890123）。"
    )
    cps = call_master(lambda s: s.get_counterparties())
    cp_df = build_counterparty_df(cps, acc_id_to_label)
    cp_select_options = [""] + account_options
    col_cfg_cp = {
        "selected": st.column_config.CheckboxColumn(
            "選択",
            help="削除対象の取引先を選択してください",
            default=False,
        ),
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "name": st.column_config.TextColumn(
            "会社名", required=True, help="正式な法人名または個人事業主名"
        ),
        "name_kana": st.column_config.TextColumn(
            "フリガナ", help="五十音順ソート用の全角カナ"
        ),
        "trade_name": st.column_config.TextColumn(
            "屋号", help="店舗名・屋号・ブランド名（AI OCR照合にも利用されます）"
        ),
        "invoice_number": st.column_config.TextColumn(
            "インボイス番号",
            help="適格請求書発行事業者番号。数字13桁を入力すると「T」が自動付与されます",
        ),
        "debit_account": st.column_config.SelectboxColumn(
            "借方勘定科目",
            options=cp_select_options,
            help="AI OCR読取時に自動補完するデフォルト借方勘定科目",
        ),
        "credit_account": st.column_config.SelectboxColumn(
            "貸方勘定科目",
            options=cp_select_options,
            help="AI OCR読取時に自動補完するデフォルト貸方勘定科目",
        ),
        "description_template": st.column_config.TextColumn(
            "摘要", help="仕訳伝票に自動補完する取引内容・摘要"
        ),
    }

    async def delete_cps(ms: MasterService, target_ids: list[int]) -> str | None:
        for target_id in target_ids:
            await ms.delete_counterparty(target_id)
        return None

    _render_master_editor_section(
        df=cp_df,
        base_key="editor_counterparties",
        entity_label="取引先",
        column_config=col_cfg_cp,
        column_order=[
            "selected",
            "name",
            "name_kana",
            "trade_name",
            "invoice_number",
            "debit_account",
            "credit_account",
            "description_template",
        ],
        plan_builder=lambda a, e, d: build_counterparty_commit_plan(
            a, e, d, cps, acc_label_to_id, acc_id_to_label
        ),
        save_fn=lambda s, item: s.save_counterparty(item),
        delete_fn=lambda s, pk: s.delete_counterparty(pk),
        batch_delete_button_key="btn_delete_selected_counterparties",
        batch_delete_handler=delete_cps,
    )


def render_abstracts_section(
    account_options: list[str],
    acc_id_to_label: dict[int | None, str],
    acc_label_to_id: dict[str, int | None],
) -> None:
    """Render frequent transaction abstracts master editor and batch delete controls."""
    st.subheader("よく使う摘要マスタ一括管理")
    abs_list = call_master(lambda s: s.get_abstracts())
    abs_df = build_abstract_df(abs_list, acc_id_to_label)
    col_cfg_abs = {
        "selected": st.column_config.CheckboxColumn(
            "選択",
            help="削除対象の摘要を選択してください",
            default=False,
        ),
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "text": st.column_config.TextColumn(
            "摘要", required=True, help="頻出する取引内容・定型文"
        ),
        "account": st.column_config.SelectboxColumn(
            "勘定科目",
            options=account_options,
            required=True,
            help="当該摘要に標準で紐づける勘定科目",
        ),
    }

    async def delete_abstracts(ms: MasterService, target_ids: list[int]) -> str | None:
        for target_id in target_ids:
            await ms.delete_abstract(target_id)
        return None

    _render_master_editor_section(
        df=abs_df,
        base_key="editor_abstracts",
        entity_label="摘要",
        column_config=col_cfg_abs,
        column_order=["selected", "text", "account"],
        plan_builder=lambda a, e, d: build_abstract_commit_plan(
            a, e, d, abs_list, acc_label_to_id
        ),
        save_fn=lambda s, item: s.save_abstract(item),
        delete_fn=lambda s, pk: s.delete_abstract(pk),
        batch_delete_button_key="btn_delete_selected_abstracts",
        batch_delete_handler=delete_abstracts,
    )
