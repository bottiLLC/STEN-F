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

from datetime import date
from typing import Any, List
import pandas as pd
import streamlit as st
import structlog

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

# Fiscal Year Selector, PDF Button & Filter Controls
col_fy_sel, col_filter, col_pdf = st.columns([3, 3, 2])

with col_fy_sel:
    fy_options = {
        f"{fy.name} ({fy.start_date} 〜 {fy.end_date}) [{fy.status}]": fy
        for fy in fiscal_years
    }
    selected_fy_label = st.selectbox("対象会計年度", list(fy_options.keys()))
    selected_fy = fy_options[selected_fy_label]

with col_filter:
    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
    hide_zero = st.checkbox(
        "残高が 0 円の科目を非表示",
        value=True,
        help="チェックを入れると、残高が 0 円の勘定科目を非表示にしてすっきりと見やすく表示します。",
    )

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


def filter_rows(rows: List[Any], hide_zeros: bool) -> List[Any]:
    """残高ゼロの勘定科目行をフィルタリングする"""
    if not rows:
        return []
    if hide_zeros:
        return [r for r in rows if r.balance != 0]
    return rows


tab_bs, tab_pl = st.tabs(["貸借対照表 (Balance Sheet)", "損益計算書 (Profit & Loss)"])

# ==============================================================================
# 1. 貸借対照表 (Balance Sheet: 左右対称・完全高さ揃え配置)
# ==============================================================================
with tab_bs:
    st.subheader("貸借対照表 (Balance Sheet)")
    st.caption(f"（{selected_fy.name} 期末現在 / 単位: 円）")

    # 1. ヘッダー行
    col_hdr_l, col_hdr_r = st.columns(2)
    with col_hdr_l:
        st.markdown(
            "### <span class='badge-debit'>【 資産の部 (Assets) 】</span>",
            unsafe_allow_html=True,
        )
    with col_hdr_r:
        st.markdown(
            "### <span class='badge-credit'>【 負債の部 (Liabilities) 】</span>",
            unsafe_allow_html=True,
        )

    # 2. 流動資産 vs 流動負債 (同じ高さに並列配置)
    col_ca, col_cl = st.columns(2)
    with col_ca:
        st.markdown(
            "<div class='statement-heading'>Ⅰ 流動資産</div>", unsafe_allow_html=True
        )
        ca_rows = filter_rows(report.current_assets.rows, hide_zero)
        if ca_rows:
            ca_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in ca_rows
                ]
            )
            st.dataframe(ca_df, hide_index=True, use_container_width=True)
        else:
            st.caption("（該当する流動資産はありません）")

    with col_cl:
        st.markdown(
            "<div class='statement-heading'>Ⅰ 流動負債</div>", unsafe_allow_html=True
        )
        cl_rows = filter_rows(report.current_liabilities.rows, hide_zero)
        if cl_rows:
            cl_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in cl_rows
                ]
            )
            st.dataframe(cl_df, hide_index=True, use_container_width=True)
        else:
            st.caption("（該当する流動負債はありません）")

    # 3. 流動資産合計 vs 流動負債合計 (同じ高さに並列配置)
    col_cat, col_clt = st.columns(2)
    with col_cat:
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>流動資産合計:</span>
                <span class='subtotal-amount'>¥{report.current_assets.total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_clt:
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>流動負債合計:</span>
                <span class='subtotal-amount'>¥{report.current_liabilities.total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 4. 固定資産 (+繰延資産) vs 固定負債 (同じ高さに並列配置)
    col_fa, col_fl = st.columns(2)
    with col_fa:
        st.markdown(
            "<div class='statement-heading'>Ⅱ 固定資産</div>", unsafe_allow_html=True
        )
        fa_rows = filter_rows(report.fixed_assets.rows, hide_zero)
        if fa_rows:
            fa_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in fa_rows
                ]
            )
            st.dataframe(fa_df, hide_index=True, use_container_width=True)
        else:
            st.caption("（該当する固定資産はありません）")

        # 繰延資産があれば配置
        da_rows = filter_rows(report.deferred_assets.rows, hide_zero)
        if da_rows or report.deferred_assets.total > 0:
            st.markdown(
                "<div class='statement-heading'>Ⅲ 繰延資産</div>",
                unsafe_allow_html=True,
            )
            if da_rows:
                da_df = pd.DataFrame(
                    [
                        {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                        for r in da_rows
                    ]
                )
                st.dataframe(da_df, hide_index=True, use_container_width=True)

    with col_fl:
        st.markdown(
            "<div class='statement-heading'>Ⅱ 固定負債</div>",
            unsafe_allow_html=True,
        )
        fl_rows = filter_rows(report.fixed_liabilities.rows, hide_zero)
        if fl_rows:
            fl_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in fl_rows
                ]
            )
            st.dataframe(fl_df, hide_index=True, use_container_width=True)
        else:
            st.caption("（該当する固定負債はありません）")

    # 5. 固定資産合計 vs 固定負債合計 (同じ高さに並列配置)
    col_fat, col_flt = st.columns(2)
    with col_fat:
        fixed_grand_total = report.fixed_assets.total + report.deferred_assets.total
        lbl_fa = (
            "固定資産・繰延資産合計:"
            if report.deferred_assets.total > 0
            else "固定資産合計:"
        )
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>{lbl_fa}</span>
                <span class='subtotal-amount'>¥{fixed_grand_total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_flt:
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>固定負債合計:</span>
                <span class='subtotal-amount'>¥{report.fixed_liabilities.total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 6. 資産の部合計 vs 負債合計 (同じ高さに並列配置)
    col_ta, col_tl = st.columns(2)
    with col_ta:
        st.markdown(
            f"""
            <div class='statement-assets-total'>
                <span>資産の部 合計</span>
                <span class='total-amount'>¥{report.total_assets:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_tl:
        st.markdown(
            f"""
            <div class='statement-liabilities-total'>
                <span>負債合計</span>
                <span class='total-amount'>¥{report.total_liabilities:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 7. 純資産の部 & 負債・純資産合計 (右側に飛び出す形で配置)
    col_space, col_eq = st.columns(2)
    with col_space:
        st.write("")

    with col_eq:
        st.markdown(
            "### <span class='badge-credit'>【 純資産の部 (Equity) 】</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<div class='statement-heading'>Ⅰ 株主資本 / 元入金</div>",
            unsafe_allow_html=True,
        )
        eq_rows = filter_rows(report.equity.rows, hide_zero)
        if eq_rows:
            eq_df = pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in eq_rows
                ]
            )
            st.dataframe(eq_df, hide_index=True, use_container_width=True)
        else:
            st.caption("（該当する資本勘定はありません）")

        # 当期純損益
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>当期純損益:</span>
                <span class='subtotal-amount'>¥{report.net_income:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 純資産合計
        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>純資産合計:</span>
                <span class='subtotal-amount'>¥{report.total_equity:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # 負債・純資産の部 合計
        is_balanced = report.total_assets == (
            report.total_liabilities + report.total_equity
        )
        balance_badge = " (貸借一致 ✅)" if is_balanced else " (不一致 ⚠️)"
        st.markdown(
            f"""
            <div class='statement-grand-highlight'>
                <span>負債・純資産の部 合計 {balance_badge}</span>
                <span class='grand-amount'>¥{(report.total_liabilities + report.total_equity):,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ==============================================================================
# 2. 損益計算書 (Profit & Loss: 段階損益表示)
# ==============================================================================
with tab_pl:
    st.subheader("損益計算書 (Profit & Loss Statement)")
    st.caption(f"（{selected_fy.start_date} 〜 {selected_fy.end_date} / 単位: 円）")

    # 1. 売上高 & 売上原価 -> 売上総利益
    st.markdown(
        "<div class='statement-heading'>Ⅰ 売上高 (Revenue)</div>",
        unsafe_allow_html=True,
    )
    rev_rows = filter_rows(report.revenue.rows, hide_zero)
    if rev_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in rev_rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("（該当する売上科目はありません）")

    st.markdown(
        f"""
        <div class='statement-subtotal'>
            <span class='subtotal-label'>売上高合計:</span>
            <span class='subtotal-amount'>¥{report.revenue.total:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        "<div class='statement-heading'>Ⅱ 売上原価 (Cost of Sales)</div>",
        unsafe_allow_html=True,
    )
    cos_rows = filter_rows(report.cost_of_sales.rows, hide_zero)
    if cos_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in cos_rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("（該当する売上原価科目はありません）")

    st.markdown(
        f"""
        <div class='statement-subtotal'>
            <span class='subtotal-label'>売上原価合計:</span>
            <span class='subtotal-amount'>¥{report.cost_of_sales.total:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 売上総損益
    st.markdown(
        f"""
        <div class='statement-assets-total'>
            <span>✨ 売上総損益 (粗利益)</span>
            <span class='total-amount'>¥{report.gross_profit:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. 販管費 -> 営業利益
    st.markdown(
        "<div class='statement-heading'>Ⅲ 販売費及び一般管理費 (SG&A)</div>",
        unsafe_allow_html=True,
    )
    sga_rows = filter_rows(report.sga.rows, hide_zero)
    if sga_rows:
        st.dataframe(
            pd.DataFrame(
                [
                    {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                    for r in sga_rows
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.caption("（該当する販管費科目はありません）")

    st.markdown(
        f"""
        <div class='statement-subtotal'>
            <span class='subtotal-label'>販売費及び一般管理費合計:</span>
            <span class='subtotal-amount'>¥{report.sga.total:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 営業損益
    st.markdown(
        f"""
        <div class='statement-assets-total'>
            <span>🏆 営業損益 (本業の利益)</span>
            <span class='total-amount'>¥{report.operating_income:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. 営業外損益 -> 経常利益
    col_no1, col_no2 = st.columns(2)
    with col_no1:
        st.markdown(
            "<div class='statement-heading'>Ⅳ 営業外収益</div>", unsafe_allow_html=True
        )
        noi_rows = filter_rows(report.non_op_income.rows, hide_zero)
        if noi_rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                        for r in noi_rows
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("（該当科目なし）")

        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>営業外収益合計:</span>
                <span class='subtotal-amount'>¥{report.non_op_income.total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_no2:
        st.markdown(
            "<div class='statement-heading'>Ⅴ 営業外費用</div>", unsafe_allow_html=True
        )
        noe_rows = filter_rows(report.non_op_expense.rows, hide_zero)
        if noe_rows:
            st.dataframe(
                pd.DataFrame(
                    [
                        {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                        for r in noe_rows
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.caption("（該当科目なし）")

        st.markdown(
            f"""
            <div class='statement-subtotal'>
                <span class='subtotal-label'>営業外費用合計:</span>
                <span class='subtotal-amount'>¥{report.non_op_expense.total:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 経常損益
    st.markdown(
        f"""
        <div class='statement-assets-total'>
            <span>📈 経常損益 (事業活動の成果)</span>
            <span class='total-amount'>¥{report.ordinary_income:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4. 特別損益 -> 税引前当期純利益
    if report.extra_income.rows or report.extra_loss.rows:
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.markdown(
                "<div class='statement-heading'>Ⅵ 特別利益</div>",
                unsafe_allow_html=True,
            )
            exi_rows = filter_rows(report.extra_income.rows, hide_zero)
            if exi_rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                            for r in exi_rows
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("（該当科目なし）")

            st.markdown(
                f"""
                <div class='statement-subtotal'>
                    <span class='subtotal-label'>特別利益合計:</span>
                    <span class='subtotal-amount'>¥{report.extra_income.total:,}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col_ex2:
            st.markdown(
                "<div class='statement-heading'>Ⅶ 特別損失</div>",
                unsafe_allow_html=True,
            )
            exl_rows = filter_rows(report.extra_loss.rows, hide_zero)
            if exl_rows:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"勘定科目": r.account_name, "金額": f"¥{r.balance:,}"}
                            for r in exl_rows
                        ]
                    ),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("（該当科目なし）")

            st.markdown(
                f"""
                <div class='statement-subtotal'>
                    <span class='subtotal-label'>特別損失合計:</span>
                    <span class='subtotal-amount'>¥{report.extra_loss.total:,}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class='statement-assets-total'>
                <span>税引前当期純利益:</span>
                <span class='total-amount'>¥{report.income_before_tax:,}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # 当期純損益 (最終結果ハイライト)
    net_badge = " (黒字 🎯)" if report.net_income >= 0 else " (赤字 ⚠️)"
    st.markdown(
        f"""
        <div class='statement-grand-highlight'>
            <span>🎉 当期純損益 (最終成果) {net_badge}</span>
            <span class='grand-amount'>¥{report.net_income:,}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
