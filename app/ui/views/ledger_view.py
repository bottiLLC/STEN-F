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

st.header("帳簿・決算", divider="blue")
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
        "📊 合計残高試算表 (T/B)",
        "📖 総勘定元帳 (General Ledger)",
        "📑 決算書 (B/S・P/L・PDF)",
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
                    "借方残高": f"¥{r.debit_balance:,}" if r.debit_balance > 0 else "-",
                    "借方合計": f"¥{r.debit_total:,}" if r.debit_total > 0 else "-",
                    "貸方合計": f"¥{r.credit_total:,}" if r.credit_total > 0 else "-",
                    "貸方残高": f"¥{r.credit_balance:,}"
                    if r.credit_balance > 0
                    else "-",
                }
                for r in tb_rows
            ]
        )
        st.dataframe(df_tb, width="stretch", hide_index=True)

        tot_db = sum(r.debit_balance for r in tb_rows)
        tot_cb = sum(r.credit_balance for r in tb_rows)
        c1, c2, c3 = st.columns(3)
        c1.metric("借方残高合計", f"¥{tot_db:,}")
        c2.metric("貸方残高合計", f"¥{tot_cb:,}")
        if tot_db == tot_cb:
            c3.success("✅ 貸借一致 (バランス検証 OK)")
        else:
            c3.error(f"❌ 貸借不一致 (差額: ¥{abs(tot_db - tot_cb):,})")

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
    col_btn, col_chk = st.columns([2, 3])
    with col_chk:
        hide_zero = st.checkbox("残高が 0 円の科目を非表示にする", value=True)

    with col_btn:
        if st.button(
            "📑 決算書 PDF を生成・ダウンロード",
            type="primary",
            width="stretch",
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
                    "⬇️ 生成された決算書 PDF を保存",
                    data=pdf_bytes,
                    file_name=f"report_{selected_fy.name}.pdf",
                    mime="application/pdf",
                    width="stretch",
                )
            except Exception as e:
                st.error(f"PDF 生成エラー: {e}")

    report = call_ledger(lambda s: s.generate_financial_report(selected_fy.id or 0))

    st.divider()
    st.markdown("### 🏛️ 貸借対照表 (Balance Sheet)")
    c_bs_l, c_bs_r = st.columns(2)
    with c_bs_l:
        st.markdown("#### 【 資産の部 】")
        st.markdown("**流動資産**")
        for r in report.current_assets.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**流動資産合計: ¥{report.current_assets.total:,}**")

        st.markdown("**固定資産**")
        for r in report.fixed_assets.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**固定資産合計: ¥{report.fixed_assets.total:,}**")
        st.markdown(f"### 資産の部 合計: ¥{report.total_assets:,}")

    with c_bs_r:
        st.markdown("#### 【 負債・純資産の部 】")
        st.markdown("**流動負債**")
        for r in report.current_liabilities.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**流動負債合計: ¥{report.current_liabilities.total:,}**")

        st.markdown("**固定負債**")
        for r in report.fixed_liabilities.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**固定負債合計: ¥{report.fixed_liabilities.total:,}**")

        st.markdown("**純資産の部**")
        for r in report.equity.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**純資産合計: ¥{report.total_equity:,}**")
        st.markdown(
            f"### 負債・純資産の部 合計: ¥{report.total_liabilities + report.total_equity:,}"
        )

    st.divider()
    st.markdown("### 📈 損益計算書 (Profit & Loss Statement)")
    c_pl1, c_pl2 = st.columns(2)
    with c_pl1:
        st.markdown("**1. 売上高 / 2. 売上原価**")
        st.write(f"- 売上高: ¥{report.revenue.total:,}")
        st.write(f"- 売上原価: ¥{report.cost_of_sales.total:,}")
        st.markdown(f"**売上総利益: ¥{report.gross_profit:,}**")

        st.markdown("**3. 販売費及び一般管理費**")
        for r in report.sga.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**販売費及び一般管理費合計: ¥{report.sga.total:,}**")
        st.markdown(f"### 営業利益: ¥{report.operating_income:,}")

    with c_pl2:
        st.markdown("**4. 営業外損益 / 5. 特別損益**")
        st.write(f"- 営業外収益: ¥{report.non_op_income.total:,}")
        st.write(f"- 営業外費用: ¥{report.non_op_expense.total:,}")
        st.markdown(f"**経常利益: ¥{report.ordinary_income:,}**")

        st.write(f"- 特別利益: ¥{report.extra_income.total:,}")
        st.write(f"- 特別損失: ¥{report.extra_loss.total:,}")
        st.markdown(f"**税引前当期純利益: ¥{report.income_before_tax:,}**")
        st.markdown(f"### 🌟 当期純利益: ¥{report.net_income:,}")
