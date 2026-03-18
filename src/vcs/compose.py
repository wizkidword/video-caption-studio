from __future__ import annotations

from dataclasses import dataclass

from .analyze import AnalysisResult
from .config import PLATFORM_PRESETS
from .ingest import VideoMetadata
from .providers.base import GeneratedContent
from .providers.local_provider import LocalHeuristicProvider
from .providers.ollama_provider import OllamaProvider, OllamaProviderError


class ComposeError(Exception):
    pass


@dataclass
class ComposeRequest:
    metadata: VideoMetadata
    analysis: AnalysisResult
    platform_key: str
    provider_key: str = "local"
    creativity: str = "medium"
    brand_voice_notes: str = ""


def get_provider(
    provider_key: str = "local",
    *,
    creativity: str = "medium",
    brand_voice_notes: str = "",
):
    if provider_key == "local":
        return LocalHeuristicProvider()
    if provider_key == "ollama":
        return OllamaProvider(creativity=creativity, brand_voice_notes=brand_voice_notes)
    raise ComposeError(f"Unknown provider: {provider_key}")


def compose_content(request: ComposeRequest) -> GeneratedContent:
    preset = PLATFORM_PRESETS.get(request.platform_key)
    if not preset:
        raise ComposeError(f"Unknown platform preset: {request.platform_key}")

    provider = get_provider(
        request.provider_key,
        creativity=request.creativity,
        brand_voice_notes=request.brand_voice_notes,
    )
    try:
        return provider.generate(request.metadata, request.analysis, preset)
    except OllamaProviderError as exc:
        raise ComposeError(str(exc)) from exc
