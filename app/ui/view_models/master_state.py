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

from .master_states.corporation_state import CorporationState
from .master_states.fiscal_year_state import FiscalYearState
from .master_states.account_state import AccountState
from .master_states.abstract_state import AbstractState
from .master_states.counterparty_state import CounterpartyState
from .master_states.system_state import SystemState
from ..di import DI


class MasterState(rx.State):
    """State for Master Management page."""

    # Active Tab
    current_tab: str = "corporation"

    # Data
    pass

    # --- Corporation (Moved to CorporationMixin) ---

    # --- Fiscal Year (Moved to FiscalYearMixin) ---

    # --- Account (Moved to AccountMixin) ---

    # --- Abstract (Moved to AbstractMixin) ---

    # --- Counterparty (Moved to CounterpartyMixin) ---

    # --- System (Moved to SystemMixin) ---

    # --- Load All ---
    async def load_all(self):
        """Load all master data."""
        async with DI.get_master_service() as service:
            # Get Substates
            corp_state = await self.get_state(CorporationState)
            fy_state = await self.get_state(FiscalYearState)
            acc_state = await self.get_state(AccountState)
            abs_state = await self.get_state(AbstractState)
            cp_state = await self.get_state(CounterpartyState)
            sys_state = await self.get_state(SystemState)

            # Load Data
            corp_state.corporation = await service.get_corporation()
            fy_state.fiscal_years = await service.get_fiscal_years()
            acc_state.accounts = await service.get_accounts()
            abs_state.abstracts = await service.get_abstracts()

            # Use specific load method for Counterparty to populate options
            await cp_state.load_counterparties()

            # Load System Settings
            await sys_state.load_settings()

            # Initialize Forms matches original logic
            if corp_state.corporation:
                corp_state.init_corporation_form()
