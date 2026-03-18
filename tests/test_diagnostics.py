from src.vcs import diagnostics
from src.vcs.diagnostics import format_diagnostics_report, run_dependency_diagnostics, windows_install_commands
from src.vcs.providers.ollama_provider import OllamaHealth


def test_run_dependency_diagnostics_reports_presence(monkeypatch):
    monkeypatch.setattr(diagnostics, "resolve_ffprobe_path", lambda: ("C:/ffprobe.exe", "bundled"))
    monkeypatch.setattr(diagnostics, "cv2", None)
    monkeypatch.setattr(diagnostics, "WhisperModel", None)
    monkeypatch.setattr(diagnostics, "runtime_mode", lambda: "exe")
    monkeypatch.setattr(
        diagnostics,
        "check_ollama_health",
        lambda model, timeout_sec: OllamaHealth(False, "not running", False, model, None),
    )

    result = run_dependency_diagnostics()

    assert [item.key for item in result.installed] == ["ffprobe"]
    assert [item.key for item in result.missing] == ["opencv", "faster_whisper", "ollama"]
    assert "bundled" in [item.presence for item in result.installed]
    assert "packaged EXE" in result.mode_note


def test_format_diagnostics_report_includes_presence_sections():
    sample = diagnostics.DependencyDiagnostics(
        statuses=[
            diagnostics.DependencyStatus("ffprobe", "ffprobe (from FFmpeg)", True, True, "metadata source", "bundled"),
            diagnostics.DependencyStatus("opencv", "OpenCV (opencv-python)", False, True, "visual source", "missing"),
        ],
        strict_requirements="strict rule",
        audio_note="audio note",
        mode_note="mode note",
    )

    report = format_diagnostics_report(sample)

    assert "Dependency Diagnostics (v1.2.1)" in report
    assert "[PASS] ffprobe (from FFmpeg)" in report
    assert "Presence: bundled" in report
    assert "[FAIL] OpenCV (opencv-python)" in report
    assert "Installed:" in report
    assert "Missing:" in report
    assert "strict rule" in report
    assert "audio note" in report
    assert "mode note" in report


def test_diagnostics_mentions_cpu_default_no_cuda_requirement(monkeypatch):
    monkeypatch.setattr(
        diagnostics,
        "check_ollama_health",
        lambda model, timeout_sec: OllamaHealth(True, "ok", True, model, model),
    )
    result = run_dependency_diagnostics()
    assert "CPU-first" in result.strict_requirements
    whisper_detail = next(item.detail for item in result.statuses if item.key == "faster_whisper")
    assert "CUDA not required" in whisper_detail


def test_windows_install_commands_source_mode(monkeypatch):
    monkeypatch.setattr(diagnostics, "runtime_mode", lambda: "source")
    commands = windows_install_commands()

    assert ".venv\\Scripts\\python -m pip install faster-whisper" in commands["faster_whisper"]
    assert "ollama pull" in commands["ollama"]


def test_windows_install_commands_exe_mode(monkeypatch):
    monkeypatch.setattr(diagnostics, "runtime_mode", lambda: "exe")
    commands = windows_install_commands()

    assert "must be bundled during build" in commands["ffprobe"]
    assert "Do NOT use system" in commands["faster_whisper"]
    assert "Ollama runs outside the EXE" in commands["ollama"]


def test_diagnostics_report_includes_configured_and_selected_ollama_models(monkeypatch):
    monkeypatch.setattr(diagnostics, "resolve_ffprobe_path", lambda: ("C:/ffprobe.exe", "bundled"))
    monkeypatch.setattr(diagnostics, "cv2", object())
    monkeypatch.setattr(diagnostics, "WhisperModel", object())
    monkeypatch.setattr(diagnostics, "runtime_mode", lambda: "source")
    monkeypatch.setattr(
        diagnostics,
        "check_ollama_health",
        lambda model, timeout_sec: OllamaHealth(
            True,
            "Configured model 'llama3.1:8b-instruct' was not found. Using 'llama3.1:8b' from local models.",
            False,
            "llama3.1:8b-instruct",
            "llama3.1:8b",
        ),
    )

    result = run_dependency_diagnostics()
    ollama_status = next(item for item in result.statuses if item.key == "ollama")
    report = format_diagnostics_report(result)

    assert ollama_status.installed is True
    assert "Configured model: llama3.1:8b-instruct" in ollama_status.detail
    assert "Selected model: llama3.1:8b" in ollama_status.detail
    assert "Configured smart model" in report
    assert "auto-selects a same-family local model" in report
