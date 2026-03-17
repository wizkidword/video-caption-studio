from __future__ import annotations

from dataclasses import dataclass

from .analyze import AnalysisResult
from .config import PLATFORM_PRESETS
from .ingest import VideoMetadata
from .providers.base import GeneratedContent
from .providers.local_provider import LocalHeuristicProvider


class ComposeError(Exception):
    pass


@dataclass
class ComposeRequest:
    metadata: VideoMetadata
    analysis: AnalysisResult
    platform_key: str
    provider_key: str = "local"


def get_provider(provider_key: str = "local"):
    if provider_key == "local":
        return LocalHeuristicProvider()
    raise ComposeError(f"Unknown provider: {provider_key}")


def compose_content(request: ComposeRequest) -> GeneratedContent:
    preset = PLATFORM_PRESETS.get(request.platform_key)
    if not preset:
        raise ComposeError(f"Unknown platform preset: {request.platform_key}")

    provider = get_provider(request.provider_key)
    return provider.generate(request.metadata, request.analysis, preset)
