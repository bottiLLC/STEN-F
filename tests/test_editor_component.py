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


def test_editor_key_rotation_and_pk_tracking():
    """Verify editor rendering and key versioning logic."""

    # Sample test script for AppTest
    test_code = """
import pandas as pd
import streamlit as st
from app.ui.editor import render_accounting_editor

df = pd.DataFrame([
    {"id": 101, "name": "Cash", "code": "100"},
    {"id": 102, "name": "Bank", "code": "101"},
])

def dummy_commit(added, edited, deleted):
    st.session_state["committed"] = True

render_accounting_editor(df, pk_column="id", base_key="test_editor", on_commit=dummy_commit)
"""
    at = AppTest.from_string(test_code, default_timeout=10)
    at.run()
    assert not at.exception
    assert "test_editor_version" in at.session_state
    assert at.session_state["test_editor_version"] == 0
