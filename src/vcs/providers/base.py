from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..analyze import AnalysisResult
from ..config import PlatformPreset
from ..ingest import VideoMetadata


@dataclass
class GeneratedContent:
    title: str
    caption: str
    hashtags: str
    resolved_model: str | None = None


class CaptionProvider(Protocol):
    def generate(
        self,
        metadata: VideoMetadata,
        analysis: AnalysisResult,
        preset: PlatformPreset,
    ) -> GeneratedContent:
        ...
