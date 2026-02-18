import reflex as rx

# Color Palette (Premium Blue/Grey Theme)
primary_bg = "#f4f6f8"
sidebar_bg = "#1a202c"
sidebar_text_color = "#cbd5e0"
sidebar_hover_bg = "#2d3748"
accent_color = "#3182ce"
text_color = "#2d3748"

# Fonts
font_family = "Inter, 'Noto Sans JP', sans-serif"

# Styles
base_style = {
    "font_family": font_family,
    "background_color": primary_bg,
}

sidebar_style = {
    "background_color": sidebar_bg,
    "color": sidebar_text_color,
    "height": "100vh",
    "width": "250px",
    "padding": "2em",
    "position": "fixed",
    "left": "0",
    "top": "0",
    "display": ["none", "none", "flex"], # Hide on mobile (breakpoint dependent)
    "flex_direction": "column",
}

content_style = {
    "padding_left": ["0", "0", "250px"], # Adjust for fixed sidebar
    "padding_top": "2em",
    "padding_bottom": "2em",
    "background_color": primary_bg,
    "min_height": "100vh",
}

# Typography
heading_style = {
    "font_weight": "700",
    "color": text_color,
}

master_form_style = {
    "padding": "1.5em",
    "border": "1px solid #e0e0e0",
    "border_radius": "8px",
    "width": "100%",
    "background_color": "transparent",
}
