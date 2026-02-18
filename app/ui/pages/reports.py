import reflex as rx
from ..layout import layout
from ..view_models.reports_state import ReportsState
from ..components.reports.trial_balance import render_trial_balance_tab
from ..components.reports.financial_statements import render_financial_statements_tab
from ..components.reports.general_ledger import render_general_ledger_tab
from ..components.reports.pdf_export import render_pdf_export_tab

def reports_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("レポート", size="8"),
            
            rx.hstack(
                rx.select(
                   ReportsState.fy_options,
                   placeholder="会計年度を選択...",
                   on_change=ReportsState.set_fy_label,
                   width="300px",
                ),
                rx.button(" 再集計", on_click=ReportsState.load_report_data),
            ),
            
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("合計残高試算表", value="tb"),
                    rx.tabs.trigger("財務諸表", value="fs"),
                    rx.tabs.trigger("総勘定元帳", value="gl"),
                    rx.tabs.trigger("PDF出力", value="pdf"),
                ),
                rx.tabs.content(
                    render_trial_balance_tab(),
                    value="tb",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_financial_statements_tab(),
                    value="fs",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_general_ledger_tab(),
                    value="gl",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_pdf_export_tab(),
                    value="pdf",
                    padding_top="1em"
                ),
                default_value="tb",
            ),
            
            on_mount=ReportsState.load_fiscal_years,
            spacing="5",
            padding="2em",
            width="100%",
        )
    )

