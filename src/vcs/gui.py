from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .analyze import AnalysisContractError, run_analysis
from .compose import ComposeError, ComposeRequest, compose_content
from .config import PLATFORM_PRESETS
from .ingest import IngestError, collect_metadata


class VideoCaptionStudioApp:
    APP_NAME = "Video Caption Studio"
    WINDOW_TITLE = "Video Caption Studio · Offline Caption Generator"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry("880x680")
        self._apply_optional_icon()

        self.video_path_var = tk.StringVar()
        self.platform_var = tk.StringVar(value="tiktok")
        self.allow_fallback_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()

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

        ttk.Checkbutton(
            top,
            text="Allow fallback generation (less accurate)",
            variable=self.allow_fallback_var,
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

        ttk.Button(top, text="Generate", command=self._generate).grid(row=4, column=1, sticky="e")
        top.columnconfigure(0, weight=1)

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

            content = compose_content(
                ComposeRequest(
                    metadata=metadata,
                    analysis=analysis,
                    platform_key=self.platform_var.get(),
                )
            )

            self._set_text(self.title_text, content.title)
            self._set_text(self.caption_text, content.caption)
            self._set_text(self.hashtags_text, content.hashtags)

            report = analysis.report
            if report:
                self._log(
                    "Analysis summary: "
                    f"metadata={report.metadata_source}, visual={report.visual_source}, transcript={report.transcript_source}"
                )
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
