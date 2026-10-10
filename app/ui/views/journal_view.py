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
import pandas as pd
import streamlit as st

from app.core_foundation import DI, call_journal, call_master, run_async
from app.domain_contracts import Transaction, TransactionLine

st.header("仕訳・記帳", divider="blue")
st.caption(
    "AI OCR（領収書・請求書自動読取）起点での振替伝票作成、および仕訳帳の一覧・検索・CSV出力を一元的に行います。"
)

accounts = call_master(lambda s: s.get_accounts())
abstracts = call_master(lambda s: s.get_abstracts())
all_fys = call_master(lambda s: s.get_fiscal_years())
open_fy = next((f for f in all_fys if f.status == "OPEN"), None)
account_labels = [""] + [
    f"{a.code}: {a.name}" for a in sorted(accounts, key=lambda x: int(x.code))
]
account_code_to_id = {f"{a.code}: {a.name}": a.id for a in accounts}
account_id_to_label = {a.id: f"{a.code}: {a.name}" for a in accounts}
abstract_options = [""] + sorted(list(set(a.text for a in abstracts if a.text)))

tab_entry, tab_history = st.tabs(
    ["📝 振替伝票・AI仕訳入力", "📖 仕訳帳 (General Journal)"]
)

# 1. 振替伝票入力
with tab_entry:
    st.subheader("Step 1: 証憑のアップロード ＆ AI自動読取")
    uploaded_file = st.file_uploader(
        "領収書・請求書をドラッグ＆ドロップ",
        type=["pdf", "png", "jpg", "jpeg"],
        key="journal_file_uploader",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_name = uploaded_file.name
        is_pdf = file_name.lower().endswith(".pdf")

        if is_pdf:
            st.info(
                f"📄 PDF形式の証憑がセットされました: **{file_name}** ({len(file_bytes) / 1024:.1f} KB)"
            )
        else:
            st.image(
                file_bytes,
                caption=f"証憑プレビュー: {file_name}",
                use_container_width=True,
            )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            run_fast = st.button(
                "⚡ 通常読取（高速）",
                key="btn_run_ocr_fast",
                use_container_width=True,
            )
        with col_btn2:
            run_boost = st.button(
                "🎯 高精度読取（ブースト）",
                type="primary",
                key="btn_run_ocr_boost",
                use_container_width=True,
            )

        if run_fast or run_boost:
            target_model = "gemini-3.5-flash-lite" if run_fast else "gemini-3.8-flash"
            model_label = "通常読取（高速）" if run_fast else "高精度読取（ブースト）"
            mime = uploaded_file.type or ("application/pdf" if is_pdf else "image/png")
            with st.spinner(f"Gemini AI ({model_label}) が証憑を解析中..."):
                try:
                    ocr_res = run_async(
                        DI.get_ocr_service().extract_receipt_data(
                            file_bytes, mime, model_id=target_model
                        )
                    )
                    st.session_state["ocr_result"] = ocr_res
                    st.session_state["ocr_bytes"] = file_bytes
                    st.session_state["ocr_filename"] = file_name
                    if ocr_res.needs_manual_review:
                        st.warning(
                            f"AI解析完了（照合スコア: {ocr_res.match_score:.1f}点 / 75点未満）: 取引先マスターと完全一致しませんでした。読み取れた生データを入力欄に自動入力しましたので、赤枠内容を確認・修正してください。"
                        )
                    else:
                        st.success(
                            f"AI解析・取引先特定成功（照合スコア: {ocr_res.match_score:.1f}点）: 取引先マスターと紐付け、振替伝票に自動展開しました。"
                        )
                except Exception as e:
                    st.error(f"AI解析エラー: {e}")

    ocr = st.session_state.get("ocr_result")

    st.divider()
    st.subheader("Step 2: 振替伝票入力")

    if ocr and ocr.needs_manual_review:
        st.markdown(
            """
            <div style="border: 2px solid #ef4444; border-radius: 8px; padding: 12px; margin-bottom: 16px; background-color: rgba(239, 68, 68, 0.08);">
                <div style="color: #b91c1c; font-weight: bold; font-size: 1.05rem; margin-bottom: 4px;">
                    ⚠️ 新規・要確認（未確定）
                </div>
                <div style="color: #374151; font-size: 0.9rem;">
                    取引先マスター照合スコアが75点未満のため、未確定として表示しています。AIが読み取った日付・金額・店名等の生データは自動入力されています。内容を確認し、必要に応じて修正してください。
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    ocr_date = date.today()
    if ocr and ocr.transaction_date:
        try:
            ocr_date = date.fromisoformat(ocr.transaction_date)
        except Exception:
            pass

    col_h1, col_h2, col_h3, col_h4 = st.columns([2, 3, 3, 2])
    with col_h1:
        tx_date = st.date_input("取引日", value=ocr_date, key="tx_header_date")
    with col_h2:
        abs_choice = st.selectbox(
            "よく使う摘要から選ぶ", abstract_options, key="tx_header_abs_choice"
        )
        tx_desc = st.text_input(
            "伝票摘要 (取引内容)",
            value=abs_choice
            if abs_choice
            else (ocr.description if ocr and ocr.description else ""),
            key="tx_header_desc",
        )
    with col_h3:
        tx_cp = st.text_input(
            "取引先",
            value=ocr.merchant_name if ocr and ocr.merchant_name else "",
            key="tx_header_cp",
        )
    with col_h4:
        tx_inv = st.text_input(
            "インボイス番号 (T+13桁)",
            value=ocr.invoice_registration_number
            if ocr and ocr.invoice_registration_number
            else "",
            key="tx_header_inv",
        )

    d_init, c_init, init_amt = "", "", 0
    if ocr:
        init_amt = ocr.total_amount_incl_tax or 0
        if ocr.inferred_debit_account_id:
            val_d = str(ocr.inferred_debit_account_id)
            if val_d.isdigit() and int(val_d) in account_id_to_label:
                d_init = account_id_to_label[int(val_d)]
            else:
                for lbl in account_labels:
                    if val_d in lbl:
                        d_init = lbl
                        break
        if ocr.inferred_credit_account_id:
            val_c = str(ocr.inferred_credit_account_id)
            if val_c.isdigit() and int(val_c) in account_id_to_label:
                c_init = account_id_to_label[int(val_c)]
            else:
                for lbl in account_labels:
                    if val_c in lbl:
                        c_init = lbl
                        break

    lines_df = pd.DataFrame(
        [
            {
                "debit_account": d_init,
                "debit_amount": init_amt,
                "credit_account": c_init,
                "credit_amount": init_amt,
                "line_desc": ocr.description if ocr and ocr.description else "",
            }
        ]
    )
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
        key="journal_voucher_lines_editor",
    )

    tx_lines: list[TransactionLine] = []
    for _, r in edited_lines_df.iterrows():
        if (d_acc := r.get("debit_account")) and (
            d_amt := int(r.get("debit_amount") or 0)
        ) > 0:
            if aid := account_code_to_id.get(str(d_acc)):
                tx_lines.append(TransactionLine(account_id=aid, debit=d_amt, credit=0))
        if (c_acc := r.get("credit_account")) and (
            c_amt := int(r.get("credit_amount") or 0)
        ) > 0:
            if aid := account_code_to_id.get(str(c_acc)):
                tx_lines.append(TransactionLine(account_id=aid, debit=0, credit=c_amt))

    total_debit = sum(line.debit for line in tx_lines)
    total_credit = sum(line.credit for line in tx_lines)

    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("借方合計", f"¥{total_debit:,}")
    col_m2.metric("貸方合計", f"¥{total_credit:,}")
    is_balanced = total_debit == total_credit > 0
    col_m3.metric(
        "貸借バランス(差額)",
        "✅ 一致" if is_balanced else f"¥{total_debit - total_credit:,}",
    )

    # Active evidence attachment indicator
    active_evidence_bytes = (
        uploaded_file.getvalue() if uploaded_file else st.session_state.get("ocr_bytes")
    )
    active_evidence_name = (
        uploaded_file.name if uploaded_file else st.session_state.get("ocr_filename")
    )
    if active_evidence_name:
        st.caption(
            f"🔒 添付証憑: **{active_evidence_name}**（登録時に電帳法準拠ストレージへ自動保存されます）"
        )

    if st.button(
        "💾 この内容で仕訳帳に登録する",
        type="primary",
        disabled=not is_balanced,
        width="stretch",
    ):
        new_tx = Transaction(
            occurred_at=tx_date,
            description=tx_desc.strip() if tx_desc else "振替仕訳",
            counterparty=tx_cp.strip() if tx_cp else None,
            invoice_number=tx_inv.strip() if tx_inv else None,
            lines=tx_lines,
        )

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
            st.session_state["ocr_result"] = None
            st.session_state["ocr_bytes"] = None
            st.session_state["ocr_filename"] = None
            st.success("仕訳が正常に登録されました！")
            st.rerun()
        except Exception as e:
            st.error(f"仕訳登録エラー: {e}")

# 2. 仕訳帳一覧
with tab_history:
    st.subheader("仕訳帳 (General Journal) 一覧・検索・CSV出力")
    _, _, col_f3 = st.columns([2, 2, 2])
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
    with col_f3:
        st.write("")
        st.write("")
        evidence_only = st.checkbox(
            "証憑添付ありのみ表示", value=False, key="hist_evidence_only"
        )

    entries = call_journal(
        lambda s: s.get_entries(start_date=s_date, end_date=e_date),
    )
    if evidence_only:
        entries = [tx for tx in entries if tx.evidence_path]

    if not entries:
        st.info("該当する仕訳データはありません。")
    else:
        rows: list[dict[str, object]] = []
        for tx in entries:
            d_lines = [line for line in tx.lines if line.debit > 0]
            c_lines = [line for line in tx.lines if line.credit > 0]
            for i in range(max(len(d_lines), len(c_lines), 1)):
                d = d_lines[i] if i < len(d_lines) else None
                c = c_lines[i] if i < len(c_lines) else None
                rows.append(
                    {
                        "id": tx.id,
                        "発生日": str(tx.occurred_at),
                        "記録日時(UTC)": tx.recorded_at.strftime("%Y-%m-%d %H:%M:%S")
                        if tx.recorded_at
                        else "-",
                        "証憑": ("📄 あり" if tx.evidence_path else "-")
                        if i == 0
                        else "",
                        "借方科目": account_id_to_label.get(d.account_id, "")
                        if d
                        else "",
                        "借方金額": d.debit if d else 0,
                        "貸方科目": account_id_to_label.get(c.account_id, "")
                        if c
                        else "",
                        "貸方金額": c.credit if c else 0,
                        "摘要": tx.description or "",
                        "取引先": tx.counterparty or "",
                        "インボイス番号": tx.invoice_number or "",
                    }
                )

        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        csv_buf = io.StringIO()
        pd.DataFrame(rows).to_csv(csv_buf, index=False)
        st.download_button(
            "📥 仕訳帳 CSV をエクスポート",
            data=csv_buf.getvalue().encode("utf_8_sig"),
            file_name=f"journal_{s_date}_{e_date}.csv",
            mime="text/csv",
            width="stretch",
        )

        st.divider()
        st.markdown("##### 🔍 選択仕訳の詳細・証憑確認 (PDF/画像)")
        tx_options = {
            f"ID {tx.id} | 発生日: {tx.occurred_at} | {tx.description or '振替仕訳'} (¥{sum(line.debit for line in tx.lines):,}) [{'📄 証憑あり' if tx.evidence_path else '証憑なし'}]": tx
            for tx in entries
        }
        selected_label = st.selectbox(
            "確認する仕訳を選択",
            options=[""] + list(tx_options.keys()),
            key="hist_selected_tx_box",
        )
        if selected_label and (selected_tx := tx_options.get(selected_label)):
            col_d_left, col_d_right = st.columns([3, 2])
            with col_d_left:
                st.markdown(
                    f"**発生日:** `{selected_tx.occurred_at}` | **記録日時:** `{selected_tx.recorded_at.strftime('%Y-%m-%d %H:%M:%S UTC') if selected_tx.recorded_at else '-'}`"
                )
                st.markdown(
                    f"**摘要:** `{selected_tx.description or '-'}` | **取引先:** `{selected_tx.counterparty or '-'}` | **インボイス番号:** `{selected_tx.invoice_number or '-'}`"
                )

                if selected_tx.evidence_path:
                    file_service = DI.get_file_service()
                    resolved = file_service.resolve_evidence_path(
                        selected_tx.evidence_path
                    )
                    if resolved and resolved.exists():
                        evidence_bytes = resolved.read_bytes()
                        evidence_filename = resolved.name
                        is_evidence_pdf = evidence_filename.lower().endswith(".pdf")
                        st.success(
                            f"📎 添付証憑: **{evidence_filename}** ({len(evidence_bytes) / 1024:.1f} KB)"
                        )
                        st.download_button(
                            label=f"📥 証憑ファイル ({evidence_filename}) をダウンロード",
                            data=evidence_bytes,
                            file_name=evidence_filename,
                            mime="application/pdf"
                            if is_evidence_pdf
                            else (
                                "image/png"
                                if evidence_filename.lower().endswith(".png")
                                else "image/jpeg"
                            ),
                            icon=":material/download:",
                            key=f"dl_evidence_{selected_tx.id}",
                        )
                        if is_evidence_pdf:
                            with st.expander("📄 PDFプレビューを表示", expanded=True):
                                b64_pdf = base64.b64encode(evidence_bytes).decode(
                                    "utf-8"
                                )
                                st.markdown(
                                    f'<iframe src="data:application/pdf;base64,{b64_pdf}" width="100%" height="500" type="application/pdf"></iframe>',
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.image(
                                evidence_bytes,
                                caption=f"証憑プレビュー: {evidence_filename}",
                                use_container_width=True,
                            )
                    else:
                        st.warning(
                            f"⚠️ 証憑ファイルがストレージ上に見つかりません: {selected_tx.evidence_path}"
                        )
                else:
                    st.caption("※ この仕訳に添付された証憑はありません。")

            with col_d_right:
                if selected_tx.id is not None:
                    target_id: int = selected_tx.id
                    st.markdown("##### 🔄 赤伝起票（反対仕訳による訂正）")
                    st.caption(
                        "※ 会計不変制約（Rule 1）に基づき、過去仕訳の上書き更新・削除は禁止されています。貸借を反転させた赤伝（反対仕訳）を発行して残高を相殺します。"
                    )
                    rev_reason = st.text_input(
                        "取消理由",
                        value="入力誤謬による取消",
                        key=f"rev_reason_{target_id}",
                    )
                    if st.button(
                        "🔄 赤伝（反対仕訳）を発行して取消",
                        type="secondary",
                        icon=":material/swap_horiz:",
                        key=f"rev_btn_{target_id}",
                        use_container_width=True,
                    ):
                        try:
                            rev_id = call_journal(
                                lambda s: s.reverse_journal_entry(
                                    target_id, reason=rev_reason
                                )
                            )
                            st.toast(
                                f"赤伝を発行しました (新仕訳ID: {rev_id})",
                                icon="🔄",
                            )
                            st.rerun()
                        except Exception as ex:
                            st.error(f"赤伝起票エラー: {ex}")
