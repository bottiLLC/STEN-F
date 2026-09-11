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

from typing import Any, Callable, Dict, List, Literal, Optional
import pandas as pd
import streamlit as st


def render_accounting_editor(
    df: pd.DataFrame,
    pk_column: str = "id",
    base_key: str = "acct_editor",
    on_commit: Optional[
        Callable[[List[Dict[str, Any]], Dict[Any, Dict[str, Any]], List[Any]], Any]
    ] = None,
    column_config: Optional[Dict[str, Any]] = None,
    disabled: bool = False,
    num_rows: Literal["fixed", "dynamic"] = "dynamic",
    hide_index: bool = True,
) -> pd.DataFrame:
    """
    Key Rotation（二重コミット物理遮断）および PK 追跡（ソート・フィルタ耐性）を備えた
    自律型・高信頼会計データエディタコンポーネント。

    :param df: 表示・編集対象の pandas DataFrame
    :param pk_column: 主キー（PK）となる列名（デフォルト: 'id'）
    :param base_key: Streamlit ウィジェットのベースキー名
    :param on_commit: 変更確定時に呼び出すコールバック関数 (added_rows, pk_edited_map, pk_deleted_list)
    :param column_config: 列の表示・編集設定（st.column_config）
    :param disabled: 編集不可（閲覧専用）モードにするか
    :param num_rows: 行の動的追加/削除設定 ('dynamic' または 'fixed')
    :param hide_index: インデックス列を非表示にするか
    :return: 編集後の DataFrame
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
    raw_added: List[Dict[str, Any]] = state.get("added_rows", [])
    raw_edited: Dict[str, Dict[str, Any]] = state.get("edited_rows", {})
    raw_deleted: List[int] = state.get("deleted_rows", [])

    if not (on_commit and (raw_added or raw_edited or raw_deleted)):
        return edited_df

    # 1. 編集対象・削除対象行の PK マッピング（ソート・フィルタ耐性）
    has_pk = pk_column in df.columns
    pk_edited_map: Dict[Any, Dict[str, Any]] = (
        {
            df.iloc[int(i)][pk_column]: c
            for i, c in raw_edited.items()
            if int(i) < len(df)
        }
        if has_pk
        else {}
    )
    pk_deleted_list: List[Any] = (
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
            # Key Rotation で古いウィジェットステートを物理破棄
            st.session_state[version_key] += 1
            st.toast("変更が正常に保存されました！", icon="✅")
            st.rerun()

    return edited_df
