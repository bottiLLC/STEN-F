import reflex as rx

class State(rx.State):
    """The base state for the app."""
    current_page: str = "journal"

    def navigate_to(self, page: str):
        self.current_page = page
        return rx.redirect(f"/{page}" if page != "journal" else "/")
