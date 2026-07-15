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

from typing import List, Dict
from domain.models.account import Account
from domain.models.abstract import Abstract
from app.ui.di import DI
from .base import JournalState

class JournalMasterState(JournalState):
    """Holds master data for the Journal Entry module."""
    
    accounts: List[Account] = []
    abstracts: List[Abstract] = []
    
    frequent_accounts: List[Account] = []
    other_accounts: List[Account] = []
    
    frequent_select_items: List[List[str]] = []
    other_select_items: List[List[str]] = []
    account_select_items: List[List[str]] = [] 
    
    account_map: Dict[str, str] = {}
    account_label_map: Dict[int, str] = {}

    async def load_accounts(self):
        """Load accounts and abstracts from MasterService."""
        async with DI.get_master_service() as service:
            self.accounts = await service.get_accounts()
            self.abstracts = await service.get_abstracts()
            
            # Fetch Frequent IDs
            async with DI.get_journal_service() as j_service:
                f_ids = await j_service.get_frequent_account_ids(5)
            
            # Split Accounts
            self.frequent_accounts = []
            self.other_accounts = []
            
            account_dict = {a.id: a for a in self.accounts}
            
            processed_ids = set()
            for fid in f_ids:
                if fid in account_dict:
                    self.frequent_accounts.append(account_dict[fid])
                    processed_ids.add(fid)
            
            for a in self.accounts:
                if a.id not in processed_ids:
                    self.other_accounts.append(a)
                    
            def make_item(a):
                return [str(a.id), f"{a.code}: {a.name}"]

            self.frequent_select_items = [make_item(a) for a in self.frequent_accounts]
            self.other_select_items = [make_item(a) for a in self.other_accounts]
            self.account_select_items = [make_item(a) for a in self.accounts]
            
            self.account_map = {f"{a.code}: {a.name}": str(a.id) for a in self.accounts}
            self.account_label_map = {a.id: f"{a.code}: {a.name}" for a in self.accounts}
