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
from ...view_models.journal.ocr import JournalOCRState


def render_ocr_upload_area() -> rx.Component:
    return rx.vstack(
        rx.text("AI-OCR (証憑読み取り)", weight="bold"),
        rx.upload(
            rx.vstack(
                rx.button(
                    "ファイルを選択",
                    color="rgb(107,99,246)",
                    bg="white",
                    border="1px solid rgb(107,99,246)",
                ),
                rx.text(
                    "または、ここにファイルをドラッグ＆ドロップ",
                    font_size="0.8em",
                    color="gray",
                ),
            ),
            id="upload_receipt",
            accept={"application/pdf": [".pdf"], "image/*": [".png", ".jpg", ".jpeg"]},
            border="1px dotted rgb(107,99,246)",
            padding="1em",
        ),
        rx.foreach(
            rx.selected_files("upload_receipt"),
            lambda f: rx.text(f, font_size="0.8em", color="gray"),
        ),
        rx.hstack(
            rx.button(
                rx.cond(JournalOCRState.is_analyzing, "読み取り中...", "AIで読み取る"),
                on_click=JournalOCRState.handle_upload(
                    rx.upload_files("upload_receipt")
                ),
                disabled=JournalOCRState.is_analyzing,
            ),
            rx.text(
                "※ PDF, JPG, PNG対応. OpenAIを使用します",
                font_size="0.8em",
                color="gray",
            ),
            align_items="center",
        ),
        padding="1em",
        border="1px solid #e0e0e0",
        border_radius="8px",
        width="600px",
        bg="#f8f9fa",
    )
