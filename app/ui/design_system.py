"""STEN-F UI/UX Design System foundation and global CSS injection.

Enforces industrial minimalism, solid financial terminal ergonomics,
strict color token enforcement, and uniform border-radius (4px).
"""

from __future__ import annotations

from typing import Final
import streamlit as st

# Color Palette Tokens per AGENTS.md
COLOR_BASE_BG: Final[str] = "#FFFFFF"
COLOR_SURFACE_BG: Final[str] = "#F8F9FA"
COLOR_SURFACE_ALT_BG: Final[str] = "#F1F3F5"
COLOR_BORDER: Final[str] = "#E5E7EB"
COLOR_TEXT_PRIMARY: Final[str] = "#1F2937"
COLOR_TEXT_MUTED: Final[str] = "#6B7280"
COLOR_PRIMARY_ACTION: Final[str] = "#1E3A8A"
COLOR_PRIMARY_ACTION_HOVER: Final[str] = "#2563EB"
COLOR_DANGER: Final[str] = "#DC2626"
COLOR_SUCCESS: Final[str] = "#059669"
BORDER_RADIUS: Final[str] = "4px"

GLOBAL_DESIGN_SYSTEM_CSS: Final[str] = f"""
<style>
/* Universal Sharp Engineering Geometry */
button, input, select, textarea, div[data-baseweb="input"], div[data-baseweb="select"],
div[data-testid="stMetric"], div[data-testid="stExpander"], div[data-testid="stAlert"],
div[data-testid="stForm"], div[data-testid="stFileUploader"] {{
    border-radius: {BORDER_RADIUS} !important;
}}

/* Typography: Tabular numbers for financial amounts */
div[data-testid="stMetricValue"], div[data-testid="stMetricDelta"],
span.tabular-nums, .fs-amount {{
    font-variant-numeric: tabular-nums !important;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace !important;
}}

/* Primary Buttons: Deep Industrial Navy */
button[kind="primary"] {{
    background-color: {COLOR_PRIMARY_ACTION} !important;
    color: #FFFFFF !important;
    border: 1px solid {COLOR_PRIMARY_ACTION} !important;
    border-radius: {BORDER_RADIUS} !important;
    font-weight: 600 !important;
    transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out !important;
}}
button[kind="primary"]:hover {{
    background-color: {COLOR_PRIMARY_ACTION_HOVER} !important;
    border-color: {COLOR_PRIMARY_ACTION_HOVER} !important;
    color: #FFFFFF !important;
}}

/* Secondary Buttons: Ghost Style */
button[kind="secondary"] {{
    background-color: {COLOR_BASE_BG} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
    border: 1px solid {COLOR_BORDER} !important;
    border-radius: {BORDER_RADIUS} !important;
    font-weight: 500 !important;
    transition: background-color 0.15s ease-in-out, border-color 0.15s ease-in-out !important;
}}
button[kind="secondary"]:hover {{
    background-color: {COLOR_SURFACE_BG} !important;
    border-color: #D1D5DB !important;
    color: {COLOR_TEXT_PRIMARY} !important;
}}

/* Destructive Button Class */
button.sten-btn-destructive, div.sten-destructive-wrapper button {{
    background-color: transparent !important;
    border: 1px solid {COLOR_DANGER} !important;
    color: {COLOR_DANGER} !important;
    border-radius: {BORDER_RADIUS} !important;
}}
button.sten-btn-destructive:hover, div.sten-destructive-wrapper button:hover {{
    background-color: rgba(220, 38, 38, 0.05) !important;
    color: {COLOR_DANGER} !important;
}}

/* Tabs: Minimal Industrial Navigation */
button[data-baseweb="tab"] {{
    font-size: 0.90rem !important;
    font-weight: 500 !important;
    color: {COLOR_TEXT_MUTED} !important;
    border-radius: {BORDER_RADIUS} {BORDER_RADIUS} 0 0 !important;
    padding: 8px 16px !important;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: {COLOR_PRIMARY_ACTION} !important;
    font-weight: 700 !important;
    border-bottom-color: {COLOR_PRIMARY_ACTION} !important;
}}

/* Cards and Surface Panels */
div[data-testid="stExpander"], div[data-testid="stForm"] {{
    border: 1px solid {COLOR_BORDER} !important;
    background-color: {COLOR_BASE_BG} !important;
}}

/* Minimal Dividers */
hr, div[data-testid="stDivider"] {{
    border-color: {COLOR_BORDER} !important;
    margin: 16px 0 !important;
}}

/* Headers and Titles */
h1, h2, h3, h4, h5, h6 {{
    color: {COLOR_TEXT_PRIMARY} !important;
    font-weight: 700 !important;
    letter-spacing: -0.01em !important;
}}
</style>
"""


def inject_global_design_system() -> None:
    """Inject global STEN-F industrial minimalism CSS into current Streamlit view."""
    st.markdown(GLOBAL_DESIGN_SYSTEM_CSS, unsafe_allow_html=True)
