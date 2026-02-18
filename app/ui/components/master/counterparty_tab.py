import reflex as rx
from ...view_models.master_states.counterparty_state import CounterpartyState
from domain.models.account import AccountType
from app.ui.styles import master_form_style

def render_counterparty_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("取引先マスタ", size="4"),
        rx.text("取引先情報とインボイス登録番号、デフォルト勘定科目を管理します。"),
        
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
        rx.heading("取引先 登録・編集", size="3"),
        
        rx.text("取引先名", weight="bold"),
        rx.input(
            placeholder="例: 株式会社サンプル商事",
            value=CounterpartyState.cp_name,
            on_change=CounterpartyState.set_cp_name,
            width="100%"
        ),
        
        rx.text("取引先名（カナ）", weight="bold"),
        rx.input(
            placeholder="例: カブシキガイシャサンプルショウジ",
            value=CounterpartyState.cp_name_kana,
            on_change=CounterpartyState.set_cp_name_kana,
            width="100%"
        ),

        rx.text("インボイス登録番号", weight="bold"),
        rx.input(
            placeholder="T + 13桁の半角数字",
            value=CounterpartyState.cp_invoice_number,
            on_change=CounterpartyState.set_cp_invoice_number,
            width="100%"
        ),

        rx.text("デフォルト勘定科目", weight="bold"),
        rx.select.root(
            rx.select.trigger(placeholder="勘定科目を選択...", width="100%"),
            rx.select.content(
                rx.select.group(
                    rx.foreach(
                        CounterpartyState.cp_account_options,
                        lambda x: rx.select.item(x[1], value=x[0])
                    )
                )
            ),
            value=CounterpartyState.cp_default_account_id,
            on_change=CounterpartyState.set_cp_default_account_id,
        ),
        rx.text("※ OCR読み取り時にこの勘定科目が優先されます", font_size="0.8em", color="gray"),

        rx.hstack(
            rx.button("クリア", on_click=CounterpartyState.clear_counterparty_form, variant="outline"),
            rx.button("保存", on_click=CounterpartyState.save_counterparty_data, color_scheme="blue"),
            rx.cond(
                CounterpartyState.cp_id,
                rx.button("削除", on_click=CounterpartyState.delete_counterparty_data, color_scheme="red", variant="outline"),
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
        rx.heading("登録済み取引先一覧", size="3"),
        rx.cond(
            CounterpartyState.counterparties,
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("", width="50px"), # Checkbox column
                        rx.table.column_header_cell("取引先名"),
                        rx.table.column_header_cell("登録番号"),
                        rx.table.column_header_cell("科目種別"),
                    )
                ),
                rx.table.body(
                    rx.foreach(
                        CounterpartyState.counterparties,
                        lambda cp: rx.table.row(
                            rx.table.cell(
                                rx.cond(
                                    CounterpartyState.cp_id == cp.id,
                                    rx.icon("circle-dot", color="blue", size=20, on_click=lambda: CounterpartyState.toggle_counterparty_selection(cp, False)),
                                    rx.icon("circle", color="gray", size=20, on_click=lambda: CounterpartyState.toggle_counterparty_selection(cp, True))
                                ),
                                padding="0.5em",
                                align="center"
                            ),
                            rx.table.cell(cp.name),
                            rx.table.cell(cp.invoice_number),
                            rx.table.cell(
                                rx.cond(
                                    cp.default_account_id,
                                    "設定あり", # Simplified for now, or need a lookup map in state
                                    "-"
                                )
                            ),
                            _hover={"bg": "#f5f5f5"}
                        )
                    )
                ),
                width="100%"
            ),
            rx.text("登録された取引先はありません。")
        ),
        width="60%",
        padding="1em"
    )
