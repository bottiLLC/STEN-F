import streamlit as st
from datetime import date
from container import Container
from application.services.ledger_service import LedgerService
from application.services.master_service import MasterService
from domain.models.fiscal_year import FiscalYear

async def render_pdf_export_tab(container: Container, ledger_service: LedgerService, master_service: MasterService, selected_fy_id: int, current_fy: FiscalYear):
    st.subheader("決算報告書 (PDF) 出力")
    
    col_p1, col_p2 = st.columns(2)
    r_date = col_p1.date_input("報告日", value=date.today())
    a_date = col_p2.date_input("監査日", value=date.today())
    
    if st.button("PDF作成 (ダウンロード)"):
        try:
            # Ensure report is fresh
            report_obj = await ledger_service.generate_financial_report(selected_fy_id)
            corp = await master_service.get_corporation()
            
            if not corp:
                st.error("法人情報が登録されていません。")
            else:
                pdf_service = container.get_pdf_service()
                pdf_bytes = pdf_service.generate_annual_report(
                    corp, report_obj, current_fy, r_date, a_date
                )
                
                st.download_button(
                    label="PDFをダウンロード",
                    data=pdf_bytes,
                    file_name=f"AnnualReport_{current_fy.name}.pdf",
                    mime="application/pdf"
                )
        except Exception as e:
            st.error(f"PDF生成エラー: {e}")
