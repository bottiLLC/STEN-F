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
