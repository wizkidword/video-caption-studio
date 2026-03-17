from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    cv2 = None


@dataclass
class AnalysisResult:
    sampled_frames: List[int] = field(default_factory=list)
    visual_tags: List[str] = field(default_factory=list)
    transcript: str = ""
    notes: List[str] = field(default_factory=list)


def build_frame_sampling_plan(total_frames: int, max_samples: int = 8) -> List[int]:
    if total_frames <= 0 or max_samples <= 0:
        return []
    if max_samples == 1:
        return [0]
    if total_frames <= max_samples:
        return list(range(total_frames))

    step = (total_frames - 1) / float(max_samples - 1)
    plan = sorted({int(round(i * step)) for i in range(max_samples)})
    return plan


def _classify_frame_brightness(mean_value: float) -> str:
    if mean_value < 70:
        return "low_light"
    if mean_value > 180:
        return "bright_scene"
    return "balanced_lighting"


def extract_visual_signals(video_path: str, max_samples: int = 8) -> AnalysisResult:
    result = AnalysisResult()
    if cv2 is None:
        result.notes.append("OpenCV unavailable; visual extraction skipped.")
        return result

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        result.notes.append("Unable to open video for analysis.")
        return result

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    sample_idxs = build_frame_sampling_plan(total_frames, max_samples=max_samples)
    result.sampled_frames = sample_idxs

    motion_hits = 0
    brightness_labels = []
    prev_gray = None

    for idx in sample_idxs:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        mean = float(gray.mean())
        brightness_labels.append(_classify_frame_brightness(mean))

        if prev_gray is not None:
            diff = cv2.absdiff(gray, prev_gray)
            if float(diff.mean()) > 18:
                motion_hits += 1
        prev_gray = gray

    cap.release()

    if brightness_labels:
        # preserve order, remove duplicates
        seen = set()
        result.visual_tags.extend([x for x in brightness_labels if not (x in seen or seen.add(x))])

    if motion_hits >= max(1, len(sample_idxs) // 3):
        result.visual_tags.append("dynamic_motion")
    else:
        result.visual_tags.append("steady_shot")

    return result


def extract_transcript_placeholder(video_path: str) -> str:
    _ = video_path
    return ""
