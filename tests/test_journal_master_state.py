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

import pytest
from app.ui.view_models.journal.master import JournalMasterState


@pytest.mark.asyncio
async def test_journal_master_load_accounts(container):
    """Test JournalMasterState.load_accounts parses frequent and other account select lists."""
    state = JournalMasterState()
    await state.load_accounts()

    assert len(state.accounts) > 0
    assert len(state.account_select_items) == len(state.accounts)
    assert len(state.frequent_select_items) + len(state.other_select_items) == len(
        state.accounts
    )
    assert len(state.account_map) == len(state.accounts)
    assert len(state.account_label_map) == len(state.accounts)
