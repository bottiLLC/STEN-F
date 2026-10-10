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
import pandas as pd
import streamlit as st

from app.core_foundation import DI, call_ledger, call_master, run_async
from app.domain_contracts import Corporation, FiscalYear
from app.ui.financial_statements import (
    render_balance_sheet,
    render_profit_and_loss,
)

st.header("帳簿・決算", divider="gray")
st.caption(
    "総勘定元帳の閲覧、合計残高試算表 (T/B) による貸借検証、および貸借対照表 (B/S)・損益計算書 (P/L) の確認・PDF 出力を一元的に行います。"
)

fys = call_master(lambda s: s.get_fiscal_years())
if not fys:
    st.warning("会計年度が登録されていません。マスタ・設定から登録してください。")
    st.stop()

fy_map = {
    f"{f.name} ({f.start_date} 〜 {f.end_date}) [{'進行中' if f.status == 'OPEN' else '締切済'}]": f
    for f in sorted(fys, key=lambda x: x.start_date, reverse=True)
}
selected_fy = fy_map[
    st.selectbox("対象会計年度", list(fy_map.keys()), key="ledger_fy_select")
]

tab_tb, tab_gl, tab_fs = st.tabs(
    [
        "合計残高試算表 (T/B)",
        "総勘定元帳 (General Ledger)",
        "決算書 (B/S・P/L・PDF)",
    ]
)

# 1. 試算表 (T/B)
with tab_tb:
    st.subheader(f"合計残高試算表 (対象: {selected_fy.name})")
    tb_rows = call_ledger(lambda s: s.get_trial_balance(selected_fy.id or 0))
    if not tb_rows:
        st.info("集計対象の仕訳データがありません。")
    else:
        df_tb = pd.DataFrame(
            [
                {
                    "コード": r.account_code,
                    "勘定科目名": r.account_name,
                    "借方残高": r.debit_balance if r.debit_balance > 0 else None,
                    "借方合計": r.debit_total if r.debit_total > 0 else None,
                    "貸方合計": r.credit_total if r.credit_total > 0 else None,
                    "貸方残高": r.credit_balance if r.credit_balance > 0 else None,
                }
                for r in tb_rows
            ]
        )
        tb_col_cfg = {
            "借方残高": st.column_config.NumberColumn("借方残高", format="¥%d"),
            "借方合計": st.column_config.NumberColumn("借方合計", format="¥%d"),
            "貸方合計": st.column_config.NumberColumn("貸方合計", format="¥%d"),
            "貸方残高": st.column_config.NumberColumn("貸方残高", format="¥%d"),
        }
        st.dataframe(df_tb, column_config=tb_col_cfg, width="stretch", hide_index=True)

        tot_db = sum(r.debit_balance for r in tb_rows)
        tot_cb = sum(r.credit_balance for r in tb_rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("借方残高合計", f"¥{tot_db:,}")
        c2.metric("貸方残高合計", f"¥{tot_cb:,}")
        if tot_db == tot_cb:
            c3.success("貸借一致 (バランス検証 OK)")
        else:
            c3.error(f"貸借不一致 (差額: ¥{abs(tot_db - tot_cb):,})")

# 2. 総勘定元帳 (General Ledger)
with tab_gl:
    st.subheader(f"総勘定元帳 (対象: {selected_fy.name})")
    accounts = call_master(lambda s: s.get_accounts())
    acc_map = {f"{a.code}: {a.name}": a for a in accounts}
    selected_acc = acc_map.get(
        st.selectbox("表示する勘定科目", list(acc_map.keys()), key="gl_acc_select")
    )

    if selected_acc is not None and selected_acc.id is not None:
        target_acc_id = selected_acc.id
        df_gl = call_ledger(
            lambda s: s.get_general_ledger(selected_fy.id or 0, target_acc_id)
        )
        if df_gl.empty:
            st.info(f"{selected_acc.name} の取引履歴はありません。")
        else:
            st.dataframe(
                df_gl.style.format(
                    {
                        "借方": lambda x: f"¥{x:,}" if x > 0 else "-",
                        "貸方": lambda x: f"¥{x:,}" if x > 0 else "-",
                        "残高": lambda x: f"¥{x:,}",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

# 3. 決算書 (B/S・P/L)
with tab_fs:
    st.subheader(f"決算書: 貸借対照表 (B/S) ＆ 損益計算書 (P/L) - {selected_fy.name}")
    col_chk, col_btn = st.columns([3, 1])
    with col_chk:
        hide_zero = st.checkbox("残高が 0 円の科目を非表示にする", value=True)

    with col_btn:
        if st.button(
            "PDF生成",
            type="primary",
            icon=":material/picture_as_pdf:",
        ):

            async def generate_pdf(fy: FiscalYear) -> bytes:
                async with DI.get_master_service() as ms, DI.get_ledger_service() as ls:
                    c = await ms.get_corporation() or Corporation()
                    r = await ls.generate_financial_report(fy.id or 0)
                    from app.external_services import PDFService

                    return PDFService.generate_annual_report(
                        c, r, fy, date.today(), date.today()
                    )

            try:
                pdf_bytes = run_async(generate_pdf(selected_fy))
                st.download_button(
                    "PDF出力",
                    data=pdf_bytes,
                    file_name=f"report_{selected_fy.name}.pdf",
                    mime="application/pdf",
                    icon=":material/download:",
                )
            except Exception as e:
                st.error(f"PDF 生成エラー: {e}")

    report = call_ledger(lambda s: s.generate_financial_report(selected_fy.id or 0))

    st.divider()
    render_balance_sheet(report, hide_zero=hide_zero)
    st.divider()
    render_profit_and_loss(report, hide_zero=hide_zero)
