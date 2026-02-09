import streamlit as st
import pandas as pd
from config import CURRENCY_SYMBOL
from application.services.ledger_service import LedgerService

async def render_financial_statements_tab(ledger_service: LedgerService, selected_fy_id: int):
    with st.spinner("財務諸表 生成中..."):
        report = await ledger_service.generate_financial_report(selected_fy_id)
    
    c1, c2 = st.columns(2)
    
    # Helper to render sections
    def render_sec(title, section):
        st.markdown(f"**{title}**")
        if section.rows:
                data = [{"科目": r.account_name, "金額": f"{r.balance:,}"} for r in section.rows if r.balance != 0]
                if data:
                    st.dataframe(pd.DataFrame(data), hide_index=True)
        st.markdown(f"**合計: {CURRENCY_SYMBOL}{section.total:,}**")
        st.write("---")

    with c1:
        st.subheader("貸借対照表 (B/S)")
        render_sec("流動資産", report.current_assets)
        render_sec("固定資産", report.fixed_assets)
        render_sec("繰延資産", report.deferred_assets)
        st.metric("資産合計", f"{CURRENCY_SYMBOL}{report.total_assets:,}")
        
        st.divider()
        
        render_sec("流動負債", report.current_liabilities)
        render_sec("固定負債", report.fixed_liabilities)
        st.metric("負債合計", f"{CURRENCY_SYMBOL}{report.total_liabilities:,}")
        
        st.divider()
        
        render_sec("純資産 (資本金・剰余金)", report.equity)
        st.metric("純資産合計 (当期純利益込)", f"{CURRENCY_SYMBOL}{report.total_equity:,}")
        
        st.success(f"負債・純資産合計: {CURRENCY_SYMBOL}{report.total_liabilities + report.total_equity:,}")

    with c2:
        st.subheader("損益計算書 (P/L)")
        render_sec("売上高", report.revenue)
        render_sec("売上原価", report.cost_of_sales)
        st.metric("売上総利益", f"{CURRENCY_SYMBOL}{report.gross_profit:,}")
        
        render_sec("販売費及び一般管理費", report.sga)
        st.metric("営業利益", f"{CURRENCY_SYMBOL}{report.operating_income:,}")
        
        render_sec("営業外収益", report.non_op_income)
        render_sec("営業外費用", report.non_op_expense)
        st.metric("経常利益", f"{CURRENCY_SYMBOL}{report.ordinary_income:,}")
        
        render_sec("特別利益", report.extra_income)
        render_sec("特別損失", report.extra_loss)
        st.metric("税引前当期純利益", f"{CURRENCY_SYMBOL}{report.income_before_tax:,}")
        
        st.metric("当期純利益", f"{CURRENCY_SYMBOL}{report.net_income:,}", delta_color="normal")
