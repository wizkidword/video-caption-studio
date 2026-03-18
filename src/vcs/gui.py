from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .analyze import AnalysisContractError, run_analysis, transcript_runtime_precheck
from .compose import ComposeError, ComposeRequest, compose_content
from .config import COMPOSITION_MODES, CREATIVITY_LEVELS, DEFAULT_COMPOSITION_MODE, PLATFORM_PRESETS
from .diagnostics import format_diagnostics_report, run_dependency_diagnostics, windows_install_commands
from .ingest import IngestError, collect_metadata


class VideoCaptionStudioApp:
    APP_NAME = f"Video Caption Studio v{__version__}"
    WINDOW_TITLE = f"Video Caption Studio v{__version__} · Offline Caption Generator"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry("880x680")
        self._apply_optional_icon()

        self.video_path_var = tk.StringVar()
        self.platform_var = tk.StringVar(value="tiktok")
        self.composition_mode_labels = {v: k for k, v in COMPOSITION_MODES.items()}
        self.composition_mode_var = tk.StringVar(value=COMPOSITION_MODES[DEFAULT_COMPOSITION_MODE])
        self.creativity_var = tk.StringVar(value="medium")
        self.brand_voice_var = tk.StringVar()
        self.allow_fallback_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()
        self._run_diagnostics()

    def _apply_optional_icon(self) -> None:
        root_dir = Path(__file__).resolve().parents[2]
        ico_candidates = [
            root_dir / "assets" / "app.ico",
            root_dir / "assets" / "icon.ico",
            root_dir / "icon.ico",
        ]
        png_candidates = [
            root_dir / "assets" / "app.png",
            root_dir / "assets" / "icon.png",
            root_dir / "icon.png",
        ]

        for ico_path in ico_candidates:
            if ico_path.exists():
                try:
                    self.root.iconbitmap(default=str(ico_path))
                    return
                except Exception:
                    pass

        for png_path in png_candidates:
            if png_path.exists():
                try:
                    icon_image = tk.PhotoImage(file=str(png_path))
                    self.root.iconphoto(True, icon_image)
                    self.root._icon_image_ref = icon_image  # type: ignore[attr-defined]
                    return
                except Exception:
                    pass

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text=self.APP_NAME, font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))

        top = ttk.LabelFrame(frame, text="Input", padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="Video File").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.video_path_var, width=80).grid(row=1, column=0, padx=(0, 8), sticky="ew")
        ttk.Button(top, text="Browse", command=self._pick_video).grid(row=1, column=1)

        ttk.Label(top, text="Platform").grid(row=2, column=0, sticky="w", pady=(10, 0))
        platform_menu = ttk.Combobox(
            top,
            textvariable=self.platform_var,
            values=list(PLATFORM_PRESETS.keys()),
            state="readonly",
            width=20,
        )
        platform_menu.grid(row=3, column=0, sticky="w")

        ttk.Label(top, text="Composition Mode").grid(row=2, column=1, sticky="w", pady=(10, 0))
        composition_menu = ttk.Combobox(
            top,
            textvariable=self.composition_mode_var,
            values=list(COMPOSITION_MODES.values()),
            state="readonly",
            width=35,
        )
        composition_menu.grid(row=3, column=1, sticky="w")

        ttk.Label(top, text="Creativity").grid(row=4, column=0, sticky="w", pady=(10, 0))
        creativity_menu = ttk.Combobox(
            top,
            textvariable=self.creativity_var,
            values=list(CREATIVITY_LEVELS),
            state="readonly",
            width=12,
        )
        creativity_menu.grid(row=5, column=0, sticky="w")

        ttk.Label(top, text="Brand voice / notes (optional)").grid(row=4, column=1, sticky="w", pady=(10, 0))
        ttk.Entry(top, textvariable=self.brand_voice_var, width=40).grid(row=5, column=1, sticky="ew")

        ttk.Checkbutton(
            top,
            text="Allow fallback generation (less accurate)",
            variable=self.allow_fallback_var,
        ).grid(row=6, column=0, sticky="w", pady=(10, 0))

        action_row = ttk.Frame(top)
        action_row.grid(row=6, column=1, sticky="e")
        ttk.Button(action_row, text="Check Dependencies", command=self._run_diagnostics).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(action_row, text="Test Transcript", command=self._test_transcript).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(action_row, text="Generate", command=self._generate).pack(side=tk.LEFT)
        top.columnconfigure(0, weight=1)

        diagnostics_frame = ttk.LabelFrame(frame, text="Dependency Diagnostics", padding=8)
        diagnostics_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.diagnostics_box = tk.Text(diagnostics_frame, height=11, wrap="word")
        self.diagnostics_box.pack(fill=tk.BOTH, expand=True)

        button_row = ttk.Frame(diagnostics_frame)
        button_row.pack(fill=tk.X, pady=(8, 0))
        self.copy_ffmpeg_btn = ttk.Button(
            button_row,
            text="Copy FFmpeg Install Command (Windows)",
            command=lambda: self._copy_install_command("ffprobe"),
        )
        self.copy_ffmpeg_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.copy_whisper_btn = ttk.Button(
            button_row,
            text="Copy faster-whisper Install Command (Windows)",
            command=lambda: self._copy_install_command("faster_whisper"),
        )
        self.copy_whisper_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.copy_ollama_btn = ttk.Button(
            button_row,
            text="Copy Ollama Setup Commands",
            command=lambda: self._copy_install_command("ollama"),
        )
        self.copy_ollama_btn.pack(side=tk.LEFT)

        output = ttk.LabelFrame(frame, text="Generated Output", padding=10)
        output.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        self.title_text = self._build_output_field(output, "Title", 0)
        self.caption_text = self._build_output_field(output, "Caption", 1)
        self.hashtags_text = self._build_output_field(output, "Hashtags", 2)

        log_frame = ttk.LabelFrame(frame, text="Status Log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self.log_box = tk.Text(log_frame, height=7, wrap="word")
        self.log_box.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))

    def _build_output_field(self, parent: ttk.LabelFrame, label: str, row: int) -> tk.Text:
        container = ttk.Frame(parent)
        container.grid(row=row, column=0, sticky="nsew", pady=(0, 8))
        parent.rowconfigure(row, weight=1)
        parent.columnconfigure(0, weight=1)

        ttk.Label(container, text=label).pack(anchor="w")
        text = tk.Text(container, height=4 if label != "Caption" else 8, wrap="word")
        text.pack(fill=tk.BOTH, expand=True)
        ttk.Button(container, text=f"Copy {label}", command=lambda t=text: self._copy_text(t)).pack(anchor="e", pady=(4, 0))
        return text

    def _pick_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose video file",
            filetypes=[("Video Files", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"), ("All files", "*.*")],
        )
        if path:
            self.video_path_var.set(path)
            self._log(f"Selected: {path}")

    def _test_transcript(self) -> None:
        video_path = self.video_path_var.get().strip()
        if not video_path:
            messagebox.showwarning("Missing input", "Please choose a video first.")
            return

        self.status_var.set("Testing transcript runtime...")
        self.root.update_idletasks()

        try:
            metadata = collect_metadata(video_path)
            if metadata.has_audio is False:
                msg = "No audio stream detected by ffprobe. Transcript runtime test not required for strict mode."
                self._log(msg)
                self.status_var.set("Transcript test skipped (no audio).")
                messagebox.showinfo("Transcript Test", msg)
                return

            ok, user_msg, detail = transcript_runtime_precheck(video_path)
            status = "PASS" if ok else "FAIL"
            self._log(f"Transcript precheck [{status}]: {user_msg}")
            if detail:
                self._log(f"Details: {detail}")
            self.status_var.set("Transcript test passed." if ok else "Transcript test failed.")
            messagebox.showinfo("Transcript Test", f"{user_msg}" + (f"\n\nDetails: {detail}" if detail else ""))
        except IngestError as exc:
            self.status_var.set("Transcript test failed.")
            messagebox.showerror("Transcript Test", str(exc))
            self._log(f"Transcript test error: {exc}")
        except Exception as exc:  # pragma: no cover - UI safety
            self.status_var.set("Transcript test failed.")
            messagebox.showerror("Transcript Test", str(exc))
            self._log(f"Transcript test unexpected error: {exc}")

    def _generate(self) -> None:
        video_path = self.video_path_var.get().strip()
        if not video_path:
            messagebox.showwarning("Missing input", "Please choose a video first.")
            return

        strict_mode = not self.allow_fallback_var.get()

        self.status_var.set("Generating...")
        self.root.update_idletasks()

        try:
            metadata = collect_metadata(video_path)
            analysis = run_analysis(video_path, metadata=metadata, strict_mode=strict_mode)

            mode_label = self.composition_mode_var.get().strip()
            provider_key = self.composition_mode_labels.get(mode_label, DEFAULT_COMPOSITION_MODE)
            self._log(f"Composition provider selected: {COMPOSITION_MODES.get(provider_key, mode_label or provider_key)}")

            content = compose_content(
                ComposeRequest(
                    metadata=metadata,
                    analysis=analysis,
                    platform_key=self.platform_var.get(),
                    provider_key=provider_key,
                    creativity=self.creativity_var.get(),
                    brand_voice_notes=self.brand_voice_var.get().strip(),
                )
            )
            self._log(f"Composition provider used: {COMPOSITION_MODES.get(provider_key, provider_key)}")
            if provider_key == "ollama" and content.resolved_model:
                self._log(f"Smart mode resolved Ollama model: {content.resolved_model}")

            self._set_text(self.title_text, content.title)
            self._set_text(self.caption_text, content.caption)
            self._set_text(self.hashtags_text, content.hashtags)

            report = analysis.report
            if report:
                self._log(
                    "Analysis summary: "
                    f"metadata={report.metadata_source}, visual={report.visual_source}, transcript={report.transcript_source}"
                )
                runtime_state = "passed" if report.transcript_runtime_ok else "failed"
                if report.transcript_runtime_ok is None:
                    runtime_state = "not-run"
                self._log(
                    "Transcript status: "
                    f"dependency={'present' if report.transcript_dependency_available else 'missing'}, "
                    f"runtime={runtime_state}"
                )
                if report.transcript_runtime_message:
                    self._log(f"Transcript: {report.transcript_runtime_message}")
                if report.transcript_error_detail:
                    self._log(f"Details: {report.transcript_error_detail}")
                for warning in report.warnings:
                    self._log(f"Warning: {warning}")
                for error in report.errors:
                    self._log(f"Error: {error}")
            self.status_var.set("Done.")
        except AnalysisContractError as exc:
            self.status_var.set("Failed.")
            messagebox.showerror("Analysis requirements not met", str(exc))
            self._log(f"Analysis error: {exc}")
        except IngestError as exc:
            self.status_var.set("Failed.")
            messagebox.showerror("Ingest error", str(exc))
            self._log(f"Error: {exc}")
        except ComposeError as exc:
            self.status_var.set("Failed.")
            messagebox.showerror("Compose error", str(exc))
            self._log(f"Compose error: {exc}")
        except Exception as exc:  # pragma: no cover - UI safety
            self.status_var.set("Failed.")
            messagebox.showerror("Unexpected error", str(exc))
            self._log(f"Unexpected error: {exc}")

    def _run_diagnostics(self) -> None:
        diagnostics = run_dependency_diagnostics()
        report = format_diagnostics_report(diagnostics)

        self.diagnostics_box.delete("1.0", tk.END)
        self.diagnostics_box.insert("1.0", report)

        missing_keys = {item.key for item in diagnostics.missing}
        self.copy_ffmpeg_btn.state(["!disabled"] if "ffprobe" in missing_keys else ["disabled"])
        self.copy_whisper_btn.state(["!disabled"] if "faster_whisper" in missing_keys else ["disabled"])
        self.copy_ollama_btn.state(["!disabled"] if "ollama" in missing_keys else ["disabled"])

        installed = ", ".join(item.label for item in diagnostics.installed) or "none"
        missing = ", ".join(item.label for item in diagnostics.missing) or "none"
        self._log(f"Diagnostics installed: {installed}")
        self._log(f"Diagnostics missing: {missing}")
        self._log("Strict mode requires ffprobe + OpenCV (+ faster-whisper when audio exists/unknown).")
        self.status_var.set("Dependency check complete.")

    def _copy_install_command(self, dependency_key: str) -> None:
        command = windows_install_commands().get(dependency_key)
        if not command:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(command)
        self.status_var.set("Install command copied. Reopen terminal/app after install.")
        self._log(f"Copied Windows install command for {dependency_key}.")

    def _set_text(self, widget: tk.Text, value: str) -> None:
        widget.delete("1.0", tk.END)
        widget.insert("1.0", value)

    def _copy_text(self, widget: tk.Text) -> None:
        text = widget.get("1.0", tk.END).strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Copied to clipboard.")

    def _log(self, line: str) -> None:
        self.log_box.insert(tk.END, f"{line}\n")
        self.log_box.see(tk.END)


def launch_app() -> None:
    root = tk.Tk()
    VideoCaptionStudioApp(root)
    root.mainloop()
