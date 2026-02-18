import reflex as rx
from ...view_models.reports_state import ReportsState

def render_pdf_export_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("決算報告書 (PDF) 出力", size="4"),
        rx.text("以下の日付を設定して、決算報告書（貸借対照表、損益計算書、附属明細書）をPDFでダウンロードします。"),
        
        rx.hstack(
            rx.vstack(
                rx.text("報告日", weight="bold"),
                rx.input(
                    type="date", 
                    value=ReportsState.report_date, 
                    on_change=ReportsState.set_report_date
                ),
            ),
            rx.vstack(
                rx.text("監査日", weight="bold"),
                rx.input(
                    type="date", 
                    value=ReportsState.audit_date, 
                    on_change=ReportsState.set_audit_date
                ),
            ),
            spacing="5"
        ),
        
        rx.button(
            "PDFファイルをダウンロード", 
            on_click=ReportsState.export_pdf, 
            size="3", 
            width="300px"
        ),
        
        spacing="5",
        width="100%"
    )
