import reflex as rx
from ..layout import layout
from ..view_models.master_state import MasterState
from ..components.master.corporation import render_corporation_tab
from ..components.master.fiscal_year import render_fiscal_year_tab
from ..components.master.account import render_account_tab
from ..components.master.abstract import render_abstract_tab
from ..components.master.counterparty_tab import render_counterparty_tab
from ..components.master.system import render_system_tab

def master_page() -> rx.Component:
    return layout(
        rx.vstack(
            rx.heading("マスタ管理", size="8"),
            
            rx.tabs.root(
                rx.tabs.list(
                    rx.tabs.trigger("法人設定", value="corporation"),
                    rx.tabs.trigger("会計年度", value="fiscal_year"),
                    rx.tabs.trigger("勘定科目", value="account"),
                    rx.tabs.trigger("取引先", value="counterparty"),
                    rx.tabs.trigger("摘要", value="abstract"),
                    rx.tabs.trigger("システム", value="system"),
                ),
                rx.tabs.content(
                    render_corporation_tab(),
                    value="corporation",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_fiscal_year_tab(),
                    value="fiscal_year",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_account_tab(),
                    value="account",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_counterparty_tab(),
                    value="counterparty",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_abstract_tab(),
                    value="abstract",
                    padding_top="1em"
                ),
                rx.tabs.content(
                    render_system_tab(),
                    value="system",
                    padding_top="1em"
                ),
                default_value="corporation",
            ),
            
            spacing="5",
            padding="2em",
            on_mount=MasterState.load_all,
            width="100%",
        )
    )
