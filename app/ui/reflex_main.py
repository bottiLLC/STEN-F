import reflex as rx
import asyncio
from .pages.journal import journal_page
from .pages.master import master_page
from .pages.reports import reports_page
from app.infrastructure.db.seed_data import seed_accounts

# Run seeding on startup
try:
    asyncio.run(seed_accounts())
except Exception as e:
    print(f"Startup Seeding Error: {e}")

app = rx.App(
    theme=rx.theme(
        appearance="light",
        has_background=True,
        radius="large",
        accent_color="blue",
    ),
)

app.add_page(journal_page, route="/", title="STEN-F | 仕訳入力")
app.add_page(master_page, route="/master", title="STEN-F | マスタ管理")
app.add_page(reports_page, route="/reports", title="STEN-F | レポート")
