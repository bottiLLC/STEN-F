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

from collections.abc import Callable
from typing import Any, Literal
import pandas as pd
import streamlit as st


def render_accounting_editor(
    df: pd.DataFrame,
    pk_column: str = "id",
    base_key: str = "acct_editor",
    on_commit: (
        Callable[[list[dict[str, Any]], dict[Any, dict[str, Any]], list[Any]], Any]
        | None
    ) = None,
    column_config: dict[str, Any] | None = None,
    disabled: bool = False,
    num_rows: Literal["fixed", "dynamic"] = "dynamic",
    hide_index: bool = True,
) -> pd.DataFrame:
    """Render autonomous accounting data editor with Key Rotation and PK tracking.

    Args:
        df: Target pandas DataFrame to display and edit.
        pk_column: Primary key column name.
        base_key: Streamlit widget unique state base identifier.
        on_commit: Callback invoked upon commit (added_list, pk_edited_map, pk_deleted_list).
        column_config: Column presentation and validation configurations.
        disabled: Whether the table is in read-only mode.
        num_rows: Dynamic or fixed row count mode.
        hide_index: Whether index column is hidden.

    Returns:
        Edited pandas DataFrame.
    """
    version_key = f"{base_key}_version"
    if version_key not in st.session_state:
        st.session_state[version_key] = 0

    current_key = f"{base_key}_v{st.session_state[version_key]}"

    edited_df = st.data_editor(
        df,
        column_config=column_config,
        num_rows=num_rows if not disabled else "fixed",
        disabled=disabled,
        use_container_width=True,
        hide_index=hide_index,
        key=current_key,
    )

    state = st.session_state.get(current_key, {})
    raw_added: list[dict[str, Any]] = state.get("added_rows", [])
    raw_edited: dict[str, dict[str, Any]] = state.get("edited_rows", {})
    raw_deleted: list[int] = state.get("deleted_rows", [])

    if not (on_commit and (raw_added or raw_edited or raw_deleted)):
        return edited_df

    has_pk = pk_column in df.columns
    pk_edited_map: dict[Any, dict[str, Any]] = (
        {
            df.iloc[int(i)][pk_column]: c
            for i, c in raw_edited.items()
            if int(i) < len(df)
        }
        if has_pk
        else {}
    )
    pk_deleted_list: list[Any] = (
        [df.iloc[i][pk_column] for i in raw_deleted if i < len(df)] if has_pk else []
    )
    added_list = list(raw_added)

    col_info, col_save = st.columns([4, 2])
    with col_info:
        st.info(
            f"📝 変更が検出されました（追加: {len(added_list)}件, "
            f"更新: {len(pk_edited_map)}件, 削除: {len(pk_deleted_list)}件）"
        )
    with col_save:
        if st.button(
            "💾 変更をデータベースに保存する",
            type="primary",
            key=f"btn_commit_{current_key}",
            use_container_width=True,
        ):
            on_commit(added_list, pk_edited_map, pk_deleted_list)
            st.session_state[version_key] += 1
            st.toast("変更が正常に保存されました！", icon="✅")
            st.rerun()

    return edited_df
