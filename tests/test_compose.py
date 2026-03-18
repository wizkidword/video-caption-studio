from src.vcs.analyze import AnalysisResult
from src.vcs.compose import ComposeError, ComposeRequest, compose_content
from src.vcs.ingest import VideoMetadata
from src.vcs.providers.base import GeneratedContent


def _metadata() -> VideoMetadata:
    return VideoMetadata(
        path="/tmp/fake.mp4",
        filename="sample_clip.mp4",
        extension=".mp4",
        size_bytes=1024,
    )


def test_local_provider_contract_outputs_nonempty_fields():
    analysis = AnalysisResult(visual_tags=["balanced_lighting", "dynamic_motion"])

    generated = compose_content(
        ComposeRequest(metadata=_metadata(), analysis=analysis, platform_key="tiktok")
    )

    assert generated.title
    assert generated.caption
    assert generated.hashtags.startswith("#")


def test_provider_routing_ollama(monkeypatch):
    analysis = AnalysisResult(visual_tags=["balanced_lighting"], transcript="sneaker restoration before and after")

    class FakeSmartProvider:
        def generate(self, metadata, analysis, preset):
            return GeneratedContent("Smart Title", "Smart Caption", "#sneakers #restore")

    monkeypatch.setattr("src.vcs.compose.OllamaProvider", lambda creativity, brand_voice_notes: FakeSmartProvider())

    generated = compose_content(
        ComposeRequest(
            metadata=_metadata(),
            analysis=analysis,
            platform_key="tiktok",
            provider_key="ollama",
            creativity="high",
            brand_voice_notes="bold but clean",
        )
    )

    assert generated.title == "Smart Title"
    assert generated.hashtags == "#sneakers #restore"


def test_compose_wraps_ollama_errors(monkeypatch):
    analysis = AnalysisResult(visual_tags=["balanced_lighting"])

    class BrokenSmartProvider:
        def generate(self, metadata, analysis, preset):
            from src.vcs.providers.ollama_provider import OllamaProviderError

            raise OllamaProviderError("Ollama unavailable")

    monkeypatch.setattr("src.vcs.compose.OllamaProvider", lambda creativity, brand_voice_notes: BrokenSmartProvider())

    try:
        compose_content(
            ComposeRequest(
                metadata=_metadata(),
                analysis=analysis,
                platform_key="tiktok",
                provider_key="ollama",
            )
        )
    except ComposeError as exc:
        assert "Ollama unavailable" in str(exc)
    else:
        raise AssertionError("Expected ComposeError")
