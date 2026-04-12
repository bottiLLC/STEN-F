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
from ...view_models.reports_state import ReportsState

def render_financial_statements_tab() -> rx.Component:
    return rx.vstack(
         rx.heading("財務諸表 (B/S, P/L)", size="4"),
         rx.cond(
             ReportsState.financial_report,
             rx.vstack(
                 # Balance Sheet
                 rx.heading("貸借対照表", size="3"),
                 rx.hstack(
                     rx.vstack(
                         rx.heading("資産の部", size="2"),
                         render_section(ReportsState.financial_report.current_assets),
                         render_section(ReportsState.financial_report.fixed_assets),
                         render_section(ReportsState.financial_report.deferred_assets),
                         rx.divider(),
                         rx.hstack(rx.text("資産合計", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.total_assets:,}", weight="bold"), width="100%"),
                         width="50%",
                         align_items="start"
                     ),
                     rx.vstack(
                         rx.heading("負債の部", size="2"),
                         render_section(ReportsState.financial_report.current_liabilities),
                         render_section(ReportsState.financial_report.fixed_liabilities),
                         rx.divider(),
                         rx.hstack(rx.text("負債合計", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.total_liabilities:,}", weight="bold"), width="100%"),
                         
                         rx.heading("純資産の部", size="2"),
                         render_section(ReportsState.financial_report.equity),
                         rx.hstack(rx.text("当期純利益", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.net_income:,}", weight="bold"), width="100%"),
                         rx.divider(),
                         rx.hstack(rx.text("純資産合計", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.total_equity:,}", weight="bold"), width="100%"),
                         width="50%",
                         align_items="start"
                     ),
                     width="100%",
                     spacing="4",
                     align_items="start"
                 ),
                 rx.divider(),
                 # Profit & Loss
                 rx.heading("損益計算書", size="3"),
                 rx.vstack(
                     render_section(ReportsState.financial_report.revenue),
                     render_section(ReportsState.financial_report.cost_of_sales),
                     rx.hstack(rx.text("売上総利益", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.gross_profit:,}", weight="bold"), width="100%"),
                     
                     render_section(ReportsState.financial_report.sga),
                     rx.hstack(rx.text("営業利益", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.operating_income:,}", weight="bold"), width="100%"),
                     
                     render_section(ReportsState.financial_report.non_op_income),
                     render_section(ReportsState.financial_report.non_op_expense),
                     rx.hstack(rx.text("経常利益", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.ordinary_income:,}", weight="bold"), width="100%"),
                     
                     render_section(ReportsState.financial_report.extra_income),
                     render_section(ReportsState.financial_report.extra_loss),
                     rx.hstack(rx.text("税引前当期純利益", weight="bold"), rx.spacer(), rx.text(f"{ReportsState.financial_report.income_before_tax:,}", weight="bold"), width="100%"),
                     width="80%"
                 ),
                 width="100%"
             ),
             rx.text("データがありません。")
         ),
         width="100%"
    )

def render_section(section: rx.Var) -> rx.Component:
    return rx.vstack(
        rx.text(section.title, weight="bold", color="gray"),
        rx.foreach(
            section.rows,
            lambda r: rx.cond(
                r.balance != 0,
                rx.hstack(
                    rx.text(r.account_name),
                    rx.spacer(),
                    rx.text(f"{r.balance:,}"),
                    width="100%"
                )
            )
        ),
        rx.cond(
            section.title.contains("合計") | section.title.contains("利益"), # Not generic but section object has total
            rx.hstack(rx.text("合計", font_size="0.8em"), rx.spacer(), rx.text(f"{section.total:,}"), width="100%")
        ),
        width="100%",
        padding_left="1em"
    )
