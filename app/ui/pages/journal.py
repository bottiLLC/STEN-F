import reflex as rx
from ..layout import layout
from ..view_models.journal_state import JournalState
from ..components.journal.input_form import render_journal_input
from ..components.journal.list_view import render_journal_list

def journal_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("仕訳入力", size="8"),
            
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("仕訳入力", value="input"),
                    rx.tabs.trigger("仕訳帳 (履歴)", value="list"),
                ),
                rx.tabs.content(
                    render_journal_input(),
                    value="input"
                ),
                rx.tabs.content(
                    render_journal_list(),
                    value="list"
                ),
                default_value="input",
                on_change=JournalState.handle_tab_change
            ),

            on_mount=[JournalState.on_mount_journal_page],
            spacing="5",
            padding="2em",
            width="100%",
        )
    )
