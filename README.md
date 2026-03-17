# Video Caption Studio

Offline-first desktop app (Tkinter) for generating short-form video **title**, **caption**, and **hashtags** from a single local video file.

Current MVP targets Windows-friendly use and keeps the architecture clean for:
- future **online AI providers** (provider-pluggable compose layer)
- future **batch processing** (analysis/compose layers already decoupled from UI)

## Features

- Local single-video workflow
- Platform presets:
  - TikTok
  - Instagram Reels
  - YouTube Shorts
- Ingest layer:
  - validates file path + extension
  - attempts metadata with `ffprobe` when available
  - falls back gracefully when `ffprobe` is unavailable
- Analyze layer:
  - frame sampling plan helper
  - lightweight OpenCV visual tags when available
  - graceful fallback when OpenCV is unavailable
  - transcript placeholder hook (returns empty transcript for now)
- Compose layer:
  - provider interface contract
  - local heuristic provider for offline generation
- GUI:
  - file picker
  - platform selector
  - Generate button
  - output fields + copy buttons
  - status log

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

## Build Windows EXE (PyInstaller)

```bat
build-windows.bat
```

Output:
- `dist\video-caption-studio.exe`

## Testing / Basic Checks

```bash
python3 -m py_compile app.py src/vcs/*.py src/vcs/providers/*.py
pytest -q
```

## Extensibility Notes

- **Provider pluggability:** `src/vcs/providers/base.py` defines the provider contract. Add online providers later and route via `compose.get_provider()`.
- **Batch-ready foundation:** ingest/analyze/compose are pure-ish service layers and can be orchestrated over multiple files without GUI changes.
- **Transcript hook:** currently placeholder for offline STT integration in a later iteration.
