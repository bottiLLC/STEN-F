from typing import Optional, Any
from datetime import date
import streamlit as st
from pydantic import BaseModel, Field, ConfigDict
import pandas as pd

class AppState(BaseModel):
    """
    Type-safe definition of the application state.
    """
    # Journal Input State
    journal_lines_df: Any = Field(default=None, description="Pandas DataFrame for journal lines")
    default_date: Optional[date] = None
    default_desc: str = ""
    ocr_amount: Optional[int] = None
    ocr_account_type: Optional[str] = None
    
    # Reports State
    report_fy_id: Optional[int] = None
    report_run: bool = False
    
    # Internal
    initialized: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)

class SessionManager:
    """
    Wrapper around Streamlit's session_state to ensure type safety and centralized management.
    """
    
    def __init__(self):
        # Initialize default state if not present
        if "initialized" not in st.session_state:
            self._initialize_defaults()

    def _initialize_defaults(self):
        defaults = AppState()
        for k, v in defaults.model_dump().items():
            if k not in st.session_state:
                st.session_state[k] = v
        st.session_state["initialized"] = True

    @property
    def state(self) -> AppState:
        """Get current state as a Pydantic model snapshot."""
        # Note: We construct from st.session_state. 
        # Be careful with DataFrame which is mutable and linked by reference usually.
        return AppState(**st.session_state)

    def get(self, key: str, default: Any = None) -> Any:
        return st.session_state.get(key, default)

    def set(self, key: str, value: Any):
        """Set a value in session state with validation (conceptually)."""
        if key not in AppState.model_fields:
            # Warn or error in strict mode? For now just allow but log?
            pass
        st.session_state[key] = value

    def update(self, **kwargs):
        """Update multiple state values."""
        for k, v in kwargs.items():
            self.set(k, v)

    # --- Typed Accessors (Properties) ---

    @property
    def journal_lines_df(self) -> pd.DataFrame:
        if st.session_state.get("journal_lines_df") is None:
             st.session_state["journal_lines_df"] = pd.DataFrame(
                [{"借方": 0, "貸方": 0, "勘定科目": None}]
            )
        return st.session_state["journal_lines_df"]

    @journal_lines_df.setter
    def journal_lines_df(self, df: pd.DataFrame):
        st.session_state["journal_lines_df"] = df

    @property
    def default_date(self) -> date:
        return st.session_state.get("default_date", date.today())
    
    @default_date.setter
    def default_date(self, d: date):
        st.session_state["default_date"] = d

    @property
    def default_desc(self) -> str:
        return st.session_state.get("default_desc", "")

    @default_desc.setter
    def default_desc(self, s: str):
        st.session_state["default_desc"] = s
    
    def clear_journal_temp_data(self):
        if "default_date" in st.session_state: del st.session_state["default_date"]
        if "default_desc" in st.session_state: del st.session_state["default_desc"]
        if "ocr_amount" in st.session_state: del st.session_state["ocr_amount"]
        if "ocr_account_type" in st.session_state: del st.session_state["ocr_account_type"]

