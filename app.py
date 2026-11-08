# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import sys
from pathlib import Path
import asyncio
from typing import Final

# Prepend script root to sys.path for deterministic module resolution
_ROOT: Final[Path] = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from backup_manager import get_backup_dir, run_backup, set_backup_dir
from app.core_foundation import DI, log, run_async, run_scoped, settings
from app.domain_contracts import Corporation, FiscalYear, IMasterRepository
from app.storage_repository import seed_accounts
from app.ui.design_system import inject_global_design_system


# --- 1. Pure Transformation Helpers ---
def resolve_active_fiscal_year(fys: list[FiscalYear]) -> FiscalYear | None:
    """Find currently active open fiscal year period from list.

    Args:
        fys: List of FiscalYear instances.

    Returns:
        Active open FiscalYear instance or None.
    """
    return next((x for x in fys if x.status == "OPEN"), None)


async def load_sidebar_metadata(
    service: IMasterRepository,
) -> tuple[Corporation | None, list[FiscalYear]]:
    """Fetch corporate profile and fiscal periods asynchronously.

    Args:
        service: MasterRepository or MasterService instance.

    Returns:
        Tuple of optional Corporation profile and list of FiscalYears.
    """
    corp, fys = await asyncio.gather(
        service.get_corporation(), service.get_fiscal_years()
    )
    return corp, fys


# --- 2. Presentation Orchestrator ---
def _render_sidebar_backup() -> None:
    """Render standardized data backup and persistence configuration controls."""
    st.divider()
    st.subheader("データ保護・バックアップ")

    current_dir = str(get_backup_dir())
    new_dir = st.text_input("保存先フォルダ", value=current_dir)
    if new_dir != current_dir:
        if st.button(
            "パス更新",
            type="secondary",
            icon=":material/folder:",
            width="stretch",
        ):
            save_res = set_backup_dir(new_dir)
            if save_res["success"]:
                st.success(save_res["message"])
                st.rerun()
            else:
                st.error(save_res["message"])

    if st.button(
        "バックアップ",
        type="primary",
        icon=":material/backup:",
        width="stretch",
    ):
        with st.spinner("圧縮・整合性検証中..."):
            res = run_backup(app_name="app")
        if res["success"]:
            st.success(res["message"])
            st.caption(f"完了日時: {res['timestamp']}")
            st.caption(f"保存先: {res['destination']}")
        else:
            st.error(str(res["message"]))


def _render_system_diagnostic(log_path: Path) -> None:
    """Mount discrete Antigravity System Diagnostic harness inside sidebar popover.

    Args:
        log_path: Path to the centralized application log file.
    """
    st.session_state["_run_count"] = st.session_state.get("_run_count", 0) + 1
    run_count = st.session_state["_run_count"]

    with st.sidebar.popover("System Diagnostic", icon=":material/bug_report:"):
        st.markdown(f"**Execution Counter:** `{run_count}`")
        st.caption("Active Session State Snapshot:")
        state_snapshot = {
            k: (
                f"<{len(v)} bytes>"
                if isinstance(v, bytes)
                else str(v)[:100] + ("..." if len(str(v)) > 100 else "")
            )
            for k, v in st.session_state.items()
            if not k.startswith("_")
        }
        st.json(state_snapshot)

        # Log Tail Retrieval
        log_lines: list[str] = []
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8")
                log_lines = [line for line in content.splitlines() if line.strip()][
                    -30:
                ]
            except Exception as e:
                log_lines = [f"[Log Read Error: {e}]"]
        else:
            log_lines = ["[Log file does not exist yet]"]

        st.caption(f"Log Tail (Last {len(log_lines)} lines):")
        st.text("\n".join(log_lines))

        # Antigravity IDE markdown block for one-click triage copy-paste
        triage_payload = (
            "### Antigravity System Diagnostic Context\n"
            f"- **Execution Count:** `{run_count}`\n"
            f"- **Session Keys:** `{list(st.session_state.keys())}`\n"
            "\n#### Recent Execution Logs (Tail 30)\n"
            "```log\n" + "\n".join(log_lines) + "\n```\n"
        )
        st.caption("Antigravity Prompt Context (Click to copy):")
        st.code(triage_payload, language="markdown")


def render_sidebar(corp_info: Corporation | None, open_fy: FiscalYear | None) -> None:
    """Render Streamlit sidebar navigation and tenant identity headers.

    Args:
        corp_info: Optional Corporation profile.
        open_fy: Optional active open FiscalYear.
    """
    with st.sidebar:
        st.title("STEN-F 会計")
        st.caption("Simple Tough Effective Next-generation Finance")
        st.divider()
        if corp_info and corp_info.name:
            st.markdown(f"**{corp_info.name}**")
            if corp_info.representative_name:
                st.caption(
                    f"代表者: {corp_info.representative_title or ''} {corp_info.representative_name}"
                )
        else:
            st.caption("※ 自社情報未設定 (マスタ管理で登録)")

        st.divider()
        if open_fy:
            st.info(
                f"**進行中の会計年度**\n\n**{open_fy.name}**\n\n`{open_fy.start_date}` 〜 `{open_fy.end_date}`"
            )
        else:
            st.warning("進行中の会計年度がありません。")

        _render_sidebar_backup()
        st.divider()
        _render_system_diagnostic(settings.LOGS_DIR / "app.log")

        st.divider()
        st.caption("© 2026 合同会社ぼっち (GPL-3.0)")


def main() -> None:
    """Streamlit application root coordinator."""
    st.set_page_config(
        page_title="STEN-F 会計システム",
        page_icon=":material/account_balance:",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_global_design_system()

    if "initialized" not in st.session_state:
        try:
            run_async(seed_accounts())
            st.session_state.initialized = True
        except Exception as e:
            log.error("startup_seeding_error", error=str(e))

    views_dir = _ROOT / "app" / "ui" / "views"
    pages = [
        st.Page(
            str(views_dir / "journal_view.py"),
            title="仕訳・記帳",
            icon=":material/edit_note:",
            help="AI OCR証憑読取、振替伝票作成、および仕訳帳の一覧・検索・CSV出力",
            default=True,
        ),
        st.Page(
            str(views_dir / "ledger_view.py"),
            title="元帳・決算",
            icon=":material/analytics:",
            help="合計残高試算表(T/B)、総勘定元帳、および決算書(B/S・P/L)・PDF出力",
        ),
        st.Page(
            str(views_dir / "master_view.py"),
            title="マスタ・設定",
            icon=":material/settings:",
            help="自社情報、会計年度・年度締め、期首残高、勘定科目・取引先・摘要マスタ、AI設定",
        ),
    ]
    nav = st.navigation(pages)

    corp_info, open_fy = None, None
    try:
        corp_res, fys_res = run_scoped(DI.get_master_service(), load_sidebar_metadata)
        corp_info = corp_res
        open_fy = resolve_active_fiscal_year(fys_res)
    except Exception as e:
        log.error("sidebar_load_error", error=str(e))

    render_sidebar(corp_info, open_fy)
    nav.run()


if __name__ == "__main__":
    main()
