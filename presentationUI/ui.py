"""Dashboard layout, styling, and chart rendering."""

from __future__ import annotations

from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from analysis import RiskAssessment, assess_risk
from simulator import SimulationFrame
from ui_config import (
    ACCENT,
    AUDIO_VIEW,
    BEHAVIOR_VIEW,
    BG_CARD,
    BG_DARK,
    BORDER,
    DASHBOARD_LAYOUT,
    DEFAULT_ALARM_THRESHOLD,
    GREEN,
    MODULE_STYLE,
    ModuleTitles,
    PAGE_TITLE,
    POINT_CLOUD_VIEW,
    PURPLE,
    RED,
    RISK_VIEW,
    SCENE_DEPTH,
    SCENE_HEIGHT,
    SCENE_WIDTH,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TRACKING_VIEW,
    YELLOW,
)

TITLES = ModuleTitles()
_PAGE = DASHBOARD_LAYOUT.page
_STYLE = MODULE_STYLE


def _module_title_html(icon: str, title: str) -> str:
    return (
        f'<div class="module-title" style="color:{ACCENT};'
        f'font-size:{_STYLE.title_font_size};'
        f'margin-bottom:{_STYLE.title_margin_bottom};">'
        f'<span style="font-size:{_STYLE.title_icon_size};">{icon}</span> {title}</div>'
    )


def inject_global_styles() -> None:
    """Inject CSS once per session."""
    if st.session_state.get("_styles_injected"):
        return
    st.session_state["_styles_injected"] = True

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');

        .stApp {{
            background: {BG_DARK};
            font-family: 'Noto Sans SC', sans-serif;
        }}
        #MainMenu, footer, header {{visibility: hidden;}}
        .block-container {{
            padding: {_PAGE.content_padding};
            max-width: 100%;
        }}
        [data-testid="stVerticalBlock"] > div {{gap: {_PAGE.row_gap};}}

        .sys-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: {_PAGE.header_padding};
            border-bottom: 1px solid {BORDER};
            margin-bottom: {_PAGE.header_margin_bottom};
        }}
        .sys-title {{
            font-family: 'Orbitron', 'Noto Sans SC', sans-serif;
            font-size: {_PAGE.title_font_size};
            font-weight: 700;
            color: {ACCENT};
            letter-spacing: 2px;
            text-shadow: 0 0 12px rgba(0,242,255,0.45);
        }}
        .sys-status {{
            display: flex;
            align-items: center;
            gap: 1.2rem;
            color: {TEXT_SECONDARY};
            font-size: {_PAGE.status_font_size};
        }}
        .sys-time {{
            font-family: 'Orbitron', monospace;
            color: {TEXT_PRIMARY};
            font-size: {_PAGE.time_font_size};
        }}
        .online-dot {{
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            background: {GREEN};
            box-shadow: 0 0 8px {GREEN};
            margin-right: 6px;
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        .module-card {{
            background: linear-gradient(135deg, {BG_CARD} 0%, #0d1a35 100%);
            border: 1px solid {BORDER};
            border-radius: {_STYLE.card_border_radius};
            padding: {_STYLE.card_padding};
            position: relative;
            box-shadow: inset 0 0 20px rgba(0,242,255,0.03);
        }}
        .module-card::before, .module-card::after {{
            content: '';
            position: absolute;
            width: {_STYLE.card_corner_size}; height: {_STYLE.card_corner_size};
            border-color: {ACCENT};
            border-style: solid;
        }}
        .module-card::before {{
            top: -1px; left: -1px;
            border-width: 2px 0 0 2px;
        }}
        .module-card::after {{
            bottom: -1px; right: -1px;
            border-width: 0 2px 2px 0;
        }}
        .module-title {{
            color: {ACCENT};
            font-size: {_STYLE.title_font_size};
            font-weight: 500;
            margin-bottom: 0.35rem;
            display: flex;
            align-items: center;
            gap: 0.4rem;
        }}
        .module-title .icon {{ font-size: {_STYLE.title_icon_size}; }}

        .stat-grid {{
            display: grid;
            grid-template-columns: repeat({_STYLE.stat_grid_columns}, 1fr);
            gap: {_STYLE.stat_grid_gap};
            margin: {_STYLE.stat_grid_margin};
        }}
        .stat-item {{
            background: rgba(0,242,255,0.04);
            border: 1px solid rgba(0,242,255,0.12);
            border-radius: 4px;
            padding: 0.5rem 0.4rem;
            text-align: center;
        }}
        .stat-label {{
            color: {TEXT_SECONDARY};
            font-size: {_STYLE.stat_label_font_size};
            margin-bottom: 0.2rem;
        }}
        .stat-value {{
            font-family: 'Orbitron', monospace;
            color: {TEXT_PRIMARY};
            font-size: {_STYLE.stat_value_font_size};
            font-weight: 700;
        }}

        .prob-bar-wrap {{ margin: {_STYLE.prob_bar_wrap_margin}; }}
        .prob-bar-label {{
            display: flex;
            justify-content: space-between;
            color: {TEXT_SECONDARY};
            font-size: {_STYLE.prob_bar_label_font_size};
            margin-bottom: 0.15rem;
        }}
        .prob-bar-bg {{
            height: {_STYLE.prob_bar_height};
            background: rgba(255,255,255,0.06);
            border-radius: 4px;
            overflow: hidden;
        }}
        .prob-bar-fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.4s ease;
        }}

        .status-bar {{
            border-radius: 4px;
            padding: {_STYLE.status_bar_padding};
            text-align: center;
            margin-top: 0.4rem;
        }}
        .status-bar .main {{
            font-size: {_STYLE.status_bar_main_font_size};
            font-weight: 600;
        }}
        .status-bar .sub {{
            font-size: {_STYLE.status_bar_sub_font_size};
            opacity: 0.85;
            margin-top: 0.15rem;
        }}

        .behavior-footer {{
            color: {TEXT_SECONDARY};
            font-size: {BEHAVIOR_VIEW.footer_font_size};
            margin-top: {BEHAVIOR_VIEW.footer_margin_top};
            padding-top: 0.4rem;
            border-top: 1px solid rgba(0,242,255,0.1);
        }}

        .bully-index {{
            text-align: center;
            margin: {_STYLE.bully_index_margin};
        }}
        .bully-index .label {{
            color: {TEXT_SECONDARY};
            font-size: {_STYLE.prob_bar_label_font_size};
        }}
        .bully-index .value {{
            font-family: 'Orbitron', monospace;
            font-size: {_STYLE.bully_index_font_size};
            font-weight: 700;
            color: {RED};
        }}

        div[data-testid="stPlotlyChart"] {{
            background: transparent !important;
        }}
        .stSlider label, .stSlider p {{
            color: {TEXT_SECONDARY} !important;
            font-size: 0.78rem !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    placeholder = st.empty()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    placeholder.markdown(
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
    return placeholder


def _scene_axis(label: str, axis_range: list[float]) -> dict:
    return dict(
        backgroundcolor="rgba(6,11,31,0)",
        gridcolor="rgba(0,242,255,0.12)",
        showbackground=True,
        zerolinecolor="rgba(0,242,255,0.2)",
        color=TEXT_SECONDARY,
        title=dict(text=label, font=dict(color=TEXT_SECONDARY, size=10)),
        tickfont=dict(color=TEXT_SECONDARY, size=9),
        range=axis_range,
    )


def build_point_cloud_figure(frame: SimulationFrame) -> go.Figure:
    """3D point cloud with coordinate system filling the module (tunable via ui_config)."""
    pc = frame.point_cloud
    cfg = POINT_CLOUD_VIEW
    x_min, x_max = -cfg.axis_pad_x, SCENE_WIDTH + cfg.axis_pad_x
    y_min, y_max = -cfg.axis_pad_y, SCENE_DEPTH + cfg.axis_pad_y
    z_min, z_max = -cfg.axis_pad_z, SCENE_HEIGHT + cfg.axis_pad_z
    fig = go.Figure()

    # Floor grid — makes the coordinate frame fill the visible area
    for i in range(int(SCENE_WIDTH) + 1):
        fig.add_trace(
            go.Scatter3d(
                x=[i, i], y=[0, SCENE_DEPTH], z=[0, 0],
                mode="lines",
                line=dict(color="rgba(0,242,255,0.15)", width=2),
                showlegend=False,
                hoverinfo="skip",
            )
        )
    for j in range(int(SCENE_DEPTH) + 1):
        fig.add_trace(
            go.Scatter3d(
                x=[0, SCENE_WIDTH], y=[j, j], z=[0, 0],
                mode="lines",
                line=dict(color="rgba(0,242,255,0.15)", width=2),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    # Scene boundary edges
    corners = [
        (0, 0), (SCENE_WIDTH, 0), (SCENE_WIDTH, SCENE_DEPTH), (0, SCENE_DEPTH), (0, 0),
    ]
    fig.add_trace(
        go.Scatter3d(
            x=[c[0] for c in corners],
            y=[c[1] for c in corners],
            z=[0] * len(corners),
            mode="lines",
            line=dict(color="rgba(0,242,255,0.35)", width=3),
            showlegend=False,
            hoverinfo="skip",
        )
    )
    for cx, cy in [(0, 0), (SCENE_WIDTH, 0), (SCENE_WIDTH, SCENE_DEPTH), (0, SCENE_DEPTH)]:
        fig.add_trace(
            go.Scatter3d(
                x=[cx, cx], y=[cy, cy], z=[0, SCENE_HEIGHT],
                mode="lines",
                line=dict(color="rgba(0,242,255,0.2)", width=1),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    fig.add_trace(
        go.Scatter3d(
            x=pc.xs,
            y=pc.ys,
            z=pc.zs,
            mode="markers",
            marker=dict(
                size=cfg.marker_size,
                color=pc.colors,
                colorscale=[
                    [0.0, PURPLE],
                    [0.4, ACCENT],
                    [0.7, GREEN],
                    [1.0, YELLOW],
                ],
                opacity=0.85,
                colorbar=dict(
                    title=dict(text="强度", font=dict(color=TEXT_SECONDARY, size=10)),
                    tickfont=dict(color=TEXT_SECONDARY, size=9),
                    len=cfg.colorbar_len,
                    thickness=cfg.colorbar_thickness,
                    x=cfg.colorbar_x,
                    bgcolor="rgba(0,0,0,0)",
                    bordercolor="rgba(0,242,255,0.2)",
                ),
            ),
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        height=DASHBOARD_LAYOUT.top_row.module_min_height - cfg.chart_height_offset,
        margin=dict(
            l=cfg.chart_margin_l,
            r=cfg.chart_margin_r,
            t=cfg.chart_margin_t,
            b=cfg.chart_margin_b,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        uirevision="point_cloud",
        scene=dict(
            xaxis=_scene_axis("X (m)", [x_min, x_max]),
            yaxis=_scene_axis("Y (m)", [y_min, y_max]),
            zaxis=_scene_axis("Z (m)", [z_min, z_max]),
            aspectmode="manual",
            aspectratio=dict(
                x=x_max - x_min,
                y=y_max - y_min,
                z=z_max - z_min,
            ),
            domain=dict(x=list(cfg.scene_domain_x), y=list(cfg.scene_domain_y)),
            bgcolor="rgba(6,11,31,0)",
            camera=dict(
                eye=dict(x=cfg.camera_eye_x, y=cfg.camera_eye_y, z=cfg.camera_eye_z),
                center=dict(
                    x=cfg.camera_center_x,
                    y=cfg.camera_center_y,
                    z=cfg.camera_center_z,
                ),
            ),
        ),
        showlegend=False,
    )
    return fig


def build_tracking_figure(frame: SimulationFrame) -> go.Figure:
    """2D top-down person position view — floor panel with clear contrast, no intensity scale."""
    cfg = TRACKING_VIEW
    fig = go.Figure()

    step = 1.0 / max(cfg.grid_subdivisions, 1)
    grid_x_vals = [i * step for i in range(int(SCENE_WIDTH / step) + 1)]
    grid_y_vals = [i * step for i in range(int(SCENE_DEPTH / step) + 1)]

    for gx in grid_x_vals:
        fig.add_trace(
            go.Scatter(
                x=[gx, gx], y=[0, SCENE_DEPTH],
                mode="lines",
                line=dict(color=cfg.grid_color, width=cfg.grid_width),
                showlegend=False,
                hoverinfo="skip",
            )
        )
    for gy in grid_y_vals:
        fig.add_trace(
            go.Scatter(
                x=[0, SCENE_WIDTH], y=[gy, gy],
                mode="lines",
                line=dict(color=cfg.grid_color, width=cfg.grid_width),
                showlegend=False,
                hoverinfo="skip",
            )
        )

    for i, p in enumerate(frame.persons):
        c = cfg.person_colors[i % len(cfg.person_colors)]
        fig.add_trace(
            go.Scatter(
                x=[p.x], y=[p.y],
                mode="markers+text",
                marker=dict(
                    size=cfg.marker_size,
                    color=c,
                    line=dict(color=cfg.marker_outline_color, width=cfg.marker_outline_width),
                ),
                text=[p.id],
                textposition="middle center",
                textfont=dict(color="white", size=cfg.marker_text_size, family="Orbitron"),
                name=p.id,
                showlegend=False,
                hoverinfo="text",
                hovertext=f"{p.id}: ({p.x:.1f}, {p.y:.1f}) m",
            )
        )

    if cfg.show_axis_titles:
        x_title = dict(text="X (m)", font=dict(color=TEXT_SECONDARY, size=cfg.axis_tick_font_size + 2))
        y_title = dict(text="Y (m)", font=dict(color=TEXT_SECONDARY, size=cfg.axis_tick_font_size + 2))
    else:
        x_title = dict(text="")
        y_title = dict(text="")

    tick_cfg = dict(
        showticklabels=cfg.show_tick_labels,
        tickfont=dict(color=TEXT_SECONDARY, size=cfg.axis_tick_font_size),
        ticklen=4 if cfg.show_tick_labels else 0,
        tickcolor="rgba(0,242,255,0.35)",
    )

    fig.update_layout(
        height=DASHBOARD_LAYOUT.top_row.module_min_height - cfg.chart_height_offset,
        margin=dict(
            l=cfg.chart_margin_l,
            r=cfg.chart_margin_r,
            t=cfg.chart_margin_t,
            b=cfg.chart_margin_b,
        ),
        paper_bgcolor=cfg.plot_paper_bgcolor,
        plot_bgcolor=cfg.plot_outer_bgcolor,
        xaxis=dict(
            range=[0, SCENE_WIDTH],
            showgrid=False,
            zeroline=False,
            title=x_title,
            scaleanchor="y",
            scaleratio=SCENE_WIDTH / SCENE_DEPTH,
            **tick_cfg,
        ),
        yaxis=dict(
            range=[0, SCENE_DEPTH],
            showgrid=False,
            zeroline=False,
            title=y_title,
            **tick_cfg,
        ),
        shapes=[
            dict(
                type="rect",
                x0=0,
                y0=0,
                x1=SCENE_WIDTH,
                y1=SCENE_DEPTH,
                xref="x",
                yref="y",
                fillcolor=cfg.floor_fillcolor,
                line=dict(color=cfg.floor_border_color, width=cfg.floor_border_width),
                layer="below",
            )
        ],
        uirevision="tracking",
        showlegend=False,
    )
    return fig


def build_risk_gauge(assessment: RiskAssessment) -> go.Figure:
    """Semicircular risk gauge."""
    cfg = RISK_VIEW
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=assessment.score,
            number=dict(
                font=dict(size=cfg.gauge_number_font_size, color=assessment.level_color, family="Orbitron"),
                suffix="",
            ),
            title=dict(text=assessment.level, font=dict(color=assessment.level_color, size=cfg.gauge_title_font_size)),
            gauge=dict(
                shape="angular",
                axis=dict(range=[0, 100], tickwidth=1, tickcolor=TEXT_SECONDARY,
                          tickfont=dict(color=TEXT_SECONDARY, size=9)),
                bar=dict(color=assessment.level_color, thickness=0.15),
                bgcolor="rgba(255,255,255,0.05)",
                borderwidth=0,
                steps=[
                    dict(range=[0, 40], color="rgba(0,255,136,0.15)"),
                    dict(range=[40, 70], color="rgba(255,204,0,0.15)"),
                    dict(range=[70, 100], color="rgba(255,51,102,0.2)"),
                ],
                threshold=dict(
                    line=dict(color=RED, width=3),
                    thickness=0.8,
                    value=assessment.score,
                ),
            ),
        )
    )
    fig.update_layout(
        height=cfg.gauge_height,
        margin=dict(
            l=cfg.gauge_margin_l,
            r=cfg.gauge_margin_r,
            t=cfg.gauge_margin_t,
            b=cfg.gauge_margin_b,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT_PRIMARY),
        uirevision="risk_gauge",
    )
    return fig


def build_audio_figure(frame: SimulationFrame) -> go.Figure:
    """Real-time audio waveform."""
    cfg = AUDIO_VIEW
    wf = frame.audio.waveform
    x = list(range(len(wf)))
    fig = go.Figure(
        go.Scatter(
            x=x,
            y=wf,
            mode="lines",
            line=dict(color=ACCENT, width=cfg.line_width),
            fill="tozeroy",
            fillcolor="rgba(0,242,255,0.12)",
        )
    )
    fig.update_layout(
        height=cfg.waveform_height,
        margin=dict(
            l=cfg.chart_margin_l,
            r=cfg.chart_margin_r,
            t=cfg.chart_margin_t,
            b=cfg.chart_margin_b,
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(6,11,31,0.5)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(
            range=[-1, 1],
            showgrid=True,
            gridcolor="rgba(0,242,255,0.08)",
            tickfont=dict(color=TEXT_SECONDARY, size=9),
            zerolinecolor="rgba(0,242,255,0.15)",
        ),
        uirevision="audio",
        showlegend=False,
    )
    return fig


def _prob_bar_html(label: str, pct: float, color: str) -> str:
    return f"""
    <div class="prob-bar-wrap">
        <div class="prob-bar-label"><span>{label}</span><span>{pct:.0f}%</span></div>
        <div class="prob-bar-bg">
            <div class="prob-bar-fill" style="width:{pct:.0f}%;background:{color};"></div>
        </div>
    </div>
    """


def _stat_item_html(label: str, value) -> str:
    return f"""
    <div class="stat-item">
        <div class="stat-label">{label}</div>
        <div class="stat-value">{value}</div>
    </div>
    """


def render_point_cloud_module(frame: SimulationFrame) -> None:
    st.markdown(_module_title_html("📡", TITLES.point_cloud), unsafe_allow_html=True)
    st.plotly_chart(
        build_point_cloud_figure(frame),
        width='stretch',
        config={"displayModeBar": False, "staticPlot": False},
        key="chart_point_cloud",
    )


def render_tracking_module(frame: SimulationFrame) -> None:
    st.markdown(_module_title_html("📍", TITLES.tracking), unsafe_allow_html=True)
    st.plotly_chart(
        build_tracking_figure(frame),
        width='stretch',
        config={"displayModeBar": False},
        key="chart_tracking",
    )


def render_risk_module(
    frame: SimulationFrame,
    assessment: RiskAssessment,
    alarm_threshold: int,
) -> None:
    st.markdown(_module_title_html("⚡", TITLES.risk), unsafe_allow_html=True)

    threshold = st.slider(
        RISK_VIEW.slider_label,
        min_value=50,
        max_value=95,
        value=alarm_threshold,
        key="alarm_threshold_slider",
    )
    st.session_state.alarm_threshold = threshold

    # Re-assess with updated threshold
    assessment = assess_risk(
        frame.risk_score, frame.actions, frame.audio, frame.behavior, threshold
    )

    st.plotly_chart(
        build_risk_gauge(assessment),
        width='stretch',
        config={"displayModeBar": False},
        key="chart_risk_gauge",
    )

    metrics_html = f"""
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:{_STYLE.risk_metrics_gap};
                font-size:{_STYLE.risk_metrics_font_size};color:{TEXT_SECONDARY};margin:0.2rem 0;">
        <div>动作分类<br><span style="color:{TEXT_PRIMARY};font-weight:600;">
            {assessment.action_label} {assessment.action_confidence:.0f}%</span></div>
        <div>音频主导<br><span style="color:{TEXT_PRIMARY};font-weight:600;">
            {assessment.audio_label} {assessment.audio_confidence:.0f}%</span></div>
        <div>行为异常指数<br><span style="color:{TEXT_PRIMARY};font-weight:600;
            font-family:Orbitron;">{assessment.behavior_index}</span></div>
    </div>
    <div class="status-bar" style="background:{assessment.status_color}22;
         border:1px solid {assessment.status_color}55;">
        <div class="main" style="color:{assessment.status_color};">{assessment.status_text}</div>
        <div class="sub" style="color:{TEXT_SECONDARY};">{assessment.status_subtext}</div>
    </div>
    """
    st.markdown(metrics_html, unsafe_allow_html=True)


def render_behavior_module(frame: SimulationFrame) -> None:
    b = frame.behavior
    st.markdown(_module_title_html("🧠", TITLES.behavior), unsafe_allow_html=True)
    grid_html = f"""
    <div class="stat-grid">
        {_stat_item_html("人数", b.people_count)}
        {_stat_item_html("聚集", f"{b.clustering}%")}
        {_stat_item_html("速度", b.speed)}
        {_stat_item_html("剧烈运动", f"{b.violent_motion}%")}
        {_stat_item_html("停留", f"{b.stay_duration}s")}
        {_stat_item_html("异常指数", b.abnormality_index)}
    </div>
    <div class="behavior-footer">▶ {b.summary}</div>
    """
    st.markdown(grid_html, unsafe_allow_html=True)


def render_action_module(frame: SimulationFrame) -> None:
    a = frame.actions
    bully_idx = int(round(a.bullying * 100))
    st.markdown(_module_title_html("🥊", TITLES.action), unsafe_allow_html=True)
    html = f"""
    <div class="bully-index">
        <div class="label">霸凌行为指数</div>
        <div class="value">{bully_idx}</div>
    </div>
    {_prob_bar_html("正常活动", a.normal * 100, GREEN)}
    {_prob_bar_html("霸凌斗殴", a.bullying * 100, RED)}
    """
    st.markdown(html, unsafe_allow_html=True)


def render_audio_module(frame: SimulationFrame) -> None:
    audio = frame.audio
    st.markdown(_module_title_html("🎙️", TITLES.audio), unsafe_allow_html=True)
    st.plotly_chart(
        build_audio_figure(frame),
        width='stretch',
        config={"displayModeBar": False},
        key="chart_audio",
    )
    bars_html = (
        _prob_bar_html("正常交流", audio.normal_comm * 100, GREEN)
        + _prob_bar_html("争吵", audio.quarrel * 100, YELLOW)
        + _prob_bar_html("尖叫", audio.scream * 100, RED)
    )
    st.markdown(bars_html, unsafe_allow_html=True)


def render_dashboard(frame: SimulationFrame, assessment: RiskAssessment) -> None:
    """Render the full dashboard layout."""
    alarm_threshold = st.session_state.get("alarm_threshold", DEFAULT_ALARM_THRESHOLD)
    top = DASHBOARD_LAYOUT.top_row
    bottom = DASHBOARD_LAYOUT.bottom_row

    top_cols = st.columns(list(top.column_weights), gap=top.column_gap)
    with top_cols[0]:
        with st.container(height=top.module_min_height, border=False):
            render_point_cloud_module(frame)
    with top_cols[1]:
        with st.container(height=top.module_min_height, border=False):
            render_tracking_module(frame)
    with top_cols[2]:
        with st.container(height=top.module_min_height, border=False):
            render_risk_module(frame, assessment, alarm_threshold)

    bottom_cols = st.columns(list(bottom.column_weights), gap=bottom.column_gap)
    with bottom_cols[0]:
        with st.container(height=bottom.module_min_height, border=False):
            render_behavior_module(frame)
    with bottom_cols[1]:
        with st.container(height=bottom.module_min_height, border=False):
            render_action_module(frame)
    with bottom_cols[2]:
        with st.container(height=bottom.module_min_height, border=False):
            render_audio_module(frame)
