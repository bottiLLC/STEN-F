# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
# GNU General Public License v3.0

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Final

# Prepend script root to sys.path for deterministic module resolution
_ROOT: Final[Path] = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from backup_manager import get_backup_dir, run_backup, set_backup_dir
from app.core_foundation import DI, log, run_async, run_scoped
from app.domain_contracts import Corporation, FiscalYear, IMasterRepository
from app.storage_repository import seed_accounts

_APP_ROOT: Final[Path] = _ROOT


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
        if st.button("保存先パスを更新", use_container_width=True):
            save_res = set_backup_dir(new_dir)
            if save_res["success"]:
                st.success(save_res["message"])
                st.rerun()
            else:
                st.error(save_res["message"])

    if st.button("今すぐバックアップを実行", use_container_width=True):
        with st.spinner("圧縮・整合性検証中..."):
            res = run_backup(app_name="app")
        if res["success"]:
            st.success(res["message"])
            st.caption(f"完了日時: {res['timestamp']}")
            st.caption(f"保存先: {res['destination']}")
        else:
            st.error(res["message"])


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
            st.markdown(f"🏢 **{corp_info.name}**")
            if corp_info.representative_name:
                st.caption(
                    f"代表者: {corp_info.representative_title or ''} {corp_info.representative_name}"
                )
        else:
            st.caption("🏢 ※ 自社情報未設定 (マスタ管理で登録)")

        st.divider()
        if open_fy:
            st.info(
                f"📅 **進行中の会計年度**\n\n**{open_fy.name}**\n\n`{open_fy.start_date}` 〜 `{open_fy.end_date}`"
            )
        else:
            st.warning("⚠️ 進行中の会計年度がありません。")

        _render_sidebar_backup()

        st.divider()
        st.caption("© 2026 合同会社ぼっち (GPL-3.0)")


def main() -> None:
    """Streamlit application root coordinator."""
    st.set_page_config(
        page_title="STEN-F 会計システム",
        page_icon="📑",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    if "initialized" not in st.session_state:
        try:
            run_async(seed_accounts())
            st.session_state.initialized = True
        except Exception as e:
            log.error("startup_seeding_error", error=str(e))

    views_dir = _APP_ROOT / "app" / "ui" / "views"
    pages = [
        st.Page(
            str(views_dir / "journal_view.py"),
            title="仕訳・記帳",
            icon=":material/edit_note:",
            default=True,
        ),
        st.Page(
            str(views_dir / "ledger_view.py"),
            title="元帳・決算",
            icon=":material/analytics:",
        ),
        st.Page(
            str(views_dir / "master_view.py"),
            title="マスタ・設定",
            icon=":material/settings:",
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
