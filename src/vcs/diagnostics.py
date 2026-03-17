from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .analyze import WhisperModel, cv2
from .ingest import resolve_ffprobe_path
from .runtime import runtime_mode


@dataclass(frozen=True)
class DependencyStatus:
    key: str
    label: str
    installed: bool
    required_for_strict: bool
    detail: str
    presence: str  # bundled | system | missing


@dataclass(frozen=True)
class DependencyDiagnostics:
    statuses: List[DependencyStatus]
    strict_requirements: str
    audio_note: str
    mode_note: str

    @property
    def missing(self) -> List[DependencyStatus]:
        return [item for item in self.statuses if not item.installed]

    @property
    def installed(self) -> List[DependencyStatus]:
        return [item for item in self.statuses if item.installed]


def _module_presence(module_obj: object | None) -> str:
    if module_obj is None:
        return "missing"
    module_file = getattr(module_obj, "__file__", "") or ""
    if "_MEI" in module_file:
        return "bundled"
    return "system"


def _symbol_presence(symbol_obj: object | None) -> str:
    if symbol_obj is None:
        return "missing"
    module_name = getattr(symbol_obj, "__module__", "")
    module = __import__(module_name, fromlist=["*"]) if module_name else None
    return _module_presence(module)


def run_dependency_diagnostics() -> DependencyDiagnostics:
    ffprobe_cmd, ffprobe_presence = resolve_ffprobe_path()
    opencv_presence = _module_presence(cv2)
    whisper_presence = _symbol_presence(WhisperModel)
    mode = runtime_mode()

    statuses = [
        DependencyStatus(
            key="ffprobe",
            label="ffprobe (from FFmpeg)",
            installed=ffprobe_cmd is not None,
            required_for_strict=True,
            detail="Required so strict mode can trust metadata and audio/no-audio detection.",
            presence=ffprobe_presence,
        ),
        DependencyStatus(
            key="opencv",
            label="OpenCV (opencv-python)",
            installed=opencv_presence != "missing",
            required_for_strict=True,
            detail="Required so strict mode can run visual frame analysis.",
            presence=opencv_presence,
        ),
        DependencyStatus(
            key="faster_whisper",
            label="faster-whisper",
            installed=whisper_presence != "missing",
            required_for_strict=False,
            detail=(
                "Needed for transcript extraction when audio exists or audio status is unknown. "
                "Strict mode can still pass without it only when ffprobe confirms no audio track."
            ),
            presence=whisper_presence,
        ),
    ]

    mode_note = (
        "Runtime mode: packaged EXE. Python dependencies and ffprobe must be bundled at build time. "
        "Do not install runtime deps with system py -m pip for the EXE."
        if mode == "exe"
        else "Runtime mode: source/venv. Install deps into .venv using .venv\\Scripts\\python -m pip ..."
    )

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
        mode_note=mode_note,
    )


def format_diagnostics_report(diagnostics: DependencyDiagnostics) -> str:
    lines: List[str] = ["Dependency Diagnostics (v1.1.3)"]

    for status in diagnostics.statuses:
        state = "PASS" if status.installed else "FAIL"
        required = "required" if status.required_for_strict else "optional/conditional"
        lines.append(f"- [{state}] {status.label} ({required})")
        lines.append(f"  Presence: {status.presence}")
        lines.append(f"  {status.detail}")

    lines.append("")
    lines.append("Installed:")
    installed = diagnostics.installed
    lines.append("- " + ", ".join(f"{item.label} [{item.presence}]" for item in installed) if installed else "- (none)")

    lines.append("Missing:")
    missing = diagnostics.missing
    lines.append("- " + ", ".join(item.label for item in missing) if missing else "- (none)")

    lines.append("")
    lines.append("Strict mode requirements:")
    lines.append(f"- {diagnostics.strict_requirements}")
    lines.append(f"- {diagnostics.audio_note}")
    lines.append(f"- {diagnostics.mode_note}")
    lines.append("- After installing or rebuilding, reopen your terminal/app before running again.")

    return "\n".join(lines)


def windows_install_commands() -> Dict[str, str]:
    mode = runtime_mode()
    if mode == "exe":
        exe_note = (
            "EXE mode detected. Dependencies must be bundled during build.\n"
            "Rebuild the EXE after ensuring build env has opencv-python, faster-whisper, and bundled ffprobe.\n"
            "Do NOT use system: py -3 -m pip install ..."
        )
        return {
            "ffprobe": exe_note,
            "faster_whisper": exe_note,
        }

    return {
        "ffprobe": (
            "winget install --id Gyan.FFmpeg -e\n"
            ":: Reopen terminal/app so ffprobe is detected on PATH"
        ),
        "faster_whisper": (
            ".venv\\Scripts\\python -m pip install faster-whisper\n"
            ":: Reopen terminal/app after install"
        ),
    }
