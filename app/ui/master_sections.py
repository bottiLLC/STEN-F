# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Modular section renderers for master data and system settings workspace."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

import pandas as pd
import streamlit as st

from app.application_services import MasterService
from app.core_foundation import (
    DI,
    call_fiscal_year,
    call_journal,
    call_master,
    run_async,
    settings,
)
from app.domain_contracts import (
    Account,
    AccountType,
    Corporation,
    FiscalYear,
    SystemSettings,
    compute_next_fiscal_year_dates,
)
from app.ui.design_system import destructive_button_container
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

    if not do_delete:
        return

    async def execute_delete() -> str | None:
        async with DI.get_master_service() as ms:
            return await delete_handler(ms, selected_ids)

    err_msg = run_async(execute_delete())
    if err_msg:
        st.error(err_msg)
        return

    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
    st.toast(
        f"{len(selected_ids)} 件の{entity_label}を正常に削除しました",
        icon=":material/delete:",
    )
    st.rerun()


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


def render_corp_section() -> None:
    """Render tenant corporation profile form."""
    st.subheader("自社・事業者情報設定")
    corp = call_master(lambda s: s.get_corporation())

    with st.form("corp_form", border=True):
        corp_name = st.text_input("法人名 / 屋号", value=corp.name if corp else "")
        corp_addr = st.text_input(
            "本店所在地 / 住所", value=corp.address if corp and corp.address else ""
        )
        c1, c2 = st.columns(2)
        corp_rep_title = c1.text_input(
            "代表者役職",
            value=corp.representative_title
            if corp and corp.representative_title
            else "代表社員",
        )
        corp_rep_name = c2.text_input(
            "代表者氏名",
            value=corp.representative_name if corp and corp.representative_name else "",
        )

        with st.container(horizontal=True, horizontal_alignment="right"):
            corp_submitted = st.form_submit_button(
                "保存", type="primary", width="content"
            )
        if corp_submitted:
            if not corp_name.strip():
                st.error("法人名・屋号を入力してください。")
            else:
                updated_corp = Corporation(
                    id=corp.id if corp else None,
                    name=corp_name.strip(),
                    address=corp_addr.strip() if corp_addr else None,
                    representative_title=corp_rep_title.strip() or None,
                    representative_name=corp_rep_name.strip() or None,
                )
                call_master(lambda s: s.save_corporation(updated_corp))
                st.toast("自社情報を保存しました", icon=":material/check_circle:")
                st.rerun()


def render_fiscal_year_section(fys: list[FiscalYear]) -> None:
    """Render fiscal period setup, overview grid, and period-end closing rollover."""
    if not fys:
        st.subheader("第1期 初期セットアップ")
        st.info("会計年度が未登録です。第1期の初期セットアップを行ってください。")
        with st.form("initial_fy_setup_form", border=True):
            c_p, c_n = st.columns([1, 2])
            new_period = c_p.number_input("期数", min_value=1, value=1)
            new_name = c_n.text_input(
                "年度名称",
                value=f"FY{date.today().year}",
                help="西暦ベースの年度名称（例: FY2026）",
            )
            c_d1, c_d2 = st.columns(2)
            new_start = c_d1.date_input("期首日", value=date(date.today().year, 1, 1))
            new_end = c_d2.date_input("期末日", value=date(date.today().year, 12, 31))

            with st.container(horizontal=True, horizontal_alignment="right"):
                fy_submitted = st.form_submit_button(
                    "第1期を作成", type="primary", width="content"
                )
            if fy_submitted:
                if new_start >= new_end:
                    st.error("期末日は期首日より後の日付を指定してください。")
                elif not new_name.strip():
                    st.error("年度名称を入力してください。")
                else:
                    new_fy = FiscalYear(
                        name=new_name.strip(),
                        period_number=int(new_period),
                        start_date=new_start,
                        end_date=new_end,
                        status="OPEN",
                    )
                    call_master(lambda s: s.save_fiscal_year(new_fy))
                    st.toast(
                        "第1期会計年度を作成しました", icon=":material/check_circle:"
                    )
                    st.rerun()
        return

    st.subheader("会計年度一覧")
    open_fy = next((f for f in fys if f.status == "OPEN"), None)
    if open_fy:
        st.caption(
            f"現在のアクティブ期: **{open_fy.name}** "
            f"(第{open_fy.period_number}期: {open_fy.start_date} 〜 {open_fy.end_date})"
        )

    fy_rows = [
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
    st.dataframe(pd.DataFrame(fy_rows), hide_index=True, width="stretch")

    if not open_fy:
        st.warning("進行中 (OPEN) の会計年度がありません。")
        return

    st.divider()
    with st.expander("年度締め・次期繰越処理", expanded=False):
        next_period = (open_fy.period_number or 0) + 1
        next_start, next_end = compute_next_fiscal_year_dates(open_fy.end_date)
        default_next_name = f"FY{next_start.year}"

        st.warning(
            f"締め処理を実行すると、現行期（`{open_fy.name}`）の仕訳データはロックされ、"
            "直接の変更・削除はできなくなります。"
        )

        c_cur, c_next = st.columns(2)
        with c_cur:
            st.markdown("**クローズ対象 (現行期)**")
            st.text(f"年度名称: {open_fy.name}")
            st.text(f"期数: 第{open_fy.period_number}期")
            st.text(f"期間: {open_fy.start_date} 〜 {open_fy.end_date}")

        with c_next:
            st.markdown("**次期パラメーター (自動算出)**")
            st.text(f"期数: 第{next_period}期")
            st.text(f"期間: {next_start} 〜 {next_end}")

        with st.form("fy_rollover_form", border=True):
            next_fy_name = st.text_input(
                "次期年度名称",
                value=default_next_name,
                help="西暦ベースの年度名称（例: FY2026）",
            )
            with st.container(horizontal=True, horizontal_alignment="right"):
                close_submitted = st.form_submit_button(
                    "次期繰越",
                    type="primary",
                    width="content",
                )
            if close_submitted:
                if not next_fy_name.strip():
                    st.error("次期年度名称を入力してください。")
                else:
                    try:
                        curr_fy_id = open_fy.id or 0
                        call_fiscal_year(
                            lambda s: s.close_fiscal_year(
                                curr_fy_id, next_fy_name.strip()
                            )
                        )
                        st.toast(
                            "年度締め処理が完了し、次期へ繰り越されました",
                            icon=":material/check_circle:",
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"年度締めエラー: {e}")


def render_opening_balance_section(
    fys: list[FiscalYear], all_accounts: list[Account]
) -> None:
    """Render opening balance registration form for active open fiscal year."""
    st.subheader("期首残高設定 (開始貸借対照表)")
    open_fy = next((x for x in fys if x.status == "OPEN"), None)
    if not open_fy:
        st.warning("進行中 (OPEN) の会計年度がありません。")
        return

    debit_accs = [
        a
        for a in all_accounts
        if a.type
        in (
            AccountType.CURRENT_ASSET,
            AccountType.FIXED_ASSET,
            AccountType.DEFERRED_ASSET,
        )
    ]
    credit_accs = [
        a
        for a in all_accounts
        if a.type
        in (
            AccountType.CURRENT_LIABILITY,
            AccountType.FIXED_LIABILITY,
            AccountType.EQUITY,
        )
    ]

    with st.form("opening_balance_form", border=True):
        c_l, c_r = st.columns(2)
        op_d: dict[str, str] = {}
        op_c: dict[str, str] = {}
        with c_l:
            st.markdown("### 【 借方 : 資産の部 】")
            for a in debit_accs:
                v = st.number_input(
                    f"{a.code}: {a.name}",
                    min_value=0,
                    value=0,
                    step=10000,
                    key=f"op_acc_{a.id}",
                )
                if a.id:
                    op_d[str(a.id)] = str(v)
        with c_r:
            st.markdown("### 【 貸方 : 負債・純資産の部 】")
            for a in credit_accs:
                v = st.number_input(
                    f"{a.code}: {a.name}",
                    min_value=0,
                    value=0,
                    step=10000,
                    key=f"op_acc_{a.id}",
                )
                if a.id:
                    op_c[str(a.id)] = str(v)

        total_d = sum(int(v) for v in op_d.values())
        total_c = sum(int(v) for v in op_c.values())
        diff = total_d - total_c
        st.divider()
        with st.grid(3):
            st.metric("資産合計 (借方)", f"¥{total_d:,}")
            st.metric("負債・純資産合計 (貸方)", f"¥{total_c:,}")
            st.metric(
                "貸借バランス(差額)",
                "一致" if diff == 0 and total_d > 0 else f"¥{diff:,}",
            )

        fy_start = open_fy.start_date
        existing_open = call_journal(
            lambda s: s.get_entries(start_date=fy_start, end_date=fy_start)
        )
        has_opening_entry = any(
            tx.description in ("期首残高", "前期繰越") for tx in existing_open
        )
        if has_opening_entry:
            st.info(
                "当該会計年度の期首残高または前期繰越は既に登録済みです（不変原則に基づきロック中）。"
                "訂正が必要な場合は、振替仕訳画面より赤伝（反対仕訳）を起票してください。"
            )

        with st.container(horizontal=True, horizontal_alignment="right"):
            op_submitted = st.form_submit_button(
                "登録",
                type="primary",
                width="content",
                disabled=has_opening_entry,
            )
        if op_submitted:
            if diff != 0 or total_d == 0:
                st.error("貸借合計を一致させ、0より大きい金額を入力してください。")
            else:
                try:
                    call_journal(
                        lambda s: s.register_opening_balance(fy_start, op_d, op_c)
                    )
                    st.toast("期首残高を登録しました", icon=":material/check_circle:")
                    st.rerun()
                except ValueError as err:
                    st.error(f"登録エラー: {err}")


def render_accounts_section(accounts: list[Account]) -> None:
    """Render chart of accounts master editor, creation popover, and batch delete."""
    col_acc_head, col_acc_add = st.columns([4, 1])
    with col_acc_head:
        st.subheader("勘定科目マスタ一括管理")
        st.caption("勘定科目の登録、編集、および一括削除を管理します。")
    with col_acc_add:
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

                if add_submitted:
                    clean_code = new_code_in.strip()
                    clean_name = new_name_in.strip()
                    clean_desc = new_desc_in.strip() or None
                    if not clean_code:
                        st.error("科目コードを入力してください。")
                    elif not clean_name:
                        st.error("科目名を入力してください。")
                    else:
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


def render_system_section() -> None:
    """Render AI API key and system configuration form."""
    st.subheader("AI（Google Gemini）＆ システム設定")
    sys_conf = call_master(lambda s: s.get_system_settings())
    with st.form("sys_form", border=True):
        api_key_input = st.text_input(
            "Gemini API キー",
            value=sys_conf.ai_api_key or settings.GEMINI_API_KEY or "",
            type="password",
            help="Google AI Studio で発行された API キー",
        )
        with st.container(horizontal=True, horizontal_alignment="right"):
            sys_submitted = st.form_submit_button(
                "保存", type="primary", width="content"
            )
        if sys_submitted:
            call_master(
                lambda s: s.save_system_settings(
                    SystemSettings(
                        id=sys_conf.id,
                        ai_api_key=api_key_input.strip() or None,
                        backup_path=sys_conf.backup_path,
                    )
                )
            )
            st.toast("システム設定を保存しました", icon=":material/check_circle:")
            st.rerun()
