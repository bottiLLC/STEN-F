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

def render_pdf_export_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("決算報告書 (PDF) 出力", size="4"),
        rx.text("以下の日付を設定して、決算報告書（貸借対照表、損益計算書、附属明細書）をPDFでダウンロードします。"),
        
        rx.hstack(
            rx.vstack(
                rx.text("報告日", weight="bold"),
                rx.input(
                    type="date", 
                    value=ReportsState.report_date, 
                    on_change=ReportsState.set_report_date
                ),
            ),
            rx.vstack(
                rx.text("監査日", weight="bold"),
                rx.input(
                    type="date", 
                    value=ReportsState.audit_date, 
                    on_change=ReportsState.set_audit_date
                ),
            ),
            spacing="5"
        ),
        
        rx.button(
            "PDFファイルをダウンロード", 
            on_click=ReportsState.export_pdf, 
            size="3", 
            width="300px"
        ),
        
        spacing="5",
        width="100%"
    )
