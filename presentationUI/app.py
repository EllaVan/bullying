"""Campus abnormal behavior intelligent early warning system — entry point."""

from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from analysis import assess_risk
from demo_script import DemoController
from ui import inject_global_styles, render_dashboard, render_header
from ui_config import (
    DEFAULT_ALARM_THRESHOLD,
    LAYOUT,
    PAGE_ICON,
    PAGE_TITLE,
    REFRESH_INTERVAL_MS,
)


def _init_session() -> None:
    if "controller" not in st.session_state:
        st.session_state.controller = DemoController()
    if "alarm_threshold" not in st.session_state:
        st.session_state.alarm_threshold = DEFAULT_ALARM_THRESHOLD


@st.fragment(run_every=timedelta(milliseconds=REFRESH_INTERVAL_MS))
def _live_dashboard(header_placeholder) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header_placeholder.markdown(
        f"""
        <div class="sys-header">
            <div class="sys-title">🛡️ {PAGE_TITLE}</div>
            <div class="sys-status">
                <span class="sys-time">{now}</span>
                <span><span class="online-dot"></span>在线</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    frame = st.session_state.controller.tick()
    assessment = assess_risk(
        frame.risk_score,
        frame.actions,
        frame.audio,
        frame.behavior,
        st.session_state.alarm_threshold,
    )
    render_dashboard(frame, assessment)


def main() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout=LAYOUT,
        initial_sidebar_state="collapsed",
    )
    _init_session()
    inject_global_styles()
    header_ph = render_header()
    _live_dashboard(header_ph)


if __name__ == "__main__":
    main()
