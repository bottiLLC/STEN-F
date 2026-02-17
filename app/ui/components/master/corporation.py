import reflex as rx
from ...view_models.master_state import MasterState

def render_corporation_tab() -> rx.Component:
    return rx.vstack(
        rx.heading("法人情報編集", size="4"),
        rx.vstack(
            rx.text("法人名"),
            rx.input(value=MasterState.corp_name, on_change=MasterState.set_corp_name, width="100%"),
            rx.text("本店所在地"),
            rx.input(value=MasterState.corp_address, on_change=MasterState.set_corp_address, width="100%"),
            rx.hstack(
                rx.vstack(
                    rx.text("代表役職"),
                    rx.input(value=MasterState.corp_rep_title, on_change=MasterState.set_corp_rep_title, width="100%")
                ),
                rx.vstack(
                    rx.text("代表者氏名"),
                    rx.input(value=MasterState.corp_rep_name, on_change=MasterState.set_corp_rep_name, width="100%")
                ),
                width="100%",
                spacing="4"
            ),
            rx.button("保存する", on_click=MasterState.save_corporation, size="3"),
            spacing="4",
            width="100%"
        ),
        padding="1em",
        border="1px solid #eaeaea",
        border_radius="8px",
        width="100%"
    )
