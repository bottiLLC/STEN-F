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

from datetime import date
from pathlib import Path
from typing import Any
import streamlit as st

from app.core_foundation import DI, call_journal, run_async
from app.domain_contracts import Transaction, TransactionLine
from app.ui.journal_helpers import (
    build_voucher_initial_df,
    build_voucher_transaction,
    parse_voucher_editor_lines,
    resolve_ocr_date,
)


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
        """
        <div class="sten-notice-danger">
            <div class="sten-notice-danger-title">新規・要確認（未確定）</div>
            <div class="sten-notice-danger-body">
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
        # Full-app rerun ensures the General Journal history fragment reflects the newly committed entry.
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


@st.fragment
def render_journal_entry_section(
    account_labels: list[str],
    account_code_to_id: dict[str, int | None],
    account_id_to_label: dict[int | None, str],
    abstract_options: list[str],
) -> None:
    """Render fragment-scoped OCR upload and double-entry voucher form."""
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
