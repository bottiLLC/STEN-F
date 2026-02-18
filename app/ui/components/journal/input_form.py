import reflex as rx
from ...view_models.journal_state import JournalState
from .ocr_upload import render_ocr_upload_area

def render_journal_input() -> rx.Component:
    return rx.vstack(
        # OCR Section
        render_ocr_upload_area(),
        
        rx.divider(),

        # Top Form
        rx.vstack(
            # Row 1: Date
            rx.vstack(
                rx.text("取引日", weight="bold"),
                rx.input(
                    type="date",
                    value=JournalState.transaction_date,
                    on_change=JournalState.set_transaction_date,
                    width="150px"
                ),
            ),
            
            # Row 2: Description, Counterparty, Invoice
            rx.hstack(
                rx.vstack(
                    rx.text("摘要", weight="bold"),
                    # Abstract Helper Select
                    rx.select.root(
                        rx.select.trigger(placeholder="よく使う摘要...", width="400px"),
                        rx.select.content(
                             rx.select.group(
                                 rx.foreach(
                                     JournalState.abstract_suggestions,
                                     lambda s: rx.select.item(s, value=s)
                                 )
                             )
                        ),
                        value=JournalState.description,
                        on_change=JournalState.set_description,
                    ),
                    rx.input(
                        placeholder="取引内容を入力...",
                        value=JournalState.description,
                        on_change=JournalState.set_description,
                        width="400px",
                        list="abstract_suggestions_list" 
                    ),
                    rx.el.datalist(
                        rx.foreach(
                            JournalState.abstract_suggestions,
                            lambda s: rx.el.option(value=s)
                        ),
                        id="abstract_suggestions_list"
                    ),
                ),
                rx.vstack(
                    rx.text("取引先", weight="bold"),
                    rx.input(
                        placeholder="取引先名...",
                        value=JournalState.counterparty,
                        on_change=JournalState.set_counterparty,
                        width="200px"
                    ),
                ),
                rx.vstack(
                    rx.text("登録番号", weight="bold"),
                    rx.input(
                         placeholder="T + 13桁の半角数字",
                         value=JournalState.invoice_number,
                         on_change=JournalState.set_invoice_number,
                         width="200px"
                    ),
                ),
                spacing="4",
                align_items="end",
                width="100%"
            ),
            spacing="4",
            align_items="start",
            width="100%"
        ),
        
        rx.divider(),

        # Dynamic Lines
        rx.vstack(
            rx.foreach(
                JournalState.lines,
                lambda line, i: rx.hstack(
                    rx.select.root(
                        rx.select.trigger(placeholder="勘定科目...", width="250px"),
                        rx.select.content(
                            rx.select.group(
                                rx.foreach(
                                    JournalState.account_select_items,
                                    lambda item: rx.select.item(item[1], value=item[0])
                                )
                            )
                        ),
                        value=line["account_id"],
                        on_change=lambda val: JournalState.update_line_account(i, val),
                    ),
                    rx.input(
                        placeholder="借方金額",
                        type="number",
                        value=line["debit"].to_string(),
                        on_change=lambda val: JournalState.update_line(i, "debit", val),
                        width="150px"
                    ),
                    rx.input(
                        placeholder="貸方金額",
                        type="number",
                        value=line["credit"].to_string(),
                         on_change=lambda val: JournalState.update_line(i, "credit", val),
                        width="150px"
                    ),
                    rx.button(
                        rx.icon("trash-2", size=18),
                        color_scheme="red",
                        variant="ghost",
                        on_click=lambda: JournalState.remove_line(i),
                        disabled=JournalState.lines.length() <= 1
                    ),
                    width="100%",
                    align_items="center",
                )
            ),
            width="100%",
            spacing="3"
        ),

        rx.button("+ 行を追加", on_click=JournalState.add_line, variant="outline"),
        
        rx.divider(),

        rx.divider(),
        
        rx.checkbox(
            "取引先マスタに登録/更新する",
            checked=JournalState.register_master,
            on_change=JournalState.set_register_master
        ),

        rx.button("登録する", on_click=JournalState.submit, size="3", width="200px"),
        
        spacing="5",
        padding="1em",
        border="1px solid #eaeaea",
        border_radius="8px",
        width="100%"
    )
