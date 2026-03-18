from src.vcs.analyze import AnalysisResult
from src.vcs.config import PLATFORM_PRESETS
from src.vcs.ingest import VideoMetadata
from src.vcs.providers import ollama_provider
from src.vcs.providers.ollama_provider import parse_model_output


def test_parse_model_output_json_hashtag_list():
    raw = '{"title":"Coffee glow-up","caption":"Brewed this in 30s","hashtags":["coffee", "MorningBrew", "#latteart"]}'
    parsed = parse_model_output(raw, hashtag_count=5)

    assert parsed.title == "Coffee glow-up"
    assert parsed.caption == "Brewed this in 30s"
    assert "#coffee" in parsed.hashtags
    assert "#morningbrew" in parsed.hashtags
    assert "#latteart" in parsed.hashtags


def test_parse_model_output_fallback_labeled_text():
    raw = """
    Title: Street food sprint
    Caption: Crispy, fast, and way too good.
    Hashtags: #streetfood #nightmarket foodieeats
    """
    parsed = parse_model_output(raw, hashtag_count=4)

    assert parsed.title == "Street food sprint"
    assert parsed.caption.startswith("Crispy")
    assert parsed.hashtags[:2] == ["#streetfood", "#nightmarket"]
    assert "#foodieeats" in parsed.hashtags


def test_ollama_provider_generate_unavailable(monkeypatch):
    provider = ollama_provider.OllamaProvider()
    metadata = VideoMetadata(path="/tmp/a.mp4", filename="a.mp4", extension=".mp4", size_bytes=1)
    analysis = AnalysisResult(visual_tags=["night_city"], transcript="we found the best ramen")

    monkeypatch.setattr(
        ollama_provider,
        "check_ollama_health",
        lambda model, timeout_sec: ollama_provider.OllamaHealth(False, "connection refused", False),
    )

    try:
        provider.generate(metadata, analysis, PLATFORM_PRESETS["tiktok"])
    except ollama_provider.OllamaProviderError as exc:
        assert "Switch Composition Mode to 'Template (Fallback)'" in str(exc)
    else:
        raise AssertionError("Expected OllamaProviderError")
