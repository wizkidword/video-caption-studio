from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import SUPPORTED_EXTENSIONS
from .runtime import bundled_root


class IngestError(Exception):
    pass


@dataclass
class VideoMetadata:
    path: str
    filename: str
    extension: str
    size_bytes: int
    duration_sec: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    has_audio: Optional[bool] = None
    source: str = "fallback"


def validate_video_path(video_path: str) -> Path:
    path = Path(video_path).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise IngestError(f"Video file not found: {video_path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise IngestError(
            f"Unsupported extension '{path.suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    return path


def resolve_ffprobe_path() -> tuple[Optional[str], str]:
    """Return (command_path, source_kind). source_kind: bundled|system|missing."""
    candidates: list[Path] = []

    bundle_dir = bundled_root()
    if bundle_dir:
        candidates.extend([bundle_dir / "ffprobe.exe", bundle_dir / "ffprobe"])

    exe_dir = Path(sys.executable).resolve().parent
    candidates.extend([exe_dir / "ffprobe.exe", exe_dir / "ffprobe"])

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate), "bundled"

    system_ffprobe = shutil.which("ffprobe")
    if system_ffprobe:
        return system_ffprobe, "system"

    return None, "missing"


def ffprobe_available() -> bool:
    return resolve_ffprobe_path()[0] is not None


def _parse_fps(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            den_f = float(den)
            return float(num) / den_f if den_f else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


def _ffprobe_metadata(path: Path) -> Optional[VideoMetadata]:
    ffprobe_cmd, _source = resolve_ffprobe_path()
    if not ffprobe_cmd:
        return None

    command = [
        ffprobe_cmd,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError):
        return None

    streams = payload.get("streams", [])
    vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    fmt = payload.get("format", {})

    try:
        duration = float(fmt.get("duration")) if fmt.get("duration") else None
    except ValueError:
        duration = None

    return VideoMetadata(
        path=str(path),
        filename=path.name,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        duration_sec=duration,
        width=vstream.get("width"),
        height=vstream.get("height"),
        fps=_parse_fps(vstream.get("r_frame_rate")),
        has_audio=has_audio,
        source="ffprobe",
    )


def collect_metadata(video_path: str) -> VideoMetadata:
    path = validate_video_path(video_path)
    meta = _ffprobe_metadata(path)
    if meta:
        return meta

    return VideoMetadata(
        path=str(path),
        filename=path.name,
        extension=path.suffix.lower(),
        size_bytes=path.stat().st_size,
        source="fallback",
    )
