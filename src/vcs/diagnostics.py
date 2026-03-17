from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .analyze import opencv_available, whisper_available
from .ingest import ffprobe_available


@dataclass(frozen=True)
class DependencyStatus:
    key: str
    label: str
    installed: bool
    required_for_strict: bool
    detail: str


@dataclass(frozen=True)
class DependencyDiagnostics:
    statuses: List[DependencyStatus]
    strict_requirements: str
    audio_note: str

    @property
    def missing(self) -> List[DependencyStatus]:
        return [item for item in self.statuses if not item.installed]

    @property
    def installed(self) -> List[DependencyStatus]:
        return [item for item in self.statuses if item.installed]


def run_dependency_diagnostics() -> DependencyDiagnostics:
    statuses = [
        DependencyStatus(
            key="ffprobe",
            label="ffprobe (from FFmpeg)",
            installed=ffprobe_available(),
            required_for_strict=True,
            detail="Required so strict mode can trust metadata and audio/no-audio detection.",
        ),
        DependencyStatus(
            key="opencv",
            label="OpenCV (opencv-python)",
            installed=opencv_available(),
            required_for_strict=True,
            detail="Required so strict mode can run visual frame analysis.",
        ),
        DependencyStatus(
            key="faster_whisper",
            label="faster-whisper",
            installed=whisper_available(),
            required_for_strict=False,
            detail=(
                "Needed for transcript extraction when audio exists or audio status is unknown. "
                "Strict mode can still pass without it only when ffprobe confirms no audio track."
            ),
        ),
    ]

    return DependencyDiagnostics(
        statuses=statuses,
        strict_requirements=(
            "Strict mode requires ffprobe + OpenCV, and requires faster-whisper when audio is present "
            "or unknown. If ffprobe confirms no audio track, transcript is not required."
        ),
        audio_note=(
            "Audio behavior note: transcript checks depend on ffprobe metadata. "
            "If ffprobe is missing, audio is treated as unknown in strict mode."
        ),
    )


def format_diagnostics_report(diagnostics: DependencyDiagnostics) -> str:
    lines: List[str] = ["Dependency Diagnostics (v1.1.1)"]

    for status in diagnostics.statuses:
        state = "PASS" if status.installed else "FAIL"
        required = "required" if status.required_for_strict else "optional/conditional"
        lines.append(f"- [{state}] {status.label} ({required})")
        lines.append(f"  {status.detail}")

    lines.append("")
    lines.append("Installed:")
    installed = diagnostics.installed
    lines.append("- " + ", ".join(item.label for item in installed) if installed else "- (none)")

    lines.append("Missing:")
    missing = diagnostics.missing
    lines.append("- " + ", ".join(item.label for item in missing) if missing else "- (none)")

    lines.append("")
    lines.append("Strict mode requirements:")
    lines.append(f"- {diagnostics.strict_requirements}")
    lines.append(f"- {diagnostics.audio_note}")
    lines.append("- After installing dependencies, reopen your terminal/app before running again.")

    return "\n".join(lines)


def windows_install_commands() -> Dict[str, str]:
    return {
        "ffprobe": (
            "winget install --id Gyan.FFmpeg -e\n"
            ":: Reopen terminal/app so ffprobe is detected on PATH"
        ),
        "faster_whisper": (
            "py -3 -m pip install faster-whisper\n"
            ":: Reopen terminal/app after install"
        ),
    }
