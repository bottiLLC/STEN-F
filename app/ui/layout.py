import reflex as rx
from .components.sidebar import sidebar
from .styles import content_style

def layout(content: rx.Component) -> rx.Component:
    """The main app layout with sidebar and content area."""
    return rx.box(
        rx.flex(
            sidebar(),
            rx.box(
                content,
                style=content_style,
                width="100%",
            ),
            width="100%",
        ),
        background_color="#f4f6f8",
    )
