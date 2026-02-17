import reflex as rx
from ...view_models.reports_state import ReportsState

def render_general_ledger_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("総勘定元帳", size="4"),
        rx.select(
            ReportsState.account_labels,
            placeholder="勘定科目を選択...",
            on_change=ReportsState.set_gl_account_label,
            width="300px"
        ),
        rx.table.root(
             rx.table.header(
                 rx.table.row(
                     rx.table.column_header_cell("日付"),
                     rx.table.column_header_cell("摘要"),
                     rx.table.column_header_cell("借方"),
                     rx.table.column_header_cell("貸方"),
                     rx.table.column_header_cell("残高"),
                 )
             ),
             rx.table.body(
                 rx.foreach(
                     ReportsState.general_ledger,
                     lambda row: rx.table.row(
                         rx.table.cell(row["日付"]),
                         rx.table.cell(row["摘要"]),
                         rx.table.cell(f"{row['借方']:,}"),
                         rx.table.cell(f"{row['貸方']:,}"),
                         rx.table.cell(f"{row['残高']:,}"),
                     )
                 )
             ),
             width="100%"
        ),
        width="100%"
    )
