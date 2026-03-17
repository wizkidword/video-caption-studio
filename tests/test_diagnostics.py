from src.vcs import diagnostics
from src.vcs.diagnostics import format_diagnostics_report, run_dependency_diagnostics, windows_install_commands


def test_run_dependency_diagnostics_reports_sources(monkeypatch):
    monkeypatch.setattr(diagnostics, "ffprobe_available", lambda: True)
    monkeypatch.setattr(diagnostics, "opencv_available", lambda: False)
    monkeypatch.setattr(diagnostics, "whisper_available", lambda: False)

    result = run_dependency_diagnostics()

    assert [item.key for item in result.installed] == ["ffprobe"]
    assert [item.key for item in result.missing] == ["opencv", "faster_whisper"]
    assert "Strict mode requires ffprobe + OpenCV" in result.strict_requirements


def test_format_diagnostics_report_includes_installed_missing_sections():
    sample = diagnostics.DependencyDiagnostics(
        statuses=[
            diagnostics.DependencyStatus("ffprobe", "ffprobe (from FFmpeg)", True, True, "metadata source"),
            diagnostics.DependencyStatus("opencv", "OpenCV (opencv-python)", False, True, "visual source"),
        ],
        strict_requirements="strict rule",
        audio_note="audio note",
    )

    report = format_diagnostics_report(sample)

    assert "[PASS] ffprobe (from FFmpeg)" in report
    assert "[FAIL] OpenCV (opencv-python)" in report
    assert "Installed:" in report
    assert "Missing:" in report
    assert "strict rule" in report
    assert "audio note" in report


def test_windows_install_commands_have_expected_entries():
    commands = windows_install_commands()

    assert "winget install --id Gyan.FFmpeg -e" in commands["ffprobe"]
    assert "pip install faster-whisper" in commands["faster_whisper"]
