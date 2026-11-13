# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

"""Modular section renderers for corporation, fiscal year, opening balance, and system settings."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from app.core_foundation import (
    call_fiscal_year,
    call_journal,
    call_master,
    settings,
)
from app.domain_contracts import (
    Account,
    Corporation,
    FiscalYear,
    SystemSettings,
    compute_next_fiscal_year_dates,
    resolve_open_fiscal_year,
)
from app.ui.master_catalog_sections import (
    _execute_commit_plan,
    _render_add_account_popover,
    _render_batch_delete_bar,
    _render_master_editor_section,
    render_abstracts_section,
    render_accounts_section,
    render_counterparties_section,
)
from app.ui.master_helpers import (
    build_fiscal_year_rows,
    partition_opening_balance_accounts,
)

__all__ = [
    "_execute_commit_plan",
    "_render_add_account_popover",
    "_render_batch_delete_bar",
    "_render_master_editor_section",
    "render_abstracts_section",
    "render_accounts_section",
    "render_corp_section",
    "render_counterparties_section",
    "render_fiscal_year_section",
    "render_opening_balance_section",
    "render_system_section",
]


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
        corp_invoice = st.text_input(
            "適格請求書発行事業者登録番号 (T+13桁・任意)",
            value=corp.invoice_number if corp and corp.invoice_number else "",
            placeholder="例: T1234567890123",
        )

        with st.container(horizontal=True, horizontal_alignment="right"):
            corp_submitted = st.form_submit_button(
                "保存", type="primary", width="content"
            )
        if corp_submitted:
            if not corp_name.strip():
                st.error("法人名・屋号を入力してください。")
            else:
                try:
                    updated_corp = Corporation(
                        id=corp.id if corp else None,
                        name=corp_name.strip(),
                        address=corp_addr.strip() if corp_addr else None,
                        representative_title=corp_rep_title.strip() or None,
                        representative_name=corp_rep_name.strip() or None,
                        invoice_number=corp_invoice.strip() or None,
                    )
                    call_master(lambda s: s.save_corporation(updated_corp))
                    st.toast("自社情報を保存しました", icon=":material/check_circle:")
                    st.rerun()
                except Exception as err:
                    st.error(f"自社情報の保存エラー: {err}")


def _render_initial_fy_form() -> None:
    """Render initial first-period fiscal year setup form."""
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
        if not fy_submitted:
            return
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
            st.toast("第1期会計年度を作成しました", icon=":material/check_circle:")
            st.rerun()


def _render_fy_rollover_expander(open_fy: FiscalYear) -> None:
    """Render period-end closing and rollover confirmation expander."""
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
            if not close_submitted:
                return
            if not next_fy_name.strip():
                st.error("次期年度名称を入力してください。")
                return
            try:
                curr_fy_id = open_fy.id or 0
                call_fiscal_year(
                    lambda s: s.close_fiscal_year(curr_fy_id, next_fy_name.strip())
                )
                st.toast(
                    "年度締め処理が完了し、次期へ繰り越されました",
                    icon=":material/check_circle:",
                )
                st.rerun()
            except Exception as e:
                st.error(f"年度締めエラー: {e}")


def render_fiscal_year_section(fys: list[FiscalYear]) -> None:
    """Render fiscal period setup, overview grid, and period-end closing rollover."""
    if not fys:
        _render_initial_fy_form()
        return

    st.subheader("会計年度一覧")
    open_fy = resolve_open_fiscal_year(fys)
    if open_fy:
        st.caption(
            f"現在のアクティブ期: **{open_fy.name}** "
            f"(第{open_fy.period_number}期: {open_fy.start_date} 〜 {open_fy.end_date})"
        )

    fy_rows = build_fiscal_year_rows(fys)
    st.dataframe(pd.DataFrame(fy_rows), hide_index=True, width="stretch")

    if not open_fy:
        st.warning("進行中 (OPEN) の会計年度がありません。")
        return

    st.divider()
    _render_fy_rollover_expander(open_fy)


def render_opening_balance_section(
    fys: list[FiscalYear], all_accounts: list[Account]
) -> None:
    """Render opening balance registration form for active open fiscal year."""
    st.subheader("期首残高設定 (開始貸借対照表)")
    open_fy = resolve_open_fiscal_year(fys)
    if not open_fy:
        st.warning("進行中 (OPEN) の会計年度がありません。")
        return

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

    debit_accs, credit_accs = partition_opening_balance_accounts(all_accounts)

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
                    disabled=has_opening_entry,
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
                    disabled=has_opening_entry,
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
