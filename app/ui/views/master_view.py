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

from __future__ import annotations

import streamlit as st

from app.core_foundation import call_master
from app.domain_contracts import (
    account_code_sort_key,
    compute_next_fiscal_year_dates,
)
from app.ui.master_sections import (
    render_abstracts_section,
    render_accounts_section,
    render_corp_section,
    render_counterparties_section,
    render_fiscal_year_section,
    render_opening_balance_section,
    render_system_section,
)

__all__ = ["compute_next_fiscal_year_dates", "main"]


_MASTER_SECTIONS: tuple[str, ...] = (
    "自社情報",
    "会計年度・年度締め",
    "期首残高設定",
    "勘定科目",
    "取引先",
    "よく使う摘要",
    "AI・システム設定",
)


def main() -> None:
    """Render master and system settings workspace using segmented section selector."""
    st.header("マスタ・システム設定", divider="gray")

    fys = call_master(lambda s: s.get_fiscal_years())
    accounts = call_master(lambda s: s.get_accounts())
    sorted_accounts = sorted(accounts, key=lambda a: account_code_sort_key(a.code))
    account_options = [f"{a.code}: {a.name}" for a in sorted_accounts]
    acc_id_to_label = {a.id: f"{a.code}: {a.name}" for a in accounts}
    acc_label_to_id = {f"{a.code}: {a.name}": a.id for a in accounts}

    selected_section = st.segmented_control(
        "設定項目",
        options=list(_MASTER_SECTIONS),
        default=_MASTER_SECTIONS[0],
        selection_mode="single",
        key="master_section_selector",
        label_visibility="collapsed",
    )

    section = selected_section or _MASTER_SECTIONS[0]
    if section == "自社情報":
        render_corp_section()
    elif section == "会計年度・年度締め":
        render_fiscal_year_section(fys)
    elif section == "期首残高設定":
        render_opening_balance_section(fys, sorted_accounts)
    elif section == "勘定科目":
        render_accounts_section(sorted_accounts)
    elif section == "取引先":
        render_counterparties_section(account_options, acc_id_to_label, acc_label_to_id)
    elif section == "よく使う摘要":
        render_abstracts_section(account_options, acc_id_to_label, acc_label_to_id)
    elif section == "AI・システム設定":
        render_system_section()


if __name__ == "__main__":
    main()
