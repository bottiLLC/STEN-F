import reflex as rx
from ...view_models.reports_state import ReportsState

def render_trial_balance_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("合計残高試算表", size="4"),
        rx.table.root(
             rx.table.header(
                 rx.table.row(
                     rx.table.column_header_cell("勘定科目"),
                     rx.table.column_header_cell("借方残高"),
                     rx.table.column_header_cell("貸方残高"),
                 )
             ),
             rx.table.body(
                 rx.foreach(
                     ReportsState.trial_balance,
                     lambda row: rx.table.row(
                         rx.table.cell(row.account_name),
                         rx.table.cell(f"{row.debit_balance:,}"),
                         rx.table.cell(f"{row.credit_balance:,}"),
                     )
                 )
             ),
             width="100%"
        ),
        width="100%"
    )
