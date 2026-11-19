
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import List, Tuple

from analysis import fuse_risk_score
from simulator import (
    ActionProbs,
    PersonState,
    SimulationFrame,
    blend_target_lists,
    build_behavior_metrics,
    format_people_summary,
    generate_audio,
    generate_point_cloud,
    lerp,
    move_persons,
    sync_persons_to_targets,
)


@dataclass
class Stage:

    name: str
    duration: float
    targets: List[Tuple[float, float]]
    intensity: float
    violent_motion: float
    normal_action: float
    bullying_action: float
    stay_duration: float
    abnormality: int
    summary_detail: str
    move_speed: float = 0.8


STAGES: List[Stage] = [
    Stage(
        name="快速入场",
        duration=2.0,
        targets=[
            (1.0, 0.9),
            (2.8, 1.2),
            (4.8, 1.0),
        ],
        intensity=0.06,
        violent_motion=2.0,
        normal_action=0.96,
        bullying_action=0.04,
        stay_duration=2.0,
        abnormality=10,
        summary_detail="多名学生快速进入监测区域。",
        move_speed=1.0,
    ),
    Stage(
        name="课间活动",
        duration=2.0,
        targets=[
            (1.2, 1.0),
            (2.5, 2.8),
            (4.2, 1.5),
            (5.0, 3.2),
            (3.5, 0.8),
        ],
        intensity=0.10,
        violent_motion=5.0,
        normal_action=0.93,
        bullying_action=0.07,
        stay_duration=3.0,
        abnormality=15,
        summary_detail="人员分散活动，整体行为正常。",
        move_speed=0.95,
    ),
    Stage(
        name="人员汇聚",
        duration=2.0,
        targets=[
            (2.8, 1.8),
            (3.2, 2.0),
            (3.6, 2.2),
            (3.0, 2.5),
            (3.4, 1.6),
            (2.6, 2.3),
        ],
        intensity=0.28,
        violent_motion=12.0,
        normal_action=0.82,
        bullying_action=0.18,
        stay_duration=4.0,
        abnormality=32,
        summary_detail="人员向同一区域汇聚，聚集度上升。",
        move_speed=1.0,
    ),
    Stage(
        name="围观围堵",
        duration=8.0,
        targets=[
            (3.0, 2.05),
            (3.15, 2.0),
            (2.5, 2.6),
            (3.8, 2.5),
            (3.0, 1.4),
            (3.6, 1.5),
        ],
        intensity=0.48,
        violent_motion=22.0,
        normal_action=0.58,
        bullying_action=0.42,
        stay_duration=7.0,
        abnormality=52,
        summary_detail="形成围观圈，中心两人距离极近，请关注。",
        move_speed=0.75,
    ),
    Stage(
        name="激烈冲突",
        duration=14.0,
        targets=[
            (3.05, 2.02),
            (3.12, 2.0),
            (2.55, 2.55),
            (3.75, 2.48),
            (2.95, 1.45),
            (3.55, 1.48),
        ],
        intensity=0.88,
        violent_motion=48.0,
        normal_action=0.22,
        bullying_action=0.78,
        stay_duration=12.0,
        abnormality=82,
        summary_detail="⚠ 检测到激烈肢体冲突，疑似霸凌行为！",
        move_speed=1.1,
    ),
    Stage(
        name="惊散逃离",
        duration=8.0,
        targets=[
            (0.8, 0.7),
            (5.2, 0.9),
            (1.0, 3.4),
            (5.0, 3.1),
            (2.0, 1.0),
        ],
        intensity=0.35,
        violent_motion=18.0,
        normal_action=0.72,
        bullying_action=0.28,
        stay_duration=5.0,
        abnormality=40,
        summary_detail="人群快速散开，冲突趋于结束。",
        move_speed=1.0,
    ),
    Stage(
        name="恢复平静",
        duration=9.0,
        targets=[
            (1.5, 1.2),
            (4.5, 2.8),
            (3.0, 3.3),
        ],
        intensity=0.12,
        violent_motion=6.0,
        normal_action=0.91,
        bullying_action=0.09,
        stay_duration=3.0,
        abnormality=18,
        summary_detail="现场恢复平静，剩余人员活动正常。",
        move_speed=0.5,
    ),
]


class DemoController:

    def __init__(self) -> None:
        self.start_time = time.time()
        self.persons: List[PersonState] = []
        self._last_tick = self.start_time
        self._stage_elapsed = 0.0
        self._stage_index = 0
        self._jitter_phase = 0.0
        first = STAGES[0]
        self.persons = sync_persons_to_targets([], first.targets)

    def _current_stage(self) -> Stage:
        return STAGES[self._stage_index % len(STAGES)]

    def _advance_stage(self, dt: float) -> None:
        self._stage_elapsed += dt
        stage = self._current_stage()
        if self._stage_elapsed >= stage.duration:
            self._stage_elapsed = 0.0
            self._stage_index = (self._stage_index + 1) % len(STAGES)

    def _resolve_targets(self, stage: Stage, next_stage: Stage) -> List[Tuple[float, float]]:
        blend_window = max(0.0, (stage.duration - self._stage_elapsed) / stage.duration)
        if blend_window >= 0.15:
            return list(stage.targets)
        t = 1.0 - blend_window / 0.15
        return blend_target_lists(stage.targets, next_stage.targets, t)

    def tick(self) -> SimulationFrame:
        now = time.time()
        dt = min(now - self._last_tick, 0.5)
        self._last_tick = now
        self._advance_stage(dt)
        self._jitter_phase += dt

        stage = self._current_stage()
        next_stage = STAGES[(self._stage_index + 1) % len(STAGES)]
        targets = self._resolve_targets(stage, next_stage)

        self.persons = sync_persons_to_targets(self.persons, targets)
        self.persons = move_persons(self.persons, targets, stage.move_speed, dt)

        blend_window = max(0.0, (stage.duration - self._stage_elapsed) / stage.duration)
        if blend_window < 0.15:
            t = 1.0 - blend_window / 0.15
            intensity = lerp(stage.intensity, next_stage.intensity, t)
            bullying = lerp(stage.bullying_action, next_stage.bullying_action, t)
        else:
            intensity = stage.intensity
            bullying = stage.bullying_action

        jitter = 0.02 + intensity * 0.06 * abs(math.sin(self._jitter_phase * 8))
        actions = ActionProbs(normal=1.0 - bullying, bullying=bullying)

        audio = generate_audio(intensity, now - self.start_time)
        summary = format_people_summary(len(self.persons), stage.summary_detail)
        behavior = build_behavior_metrics(
            self.persons,
            violent_motion=stage.violent_motion + intensity * 10 * abs(math.sin(self._jitter_phase * 6)),
            stay_duration=stage.stay_duration,
            abnormality=stage.abnormality,
            summary=summary,
        )
        risk = fuse_risk_score(intensity, actions, audio, behavior)
        point_cloud = generate_point_cloud(self.persons, jitter=jitter)

        return SimulationFrame(
            timestamp=now,
            persons=self.persons,
            point_cloud=point_cloud,
            audio=audio,
            actions=actions,
            behavior=behavior,
            risk_score=risk,
            stage_name=stage.name,
        )

    def reset(self) -> None:
        self.__init__()
