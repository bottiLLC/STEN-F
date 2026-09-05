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
from datetime import date

from app.domain.models.corporation import Corporation
from app.ui.async_helper import run_async
from app.ui.di import DI
from app.ui.styles import apply_accounting_styles

log = structlog.get_logger()
apply_accounting_styles()

st.header("決算書 (財務諸表: B/S・P/L)", divider="blue")
st.caption(
    "企業の財政状態を示す「貸借対照表 (B/S)」および経営成績を示す「損益計算書 (P/L)」です。"
)


# --- Fetch Master & Fiscal Years ---
async def fetch_init_data():
    async with DI.get_master_service() as m_service:
        fys = await m_service.get_fiscal_years()
        accounts = await m_service.get_accounts()
        corp = await m_service.get_corporation()
    return fys, accounts, corp


fiscal_years, accounts, corporation = run_async(fetch_init_data())

if not fiscal_years:
    st.warning(
        "会計年度が登録されていません。「マスタ管理」から会計年度を登録してください。"
    )
    st.stop()

# Fiscal Year Selector & PDF Button
col_fy_sel, col_pdf = st.columns([3, 2])

with col_fy_sel:
    fy_options = {
        f"{fy.name} ({fy.start_date} 〜 {fy.end_date}) [{fy.status}]": fy
        for fy in fiscal_years
    }
    selected_fy_label = st.selectbox("対象会計年度", list(fy_options.keys()))
    selected_fy = fy_options[selected_fy_label]

with col_pdf:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    if st.button(
        "📑 決算書 PDF を生成・保存",
        type="primary",
        icon=":material/picture_as_pdf:",
        use_container_width=True,
    ):
        with st.spinner("決算書 PDF を生成中..."):
            try:

                async def generate_pdf():
                    async with DI.get_ledger_service() as l_service:
                        report_data = await l_service.generate_financial_report(
                            selected_fy.id
                        )
                    pdf_service = DI.get_pdf_service()
                    target_corp = corporation or Corporation(name="自社未設定")
                    return pdf_service.generate_annual_report(
                        target_corp,
                        report_data,
                        selected_fy,
                        date.today(),
                        date.today(),
                    )

                pdf_bytes = run_async(generate_pdf())
                st.download_button(
                    label=f"💾 生成された PDF ({selected_fy.name}) をダウンロード",
                    data=pdf_bytes,
                    file_name=f"financial_report_{selected_fy.name}.pdf",
                    mime="application/pdf",
                    icon=":material/download:",
                )
                st.toast("決算書 PDF の生成が完了しました！", icon="✅")
            except Exception as e:
                log.error("PDF generation failed", error=str(e), exc_info=True)
                st.error(f"PDF生成エラー: {e}")

st.markdown("---")


# Fetch Financial Report
async def fetch_report():
    async with DI.get_ledger_service() as service:
        return await service.generate_financial_report(selected_fy.id)


report = run_async(fetch_report())

if not report:
    st.info("決算書データを取得できませんでした。")
    st.stop()

tab_bs, tab_pl = st.tabs(["貸借対照表 (Balance Sheet)", "損益計算書 (Profit & Loss)"])

# ==============================================================================
# 1. 貸借対照表 (Balance Sheet: 左右対照表示)
# ==============================================================================
with tab_bs:
    st.subheader("貸借対照表 (Balance Sheet)")
    st.caption(f"（{selected_fy.name} 期末現在 / 単位: 円）")

    col_bs_left, col_bs_right = st.columns(2)

    # Left: Assets
    with col_bs_left:
        st.markdown(
            "### <span class='badge-debit'>【 資産の部 (Assets) 】</span>",
            unsafe_allow_html=True,
        )

        # Current Assets
        st.markdown(
            "<div class='statement-heading'>Ⅰ 流動資産</div>", unsafe_allow_html=True
        )
        if report.current_assets.rows:
            ca_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.current_assets.rows
                ]
            )
            st.dataframe(ca_df, hide_index=True, use_container_width=True)
        st.markdown(f"**流動資産合計:** `¥{report.current_assets.total:,}`")

        # Fixed Assets
        st.markdown(
            "<div class='statement-heading'>Ⅱ 固定資産</div>", unsafe_allow_html=True
        )
        if report.fixed_assets.rows:
            fa_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.fixed_assets.rows
                ]
            )
            st.dataframe(fa_df, hide_index=True, use_container_width=True)
        st.markdown(f"**固定資産合計:** `¥{report.fixed_assets.total:,}`")

        # Deferred Assets
        if report.deferred_assets.rows:
            st.markdown(
                "<div class='statement-heading'>Ⅲ 繰延資産</div>",
                unsafe_allow_html=True,
            )
            da_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.deferred_assets.rows
                ]
            )
            st.dataframe(da_df, hide_index=True, use_container_width=True)
            st.markdown(f"**繰延資産合計:** `¥{report.deferred_assets.total:,}`")

        st.divider()
        st.metric("資産の部 合計", f"¥{report.total_assets:,}")

    # Right: Liabilities & Equity
    with col_bs_right:
        st.markdown(
            "### <span class='badge-credit'>【 負債の部 (Liabilities) 】</span>",
            unsafe_allow_html=True,
        )

        # Current Liabilities
        st.markdown(
            "<div class='statement-heading'>Ⅰ 流動負債</div>", unsafe_allow_html=True
        )
        if report.current_liabilities.rows:
            cl_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.current_liabilities.rows
                ]
            )
            st.dataframe(cl_df, hide_index=True, use_container_width=True)
        st.markdown(f"**流動負債合計:** `¥{report.current_liabilities.total:,}`")

        # Fixed Liabilities
        if report.fixed_liabilities.rows:
            st.markdown(
                "<div class='statement-heading'>Ⅱ 固定負債</div>",
                unsafe_allow_html=True,
            )
            fl_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.fixed_liabilities.rows
                ]
            )
            st.dataframe(fl_df, hide_index=True, use_container_width=True)
            st.markdown(f"**固定負債合計:** `¥{report.fixed_liabilities.total:,}`")

        st.markdown(f"**負債合計:** `¥{report.total_liabilities:,}`")

        st.markdown(
            "### <span class='badge-credit'>【 純資産の部 (Equity) 】</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='statement-heading'>Ⅰ 株主資本 / 元入金</div>",
            unsafe_allow_html=True,
        )
        if report.equity.rows:
            eq_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.equity.rows
                ]
            )
            st.dataframe(eq_df, hide_index=True, use_container_width=True)
        st.markdown(f"**当期純利益:** `¥{report.net_income:,}`")
        st.markdown(f"**純資産合計:** `¥{report.total_equity:,}`")

        st.divider()
        st.metric(
            "負債・純資産の部 合計",
            f"¥{(report.total_liabilities + report.total_equity):,}",
            delta="貸借一致 ✅"
            if report.total_assets == (report.total_liabilities + report.total_equity)
            else "不一致 ⚠️",
        )


# ==============================================================================
# 2. 損益計算書 (Profit & Loss: 段階利益表示)
# ==============================================================================
with tab_pl:
    st.subheader("損益計算書 (Profit & Loss Statement)")
    st.caption(f"（{selected_fy.start_date} 〜 {selected_fy.end_date} / 単位: 円）")

    # 1. 売上高 & 売上原価 -> 売上総利益
    st.markdown(
        "<div class='statement-heading'>Ⅰ 売上高 (Revenue)</div>",
        unsafe_allow_html=True,
    )
    if report.revenue.rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.revenue.rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown(f"**売上高合計:** `¥{report.revenue.total:,}`")

    st.markdown(
        "<div class='statement-heading'>Ⅱ 売上原価 (Cost of Sales)</div>",
        unsafe_allow_html=True,
    )
    if report.cost_of_sales.rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.cost_of_sales.rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown(f"**売上原価合計:** `¥{report.cost_of_sales.total:,}`")

    st.info(f"✨ **売上総損益 (粗利益):** `¥{report.gross_profit:,}`")

    # 2. 販管費 -> 営業利益
    st.markdown(
        "<div class='statement-heading'>Ⅲ 販売費及び一般管理費 (SG&A)</div>",
        unsafe_allow_html=True,
    )
    if report.sga.rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in report.sga.rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    st.markdown(f"**販売費及び一般管理費合計:** `¥{report.sga.total:,}`")

    st.info(f"🏆 **営業損益 (本業の利益):** `¥{report.operating_income:,}`")

    # 3. 営業外損益 -> 経常利益
    col_no1, col_no2 = st.columns(2)
    with col_no1:
        st.markdown(
            "<div class='statement-heading'>Ⅳ 営業外収益</div>", unsafe_allow_html=True
        )
        if report.non_op_income.rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                        for r in report.non_op_income.rows
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        st.markdown(f"**営業外収益合計:** `¥{report.non_op_income.total:,}`")

    with col_no2:
        st.markdown(
            "<div class='statement-heading'>Ⅴ 営業外費用</div>", unsafe_allow_html=True
        )
        if report.non_op_expense.rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                        for r in report.non_op_expense.rows
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        st.markdown(f"**営業外費用合計:** `¥{report.non_op_expense.total:,}`")

    st.info(f"📈 **経常損益 (事業活動の成果):** `¥{report.ordinary_income:,}`")

    # 4. 特別損益 -> 当期純利益
    if report.extra_income.rows or report.extra_loss.rows:
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.markdown(
                "<div class='statement-heading'>Ⅵ 特別利益</div>",
                unsafe_allow_html=True,
            )
            if report.extra_income.rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                            for r in report.extra_income.rows
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            st.markdown(f"**特別利益合計:** `¥{report.extra_income.total:,}`")
        with col_ex2:
            st.markdown(
                "<div class='statement-heading'>Ⅶ 特別損失</div>",
                unsafe_allow_html=True,
            )
            if report.extra_loss.rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"科目": r.account_name, "金額": f"¥{r.balance:,}"}
                            for r in report.extra_loss.rows
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            st.markdown(f"**特別損失合計:** `¥{report.extra_loss.total:,}`")

    st.divider()

    col_res1, col_res2 = st.columns(2)
    with col_res1:
        st.metric(
            "当期純損益 (Net Income)",
            f"¥{report.net_income:,}",
            delta="黒字 (利益)" if report.net_income >= 0 else "赤字 (損失)",
            delta_color="normal" if report.net_income >= 0 else "inverse",
        )
    with col_res2:
        if report.revenue.total > 0:
            profit_margin = (report.net_income / report.revenue.total) * 100
            st.metric("当期純利益率 (売上高比)", f"{profit_margin:.2f} %")
