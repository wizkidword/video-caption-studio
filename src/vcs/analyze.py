from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .ingest import VideoMetadata
from .runtime import runtime_mode

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    cv2 = None

try:
    from faster_whisper import WhisperModel  # type: ignore
except Exception:  # pragma: no cover - optional dependency path
    WhisperModel = None


class AnalysisContractError(Exception):
    pass


@dataclass
class AnalysisReport:
    metadata_source: str
    visual_source: str
    transcript_source: str
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


@dataclass
class AnalysisResult:
    sampled_frames: List[int] = field(default_factory=list)
    visual_tags: List[str] = field(default_factory=list)
    transcript: str = ""
    notes: List[str] = field(default_factory=list)
    report: Optional[AnalysisReport] = None


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


def opencv_available() -> bool:
    return cv2 is not None


def whisper_available() -> bool:
    return WhisperModel is not None


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
        seen = set()
        result.visual_tags.extend([x for x in brightness_labels if not (x in seen or seen.add(x))])

    if sample_idxs:
        if motion_hits >= max(1, len(sample_idxs) // 3):
            result.visual_tags.append("dynamic_motion")
        else:
            result.visual_tags.append("steady_shot")

    return result


def extract_transcript_whisper(video_path: str) -> tuple[str, Optional[str]]:
    if WhisperModel is None:
        return "", "faster-whisper not installed; transcript extraction skipped."

    try:
        model = WhisperModel("tiny", compute_type="int8")
        segments, _ = model.transcribe(video_path, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return text.strip(), None
    except Exception as exc:
        return "", f"Whisper transcription failed: {exc}"


def _install_guidance() -> str:
    if runtime_mode() == "exe":
        return (
            "EXE runtime detected. Strict analysis dependencies must be bundled during EXE build:\n"
            "- Include ffprobe binary in the packaged app\n"
            "- Ensure opencv-python and faster-whisper are installed in build environment before PyInstaller\n"
            "- Rebuild the EXE (do not use system py -m pip to patch a built EXE)\n"
            "If you need a best-effort run anyway, enable 'Allow fallback generation (less accurate)'."
        )

    return (
        "Install requirements for strict analysis in your project venv:\n"
        "- ffprobe (from ffmpeg): https://ffmpeg.org/download.html\n"
        "- OpenCV: .venv\\Scripts\\python -m pip install opencv-python\n"
        "- Optional transcript support: .venv\\Scripts\\python -m pip install faster-whisper\n"
        "If you need a best-effort run anyway, enable 'Allow fallback generation (less accurate)'."
    )


def _validate_strict_requirements(report: AnalysisReport, has_audio: Optional[bool]) -> None:
    issues: List[str] = []

    if report.metadata_source != "ffprobe":
        issues.append("Metadata must come from ffprobe.")
    if report.visual_source != "opencv":
        issues.append("Visual analysis must come from OpenCV.")

    if has_audio is False:
        pass
    elif report.transcript_source != "whisper":
        issues.append("Transcript must come from faster-whisper when audio is present or unknown.")

    if issues:
        raise AnalysisContractError("Strict analysis requirements not met:\n- " + "\n- ".join(issues) + "\n\n" + _install_guidance())


def run_analysis(video_path: str, metadata: VideoMetadata, strict_mode: bool = True) -> AnalysisResult:
    warnings: List[str] = []
    errors: List[str] = []

    visual_result = extract_visual_signals(video_path)
    visual_source = "opencv"
    if not opencv_available() or not visual_result.sampled_frames:
        visual_source = "none"
        if not opencv_available():
            warnings.append("OpenCV not available.")
        else:
            errors.append("OpenCV could not analyze the video frames.")

    transcript = ""
    transcript_source = "none"
    if metadata.has_audio is False:
        warnings.append("No audio track detected by ffprobe; transcript not required.")
    else:
        transcript, transcript_error = extract_transcript_whisper(video_path)
        if transcript:
            transcript_source = "whisper"
        elif transcript_error:
            warnings.append(transcript_error)

    report = AnalysisReport(
        metadata_source=metadata.source,
        visual_source=visual_source,
        transcript_source=transcript_source,
        warnings=warnings,
        errors=errors,
    )

    result = AnalysisResult(
        sampled_frames=visual_result.sampled_frames,
        visual_tags=visual_result.visual_tags,
        transcript=transcript,
        notes=[*visual_result.notes, *warnings, *errors],
        report=report,
    )

    if strict_mode:
        _validate_strict_requirements(report, metadata.has_audio)

    return result
