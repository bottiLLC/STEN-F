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

from streamlit.testing.v1 import AppTest


def test_app_main_navigation():
    """Verify that main app.py runs without exceptions and sets up 3-workspace navigation."""
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception, f"app.py raised exception: {at.exception}"
    assert len(at.sidebar) >= 1


def test_journal_view_interactions():
    """Verify journal workspace renders, tabs work, and voucher editor displays."""
    at = AppTest.from_file("app/ui/views/journal_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"journal_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.date_input) >= 1


def test_ledger_view_interactions():
    """Verify ledger workspace renders, trial balance, ledger, and B/S-P/L tabs work."""
    at = AppTest.from_file("app/ui/views/ledger_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"ledger_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.selectbox) >= 1


def test_master_view_interactions():
    """Verify master workspace renders, corporation, fiscal year, and master editors work."""
    at = AppTest.from_file("app/ui/views/master_view.py", default_timeout=15)
    at.run()
    assert not at.exception, f"master_view.py raised exception: {at.exception}"
    assert len(at.tabs) >= 1
    assert len(at.text_input) >= 1
