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

import streamlit as st

ACCOUNTING_CSS = """
<style>
/* Base typography for accounting values */
.font-mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.text-right {
    text-align: right;
}

/* Debit & Credit badges */
.badge-debit {
    background-color: rgba(37, 99, 235, 0.12);
    color: #1d4ed8;
    border: 1px solid rgba(37, 99, 235, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    font-weight: 600;
}

.badge-credit {
    background-color: rgba(16, 185, 129, 0.12);
    color: #047857;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.85em;
    font-weight: 600;
}

/* Balance check cards */
.balance-card-ok {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(5, 150, 105, 0.04) 100%);
    border: 1px solid rgba(16, 185, 129, 0.3);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
}

.balance-card-error {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.04) 100%);
    border: 1px solid rgba(239, 68, 68, 0.3);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
}

/* Statement Section Headers */
.statement-heading {
    font-weight: 700;
    font-size: 1.05rem;
    padding: 6px 12px;
    background-color: rgba(100, 116, 139, 0.08);
    border-left: 4px solid #3b82f6;
    border-radius: 0 4px 4px 0;
    margin-top: 14px;
    margin-bottom: 8px;
}

.statement-total-row {
    font-weight: 700;
    background-color: rgba(100, 116, 139, 0.12);
    border-top: 2px solid #64748b;
    border-bottom: 2px solid #64748b;
    padding: 6px 12px;
}

/* T-Account visual divider */
.t-account-divider {
    border-right: 2px dashed #94a3b8;
    height: 100%;
}
</style>
"""


def apply_accounting_styles() -> None:
    """Injects custom CSS styles tailored for accounting and bookkeeping UI."""
    st.markdown(ACCOUNTING_CSS, unsafe_allow_html=True)
