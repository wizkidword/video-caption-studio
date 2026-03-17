from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .analyze import extract_transcript_placeholder, extract_visual_signals
from .compose import ComposeRequest, compose_content
from .config import PLATFORM_PRESETS
from .ingest import IngestError, collect_metadata


class VideoCaptionStudioApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Video Caption Studio")
        self.root.geometry("880x680")

        self.video_path_var = tk.StringVar()
        self.platform_var = tk.StringVar(value="tiktok")
        self.status_var = tk.StringVar(value="Ready.")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

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

        ttk.Button(top, text="Generate", command=self._generate).grid(row=3, column=1, sticky="e")
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

        self.status_var.set("Generating...")
        self.root.update_idletasks()

        try:
            metadata = collect_metadata(video_path)
            analysis = extract_visual_signals(video_path)
            analysis.transcript = extract_transcript_placeholder(video_path)

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

            self._log(f"Metadata source: {metadata.source}; tags={analysis.visual_tags or ['none']}")
            if analysis.notes:
                for note in analysis.notes:
                    self._log(note)
            self.status_var.set("Done.")
        except IngestError as exc:
            self.status_var.set("Failed.")
            messagebox.showerror("Ingest error", str(exc))
            self._log(f"Error: {exc}")
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
