import reflex as rx
from ...view_models.journal_state import JournalState

def render_journal_list() -> rx.Component:
    return rx.vstack(
        # Date Filter Row
        rx.hstack(
            rx.text("期間:", font_weight="bold"),
            rx.input(
                type="date",
                value=JournalState.filter_start_date,
                on_change=JournalState.set_filter_start_date,
                width="150px"
            ),
            rx.text("〜"),
            rx.input(
                type="date",
                value=JournalState.filter_end_date,
                on_change=JournalState.set_filter_end_date,
                width="150px"
            ),
            rx.button("検索", on_click=JournalState.load_entries, size="2"),
            rx.button(
                rx.icon("download", size=16),
                "CSV",
                on_click=JournalState.export_csv,
                size="2",
                variant="outline"
            ),
            rx.spacer(),
            rx.checkbox(
                "削除済を表示", 
                checked=JournalState.show_deleted, 
                on_change=JournalState.toggle_show_deleted
            ),
            width="100%",
            align_items="center",
            spacing="3",
            padding_bottom="4",
            padding_top="1em"
        ),
        rx.vstack(
            rx.foreach(
                JournalState.journal_entries,
                lambda t: rx.vstack(
                    # Card Container
                    rx.vstack(
                        # Header
                        rx.hstack(
                             rx.text(t.date, width="120px", weight="bold", size="4"),
                             rx.text(t.description, weight="bold", size="4"),
                             rx.spacer(),
                             rx.cond(
                                 t.deleted_at,
                                 rx.badge("削除済", color_scheme="red", variant="solid"),
                             ),
                             rx.text(f"ID: {t.id}", size="1", color="gray", width="50px", text_align="right"),
                             width="100%",
                             align_items="center",
                             spacing="2",
                             padding_bottom="3",
                             border_bottom="1px solid #eee"
                        ),
                        # Metadata & Actions
                        rx.hstack(
                             rx.text(f"取引先: {t.counterparty}", size="2", color="gray"),
                             rx.text(f"登録番号: {t.invoice_number}", size="2", color="gray"),
                             rx.spacer(),
                             rx.cond(
                                 t.evidence_path,
                                 rx.button(
                                     rx.icon("file-text", size=16),
                                     "証憑",
                                     size="1",
                                     variant="soft",
                                     on_click=lambda: JournalState.download_evidence(t.id)
                                 )
                             ),
                             rx.cond(
                                 t.deleted_at,
                                 rx.text(f"削除日時: {t.deleted_at}", size="2", color="red"),
                                 rx.button(
                                     rx.icon("trash-2", size=16),
                                     "削除",
                                     color_scheme="red",
                                     variant="outline",
                                     size="1",
                                     on_click=lambda: JournalState.delete_entry(t.id)
                                 )
                             ),
                             width="100%",
                             padding_y="3",
                             align_items="center",
                             spacing="3"
                        ),
                        # Lines Table
                        rx.table.root(
                            rx.table.header(
                                rx.table.row(
                                    rx.table.column_header_cell("勘定科目"),
                                    rx.table.column_header_cell("借方", align="right"),
                                    rx.table.column_header_cell("貸方", align="right"),
                                )
                            ),
                            rx.table.body(
                                rx.foreach(
                                    t.lines,
                                    lambda tx_line: rx.table.row(
                                        rx.table.cell(JournalState.account_label_map[tx_line.account_id]),
                                        rx.table.cell(rx.cond(tx_line.debit > 0, tx_line.debit.to_string(), ""), align="right"),
                                        rx.table.cell(rx.cond(tx_line.credit > 0, tx_line.credit.to_string(), ""), align="right"),
                                    )
                                )
                            ),
                            width="100%",
                            size="2",
                            variant="surface",
                            margin_top="2"
                        ),
                        
                        padding="2rem",
                        border="1px solid #e0e0e0",
                        border_radius="12px",
                        bg="white",
                        box_shadow="0 4px 6px rgba(0,0,0,0.05)",
                        width="100%",
                        align_items="stretch",
                        spacing="5"
                    ),
                    width="100%",
                )
            ),
            width="100%",
            spacing="3"
        ),
        spacing="6",
        width="100%"
    )
