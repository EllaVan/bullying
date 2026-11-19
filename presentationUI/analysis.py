
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from simulator import ActionProbs, AudioFrame, BehaviorMetrics


@dataclass
class RiskAssessment:
    score: int
    level: str
    level_color: str
    is_alarm: bool
    action_label: str
    action_confidence: float
    audio_label: str
    audio_confidence: float
    behavior_index: int
    status_text: str
    status_subtext: str
    status_color: str


def _risk_level(score: int) -> Tuple[str, str]:
    if score < 40:
        return "正常", "#00ff88"
    if score < 70:
        return "关注", "#ffcc00"
    return "高危", "#ff3366"


def assess_risk(
    risk_score: float,
    actions: ActionProbs,
    audio: AudioFrame,
    behavior: BehaviorMetrics,
    alarm_threshold: int,
) -> RiskAssessment:
    score = int(round(max(0, min(100, risk_score))))
    level, color = _risk_level(score)
    is_alarm = score >= alarm_threshold

    if actions.bullying >= 0.3:
        action_label = "霸凌斗殴"
        action_conf = actions.bullying
    else:
        action_label = "正常活动"
        action_conf = actions.normal

    if audio.scream >= 0.15:
        audio_label = "尖叫"
        audio_conf = audio.scream
    elif audio.quarrel >= 0.2:
        audio_label = "争吵"
        audio_conf = audio.quarrel
    else:
        audio_label = "正常交流"
        audio_conf = audio.normal_comm

    if is_alarm:
        status_text = "⚠ 报警触发"
        status_subtext = "检测到异常行为，请立即关注现场"
        status_color = "#ff3366"
    elif score >= 40:
        status_text = "监测关注"
        status_subtext = "行为指标升高，系统持续监测中"
        status_color = "#ffcc00"
    else:
        status_text = "监测正常"
        status_subtext = "当前无报警事件，系统持续运行中"
        status_color = "#00ff88"

    return RiskAssessment(
        score=score,
        level=level,
        level_color=color,
        is_alarm=is_alarm,
        action_label=action_label,
        action_confidence=round(action_conf * 100, 1),
        audio_label=audio_label,
        audio_confidence=round(audio_conf * 100, 1),
        behavior_index=behavior.abnormality_index,
        status_text=status_text,
        status_subtext=status_subtext,
        status_color=status_color,
    )


def fuse_risk_score(
    stage_intensity: float,
    actions: ActionProbs,
    audio: AudioFrame,
    behavior: BehaviorMetrics,
) -> float:
    """Weighted fusion of multimodal signals into 0-100 risk score."""
    action_risk = actions.bullying * 100
    audio_risk = (audio.quarrel * 0.4 + audio.scream * 0.6) * 100
    behavior_risk = min(100, behavior.abnormality_index * 2.5 + behavior.violent_motion * 3)
    base = stage_intensity * 85

    fused = (
        base * 0.25
        + action_risk * 0.30
        + audio_risk * 0.20
        + behavior_risk * 0.25
    )
    return max(5.0, min(98.0, fused))
