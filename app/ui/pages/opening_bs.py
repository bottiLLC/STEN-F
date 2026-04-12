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
from ..layout import layout
from ..view_models.opening_bs_state import OpeningBSState

def account_input_row(account) -> rx.Component:
    # 資産科目であるかを判定し、視覚的なヒントとして背景色を分ける
    is_asset = account["type"].contains("Asset")
    
    return rx.hstack(
        rx.text(account["code"] + " " + account["name"], width="220px", font_weight="bold", size="3"),
        # 借方入力
        rx.input(
            placeholder="借方(Debit)",
            type="number",
            value=OpeningBSState.debit_balances[account["id"]],
            on_change=lambda val: OpeningBSState.update_debit_balance(account["id"], val),
            width="180px",
            text_align="right",
            bg=rx.cond(is_asset, "#f0f8ff", "white"),
        ),
        # 貸方入力
        rx.input(
            placeholder="貸方(Credit)",
            type="number",
            value=OpeningBSState.credit_balances[account["id"]],
            on_change=lambda val: OpeningBSState.update_credit_balance(account["id"], val),
            width="180px",
            text_align="right",
            bg=rx.cond(~is_asset, "#f5fffa", "white"),
        ),
        align_items="center",
        justify="start",
        spacing="5",
        padding_y="2",
        border_bottom="1px solid #f0f0f0",
        width="100%",
    )

def opening_bs_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("期首BS入力", size="8"),
            rx.text("資産運用法人の期首残高（6月1日付）を登録します。", color="gray"),
            
            rx.cond(
                OpeningBSState.is_loading,
                rx.center(rx.spinner(size="3"), width="100%", padding="50px"),
                rx.vstack(
                    rx.card(
                        rx.vstack(
                            # ヘッダー列
                            rx.hstack(
                                rx.text("勘定科目", width="220px", font_weight="bold", color="gray"),
                                rx.text("借方 (Assets)", width="180px", font_weight="bold", color="blue"),
                                rx.text("貸方 (Liabs / Equity)", width="180px", font_weight="bold", color="green"),
                                spacing="5",
                                padding_y="3",
                                border_bottom="2px solid #eaeaea",
                                width="100%",
                            ),
                            # 各科目の入力行
                            rx.vstack(
                                rx.foreach(
                                    OpeningBSState.bs_accounts,
                                    account_input_row
                                ),
                                width="100%",
                                spacing="0",
                            ),
                            # 合計行
                            rx.hstack(
                                rx.text("合計", width="220px", font_weight="bold", size="5"),
                                rx.text(OpeningBSState.total_debit.to_string(), width="180px", font_weight="bold", text_align="right", size="5"),
                                rx.text(OpeningBSState.total_credit.to_string(), width="180px", font_weight="bold", text_align="right", size="5"),
                                spacing="5",
                                padding_y="4",
                                border_top="2px solid #eaeaea",
                                width="100%",
                            ),
                            width="100%",
                            padding="4",
                        ),
                        width="100%",
                        border_radius="8px",
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
            on_mount=OpeningBSState.load_accounts,
            spacing="5",
            padding="2em",
            width="100%",
            align_items="center",
        )
    )
