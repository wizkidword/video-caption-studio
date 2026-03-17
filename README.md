# Video Caption Studio

Offline-first desktop app (Tkinter) for generating short-form video **title**, **caption**, and **hashtags** from a single local video file.

Current MVP targets Windows-friendly use and keeps the architecture clean for:
- future **online AI providers** (provider-pluggable compose layer)
- future **batch processing** (analysis/compose layers already decoupled from UI)

## Features (v1.1.3)

- Local single-video workflow
- Platform presets:
  - TikTok
  - Instagram Reels
  - YouTube Shorts
- Ingest layer:
  - validates file path + extension
  - uses `ffprobe` for metadata (with fallback when unavailable)
  - detects whether audio track exists (when `ffprobe` is available)
- Analyze layer:
  - frame sampling plan helper
  - OpenCV visual analysis (when available)
  - optional local transcript extraction via `faster-whisper`
  - structured analysis report with real source attribution
- Compose layer:
  - provider interface contract
  - local heuristic provider for offline generation
- GUI:
  - file picker
  - platform selector
  - **strict mode by default** (fallback disabled unless user enables it)
  - fallback toggle: `Allow fallback generation (less accurate)`
  - **Check Dependencies** action with pass/fail diagnostics
  - **Test Transcript** action for selected file (runtime precheck + details)
  - diagnostics panel showing installed/missing dependencies + strict mode requirements
  - one-click copy for Windows install commands (FFmpeg/ffprobe and faster-whisper)
  - output fields + copy buttons
  - status log with analysis source summary including transcript dependency vs runtime state

## Project Layout

```text
app.py
src/vcs/
  __init__.py
  config.py
  ingest.py
  analyze.py
  compose.py
  gui.py
  providers/
    __init__.py
    base.py
    local_provider.py
tests/
requirements.txt
run-windows.bat
build-windows.bat
```

## Install (Linux/macOS/WSL)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Run on Windows

```bat
run-windows.bat
```

The script will:
1. detect Python via `py -3` or `python`
2. create `.venv` if needed
3. install requirements
4. launch the app

## v1.1.3 Strict Analysis Mode + Runtime Transcript Diagnostics

v1.1.3 keeps strict, grounded analysis as the default and adds runtime transcript prechecks with actionable failure details.

- Generate will **fail** with actionable guidance if required analysis cannot run.
- Strict mode requires:
  - `metadata_source=ffprobe`
  - `visual_source=opencv`
  - `transcript_source=whisper` when audio is present/unknown
  - OR explicit no-audio detection from `ffprobe`
- To allow best-effort generation, enable:
  - `Allow fallback generation (less accurate)` in the GUI

Status log now reports what actually ran, for example:
- `metadata=ffprobe, visual=opencv, transcript=whisper`
- warnings/errors from runtime dependency checks

## Quick setup troubleshooting (v1.1.3)

In the app, click **Check Dependencies**.

You will see pass/fail status for:
- `ffprobe` (from FFmpeg)
- OpenCV (`opencv-python`)
- `faster-whisper`

The diagnostics panel also shows:
- what is installed
- what is missing
- what strict mode requires
- audio assumption notes (strict transcript checks depend on ffprobe metadata)

If a dependency is missing, use one-click copy buttons for Windows install commands:
- **Copy FFmpeg Install Command (Windows)**
- **Copy faster-whisper Install Command (Windows)**

After installing, reopen your terminal/app so PATH/package changes are detected.

### Transcript runtime troubleshooting (v1.1.3)

If **Generate** fails strict mode while diagnostics show faster-whisper is installed, use **Test Transcript** on the same file.

The app now reports a user-friendly cause plus a `Details:` line with truncated runtime exception text.

Common causes and fixes:
- **Model load/cache/permission failure**
  - Ensure user has write access to whisper cache directories.
  - Retry once with internet access if model files were not downloaded yet.
- **Missing runtime libraries / DLL / shared objects**
  - In source mode: reinstall into `.venv` and relaunch app.
  - In EXE mode: rebuild EXE with dependencies bundled (do not patch with system `py -m pip`).
- **Unsupported GPU/CUDA path**
  - Use CPU-compatible runtime setup or install matching CUDA/cuDNN stack.
- **Audio decode/ffmpeg path issues**
  - Verify the selected file plays normally and contains a valid audio stream.
  - Re-export/remux the video if decode errors persist.

Strict mode behavior:
- If `ffprobe` confirms **no audio stream**, transcript is not required.
- If audio is present/unknown and transcript runtime fails, strict mode fails with the specific transcript reason + details.

## EXE vs source mode dependencies (v1.1.3)

The app now reports dependency presence as one of:
- `bundled` (inside packaged EXE)
- `system` (resolved from normal Python/PATH)
- `missing`

### Source / venv mode

Install Python packages into the project venv (not global Python):

```bat
.venv\Scripts\python -m pip install opencv-python
.venv\Scripts\python -m pip install faster-whisper
```

Also install FFmpeg so `ffprobe` is on PATH:

```bat
winget install --id Gyan.FFmpeg -e
```

### Packaged EXE mode

Do **not** try to fix dependencies with `py -m pip` after the EXE is built.
In EXE mode, dependencies must be bundled at build time:
- `opencv-python`
- `faster-whisper` (and transitive runtime libs)
- `ffprobe.exe` (bundled into the EXE)

If EXE diagnostics show `missing`, rebuild the EXE with bundled deps.

## Build Windows EXE (PyInstaller)

1. Put `ffprobe.exe` at `third_party\ffprobe.exe` (recommended), or ensure build env sets `VCS_FFPROBE_PATH`.
2. Run:

```bat
build-windows.bat
```

This uses `video-caption-studio.spec` to bundle:
- faster-whisper stack
- ctranslate2/tokenizers runtime pieces
- ffprobe binary when available

Output:
- `dist\video-caption-studio.exe`

## Automated Windows EXE Releases (GitHub Actions)

This repo includes:
- `.github/workflows/release-windows-exe.yml`

It will:
- run on `workflow_dispatch` (manual trigger) and tag pushes matching `v*`
- build `video-caption-studio.exe` on `windows-latest` with Python 3.11
- upload the EXE as a workflow artifact
- on tag pushes (`v*`), create/update the GitHub Release and attach the EXE asset

### Create a release tag

```bash
git tag v0.1.0
git push origin v0.1.0
```

### Download the EXE

After the workflow finishes, download from either:
- **GitHub Releases** page for the tagged version (asset: `video-caption-studio.exe`)
- **Actions run artifacts** (`video-caption-studio-windows-exe`) for manual runs

## Testing / Basic Checks

```bash
python3 -m py_compile app.py src/vcs/*.py src/vcs/providers/*.py
pytest -q
```

## Extensibility Notes

- **Provider pluggability:** `src/vcs/providers/base.py` defines the provider contract. Add online providers later and route via `compose.get_provider()`.
- **Batch-ready foundation:** ingest/analyze/compose are pure-ish service layers and can be orchestrated over multiple files without GUI changes.
- **Transcript hook:** currently placeholder for offline STT integration in a later iteration.
