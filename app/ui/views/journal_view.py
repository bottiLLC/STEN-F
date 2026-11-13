# Copyright (C) 2026 合同会社ぼっち (bottiLLC)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations

import base64
from datetime import date
import io
from pathlib import Path
from typing import Any
import pandas as pd
import streamlit as st

from app.core_foundation import DI, call_journal, call_master, run_async
from app.domain_contracts import (
    FiscalYear,
    Transaction,
    TransactionLine,
    account_code_sort_key,
)
from app.ui.design_system import (
    COLOR_DANGER,
    COLOR_SURFACE_BG,
    COLOR_TEXT_PRIMARY,
    destructive_button_container,
)
from app.ui.journal_helpers import (
    build_detail_line_rows,
    build_journal_display_rows,
    build_voucher_initial_df,
    build_voucher_transaction,
    filter_journal_entries,
    is_red_slip_transaction,
    parse_voucher_editor_lines,
    resolve_evidence_mime,
    resolve_ocr_date,
)

_resolve_evidence_mime = resolve_evidence_mime


@st.cache_data(max_size=32, ttl=300)
def _load_evidence_payload(resolved_path: str) -> bytes:
    """Read stored evidence bytes with bounded cache to avoid redundant disk I/O."""
    return Path(resolved_path).read_bytes()


def _build_evidence_popup_html(b64_data: str, mime_type: str) -> str:
    """Build self-contained HTML/JS button that opens base64 evidence in a new browser window via Blob URL."""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ margin: 0; padding: 0; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
  .btn-view {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    width: auto;
    min-width: 140px;
    max-width: 220px;
    height: 38px;
    padding: 0 16px;
    box-sizing: border-box;
    background-color: #1E3A8A;
    color: #FFFFFF;
    border: 1px solid #1E3A8A;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    white-space: nowrap;
    transition: all 0.15s ease;
  }}
  .btn-view:hover {{
    background-color: #2563EB;
    border-color: #2563EB;
  }}
</style>
</head>
<body>
  <button class="btn-view" onclick="openEvidence()">
    <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
      <path d="M19 19H5V5h7V3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z"/>
    </svg>
    証憑の表示
  </button>
  <script>
    function openEvidence() {{
      const b64 = "{b64_data}";
      const mime = "{mime_type}";
      const byteChars = atob(b64);
      const byteNums = new Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) {{
        byteNums[i] = byteChars.charCodeAt(i);
      }}
      const byteArray = new Uint8Array(byteNums);
      const blob = new Blob([byteArray], {{type: mime}});
      const fileUrl = URL.createObjectURL(blob);
      window.open(fileUrl, '_blank', 'noopener,noreferrer');
    }}
  </script>
</body>
</html>"""


def _render_ocr_upload_step(form_ver: int) -> Any:
    """Render evidence upload control and Gemini AI OCR triggers."""
    st.subheader("Step 1: 証憑のアップロード ＆ AI自動読取")
    uploaded_file = st.file_uploader(
        "領収書・請求書をドラッグ＆ドロップ",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        key=f"journal_file_uploader_{form_ver}",
    )
    if uploaded_file is None:
        return None

    file_bytes = uploaded_file.getvalue()
    file_name = uploaded_file.name
    is_pdf = file_name.lower().endswith(".pdf")

    if is_pdf:
        st.info(
            f"PDF形式の証憑がセットされました: **{file_name}** ({len(file_bytes) / 1024:.1f} KB)"
        )
    else:
        st.image(
            file_bytes,
            caption=f"証憑プレビュー: {file_name}",
            width="stretch",
        )

    with st.container(horizontal=True, horizontal_alignment="right"):
        run_fast = st.button(
            "通常読取",
            key="btn_run_ocr_fast",
            icon=":material/bolt:",
            width="content",
        )
        run_boost = st.button(
            "高精度読取",
            type="primary",
            key="btn_run_ocr_boost",
            icon=":material/auto_awesome:",
            width="content",
        )

    if run_fast or run_boost:
        target_model = "gemini-3.5-flash-lite" if run_fast else "gemini-3.8-flash"
        model_label = "通常読取" if run_fast else "高精度読取"
        file_ext = Path(file_name).suffix.lstrip(".").lower()
        file_format = uploaded_file.type or file_ext or ("pdf" if is_pdf else "png")
        with st.spinner(f"Gemini AI ({model_label}) が証憑を解析中..."):
            try:
                ocr_res = run_async(
                    DI.get_ocr_service().extract_receipt_data(
                        file_bytes, file_format, model_id=target_model
                    )
                )
                st.session_state["ocr_result"] = ocr_res
                st.session_state["ocr_bytes"] = file_bytes
                st.session_state["ocr_filename"] = file_name
                if ocr_res.needs_manual_review:
                    st.warning(
                        f"AI解析完了（照合スコア: {ocr_res.match_score:.1f}点 / 75点未満）: "
                        "取引先マスターと完全一致しませんでした。読み取れた生データを入力欄に自動入力しましたので、赤枠内容を確認・修正してください。"
                    )
                else:
                    st.toast(
                        f"AI解析・取引先特定成功（照合スコア: {ocr_res.match_score:.1f}点）",
                        icon=":material/check_circle:",
                    )
            except Exception as e:
                st.error(f"AI解析エラー: {e}")

    return uploaded_file


def _render_manual_review_notice() -> None:
    """Render high-visibility border notice when OCR score falls below identification threshold."""
    st.html(
        f"""
        <div style="border: 1px solid {COLOR_DANGER}; border-radius: 4px; padding: 12px; margin-bottom: 16px; background-color: {COLOR_SURFACE_BG};">
            <div style="color: {COLOR_DANGER}; font-weight: bold; font-size: 1.05rem; margin-bottom: 4px;">
                新規・要確認（未確定）
            </div>
            <div style="color: {COLOR_TEXT_PRIMARY}; font-size: 0.9rem;">
                取引先マスター照合スコアが75点未満のため、未確定として表示しています。AIが読み取った日付・金額・店名等の生データは自動入力されています。内容を確認し、必要に応じて修正してください。
            </div>
        </div>
        """
    )


def _clear_voucher_form_state(form_ver: int) -> None:
    """Reset voucher widget keys and bump form version counter after commit."""
    for key in (
        f"journal_file_uploader_{form_ver}",
        f"tx_header_date_{form_ver}",
        f"tx_header_abs_choice_{form_ver}",
        f"tx_header_desc_{form_ver}",
        f"tx_header_cp_{form_ver}",
        f"tx_header_inv_{form_ver}",
        f"journal_voucher_lines_editor_{form_ver}",
    ):
        st.session_state.pop(key, None)
    st.session_state["ocr_result"] = None
    st.session_state["ocr_bytes"] = None
    st.session_state["ocr_filename"] = None
    st.session_state["journal_entry_form_version"] = form_ver + 1
    st.session_state["journal_tx_submitting"] = False


def _render_voucher_header(
    form_ver: int, ocr: Any, abstract_options: list[str]
) -> tuple[date, str, str, str]:
    """Render voucher metadata header inputs and return normalized widget values."""
    ocr_date = resolve_ocr_date(ocr)
    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 2])
    with col_h1:
        tx_date = st.date_input(
            "取引日", value=ocr_date, key=f"tx_header_date_{form_ver}"
        )
    with col_h2:
        abs_choice = st.selectbox(
            "よく使う摘要から選ぶ",
            abstract_options,
            key=f"tx_header_abs_choice_{form_ver}",
        )
        tx_desc = st.text_input(
            "伝票摘要 (取引内容)",
            value=abs_choice
            if abs_choice
            else (ocr.description if ocr and ocr.description else ""),
            key=f"tx_header_desc_{form_ver}",
        )
    with col_h3:
        tx_cp = st.text_input(
            "取引先",
            value=ocr.merchant_name if ocr and ocr.merchant_name else "",
            key=f"tx_header_cp_{form_ver}",
        )
    with col_h4:
        tx_inv = st.text_input(
            "インボイス番号 (T+13桁)",
            value=ocr.invoice_registration_number
            if ocr and ocr.invoice_registration_number
            else "",
            key=f"tx_header_inv_{form_ver}",
        )
    return tx_date, tx_desc, tx_cp, tx_inv


def _render_voucher_lines_editor(
    form_ver: int,
    ocr: Any,
    account_labels: list[str],
    account_code_to_id: dict[str, int | None],
    account_id_to_label: dict[int | None, str],
) -> tuple[list[TransactionLine], bool]:
    """Render split journal lines editor with real-time debit/credit balance metrics."""
    lines_df = build_voucher_initial_df(ocr, account_id_to_label, account_labels)
    col_cfg = {
        "debit_account": st.column_config.SelectboxColumn(
            "借方科目", options=account_labels
        ),
        "debit_amount": st.column_config.NumberColumn(
            "借方金額 (¥)", min_value=0, step=1000, required=True
        ),
        "credit_account": st.column_config.SelectboxColumn(
            "貸方科目", options=account_labels
        ),
        "credit_amount": st.column_config.NumberColumn(
            "貸方金額 (¥)", min_value=0, step=1000, required=True
        ),
        "line_desc": st.column_config.TextColumn("行摘要"),
    }

    st.markdown("##### 【 振替伝票 明細行 】")
    edited_lines_df = st.data_editor(
        lines_df,
        column_config=col_cfg,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"journal_voucher_lines_editor_{form_ver}",
    )

    tx_lines = parse_voucher_editor_lines(edited_lines_df, account_code_to_id)
    total_debit = sum(line.debit for line in tx_lines)
    total_credit = sum(line.credit for line in tx_lines)
    is_balanced = total_debit == total_credit > 0

    with st.grid(3):
        st.metric("借方合計", f"¥{total_debit:,}", border=True)
        st.metric("貸方合計", f"¥{total_credit:,}", border=True)
        st.metric(
            "貸借バランス(差額)",
            "一致" if is_balanced else f"¥{total_debit - total_credit:,}",
            border=True,
        )
    return tx_lines, is_balanced


def _submit_voucher_transaction(
    form_ver: int,
    new_tx: Transaction,
    active_evidence_bytes: bytes | None,
    active_evidence_name: str | None,
) -> None:
    """Persist balanced journal transaction with optional electronic evidence."""
    try:
        ext = Path(active_evidence_name).suffix if active_evidence_name else ".pdf"
        call_journal(
            lambda s: (
                s.add_journal_entry_with_evidence(
                    new_tx,
                    active_evidence_bytes,
                    DI.get_file_service(),
                    extension=ext,
                )
                if active_evidence_bytes
                else s.add_journal_entry(new_tx)
            ),
        )
        _clear_voucher_form_state(form_ver)
        st.toast("仕訳が正常に登録されました", icon=":material/check_circle:")
        st.rerun()
    except Exception as e:
        st.session_state["journal_tx_submitting"] = False
        st.error(f"仕訳登録エラー: {e}")


def _render_voucher_entry_step(
    form_ver: int,
    uploaded_file: Any,
    account_labels: list[str],
    account_code_to_id: dict[str, int | None],
    account_id_to_label: dict[int | None, str],
    abstract_options: list[str],
) -> None:
    """Render double-entry transfer voucher editor and commit transaction."""
    is_submitting = bool(st.session_state.get("journal_tx_submitting", False))
    ocr = st.session_state.get("ocr_result")

    st.divider()
    st.subheader("Step 2: 振替伝票入力")
    if ocr and ocr.needs_manual_review:
        _render_manual_review_notice()

    tx_date, tx_desc, tx_cp, tx_inv = _render_voucher_header(
        form_ver, ocr, abstract_options
    )
    tx_lines, is_balanced = _render_voucher_lines_editor(
        form_ver, ocr, account_labels, account_code_to_id, account_id_to_label
    )

    active_evidence_bytes = (
        uploaded_file.getvalue() if uploaded_file else st.session_state.get("ocr_bytes")
    )
    active_evidence_name = (
        uploaded_file.name if uploaded_file else st.session_state.get("ocr_filename")
    )
    if active_evidence_name:
        st.caption(
            f"添付証憑: **{active_evidence_name}**（登録時に電帳法準拠ストレージへ自動保存されます）"
        )

    with st.container(horizontal=True, horizontal_alignment="right"):
        do_submit_tx = st.button(
            "仕訳登録",
            type="primary",
            icon=":material/check:",
            width="content",
            disabled=(not is_balanced) or is_submitting,
            key=f"btn_submit_tx_{form_ver}",
        )

    if do_submit_tx and not is_submitting:
        st.session_state["journal_tx_submitting"] = True
        new_tx = build_voucher_transaction(tx_date, tx_desc, tx_cp, tx_inv, tx_lines)
        _submit_voucher_transaction(
            form_ver, new_tx, active_evidence_bytes, active_evidence_name
        )


def _render_detail_header_and_lines(
    selected_tx: Transaction, account_id_to_label: dict[int | None, str]
) -> None:
    """Render read-only header fields, split lines table, and balance metrics."""
    st.caption(
        f"仕訳ID: {selected_tx.id} | 記録日時: {selected_tx.recorded_at.strftime('%Y-%m-%d %H:%M:%S UTC') if selected_tx.recorded_at else '-'}"
    )
    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 2])
    with col_h1:
        st.date_input(
            "取引日",
            value=selected_tx.occurred_at,
            disabled=True,
            key=f"detail_tx_date_{selected_tx.id}",
        )
    with col_h2:
        st.text_input(
            "伝票摘要 (取引内容)",
            value=selected_tx.description or "",
            disabled=True,
            key=f"detail_tx_desc_{selected_tx.id}",
        )
    with col_h3:
        st.text_input(
            "取引先",
            value=selected_tx.counterparty or "",
            disabled=True,
            key=f"detail_tx_cp_{selected_tx.id}",
        )
    with col_h4:
        st.text_input(
            "インボイス番号 (T+13桁)",
            value=selected_tx.invoice_number or "",
            disabled=True,
            key=f"detail_tx_inv_{selected_tx.id}",
        )

    st.markdown("##### 【 振替伝票 明細行 】")
    detail_rows = build_detail_line_rows(selected_tx, account_id_to_label)
    detail_cfg = {
        "借方金額 (¥)": st.column_config.NumberColumn("借方金額 (¥)", format="¥%d"),
        "貸方金額 (¥)": st.column_config.NumberColumn("貸方金額 (¥)", format="¥%d"),
    }
    st.dataframe(
        pd.DataFrame(detail_rows),
        column_config=detail_cfg,
        hide_index=True,
        width="stretch",
        key=f"detail_lines_df_{selected_tx.id}",
    )

    total_debit = sum(line.debit for line in selected_tx.lines)
    total_credit = sum(line.credit for line in selected_tx.lines)
    is_balanced = total_debit == total_credit > 0
    with st.grid(3):
        st.metric("借方合計", f"¥{total_debit:,}", border=True)
        st.metric("貸方合計", f"¥{total_credit:,}", border=True)
        st.metric(
            "貸借バランス(差額)",
            "一致" if is_balanced else f"¥{total_debit - total_credit:,}",
            border=True,
        )


def _render_evidence_actions(selected_tx: Transaction) -> None:
    """Render attached evidence preview popup and download control."""
    st.markdown("##### 証憑情報・操作")
    if not selected_tx.evidence_path:
        st.caption("※ この仕訳に添付された証憑はありません。")
        return

    resolved = DI.get_file_service().resolve_evidence_path(selected_tx.evidence_path)
    if not resolved or not resolved.exists():
        st.warning(
            f"証憑ファイルがストレージ上に見つかりません: {selected_tx.evidence_path}"
        )
        return

    evidence_bytes = _load_evidence_payload(str(resolved))
    evidence_filename = resolved.name
    mime_type = resolve_evidence_mime(evidence_filename)
    st.info(f"添付証憑: **{evidence_filename}** ({len(evidence_bytes) / 1024:.1f} KB)")
    col_btn_view, col_btn_dl = st.columns(2)
    with col_btn_view:
        b64_evidence = base64.b64encode(evidence_bytes).decode("utf-8")
        st.iframe(_build_evidence_popup_html(b64_evidence, mime_type), height=42)
    with col_btn_dl:
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.download_button(
                label="証憑出力",
                data=evidence_bytes,
                file_name=evidence_filename,
                mime=mime_type,
                icon=":material/download:",
                width="content",
                key=f"dl_evidence_{selected_tx.id}",
            )


def _render_reversal_panel(
    selected_tx: Transaction, cancelled_orig_ids: set[int]
) -> None:
    """Render reversing entry (red-slip) controls under Rule 1 immutability."""
    if selected_tx.id is None:
        return
    target_id: int = selected_tx.id
    st.markdown("##### 赤伝起票（反対仕訳による取消）")
    is_already_reversed = target_id in cancelled_orig_ids or is_red_slip_transaction(
        selected_tx
    )
    if is_already_reversed:
        st.info(
            "※ この仕訳は既に取消（赤伝）処理済み、または赤伝仕訳のため再取消できません。"
        )
    rev_reason = st.text_input(
        "取消理由",
        value="入力誤謬による取消",
        key=f"rev_reason_{target_id}",
        disabled=is_already_reversed,
    )
    with st.container(horizontal=True, horizontal_alignment="right"):
        with destructive_button_container(f"rev_{target_id}"):
            do_rev = st.button(
                "赤伝発行",
                type="secondary",
                icon=":material/swap_horiz:",
                width="content",
                disabled=is_already_reversed,
                key=f"rev_btn_{target_id}",
            )
    if do_rev and not is_already_reversed:
        try:
            rev_id = call_journal(
                lambda s: s.reverse_journal_entry(target_id, reason=rev_reason)
            )
            st.toast(
                f"赤伝を発行しました (新仕訳ID: {rev_id})",
                icon=":material/check:",
            )
            st.rerun()
        except Exception as ex:
            st.error(f"赤伝起票エラー: {ex}")


def _render_transaction_detail_card(
    selected_tx: Transaction,
    account_id_to_label: dict[int | None, str],
    cancelled_orig_ids: set[int],
) -> None:
    """Render single selected transaction detail card with evidence popup and red-slip reversal."""
    with st.container(border=True):
        _render_detail_header_and_lines(selected_tx, account_id_to_label)
        col_d_left, col_d_right = st.columns([3, 2])
        with col_d_left:
            _render_evidence_actions(selected_tx)
        with col_d_right:
            _render_reversal_panel(selected_tx, cancelled_orig_ids)


@st.fragment
def render_journal_history_section(
    open_fy: FiscalYear | None, account_id_to_label: dict[int | None, str]
) -> None:
    """Render journal entries table, CSV export, and reversing entry controls.

    Args:
        open_fy: Active open FiscalYear period or None.
        account_id_to_label: Mapping from account primary keys to human-readable labels.
    """
    st.subheader("仕訳帳 (General Journal) 一覧・検索・CSV出力")
    with st.container(horizontal=True, vertical_alignment="bottom"):
        s_date = st.date_input(
            "開始日",
            value=open_fy.start_date if open_fy else date(date.today().year, 1, 1),
            key="hist_s_date",
        )
        e_date = st.date_input(
            "終了日",
            value=open_fy.end_date if open_fy else date(date.today().year, 12, 31),
            key="hist_e_date",
        )
        evidence_only = st.checkbox(
            "証憑添付ありのみ表示", value=False, key="hist_evidence_only"
        )
        exclude_cancelled = st.checkbox(
            "取消(赤伝)処理したものを非表示",
            value=True,
            key="hist_exclude_cancelled",
        )

    all_txs = call_journal(lambda s: s.get_entries())
    entries, cancelled_orig_ids = filter_journal_entries(
        all_txs, s_date, e_date, exclude_cancelled, evidence_only
    )

    if not entries:
        st.info("該当する仕訳データはありません。")
        return

    rows = build_journal_display_rows(entries, account_id_to_label)
    df_display = pd.DataFrame(rows)
    csv_buf = io.StringIO()
    df_display.drop(columns=["選択"]).to_csv(csv_buf, index=False)

    col_tbl_info, col_tbl_action = st.columns([4, 1])
    with col_tbl_info:
        st.caption(f"抽出件数: {len(entries)} 件")
    with col_tbl_action:
        with st.container(horizontal=True, horizontal_alignment="right"):
            st.download_button(
                "CSV出力",
                data=csv_buf.getvalue().encode("utf_8_sig"),
                file_name=f"journal_{s_date}_{e_date}.csv",
                mime="text/csv",
                icon=":material/download:",
                width="content",
            )

    col_cfg = {
        "選択": st.column_config.CheckboxColumn(
            "選択",
            help="詳細・証憑を確認する仕訳を選択",
            default=False,
        ),
        "借方金額": st.column_config.NumberColumn("借方金額", format="¥%d"),
        "貸方金額": st.column_config.NumberColumn("貸方金額", format="¥%d"),
    }
    disabled_cols = [c for c in df_display.columns if c != "選択"]
    edited_df = st.data_editor(
        df_display,
        column_config=col_cfg,
        disabled=disabled_cols,
        hide_index=True,
        width="stretch",
        key="hist_journal_editor",
    )

    st.divider()
    st.markdown("##### 選択仕訳の詳細・証憑確認 (PDF/画像)")

    checked_mask = edited_df["選択"].fillna(False).astype(bool)
    selected_ids: list[int] = [
        int(tid) for tid in edited_df.loc[checked_mask, "id"].dropna().unique()
    ]
    tx_by_id: dict[int, Transaction] = {
        tx.id: tx for tx in entries if tx.id is not None
    }
    selected_txs = [tx_by_id[tid] for tid in selected_ids if tid in tx_by_id]

    if not selected_txs:
        st.info(
            "仕訳一覧の「選択」チェックボックスにチェックを入れると、ここに詳細と証憑が表示されます。"
        )
        return

    for selected_tx in selected_txs:
        _render_transaction_detail_card(
            selected_tx, account_id_to_label, cancelled_orig_ids
        )


def main() -> None:
    """Render journal entry and history workspace tabs."""
    st.header("仕訳・記帳", divider="gray")

    accounts = call_master(lambda s: s.get_accounts())
    abstracts = call_master(lambda s: s.get_abstracts())
    all_fys = call_master(lambda s: s.get_fiscal_years())
    open_fy = next((f for f in all_fys if f.status == "OPEN"), None)

    sorted_accounts = sorted(accounts, key=lambda x: account_code_sort_key(x.code))
    account_labels = [""] + [f"{a.code}: {a.name}" for a in sorted_accounts]
    account_code_to_id = {f"{a.code}: {a.name}": a.id for a in accounts}
    account_id_to_label = {a.id: f"{a.code}: {a.name}" for a in accounts}
    abstract_options = [""] + sorted({a.text for a in abstracts if a.text})

    tab_entry, tab_history = st.tabs(
        ["振替伝票・AI仕訳入力", "仕訳帳 (General Journal)"]
    )
    with tab_entry:
        form_ver = int(st.session_state.get("journal_entry_form_version", 0))
        uploaded_file = _render_ocr_upload_step(form_ver)
        _render_voucher_entry_step(
            form_ver,
            uploaded_file,
            account_labels,
            account_code_to_id,
            account_id_to_label,
            abstract_options,
        )

    with tab_history:
        render_journal_history_section(open_fy, account_id_to_label)


if __name__ == "__main__":
    main()
