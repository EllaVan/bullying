"""UI 尺寸、颜色与样式常量。
"""

from dataclasses import dataclass, field

# ═══════════════════════════════════════════════════════════════
# 颜色
# ═══════════════════════════════════════════════════════════════
BG_DARK = "#060b1f"
BG_CARD = "#0a1228"
BG_CARD_INNER = "#0d1630"
BORDER = "rgba(0, 242, 255, 0.25)"
ACCENT = "#00f2ff"
ACCENT_DIM = "rgba(0, 242, 255, 0.15)"
TEXT_PRIMARY = "#e8f4ff"
TEXT_SECONDARY = "#7a9bbf"
GREEN = "#00ff88"
YELLOW = "#ffcc00"
RED = "#ff3366"
PURPLE = "#9b59ff"

# ═══════════════════════════════════════════════════════════════
# 页面基础
# ═══════════════════════════════════════════════════════════════
PAGE_TITLE = "校园异常行为智能预警系统"
PAGE_ICON = "🛡️"
LAYOUT = "wide"  # Streamlit 页面布局：wide / centered

# 监测场景物理尺寸（米），影响点云/轨迹坐标范围，一般无需改动
SCENE_WIDTH = 6
SCENE_DEPTH = 5.0
SCENE_HEIGHT = 3

# 刷新间隔（毫秒）
REFRESH_INTERVAL_MS = 1000

# 风险报警
DEFAULT_ALARM_THRESHOLD = 70
RISK_LOW = 40
RISK_MEDIUM = 70


@dataclass(frozen=True)
class ModuleTitles:
    point_cloud: str = "毫米波原始点云"
    tracking: str = "人员位置分析"
    risk: str = "AI 融合 · 风险评分"
    behavior: str = "AI 行为分析"
    action: str = "霸凌动作分类"
    audio: str = "音频分析"


# ═══════════════════════════════════════════════════════════════
# 页面整体布局
# ═══════════════════════════════════════════════════════════════
@dataclass
class PageLayoutConfig:
    """页面级间距与排版。"""

    # 主内容区内边距 (CSS: 上 右 下 左)
    content_padding: str = "0.8rem 1.2rem 1rem 1.2rem"
    # 上下两行模块之间的垂直间距 (rem)
    row_gap: str = "0.6rem"

    # ── 顶栏 ──
    header_padding: str = "0.5rem 0.2rem 0.8rem"
    header_margin_bottom: str = "0.4rem"
    title_font_size: str = "1.55rem"
    status_font_size: str = "0.85rem"
    time_font_size: str = "0.9rem"


@dataclass
class RowLayoutConfig:
    """单行（上排 / 下排）三列模块的布局。"""

    # 该行每个模块容器的最小高度 (px)，增大可整体拉高该行
    module_min_height: int = 380
    # 三列宽度比例，例如 (2, 1, 1) 表示第一列占 50%
    column_weights: tuple[int, int, int] = (1, 1, 1)
    # 列间距：small / medium / large（Streamlit columns gap）
    column_gap: str = "small"


@dataclass
class DashboardLayoutConfig:
    """仪表盘整体布局 —— 最常用的调整入口。"""

    page: PageLayoutConfig = field(default_factory=PageLayoutConfig)
    # 上排：点云 | 轨迹 | 风险评分
    top_row: RowLayoutConfig = field(
        default_factory=lambda: RowLayoutConfig(module_min_height=480)
    )
    # 下排：行为分析 | 动作分类 | 音频分析
    bottom_row: RowLayoutConfig = field(
        default_factory=lambda: RowLayoutConfig(module_min_height=300)
    )


# ═══════════════════════════════════════════════════════════════
# 模块通用样式（HTML/CSS 部分）
# ═══════════════════════════════════════════════════════════════
@dataclass
class ModuleStyleConfig:
    """各模块标题、卡片、统计格等 CSS 尺寸。"""

    # 模块标题
    title_font_size: str = "1.2rem"
    title_margin_bottom: str = "0.1rem"
    title_icon_size: str = "1.2rem"

    # 卡片容器
    card_padding: str = "0.65rem 0.75rem 0.5rem"
    card_border_radius: str = "6px"
    card_corner_size: str = "12px"

    # 行为分析 · 统计网格 (2 行 × 3 列)
    stat_grid_columns: int = 2 #  几列
    stat_grid_gap: str = "0.4rem"
    stat_grid_margin: str = "0.5rem 0"
    stat_label_font_size: str = "0.8rem"
    stat_value_font_size: str = "1.1rem"

    # 动作 / 音频 · 概率条
    prob_bar_height: str = "8px"
    prob_bar_label_font_size: str = "0.76rem"
    prob_bar_wrap_margin: str = "0.35rem 0"

    # 霸凌行为指数数字
    bully_index_font_size: str = "5rem"
    bully_index_margin: str = "0.5rem 0 0.6rem"

    # 风险模块 · 状态栏
    status_bar_padding: str = "0.5rem 0.8rem"
    status_bar_main_font_size: str = "0.95rem"
    status_bar_sub_font_size: str = "0.72rem"
    risk_metrics_font_size: str = "1.0rem"
    risk_metrics_gap: str = "0.4rem"


# ═══════════════════════════════════════════════════════════════
# 各模块图表尺寸
# ═══════════════════════════════════════════════════════════════
@dataclass
class PointCloudViewConfig:
    """【上排-左】3D 点云视图参数。"""

    # 图表高度 = 上排 module_min_height - chart_height_offset
    chart_height_offset: int = 36

    # 坐标轴外扩边距（米）：越大，场景在视图内越小
    axis_pad_x: float = 0.0
    axis_pad_y: float = 0.0
    axis_pad_z: float = 0.0

    # 相机 eye：数值越大，视角越远
    camera_eye_x: float = 7.0
    camera_eye_y: float = -4.8
    camera_eye_z: float = 1.0

    # 相机观察中心（米）
    camera_center_x: float = SCENE_WIDTH / 2 - 4
    camera_center_y: float = SCENE_DEPTH / 2
    camera_center_z: float = SCENE_HEIGHT / 2 - 2

    # 3D 场景在卡片内的占比 [0~1]，缩小右边界可为 colorbar 留空
    scene_domain_x: tuple[float, float] = (0.00, 0.98)
    scene_domain_y: tuple[float, float] = (0.00, 0.98)

    # Plotly 图表像素边距
    chart_margin_l: int = 0
    chart_margin_r: int = 8
    chart_margin_t: int = 4
    chart_margin_b: int = 4

    marker_size: float = 1.8
    colorbar_len: float = 0.5
    colorbar_x: float = 0.92
    colorbar_thickness: int = 10


@dataclass
class TrackingViewConfig:
    """【上排-中】人员位置 2D 轨迹图参数。"""

    chart_height_offset: int = 40
    # 无强度条时可缩小左侧留白
    chart_margin_l: int = 8
    chart_margin_r: int = 8
    chart_margin_t: int = 8
    chart_margin_b: int = 8

    # 监测区域底板（与页面背景拉开对比）
    floor_fillcolor: str = "#0d1630"
    floor_border_color: str = "rgba(0, 242, 255, 0.55)"
    floor_border_width: int = 2

    # 网格线
    grid_color: str = "rgba(0, 242, 255, 0.22)"
    grid_width: float = 1.2
    grid_subdivisions: int = 1  # 1=整米网格；2=每 0.5m 一格

    # 图表外层背景（透明则与 Streamlit 背景融合）
    plot_paper_bgcolor: str = "rgba(0, 0, 0, 0)"
    plot_outer_bgcolor: str = "rgba(6, 11, 31, 0.35)"

    # 人员标记
    marker_size: int = 20
    marker_text_size: int = 9
    marker_outline_color: str = "#ffffff"
    marker_outline_width: int = 2
    person_colors: tuple[str, ...] = (GREEN, ACCENT, YELLOW, PURPLE, "#ff9966", "#66ccff")

    # 坐标轴
    show_axis_titles: bool = False
    show_tick_labels: bool = True
    axis_tick_font_size: int = 8


@dataclass
class RiskViewConfig:
    """【上排-右】风险评分仪表盘参数。"""

    gauge_height: int = 200
    gauge_margin_l: int = 20
    gauge_margin_r: int = 20
    gauge_margin_t: int = 30
    gauge_margin_b: int = 0
    gauge_number_font_size: int = 50
    gauge_title_font_size: int = 15
    slider_label: str = "报警阈值"


@dataclass
class BehaviorViewConfig:
    """【下排-左】行为分析模块参数。"""

    # 仅 HTML 区域，高度由 bottom_row.module_min_height 与内容共同决定
    footer_font_size: str = "0.78rem"
    footer_margin_top: str = "0.5rem"


@dataclass
class ActionViewConfig:
    """【下排-中】霸凌动作分类模块参数。"""

    # 概率条数量固定，主要调 ModuleStyleConfig 中的 prob_bar_* / bully_index_*
    pass


@dataclass
class AudioViewConfig:
    """【下排-右】音频分析模块参数。"""

    waveform_height: int = 110
    chart_margin_l: int = 30
    chart_margin_r: int = 10
    chart_margin_t: int = 5
    chart_margin_b: int = 25
    line_width: float = 1.2


# ═══════════════════════════════════════════════════════════════
# 默认配置实例
'''
DASHBOARD_LAYOUT 上/下排行高、列宽比例、列间距
MODULE_STYLE 标题、统计格、概率条、状态栏等 CSS 尺寸
POINT_CLOUD_VIEW 上排左 3D 点云相机、坐标轴、图表边距
TRACKING_VIEW 上排中 轨迹图高度、边距、标记大小
RISK_VIEW 上排右 仪表盘高度、字号、阈值滑块
BEHAVIOR_VIEW 下排左 页脚文字样式
AUDIO_VIEW 下排右 波形图高度与边距
'''
# ═══════════════════════════════════════════════════════════════
DASHBOARD_LAYOUT = DashboardLayoutConfig()
MODULE_STYLE = ModuleStyleConfig()
POINT_CLOUD_VIEW = PointCloudViewConfig()
TRACKING_VIEW = TrackingViewConfig()
RISK_VIEW = RiskViewConfig()
BEHAVIOR_VIEW = BehaviorViewConfig()
ACTION_VIEW = ActionViewConfig()
AUDIO_VIEW = AudioViewConfig()


# ── 兼容旧引用 ──
CARD_HEIGHT_TOP = DASHBOARD_LAYOUT.top_row.module_min_height
CARD_HEIGHT_BOTTOM = DASHBOARD_LAYOUT.bottom_row.module_min_height
CHART_MARGIN = dict(l=0, r=0, t=0, b=0)
