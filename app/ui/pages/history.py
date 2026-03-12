import reflex as rx
from ..layout import layout
from ..view_models.journal import JournalCoordinatorState
from ..components.journal.list_view import render_journal_list

def history_page() -> rx.Component:
    """Standalone page for viewing journal history."""
    return layout(
        rx.vstack(
            rx.hstack(
                rx.heading("仕訳履歴", size="8"),
                rx.spacer(),
                # Optional: button to go back to journal input quickly
                rx.link(
                    rx.button(
                        rx.icon("notebook-pen", size=18),
                        "仕訳入力へ戻る",
                        size="3",
                        variant="soft"
                    ),
                    href="/",
                ),
                width="100%",
                align_items="center"
            ),
            
            # Re-use the existing list view component
            rx.box(
                render_journal_list(),
                width="100%",
                padding_top="1em"
            ),

            # Make sure state builds up correctly when this page is loaded directly
            on_mount=[JournalCoordinatorState.on_mount_journal],
            spacing="5",
            padding="2em",
            width="100%",
        )
    )
