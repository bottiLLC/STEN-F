import reflex as rx
from ...view_models.master_states.journal_template_state import JournalTemplateState
from app.ui.styles import master_form_style

def render_journal_template_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("仕訳辞書マスタ", size="4"),
        rx.text("特定のキーワード（取引先名等）を含む明細が読み取られた際、自動で適用される勘定科目ルールを管理します。OCR時の自動学習結果もここに登録されます。"),
        
        rx.hstack(
            _render_form(),
            _render_list(),
            width="100%",
            spacing="5",
            align_items="start"
        ),
        width="100%"
    )

def _render_form() -> rx.Component:
    return rx.vstack(
        rx.heading("仕訳辞書ルール 登録・編集", size="3"),
        
        rx.text("キーワード (取引先名等)", weight="bold"),
        rx.input(
            placeholder="例: Amazon, 株式会社サンプル",
            value=JournalTemplateState.jt_keyword,
            on_change=JournalTemplateState.set_jt_keyword,
            width="100%"
        ),
        
        rx.text("借方科目", weight="bold"),
        rx.select.root(
            rx.select.trigger(placeholder="借方科目を選択...", width="100%"),
            rx.select.content(
                rx.select.group(
                    rx.foreach(
                        JournalTemplateState.jt_account_options,
                        lambda x: rx.select.item(x[1], value=x[0])
                    )
                )
            ),
            value=JournalTemplateState.jt_debit_account_id,
            on_change=JournalTemplateState.set_jt_debit_account_id,
        ),

        rx.text("貸方科目", weight="bold"),
        rx.select.root(
            rx.select.trigger(placeholder="貸方科目を選択...", width="100%"),
            rx.select.content(
                rx.select.group(
                    rx.foreach(
                        JournalTemplateState.jt_account_options,
                        lambda x: rx.select.item(x[1], value=x[0])
                    )
                )
            ),
            value=JournalTemplateState.jt_credit_account_id,
            on_change=JournalTemplateState.set_jt_credit_account_id,
        ),

        rx.text("自動摘要フォーマット", weight="bold"),
        rx.input(
            placeholder="例: {keyword} 支払い",
            value=JournalTemplateState.jt_description_template,
            on_change=JournalTemplateState.set_jt_description_template,
            width="100%"
        ),

        rx.hstack(
            rx.button("クリア", on_click=JournalTemplateState.clear_template_form, variant="outline"),
            rx.button("保存", on_click=JournalTemplateState.save_template_data, color_scheme="blue"),
            rx.cond(
                JournalTemplateState.jt_id,
                rx.button("削除", on_click=JournalTemplateState.delete_template_data, color_scheme="red", variant="outline"),
            ),
            spacing="3",
            margin_top="1em",
            wrap="wrap"
        ),
        
        **dict(master_form_style, width="40%"),
        align_items="start"
    )

def _render_list() -> rx.Component:
    return rx.vstack(
        rx.heading("登録済み仕訳辞書一覧", size="3"),
        rx.cond(
            JournalTemplateState.templates,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("", width="50px"), # Checkbox column
                        rx.table.column_header_cell("キーワード"),
                        rx.table.column_header_cell("借方科目ID"),
                        rx.table.column_header_cell("貸方科目ID"),
                        rx.table.column_header_cell("摘要テンプレート"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        JournalTemplateState.templates,
                        lambda jt: rx.table.row(
                            rx.table.cell(
                                rx.cond(
                                    JournalTemplateState.jt_id == jt.id,
                                    rx.icon("circle-dot", color="blue", size=20, on_click=lambda: JournalTemplateState.toggle_template_selection(jt, False)),
                                    rx.icon("circle", color="gray", size=20, on_click=lambda: JournalTemplateState.toggle_template_selection(jt, True))
                                ),
                                padding="0.5em",
                                align="center"
                            ),
                            rx.table.cell(jt.keyword),
                            rx.table.cell(jt.debit_account_id),
                            rx.table.cell(jt.credit_account_id),
                            rx.table.cell(jt.description_template),
                            _hover={"bg": "#f5f5f5"}
                        )
                    )
                ),
                width="100%"
            ),
            rx.text("登録された仕訳辞書ルールはありません。")
        ),
        width="60%",
        padding="1em"
    )
