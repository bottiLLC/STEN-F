"""STEN-F UI/UX Design System foundation and global CSS injection.

Enforces industrial minimalism, solid financial terminal ergonomics,
strict color token enforcement, and uniform border-radius (4px).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final
import streamlit as st

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

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
    border-color: {COLOR_BORDER} !important;
    color: {COLOR_TEXT_PRIMARY} !important;
}}

/* Standard Button Ergonomics: Industrial Dimensions & Layout Constraints */
div[data-testid="stButton"] > button,
div[data-testid="stDownloadButton"] > button,
div[data-testid="stFormSubmitButton"] > button {{
    width: auto !important;
    min-width: 140px !important;
    max-width: 220px !important;
    height: 38px !important;
    padding: 0.5rem 1.25rem !important;
    box-sizing: border-box !important;
    white-space: nowrap !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
}}

/* Enforce No Text Wrapping across all button elements */
div[data-testid="stButton"] > button *,
div[data-testid="stDownloadButton"] > button *,
div[data-testid="stFormSubmitButton"] > button * {{
    white-space: nowrap !important;
}}

/* Icon & Text Alignment: Fixed gap 6px and vertical centering */
div[data-testid="stButton"] > button [data-testid="stIconMaterial"],
div[data-testid="stDownloadButton"] > button [data-testid="stIconMaterial"],
div[data-testid="stFormSubmitButton"] > button [data-testid="stIconMaterial"] {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-size: 1.15rem !important;
    line-height: 1 !important;
    margin: 0 !important;
}}

/* Ultra-Compact Table-Row Action Buttons */
div.sten-table-btn div[data-testid="stButton"] > button,
div.sten-table-btn div[data-testid="stDownloadButton"] > button,
div.sten-table-btn div[data-testid="stFormSubmitButton"] > button,
button.sten-btn-compact {{
    min-width: unset !important;
    max-width: 160px !important;
    height: 28px !important;
    padding: 0.25rem 0.75rem !important;
    font-size: 0.85rem !important;
    white-space: nowrap !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
}}

/* Destructive Button: Ghost Outline with Danger Accent */
button.sten-btn-destructive,
div.sten-destructive-wrapper div[data-testid="stButton"] > button,
div.sten-destructive-wrapper div[data-testid="stFormSubmitButton"] > button,
[class*="st-key-sten_destructive_"] div[data-testid="stButton"] > button,
[class*="st-key-sten_destructive_"] div[data-testid="stFormSubmitButton"] > button {{
    background-color: {COLOR_BASE_BG} !important;
    border: 1px solid {COLOR_DANGER} !important;
    color: {COLOR_DANGER} !important;
    border-radius: {BORDER_RADIUS} !important;
    font-weight: 500 !important;
    white-space: nowrap !important;
}}
button.sten-btn-destructive:hover,
div.sten-destructive-wrapper div[data-testid="stButton"] > button:hover,
div.sten-destructive-wrapper div[data-testid="stFormSubmitButton"] > button:hover,
[class*="st-key-sten_destructive_"] div[data-testid="stButton"] > button:hover,
[class*="st-key-sten_destructive_"] div[data-testid="stFormSubmitButton"] > button:hover {{
    background-color: {COLOR_SURFACE_BG} !important;
    color: {COLOR_DANGER} !important;
    border-color: {COLOR_DANGER} !important;
}}

/* Critical Confirmation Modal Destructive Button: Solid Danger Accent */
[class*="st-key-sten_destructive_confirm_"] div[data-testid="stButton"] > button,
[class*="st-key-sten_destructive_confirm_"] div[data-testid="stFormSubmitButton"] > button {{
    background-color: {COLOR_DANGER} !important;
    border: 1px solid {COLOR_DANGER} !important;
    color: #FFFFFF !important;
    border-radius: {BORDER_RADIUS} !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
}}
[class*="st-key-sten_destructive_confirm_"] div[data-testid="stButton"] > button:hover,
[class*="st-key-sten_destructive_confirm_"] div[data-testid="stFormSubmitButton"] > button:hover {{
    background-color: #B91C1C !important;
    border-color: #B91C1C !important;
    color: #FFFFFF !important;
}}

/* Manual Review Danger Notice Banner */
.sten-notice-danger {{
    border: 1px solid {COLOR_DANGER};
    border-radius: {BORDER_RADIUS};
    padding: 12px;
    margin-bottom: 16px;
    background-color: {COLOR_SURFACE_BG};
}}
.sten-notice-danger-title {{
    color: {COLOR_DANGER};
    font-weight: 700;
    font-size: 1.05rem;
    margin-bottom: 4px;
}}
.sten-notice-danger-body {{
    color: {COLOR_TEXT_PRIMARY};
    font-size: 0.9rem;
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
    st.html(GLOBAL_DESIGN_SYSTEM_CSS)


def destructive_button_container(key: str) -> DeltaGenerator:
    """Create a real Streamlit container targeted by destructive-button CSS rules."""
    return st.container(key=f"sten_destructive_{key}")


def destructive_confirm_container(key: str) -> DeltaGenerator:
    """Create a real Streamlit container targeted by solid-red modal confirmation CSS rules."""
    return st.container(key=f"sten_destructive_confirm_{key}")


def render_system_diagnostic(log_path: Path) -> None:
    """Mount discrete Antigravity System Diagnostic harness inside popover.

    Args:
        log_path: Path to the centralized application log file.
    """
    st.session_state["_run_count"] = int(st.session_state.get("_run_count", 0)) + 1
    run_count: int = int(st.session_state["_run_count"])

    with st.popover("System Diagnostic", icon=":material/bug_report:"):
        st.markdown(f"**Execution Counter:** `{run_count}`")
        st.caption("Active Session State Snapshot:")
        state_snapshot: dict[str, str] = {
            str(k): (
                f"<{len(v)} bytes>"
                if isinstance(v, bytes)
                else str(v)[:100] + ("..." if len(str(v)) > 100 else "")
            )
            for k, v in st.session_state.items()
            if not str(k).startswith("_")
        }
        st.json(state_snapshot)

        # Log Tail Retrieval
        log_lines: list[str] = []
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8")
                log_lines = [line for line in content.splitlines() if line.strip()][
                    -30:
                ]
            except Exception as e:
                log_lines = [f"[Log Read Error: {e}]"]
        else:
            log_lines = ["[Log file does not exist yet]"]

        st.caption(f"Log Tail (Last {len(log_lines)} lines):")
        st.text("\n".join(log_lines))

        # Antigravity IDE markdown block for one-click triage copy-paste
        triage_payload: str = (
            "### Antigravity System Diagnostic Context\n"
            f"- **Execution Count:** `{run_count}`\n"
            f"- **Session Keys:** `{list(st.session_state.keys())}`\n"
            "\n#### Recent Execution Logs (Tail 30)\n"
            "```log\n" + "\n".join(log_lines) + "\n```\n"
        )
        st.caption("Antigravity Prompt Context (Click to copy):")
        st.code(triage_payload, language="markdown")
