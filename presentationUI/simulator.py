
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from ui_config import SCENE_DEPTH, SCENE_HEIGHT, SCENE_WIDTH


@dataclass
class PersonState:
    id: str
    x: float
    y: float
    z: float = 0.0
    speed: float = 0.0
    label: str = ""


@dataclass
class PointCloudFrame:
    xs: np.ndarray
    ys: np.ndarray
    zs: np.ndarray
    colors: np.ndarray  # intensity 0-1


@dataclass
class AudioFrame:
    waveform: np.ndarray
    normal_comm: float
    quarrel: float
    scream: float


@dataclass
class ActionProbs:
    normal: float
    bullying: float


@dataclass
class BehaviorMetrics:
    people_count: int
    clustering: float
    speed: float
    violent_motion: float
    stay_duration: float
    abnormality_index: int
    summary: str


@dataclass
class SimulationFrame:
    timestamp: float
    persons: List[PersonState]
    point_cloud: PointCloudFrame
    audio: AudioFrame
    actions: ActionProbs
    behavior: BehaviorMetrics
    risk_score: float
    stage_name: str


def _human_point_cloud(
    cx: float, cy: float, cz: float, scale: float, jitter: float, n: int = 120
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int((cx + cy) * 1000) % 2**31)
    parts = []

    # torso
    torso = rng.uniform(-0.25, 0.25, (n // 3, 3))
    torso[:, 0] *= 0.35 * scale
    torso[:, 1] *= 0.25 * scale
    torso[:, 2] = rng.uniform(0.8, 1.5, n // 3) * scale
    parts.append(torso)

    # head
    head_n = n // 6
    theta = rng.uniform(0, 2 * math.pi, head_n)
    r = rng.uniform(0, 0.18, head_n) * scale
    head = np.column_stack([
        r * np.cos(theta),
        r * np.sin(theta),
        np.full(head_n, 1.65 * scale) + rng.uniform(-0.05, 0.05, head_n),
    ])
    parts.append(head)

    # legs
    leg_n = n // 4
    for side in (-1, 1):
        leg = np.column_stack([
            np.full(leg_n // 2, side * 0.12 * scale) + rng.uniform(-0.04, 0.04, leg_n // 2),
            rng.uniform(-0.08, 0.08, leg_n // 2) * scale,
            rng.uniform(0, 0.75, leg_n // 2) * scale,
        ])
        parts.append(leg)

    pts = np.vstack(parts)
    pts += rng.normal(0, jitter, pts.shape)
    pts[:, 0] += cx
    pts[:, 1] += cy
    pts[:, 2] += cz

    intensity = (pts[:, 2] - cz) / (1.8 * scale)
    intensity = np.clip(intensity, 0, 1)
    return pts[:, 0], pts[:, 1], pts[:, 2], intensity


def generate_point_cloud(
    persons: List[PersonState],
    jitter: float = 0.02,
    noise_points: int = 40,
) -> PointCloudFrame:
    all_x, all_y, all_z, all_c = [], [], [], []
    for p in persons:
        scale = 1.0 + 0.1 * math.sin(p.x + p.y)
        x, y, z, c = _human_point_cloud(p.x, p.y, p.z, scale, jitter)
        all_x.append(x)
        all_y.append(y)
        all_z.append(z)
        all_c.append(c)

    rng = np.random.default_rng(42)
    nx = rng.uniform(0, SCENE_WIDTH, noise_points)
    ny = rng.uniform(0, SCENE_DEPTH, noise_points)
    nz = rng.uniform(0, 0.3, noise_points)
    all_x.append(nx)
    all_y.append(ny)
    all_z.append(nz)
    all_c.append(np.full(noise_points, 0.1))

    return PointCloudFrame(
        xs=np.concatenate(all_x),
        ys=np.concatenate(all_y),
        zs=np.concatenate(all_z),
        colors=np.concatenate(all_c),
    )


def generate_audio(
    stage_intensity: float,
    t: float,
    sample_count: int = 200,
) -> AudioFrame:
    rng = np.random.default_rng(int(t * 10) % 2**31)
    x = np.linspace(0, 4 * math.pi, sample_count)
    base = 0.15 * np.sin(x + t * 2)
    noise = rng.normal(0, 0.05 + stage_intensity * 0.15, sample_count)

    if stage_intensity > 0.5:
        spikes = np.zeros(sample_count)
        spike_idx = rng.integers(0, sample_count, size=int(3 + stage_intensity * 8))
        spikes[spike_idx] = rng.uniform(0.4, 1.0, len(spike_idx))
        waveform = base + noise + spikes * 0.6
    else:
        waveform = base + noise

    waveform = np.clip(waveform, -1, 1)

    quarrel = min(0.45, 0.02 + stage_intensity * 0.35 + rng.uniform(-0.02, 0.02))
    scream = min(0.25, 0.01 + stage_intensity * 0.22 + rng.uniform(-0.01, 0.01))
    normal = max(0.0, 1.0 - quarrel - scream)
    total = normal + quarrel + scream
    return AudioFrame(
        waveform=waveform,
        normal_comm=normal / total,
        quarrel=quarrel / total,
        scream=scream / total,
    )


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * max(0.0, min(1.0, t))


def move_persons(
    persons: List[PersonState],
    targets: List[Tuple[float, float]],
    speed: float,
    dt: float,
) -> List[PersonState]:
    updated = []
    for p, (tx, ty) in zip(persons, targets):
        dx, dy = tx - p.x, ty - p.y
        dist = math.hypot(dx, dy)
        if dist < 0.05:
            new_x, new_y = tx, ty
            spd = 0.0
        else:
            step = min(speed * dt, dist)
            new_x = p.x + dx / dist * step
            new_y = p.y + dy / dist * step
            spd = step / dt if dt > 0 else 0.0
        updated.append(PersonState(id=p.id, x=new_x, y=new_y, z=p.z, speed=spd, label=p.label))
    return updated


# 新入场人员默认从场景左下角出现
SPAWN_POSITIONS: Tuple[Tuple[float, float], ...] = (
    (0.4, 0.5),
    (0.6, 0.8),
    (0.5, 1.0),
    (0.7, 0.4),
    (0.3, 0.7),
    (0.8, 0.6),
)


def sync_persons_to_targets(
    persons: List[PersonState],
    targets: List[Tuple[float, float]],
) -> List[PersonState]:
    """按目标数量增减人员，新增者从入场点出现。"""
    synced = list(persons)
    while len(synced) < len(targets):
        idx = len(synced) + 1
        sx, sy = SPAWN_POSITIONS[(idx - 1) % len(SPAWN_POSITIONS)]
        synced.append(PersonState(id=f"P{idx}", x=sx, y=sy, label=f"P{idx}"))
    return synced[: len(targets)]


def blend_target_lists(
    current: List[Tuple[float, float]],
    nxt: List[Tuple[float, float]],
    t: float,
) -> List[Tuple[float, float]]:
    """阶段切换时平滑过渡位置；人数不同时按较多的一方对齐。"""
    t = max(0.0, min(1.0, t))
    length = max(len(current), len(nxt))
    blended: List[Tuple[float, float]] = []
    for i in range(length):
        cx, cy = current[min(i, len(current) - 1)]
        nx, ny = nxt[min(i, len(nxt) - 1)]
        blended.append((lerp(cx, nx, t), lerp(cy, ny, t)))
    return blended


def format_people_summary(count: int, detail: str) -> str:
    return f"当前检测到 {count} 名人员，{detail}"


def compute_clustering(persons: List[PersonState]) -> float:
    if len(persons) < 2:
        return 0.0
    dists = []
    for i in range(len(persons)):
        for j in range(i + 1, len(persons)):
            dists.append(math.hypot(persons[i].x - persons[j].x, persons[i].y - persons[j].y))
    avg = sum(dists) / len(dists)
    # closer = higher clustering %
    return max(0.0, min(100.0, (2.5 - avg) / 2.5 * 100))


def build_behavior_metrics(
    persons: List[PersonState],
    violent_motion: float,
    stay_duration: float,
    abnormality: int,
    summary: str,
) -> BehaviorMetrics:
    avg_speed = sum(p.speed for p in persons) / max(len(persons), 1)
    return BehaviorMetrics(
        people_count=len(persons),
        clustering=round(compute_clustering(persons), 1),
        speed=round(avg_speed, 1),
        violent_motion=round(violent_motion, 1),
        stay_duration=round(stay_duration, 1),
        abnormality_index=abnormality,
        summary=summary,
    )
