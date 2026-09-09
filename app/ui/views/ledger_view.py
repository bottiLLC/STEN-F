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

import pandas as pd
import streamlit as st
import structlog

from app.ui.async_helper import run_async
from app.ui.di import DI

log = structlog.get_logger()

st.header("帳簿・決算ワークスペース", divider="blue")
st.caption(
    "総勘定元帳の閲覧、合計残高試算表 (T/B) による貸借バランス検証、および貸借対照表 (B/S)・損益計算書 (P/L) の確認・PDF 出力を一元的に行います。"
)


# Fetch Fiscal Years
async def fetch_fiscal_years():
    async with DI.get_master_service() as s:
        return await s.get_fiscal_years()


fys = run_async(fetch_fiscal_years())

if not fys:
    st.warning(
        "会計年度が登録されていません。マスタ・設定ワークスペースから登録してください。"
    )
    st.stop()

# Fiscal Year Selector
fy_map = {
    f"{f.name} ({f.start_date} 〜 {f.end_date}) [{'進行中' if f.status == 'OPEN' else '締切済'}]": f
    for f in sorted(fys, key=lambda x: x.start_date, reverse=True)
}
selected_fy_label = st.selectbox(
    "対象会計年度", list(fy_map.keys()), key="ledger_fy_select"
)
selected_fy = fy_map[selected_fy_label]

tab_tb, tab_gl, tab_fs = st.tabs(
    [
        "📊 合計残高試算表 (T/B)",
        "📖 総勘定元帳 (General Ledger)",
        "📑 決算書 (B/S・P/L・PDF)",
    ]
)

# ==============================================================================
# 1. Trial Balance Tab
# ==============================================================================
with tab_tb:
    st.subheader(f"合計残高試算表 (対象: {selected_fy.name})")

    async def fetch_tb():
        async with DI.get_ledger_service() as s:
            return await s.get_trial_balance(selected_fy.id)

    tb_rows = run_async(fetch_tb())

    if not tb_rows:
        st.info("集計対象の仕訳データがありません。")
    else:
        df_tb = pd.DataFrame(
            [
                {
                    "勘定科目コード": r.account_code,
                    "勘定科目名": r.account_name,
                    "勘定区分": r.account_type.label
                    if hasattr(r.account_type, "label")
                    else str(r.account_type),
                    "借方合計 (¥)": f"{r.debit_total:,}" if r.debit_total else "-",
                    "貸方合計 (¥)": f"{r.credit_total:,}" if r.credit_total else "-",
                    "借方残高 (¥)": f"{r.debit_balance:,}" if r.debit_balance else "-",
                    "貸方残高 (¥)": f"{r.credit_balance:,}"
                    if r.credit_balance
                    else "-",
                }
                for r in tb_rows
            ]
        )
        st.dataframe(df_tb, hide_index=True, use_container_width=True)

        total_d_sum = sum(r.debit_total for r in tb_rows)
        total_c_sum = sum(r.credit_total for r in tb_rows)
        total_d_bal = sum(r.debit_balance for r in tb_rows)
        total_c_bal = sum(r.credit_balance for r in tb_rows)

        st.markdown("---")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("借方合計総額", f"¥{total_d_sum:,}")
        col_m2.metric("貸方合計総額", f"¥{total_c_sum:,}")
        col_m3.metric("借方残高総額", f"¥{total_d_bal:,}")
        col_m4.metric("貸方残高総額", f"¥{total_c_bal:,}")

        diff_total = total_d_sum - total_c_sum
        diff_bal = total_d_bal - total_c_bal
        if diff_total == 0 and diff_bal == 0:
            st.success("✅ 試算表の貸借バランスは完全に一致しています。")
        else:
            st.error(
                f"⚠️ 貸借不一致が検出されました (合計差額: ¥{diff_total:,}, 残高差額: ¥{diff_bal:,})"
            )

# ==============================================================================
# 2. General Ledger Tab
# ==============================================================================
with tab_gl:
    st.subheader("総勘定元帳 (General Ledger)")

    async def fetch_accounts():
        async with DI.get_master_service() as s:
            return await s.get_accounts()

    acc_list = run_async(fetch_accounts())
    acc_map = {
        f"{a.code}: {a.name}": a for a in sorted(acc_list, key=lambda x: int(x.code))
    }

    selected_acc_label = st.selectbox(
        "勘定科目を指定", list(acc_map.keys()), key="gl_acc_select"
    )
    selected_acc = acc_map[selected_acc_label]

    async def fetch_gl(fid, aid):
        async with DI.get_ledger_service() as s:
            return await s.get_general_ledger(fid, aid)

    gl_df = run_async(fetch_gl(selected_fy.id, selected_acc.id))

    if gl_df is None or gl_df.empty:
        st.info(f"「{selected_acc.name}」に関する取引データはありません。")
    else:
        st.dataframe(gl_df, hide_index=True, use_container_width=True)

# ==============================================================================
# 3. Financial Statements & PDF Tab
# ==============================================================================
with tab_fs:
    st.subheader(f"決算書: 貸借対照表 (B/S) ＆ 損益計算書 (P/L) - {selected_fy.name}")

    col_btn, col_chk = st.columns([2, 3])
    with col_chk:
        hide_zero = st.checkbox("残高が 0 円の科目を非表示にする", value=True)

    with col_btn:
        if st.button(
            "📑 決算書 PDF を生成・ダウンロード",
            type="primary",
            use_container_width=True,
        ):

            async def generate_pdf(fy):
                async with DI.get_pdf_service() as s:
                    return await s.generate_annual_report(fy)

            try:
                pdf_bytes = run_async(generate_pdf(selected_fy))
                st.download_button(
                    label="⬇️ 生成された決算書 PDF を保存",
                    data=pdf_bytes,
                    file_name=f"financial_report_{selected_fy.name}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"PDF 生成エラー: {e}")

    async def fetch_report(fid):
        async with DI.get_ledger_service() as s:
            return await s.generate_financial_report(fid)

    report = run_async(fetch_report(selected_fy.id))

    st.markdown("---")
    st.markdown("### 🏛️ 貸借対照表 (Balance Sheet)")

    col_bs_l, col_bs_r = st.columns(2)
    with col_bs_l:
        st.markdown("#### 【 資産の部 】")
        # Current Assets
        st.markdown("**流動資産**")
        for r in report.current_assets.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**流動資産合計: ¥{report.current_assets.total:,}**")

        # Fixed Assets
        st.markdown("**固定資産**")
        for r in report.fixed_assets.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**固定資産合計: ¥{report.fixed_assets.total:,}**")

        st.markdown(f"### 資産の部 合計: ¥{report.total_assets:,}")

    with col_bs_r:
        st.markdown("#### 【 負債・純資産の部 】")
        # Current Liabilities
        st.markdown("**流動負債**")
        for r in report.current_liabilities.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**流動負債合計: ¥{report.current_liabilities.total:,}**")

        # Fixed Liabilities
        st.markdown("**固定負債**")
        for r in report.fixed_liabilities.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**固定負債合計: ¥{report.fixed_liabilities.total:,}**")

        # Equity
        st.markdown("**純資産の部**")
        for r in report.equity.rows:
            if not hide_zero or r.balance != 0:
                st.write(f"- {r.account_name}: ¥{r.balance:,}")
        st.markdown(f"**純資産合計: ¥{report.total_equity:,}**")

        total_liab_equity = report.total_liabilities + report.total_equity
        st.markdown(f"### 負債・純資産の部 合計: ¥{total_liab_equity:,}")

    st.markdown("---")
    st.markdown("### 📈 損益計算書 (Profit & Loss Statement)")

    col_pl1, col_pl2 = st.columns(2)
    with col_pl1:
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

    with col_pl2:
        st.markdown("**4. 営業外損益 / 5. 特別損益**")
        st.write(f"- 営業外収益: ¥{report.non_op_income.total:,}")
        st.write(f"- 営業外費用: ¥{report.non_op_expense.total:,}")
        st.markdown(f"**経常利益: ¥{report.ordinary_income:,}**")

        st.write(f"- 特別利益: ¥{report.extra_income.total:,}")
        st.write(f"- 特別損失: ¥{report.extra_loss.total:,}")
        st.markdown(f"**税引前当期純利益: ¥{report.income_before_tax:,}**")
        st.markdown(f"### 🌟 当期純利益: ¥{report.net_income:,}")
