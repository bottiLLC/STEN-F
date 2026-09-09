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

import structlog
from app.domain.constants.default_accounts import DEFAULT_ACCOUNTS
from app.domain.models.account import Account

log = structlog.get_logger()


async def seed_accounts_with_service(service):
    """Seed default accounts using the provided master service."""
    existing = await service.get_accounts()
    existing_codes = {acc.code for acc in existing}

    added_count = 0
    for acc_data in DEFAULT_ACCOUNTS:
        if acc_data["code"] not in existing_codes:
            acc = Account(**acc_data)
            await service.save_account(acc)
            added_count += 1

    if added_count > 0:
        log.info("Default accounts synced", added_count=added_count)


async def seed_accounts():
    """Seed existing database with default accounts if empty, or sync missing ones."""
    # Ensure tables exist
    from app.infrastructure.db.session import init_db

    await init_db()

    from app.container import container

    async with container.master_service_scope() as service:
        await seed_accounts_with_service(service)
