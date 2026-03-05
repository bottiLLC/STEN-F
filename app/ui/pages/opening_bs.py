import reflex as rx
from ..layout import layout
from ..view_models.opening_bs_state import OpeningBSState

def account_input_row(account) -> rx.Component:
    return rx.hstack(
        rx.text(account["code"] + " " + account["name"], width="180px", size="2"),
        rx.input(
            type="number",
            value=OpeningBSState.balances[account["id"]],
            on_change=lambda val: OpeningBSState.update_balance(account["id"], val),
            width="150px",
            text_align="right",
        ),
        align_items="center",
        justify="between",
        width="100%",
        padding_y="1",
    )

def opening_bs_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("期首BS入力", size="8"),
            rx.text("資産運用法人の期首残高（6月1日付）を登録します。", color="gray"),
            
            rx.cond(
                OpeningBSState.is_loading,
                rx.spinner(),
                rx.vstack(
                    rx.hstack(
                        # 資産の部（左）
                        rx.vstack(
                            rx.heading("資産の部", size="5", color="blue"),
                            rx.divider(),
                            rx.foreach(
                                OpeningBSState.asset_accounts,
                                account_input_row
                            ),
                            rx.divider(),
                            rx.hstack(
                                rx.text("資産合計", font_weight="bold"),
                                rx.text(OpeningBSState.total_assets.to_string(), font_weight="bold"),
                                justify="between",
                                width="100%",
                                padding_y="2",
                            ),
                            width="50%",
                            padding="4",
                            border="1px solid #eaeaea",
                            border_radius="8px",
                            bg="white",
                            align_items="stretch",
                        ),
                        
                        # 負債・純資産の部（右）
                        rx.vstack(
                            rx.heading("負債・純資産の部", size="5", color="green"),
                            rx.divider(),
                            rx.foreach(
                                OpeningBSState.liability_equity_accounts,
                                account_input_row
                            ),
                            rx.divider(),
                            rx.hstack(
                                rx.text("負債・純資産合計", font_weight="bold"),
                                rx.text(OpeningBSState.total_liabilities_equity.to_string(), font_weight="bold"),
                                justify="between",
                                width="100%",
                                padding_y="2",
                            ),
                            width="50%",
                            padding="4",
                            border="1px solid #eaeaea",
                            border_radius="8px",
                            bg="white",
                            align_items="stretch",
                        ),
                        width="100%",
                        align_items="start",
                        spacing="6",
                    ),
                    
                    # フッター部分（貸借差額と登録ボタン）
                    rx.hstack(
                        rx.hstack(
                            rx.text("貸借差額: ", font_weight="bold", size="6"),
                            rx.text(
                                OpeningBSState.difference.to_string() + " 円", 
                                color=rx.cond(OpeningBSState.is_balanced, "green", "red"),
                                font_weight="bold",
                                size="6"
                            ),
                            spacing="2"
                        ),
                        rx.button(
                            "期首残高を登録する", 
                            on_click=OpeningBSState.submit,
                            disabled=~OpeningBSState.is_balanced,
                            size="3",
                            # Reflex button color_scheme must be a literal or a Var that returns a valid color scheme name.
                            # Just using basic rx.cond on opacity or style is safer.
                            style={"opacity": rx.cond(OpeningBSState.is_balanced, "1", "0.5")}
                        ),
                        justify="between",
                        align_items="center",
                        width="100%",
                        padding="6",
                        border="1px solid #eaeaea",
                        border_radius="8px",
                        bg="white",
                        margin_top="4",
                    ),
                    width="100%",
                    max_width="900px",
                )
            ),
            
            # Initialization
            on_mount=[OpeningBSState.on_mount],
            spacing="5",
            padding="2em",
            width="100%",
            align_items="center",
        )
    )
