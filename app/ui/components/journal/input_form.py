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

import reflex as rx
from ...view_models.journal.master import JournalMasterState
from ...view_models.journal.form import JournalFormState
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
                    value=JournalFormState.transaction_date,
                    on_change=JournalFormState.set_transaction_date,
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
                                     JournalFormState.abstract_suggestions,
                                     lambda s: rx.select.item(s, value=s)
                                 )
                             )
                        ),
                        value=JournalFormState.description,
                        on_change=JournalFormState.set_description,
                    ),
                    rx.input(
                        placeholder="取引内容を入力...",
                        value=JournalFormState.description,
                        on_change=JournalFormState.set_description,
                        width="400px",
                        list="abstract_suggestions_list" 
                    ),
                    rx.el.datalist(
                        rx.foreach(
                            JournalFormState.abstract_suggestions,
                            lambda s: rx.el.option(value=s)
                        ),
                        id="abstract_suggestions_list"
                    ),
                ),
                rx.vstack(
                    rx.text("取引先", weight="bold"),
                    rx.input(
                        placeholder="取引先名...",
                        value=JournalFormState.counterparty,
                        on_change=JournalFormState.set_counterparty,
                        width="200px"
                    ),
                ),
                rx.vstack(
                    rx.text("登録番号", weight="bold"),
                    rx.input(
                         placeholder="T + 13桁の半角数字",
                         value=JournalFormState.invoice_number,
                         on_change=JournalFormState.set_invoice_number,
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
                JournalFormState.lines,
                lambda line, i: rx.hstack(
                    rx.select.root(
                        rx.select.trigger(placeholder="勘定科目...", width="250px"),
                        rx.select.content(
                            rx.cond(
                                JournalMasterState.frequent_select_items,
                                rx.fragment(
                                    rx.select.group(
                                        rx.select.label("よく使う科目"),
                                        rx.foreach(
                                            JournalMasterState.frequent_select_items,
                                            lambda item: rx.select.item(item[1], value=item[0])
                                        )
                                    ),
                                    rx.select.separator(),
                                    rx.select.group(
                                        rx.select.label("その他の科目"),
                                        rx.foreach(
                                            JournalMasterState.other_select_items,
                                            lambda item: rx.select.item(item[1], value=item[0])
                                        )
                                    )
                                ),
                                # Fallback if no frequent items (clean state)
                                rx.select.group(
                                    rx.foreach(
                                        JournalMasterState.other_select_items,
                                        lambda item: rx.select.item(item[1], value=item[0])
                                    )
                                )
                            )
                        ),
                        value=line["account_id"],
                        on_change=lambda val: JournalFormState.update_line_account(i, val),
                    ),
                    rx.input(
                        placeholder="借方金額",
                        type="number",
                        value=line["debit"].to_string(),
                        on_change=lambda val: JournalFormState.update_line(i, "debit", val),
                        width="150px"
                    ),
                    rx.input(
                        placeholder="貸方金額",
                        type="number",
                        value=line["credit"].to_string(),
                         on_change=lambda val: JournalFormState.update_line(i, "credit", val),
                        width="150px"
                    ),
                    rx.button(
                        rx.icon("trash-2", size=18),
                        color_scheme="red",
                        variant="ghost",
                        on_click=lambda: JournalFormState.remove_line(i),
                        disabled=JournalFormState.lines.length() <= 1
                    ),
                    width="100%",
                    align_items="center",
                )
            ),
            width="100%",
            spacing="3"
        ),

        rx.button("+ 行を追加", on_click=JournalFormState.add_line, variant="outline"),
        
        rx.divider(),

        rx.divider(),
        rx.hstack(
            rx.checkbox(
                "取引先マスタに登録/更新する",
                checked=JournalFormState.register_master,
                on_change=JournalFormState.set_register_master
            ),
            rx.checkbox(
                "連続して登録する（入力内容を保持）",
                checked=JournalFormState.continuous_entry,
                on_change=JournalFormState.set_continuous_entry
            ),
            spacing="5"
        ),

        rx.hstack(
            rx.button(
                "クリア",
                on_click=JournalFormState.clear_form,
                size="3",
                variant="outline",
                color_scheme="gray",
                width="120px",
                disabled=JournalFormState.is_processing,
            ),
            rx.button(
                rx.cond(
                    JournalFormState.is_processing,
                    rx.spinner(size="2"),
                    "登録する",
                ),
                on_click=JournalFormState.submit,
                size="3",
                width="200px",
                disabled=JournalFormState.is_processing,
            ),
            spacing="5",
        ),
        
        spacing="5",
        padding="1em",
        border="1px solid #eaeaea",
        border_radius="8px",
        width="100%"
    )
