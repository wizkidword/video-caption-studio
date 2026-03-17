from pathlib import Path

import pytest

from src.vcs.ingest import IngestError, validate_video_path


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
