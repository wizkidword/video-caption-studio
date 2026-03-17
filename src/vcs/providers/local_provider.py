from __future__ import annotations

from ..analyze import AnalysisResult
from ..config import PlatformPreset
from ..ingest import VideoMetadata
from .base import GeneratedContent


class LocalHeuristicProvider:
    """Offline heuristic provider.

    Deterministic, local-only generation to keep MVP fully offline.
    """

    def generate(
        self,
        metadata: VideoMetadata,
        analysis: AnalysisResult,
        preset: PlatformPreset,
    ) -> GeneratedContent:
        base_subject = metadata.filename.rsplit(".", 1)[0].replace("_", " ").strip() or "This clip"
        tags = analysis.visual_tags or ["video"]
        transcript_hint = ""
        if analysis.transcript:
            transcript_hint = f"\nQuote: \"{analysis.transcript[:120]}\""

        title = self._build_title(base_subject, tags, preset)
        caption = (
            f"{base_subject} — crafted for {preset.label}.\n"
            f"Visual vibe: {', '.join(tags)}.\n"
            f"Tone: {preset.tone}. Style: {preset.caption_style}."
            f"{transcript_hint}\n"
            "Follow for more short-form edits."
        )

        hashtags = self._hashtags(tags, preset.hashtag_count, preset.key)
        return GeneratedContent(title=title, caption=caption, hashtags=hashtags)

    def _build_title(self, subject: str, tags: list[str], preset: PlatformPreset) -> str:
        lead = {
            "tiktok": "POV:",
            "instagram": "A moment:",
            "youtube_shorts": "Watch:",
        }.get(preset.key, "Spotlight:")
        vibe = tags[0].replace("_", " ") if tags else "highlight"
        return f"{lead} {subject} ({vibe})"

    def _hashtags(self, tags: list[str], count: int, platform_key: str) -> str:
        seed = [platform_key, "videocreator", "shortvideo", "contentstrategy"] + tags
        normalized = []
        seen = set()
        for item in seed:
            clean = "".join(ch for ch in item.lower() if ch.isalnum())
            if clean and clean not in seen:
                seen.add(clean)
                normalized.append(f"#{clean}")
        return " ".join(normalized[:count])
