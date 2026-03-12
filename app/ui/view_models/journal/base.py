import reflex as rx

class JournalState(rx.State):
    """
    Base state for the Journal Entry module.
    Substates will inherit from this to group related logic and share the same WebSocket channel scope properly.
    """
    pass
