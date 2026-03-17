from pathlib import Path

import pytest

from src.vcs.ingest import IngestError, VideoMetadata, collect_metadata, resolve_ffprobe_path, validate_video_path


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


def test_resolve_ffprobe_path_prefers_bundled(tmp_path: Path, monkeypatch):
    fake_exe = tmp_path / "python.exe"
    fake_exe.write_text("x")
    bundled_ffprobe = tmp_path / "ffprobe.exe"
    bundled_ffprobe.write_text("x")

    monkeypatch.setattr("src.vcs.ingest.bundled_root", lambda: None)
    monkeypatch.setattr("src.vcs.ingest.sys.executable", str(fake_exe))
    monkeypatch.setattr("src.vcs.ingest.shutil.which", lambda _name: "C:/Windows/System32/ffprobe.exe")

    cmd, source = resolve_ffprobe_path()
    assert cmd == str(bundled_ffprobe)
    assert source == "bundled"


def test_resolve_ffprobe_path_reports_missing(monkeypatch):
    monkeypatch.setattr("src.vcs.ingest.bundled_root", lambda: None)
    monkeypatch.setattr("src.vcs.ingest.sys.executable", "/nonexistent/python")
    monkeypatch.setattr("src.vcs.ingest.shutil.which", lambda _name: None)

    cmd, source = resolve_ffprobe_path()
    assert cmd is None
    assert source == "missing"
