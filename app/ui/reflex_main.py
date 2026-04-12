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
import asyncio
from core.logging import logger
from .pages.journal import journal_page
from .pages.master import master_page
from .pages.reports import reports_page
from .pages.opening_bs import opening_bs_page
from .pages.history import history_page
from app.infrastructure.db.seed_data import seed_accounts

# Run seeding on startup
try:
    asyncio.run(seed_accounts())
except Exception as e:
    logger.error("Startup Seeding Error", error=str(e), exc_info=True)

app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    ),
)

app.add_page(journal_page, route="/", title="STEN-F | 仕訳入力")
app.add_page(history_page, route="/history", title="STEN-F | 仕訳履歴")
app.add_page(master_page, route="/master", title="STEN-F | マスタ管理")
app.add_page(reports_page, route="/reports", title="STEN-F | レポート")
app.add_page(opening_bs_page, route="/opening_bs", title="STEN-F | 期首BS入力")
