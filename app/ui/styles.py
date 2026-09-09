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
/* =============================================================================
   1. レスポンシブ・レイアウト最適化 (2560x1440 半画面: ~1280px に完全適合)
   ============================================================================= */

/* メインコンテンツ領域の余白スリム化 */
.block-container {
    padding-top: 1.25rem !important;
    padding-bottom: 2rem !important;
    padding-left: 1.25rem !important;
    padding-right: 1.25rem !important;
    max-width: 100% !important;
}

/* サイドバーの幅とパディングの最適化 */
[data-testid="stSidebar"] {
    min-width: 240px !important;
    max-width: 270px !important;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 1.25rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}

/* カラム間の隙間（Gap）をスリム化 */
[data-testid="column"] {
    padding: 0 0.25rem !important;
}

/* =============================================================================
   2. タイポグラフィ・ヘッダーのコンパクト化
   ============================================================================= */

h1, .stHeadingContainer h1 {
    font-size: 1.45rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.4rem !important;
}

h2, .stHeadingContainer h2 {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    margin-bottom: 0.35rem !important;
}

h3, .stHeadingContainer h3 {
    font-size: 1.05rem !important;
    font-weight: 600 !important;
    margin-bottom: 0.25rem !important;
}

h4, .stHeadingContainer h4 {
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    margin-bottom: 0.2rem !important;
}

p, .stCaption, [data-testid="stMarkdownContainer"] p {
    font-size: 0.875rem;
    line-height: 1.45;
}

/* =============================================================================
   3. フォーム入力ウィジェット（Input / Select / Number / Date）の最適化
   ============================================================================= */

/* 入力ラベル */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label {
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    margin-bottom: 0.15rem !important;
    color: #334155 !important;
}

/* テキストボックス・セレクトボックス・数値入力欄の内側パディングと文字サイズ */
input[type="text"], input[type="number"], select, [data-baseweb="select"] {
    font-size: 0.875rem !important;
    min-height: 2.2rem !important;
    height: 2.2rem !important;
}

div[data-baseweb="input"] {
    min-height: 2.2rem !important;
    height: 2.2rem !important;
}

/* ドロップダウン選択項目 */
div[data-baseweb="select"] > div {
    min-height: 2.2rem !important;
    font-size: 0.875rem !important;
}

/* ウィジェット下の余白を縮小して画面収まりを向上 */
div[data-testid="stDateInput"],
div[data-testid="stTextInput"],
div[data-testid="stSelectbox"],
div[data-testid="stNumberInput"],
div[data-testid="stCheckbox"] {
    margin-bottom: 0.35rem !important;
}

/* =============================================================================
   4. メトリック (Metrics) のコンパクト化 (1280px 幅での折り返し防止)
   ============================================================================= */

[data-testid="stMetric"] {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 0.5rem 0.75rem !important;
}

[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    color: #64748b !important;
}

[data-testid="stMetricValue"] {
    font-size: 1.25rem !important;
    font-weight: 700 !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
}

[data-testid="stMetricDelta"] {
    font-size: 0.75rem !important;
}

/* =============================================================================
   5. テーブル & データフレーム (DataFrame) の最適化
   ============================================================================= */

[data-testid="stDataFrame"], [data-testid="stTable"] {
    font-size: 0.83rem !important;
}

[data-testid="stDataFrame"] div[role="grid"] {
    border-radius: 6px !important;
}

/* =============================================================================
   6. タブ (Tabs) のコンパクト化
   ============================================================================= */

div[data-testid="stTabs"] button[role="tab"] {
    padding: 0.4rem 0.75rem !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}

/* =============================================================================
   7. 簿記・会計専用スタイリング (借方/貸方バッジ・仕訳伝票)
   ============================================================================= */

/* 等幅フォント */
.font-mono {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
}

.text-right {
    text-align: right;
}

/* 借方・貸方バッジ */
.badge-debit {
    background-color: rgba(37, 99, 235, 0.12);
    color: #1d4ed8;
    border: 1px solid rgba(37, 99, 235, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.82rem;
    font-weight: 600;
}

.badge-credit {
    background-color: rgba(16, 185, 129, 0.12);
    color: #047857;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.82rem;
    font-weight: 600;
}

/* 決算書セクションヘッダー */
.statement-heading {
    font-weight: 700;
    font-size: 0.95rem;
    padding: 4px 10px;
    background-color: rgba(100, 116, 139, 0.08);
    border-left: 4px solid #3b82f6;
    border-radius: 0 4px 4px 0;
    margin-top: 6px;
    margin-bottom: 6px;
}

/* 決算書 小計行 (流動資産合計・流動負債合計・固定資産合計など) */
.statement-subtotal {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    margin: 4px 0 10px 0;
    font-size: 0.92rem;
    font-weight: 700;
    color: #1e293b;
}

.statement-subtotal .subtotal-label {
    font-weight: 700;
    font-size: 0.92rem;
}

.statement-subtotal .subtotal-amount {
    font-size: 1.05rem;
    font-weight: 800;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #0f172a;
}

/* 決算書 資産合計ハイライト */
.statement-assets-total {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: rgba(37, 99, 235, 0.08);
    border: 1.5px solid #2563eb;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 6px 0 10px 0;
    font-size: 1rem;
    font-weight: 800;
    color: #1d4ed8;
}

.statement-assets-total .total-amount {
    font-size: 1.2rem;
    font-weight: 800;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #1e40af;
}

/* 決算書 負債合計ハイライト */
.statement-liabilities-total {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: rgba(16, 185, 129, 0.08);
    border: 1.5px solid #10b981;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 6px 0 10px 0;
    font-size: 1rem;
    font-weight: 800;
    color: #047857;
}

.statement-liabilities-total .total-amount {
    font-size: 1.2rem;
    font-weight: 800;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #065f46;
}

/* 決算書 負債・純資産合計ハイライト */
.statement-grand-highlight {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: rgba(99, 102, 241, 0.08);
    border: 2px solid #6366f1;
    border-radius: 6px;
    padding: 10px 14px;
    margin: 10px 0 12px 0;
    font-size: 1.05rem;
    font-weight: 800;
    color: #4338ca;
}

.statement-grand-highlight .grand-amount {
    font-size: 1.25rem;
    font-weight: 800;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    color: #3730a3;
}

.statement-total-row {
    font-weight: 700;
    background-color: rgba(100, 116, 139, 0.12);
    border-top: 2px solid #64748b;
    border-bottom: 2px solid #64748b;
    padding: 4px 10px;
    font-size: 0.88rem;
}

/* =============================================================================
   8. メディアクエリ (~1300px 以下の半画面時)
   ============================================================================= */
@media screen and (max-width: 1300px) {
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
    }
    input[type="text"], input[type="number"], select {
        font-size: 0.82rem !important;
    }
}
</style>
"""


def apply_accounting_styles() -> None:
    """Injects custom CSS styles tailored for accounting and bookkeeping UI."""
    st.markdown(ACCOUNTING_CSS, unsafe_allow_html=True)
