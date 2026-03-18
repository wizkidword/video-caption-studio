from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

DEFAULT_COMPOSITION_MODE = "ollama"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b-instruct"
DEFAULT_OLLAMA_TIMEOUT_SEC = 45

COMPOSITION_MODES: Dict[str, str] = {
    "ollama": "Smart (Local LLM via Ollama)",
    "local": "Template (Fallback)",
}

CREATIVITY_LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class PlatformPreset:
    key: str
    label: str
    tone: str
    caption_style: str
    hashtag_count: int


PLATFORM_PRESETS: Dict[str, PlatformPreset] = {
    "tiktok": PlatformPreset(
        key="tiktok",
        label="TikTok",
        tone="energetic and hook-first",
        caption_style="short punchy lines with quick CTA",
        hashtag_count=7,
    ),
    "instagram": PlatformPreset(
        key="instagram",
        label="Instagram Reels",
        tone="aesthetic and relatable",
        caption_style="story-forward with lifestyle vibe",
        hashtag_count=10,
    ),
    "youtube_shorts": PlatformPreset(
        key="youtube_shorts",
        label="YouTube Shorts",
        tone="clear and curiosity-driven",
        caption_style="informative but compact",
        hashtag_count=5,
    ),
}


@dataclass
class AppConfig:
    provider_key: str = DEFAULT_COMPOSITION_MODE
    max_frames: int = 8
    transcript_enabled: bool = False
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_timeout_sec: int = DEFAULT_OLLAMA_TIMEOUT_SEC


def platform_keys() -> List[str]:
    return list(PLATFORM_PRESETS.keys())
