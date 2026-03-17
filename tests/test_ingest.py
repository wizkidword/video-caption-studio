from pathlib import Path

import pytest

from src.vcs.ingest import IngestError, VideoMetadata, collect_metadata, validate_video_path


def test_validate_video_path_rejects_unknown_extension(tmp_path: Path):
    p = tmp_path / "clip.txt"
    p.write_text("x")

    with pytest.raises(IngestError):
        validate_video_path(str(p))


def test_validate_video_path_accepts_supported_extension(tmp_path: Path):
    p = tmp_path / "clip.mp4"
    p.write_text("x")

    resolved = validate_video_path(str(p))
    assert resolved.name == "clip.mp4"


def test_collect_metadata_uses_ffprobe_when_available(tmp_path: Path, monkeypatch):
    p = tmp_path / "clip.mp4"
    p.write_text("x")

    monkeypatch.setattr(
        "src.vcs.ingest._ffprobe_metadata",
        lambda _path: VideoMetadata(
            path=str(p),
            filename=p.name,
            extension=".mp4",
            size_bytes=1,
            source="ffprobe",
            has_audio=True,
        ),
    )

    meta = collect_metadata(str(p))
    assert meta.source == "ffprobe"
    assert meta.has_audio is True
