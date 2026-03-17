from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

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
    transcript_dependency_available: bool = False
    transcript_runtime_ok: Optional[bool] = None
    transcript_runtime_message: str = ""
    transcript_error_detail: str = ""
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


def _truncate_detail(message: str, max_len: int = 380) -> str:
    clean = " ".join((message or "").split())
    if len(clean) <= max_len:
        return clean
    return clean[: max_len - 3] + "..."


def _actionable_transcript_message(detail: str) -> str:
    text = detail.lower()
    if any(k in text for k in ["dll", "lib", "not found", "cannot open shared object"]):
        return "Transcript runtime failed: required whisper/runtime libraries were not found."
    if any(k in text for k in ["cuda", "cudnn", "gpu", "compute capability"]):
        return "Transcript runtime failed: unsupported/misconfigured GPU path. Try CPU mode or install matching CUDA/cuDNN."
    if any(k in text for k in ["model", "download", "permission", "cache"]):
        return "Transcript runtime failed while loading whisper model files."
    if any(k in text for k in ["ffmpeg", "decode", "invalid data", "moov atom", "could not open"]):
        return "Transcript runtime failed while decoding audio from the video file."
    if any(k in text for k in ["avx", "illegal instruction", "not supported"]):
        return "Transcript runtime failed: unsupported CPU instruction/runtime path."
    return "Transcript runtime failed during faster-whisper execution."


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


def transcript_runtime_precheck(video_path: str) -> Tuple[bool, str, str]:
    """Attempt lightweight runtime init/test for faster-whisper on selected file.

    Returns: (ok, user_message, detail)
    """
    if WhisperModel is None:
        detail = "faster-whisper import unavailable in current runtime"
        return False, "Transcript precheck failed: faster-whisper is not installed/available.", detail

    try:
        model = WhisperModel("tiny", compute_type="int8")
        segments, _ = model.transcribe(video_path, vad_filter=True, beam_size=1)
        # Consume at most one segment to force real runtime path without full transcription.
        _ = next(iter(segments), None)
        return True, "Transcript precheck passed.", ""
    except Exception as exc:
        detail = _truncate_detail(str(exc))
        return False, _actionable_transcript_message(detail), detail


def extract_transcript_whisper(video_path: str) -> tuple[str, Optional[str], Optional[str]]:
    if WhisperModel is None:
        detail = "faster-whisper import unavailable in current runtime"
        return "", "faster-whisper not installed; transcript extraction skipped.", detail

    try:
        model = WhisperModel("tiny", compute_type="int8")
        segments, _ = model.transcribe(video_path, vad_filter=True)
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return text.strip(), None, None
    except Exception as exc:
        detail = _truncate_detail(str(exc))
        return "", _actionable_transcript_message(detail), detail


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
        if report.transcript_runtime_message:
            issues.append(report.transcript_runtime_message)
        else:
            issues.append("Transcript must come from faster-whisper when audio is present or unknown.")
        if report.transcript_error_detail:
            issues.append(f"Details: {report.transcript_error_detail}")

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
    transcript_dependency_available = whisper_available()
    transcript_runtime_ok: Optional[bool] = None
    transcript_runtime_message = ""
    transcript_error_detail = ""

    if metadata.has_audio is False:
        warnings.append("No audio track detected by ffprobe; transcript not required.")
        transcript_runtime_ok = True
        transcript_runtime_message = "Skipped transcript runtime test because ffprobe confirmed no audio stream."
    else:
        precheck_ok, precheck_message, precheck_detail = transcript_runtime_precheck(video_path)
        transcript_runtime_ok = precheck_ok
        transcript_runtime_message = precheck_message
        transcript_error_detail = precheck_detail

        if not precheck_ok:
            warnings.append(precheck_message)
            if precheck_detail:
                warnings.append(f"Details: {precheck_detail}")
        else:
            transcript, transcript_error, transcript_detail = extract_transcript_whisper(video_path)
            if transcript:
                transcript_source = "whisper"
            else:
                transcript_runtime_ok = False
                transcript_runtime_message = transcript_error or "Transcript extraction failed."
                transcript_error_detail = transcript_detail or transcript_error or ""
                if transcript_runtime_message:
                    warnings.append(transcript_runtime_message)
                if transcript_error_detail:
                    warnings.append(f"Details: {transcript_error_detail}")

    report = AnalysisReport(
        metadata_source=metadata.source,
        visual_source=visual_source,
        transcript_source=transcript_source,
        transcript_dependency_available=transcript_dependency_available,
        transcript_runtime_ok=transcript_runtime_ok,
        transcript_runtime_message=transcript_runtime_message,
        transcript_error_detail=transcript_error_detail,
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
