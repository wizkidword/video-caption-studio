import pytest

from src.vcs import analyze
from src.vcs.analyze import AnalysisContractError, AnalysisResult, build_frame_sampling_plan, run_analysis
from src.vcs.ingest import VideoMetadata


def test_sampling_plan_spreads_indices():
    plan = build_frame_sampling_plan(total_frames=100, max_samples=5)
    assert plan[0] == 0
    assert plan[-1] == 99
    assert len(plan) == 5


def test_sampling_plan_handles_small_inputs():
    assert build_frame_sampling_plan(total_frames=0, max_samples=5) == []
    assert build_frame_sampling_plan(total_frames=3, max_samples=8) == [0, 1, 2]


def test_sampling_plan_handles_single_sample_request():
    assert build_frame_sampling_plan(total_frames=100, max_samples=1) == [0]


def test_strict_mode_fails_when_dependencies_missing(monkeypatch):
    metadata = VideoMetadata(
        path="/tmp/fake.mp4",
        filename="fake.mp4",
        extension=".mp4",
        size_bytes=1,
        has_audio=True,
        source="fallback",
    )

    monkeypatch.setattr(analyze, "opencv_available", lambda: False)
    monkeypatch.setattr(analyze, "extract_visual_signals", lambda *args, **kwargs: AnalysisResult())
    monkeypatch.setattr(
        analyze,
        "extract_transcript_whisper",
        lambda *_args, **_kwargs: ("", "faster-whisper not installed; transcript extraction skipped."),
    )

    with pytest.raises(AnalysisContractError):
        run_analysis("/tmp/fake.mp4", metadata=metadata, strict_mode=True)


def test_strict_mode_passes_without_transcript_if_no_audio(monkeypatch):
    metadata = VideoMetadata(
        path="/tmp/fake.mp4",
        filename="fake.mp4",
        extension=".mp4",
        size_bytes=1,
        has_audio=False,
        source="ffprobe",
    )

    monkeypatch.setattr(analyze, "opencv_available", lambda: True)
    monkeypatch.setattr(
        analyze,
        "extract_visual_signals",
        lambda *args, **kwargs: AnalysisResult(sampled_frames=[0, 1], visual_tags=["steady_shot"]),
    )

    result = run_analysis("/tmp/fake.mp4", metadata=metadata, strict_mode=True)

    assert result.report is not None
    assert result.report.metadata_source == "ffprobe"
    assert result.report.visual_source == "opencv"
    assert result.report.transcript_source == "none"
    assert any("No audio track detected" in w for w in result.report.warnings)


def test_fallback_mode_reports_actual_sources(monkeypatch):
    metadata = VideoMetadata(
        path="/tmp/fake.mp4",
        filename="fake.mp4",
        extension=".mp4",
        size_bytes=1,
        has_audio=True,
        source="fallback",
    )

    monkeypatch.setattr(analyze, "opencv_available", lambda: False)
    monkeypatch.setattr(analyze, "extract_visual_signals", lambda *args, **kwargs: AnalysisResult())
    monkeypatch.setattr(
        analyze,
        "extract_transcript_whisper",
        lambda *_args, **_kwargs: ("hello world", None),
    )

    result = run_analysis("/tmp/fake.mp4", metadata=metadata, strict_mode=False)

    assert result.report is not None
    assert result.report.metadata_source == "fallback"
    assert result.report.visual_source == "none"
    assert result.report.transcript_source == "whisper"
