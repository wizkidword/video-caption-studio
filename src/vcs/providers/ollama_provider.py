from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

from ..analyze import AnalysisResult
from ..config import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_TIMEOUT_SEC, PlatformPreset
from ..ingest import VideoMetadata
from .base import GeneratedContent


class OllamaProviderError(Exception):
    pass


@dataclass(frozen=True)
class OllamaHealth:
    available: bool
    detail: str
    model_available: bool


def check_ollama_health(model: str = DEFAULT_OLLAMA_MODEL, timeout_sec: int = 3) -> OllamaHealth:
    base = "http://127.0.0.1:11434"
    try:
        tags_resp = _post_json(
            f"{base}/api/tags",
            payload={},
            timeout_sec=timeout_sec,
            method="GET",
        )
    except OllamaProviderError as exc:
        return OllamaHealth(False, str(exc), False)

    models = tags_resp.get("models", []) if isinstance(tags_resp, dict) else []
    names = {str(item.get("name", "")).strip() for item in models if isinstance(item, dict)}
    has_model = model in names
    if has_model:
        return OllamaHealth(True, f"Ollama running. Model '{model}' is available.", True)
    return OllamaHealth(
        True,
        f"Ollama running, but model '{model}' not found. Run: ollama pull {model}",
        False,
    )


class OllamaProvider:
    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        timeout_sec: int = DEFAULT_OLLAMA_TIMEOUT_SEC,
        creativity: str = "medium",
        brand_voice_notes: str = "",
    ) -> None:
        self.model = model
        self.timeout_sec = timeout_sec
        self.creativity = creativity.lower().strip() or "medium"
        self.brand_voice_notes = brand_voice_notes.strip()

    def generate(
        self,
        metadata: VideoMetadata,
        analysis: AnalysisResult,
        preset: PlatformPreset,
    ) -> GeneratedContent:
        health = check_ollama_health(model=self.model, timeout_sec=min(self.timeout_sec, 5))
        if not health.available:
            raise OllamaProviderError(
                "Smart mode requires local Ollama at http://127.0.0.1:11434. "
                f"{health.detail} Switch Composition Mode to 'Template (Fallback)' or start Ollama."
            )
        if not health.model_available:
            raise OllamaProviderError(
                f"Smart mode model is unavailable: {health.detail} "
                "Switch Composition Mode to 'Template (Fallback)' or pull the model."
            )

        prompt = build_prompt(metadata, analysis, preset, self.creativity, self.brand_voice_notes)
        try:
            payload = _post_json(
                "http://127.0.0.1:11434/api/generate",
                payload={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": creativity_temperature(self.creativity),
                    },
                },
                timeout_sec=self.timeout_sec,
            )
        except OllamaProviderError as exc:
            raise OllamaProviderError(
                f"Smart mode timed out/failed talking to Ollama: {exc}. "
                "Switch to 'Template (Fallback)' if needed."
            ) from exc

        response_text = str(payload.get("response", "")).strip() if isinstance(payload, dict) else ""
        if not response_text:
            raise OllamaProviderError("Ollama returned an empty response.")

        parsed = parse_model_output(response_text, hashtag_count=preset.hashtag_count)
        return GeneratedContent(title=parsed.title, caption=parsed.caption, hashtags=" ".join(parsed.hashtags))


def creativity_temperature(level: str) -> float:
    lookup = {"low": 0.25, "medium": 0.55, "high": 0.85}
    return lookup.get(level.lower().strip(), 0.55)


def platform_instruction(preset: PlatformPreset) -> str:
    if preset.key == "tiktok":
        return "TikTok: strong first-line hook, playful energy, one short CTA."
    if preset.key == "instagram":
        return "Instagram Reels: polished lifestyle voice, conversational, concise."
    return "YouTube Shorts: clear curiosity hook, direct and informative concise tone."


def _keyword_candidates(metadata: VideoMetadata, analysis: AnalysisResult) -> list[str]:
    words: list[str] = []
    words.extend(tag.replace("_", " ") for tag in analysis.visual_tags)
    subject = metadata.filename.rsplit(".", 1)[0].replace("_", " ")
    words.extend(subject.split())
    words.extend(re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", analysis.transcript or ""))

    stop = {
        "this",
        "that",
        "with",
        "from",
        "have",
        "your",
        "about",
        "video",
        "clip",
        "just",
        "really",
        "into",
    }
    cleaned: list[str] = []
    seen = set()
    for raw in words:
        token = "".join(ch for ch in raw.lower() if ch.isalnum())
        if len(token) < 4 or token in stop or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
        if len(cleaned) >= 16:
            break
    return cleaned


def build_prompt(
    metadata: VideoMetadata,
    analysis: AnalysisResult,
    preset: PlatformPreset,
    creativity: str,
    brand_voice_notes: str,
) -> str:
    transcript = (analysis.transcript or "").strip()
    transcript_excerpt = transcript[:900] if transcript else "(no transcript captured)"
    keywords = _keyword_candidates(metadata, analysis)
    keyword_hint = ", ".join(keywords[:8]) if keywords else "none"

    return (
        "You are an expert short-form social copywriter.\n"
        "Return ONLY compact JSON with keys: title, caption, hashtags.\n"
        "hashtags can be array of strings OR space-delimited hashtag string.\n"
        "No markdown. No explanation.\n\n"
        f"Platform: {preset.label}\n"
        f"Platform guidance: {platform_instruction(preset)}\n"
        f"Target hashtag count: {preset.hashtag_count}\n"
        f"Creativity level: {creativity}\n"
        f"Tone baseline: {preset.tone}\n"
        f"Caption style: {preset.caption_style}\n"
        f"Brand voice notes: {brand_voice_notes or '(none)'}\n"
        f"Video filename subject: {metadata.filename}\n"
        f"Visual tags: {', '.join(analysis.visual_tags) if analysis.visual_tags else 'none'}\n"
        f"Detected keywords: {keyword_hint}\n"
        f"Transcript excerpt: {transcript_excerpt}\n\n"
        "Guardrails:\n"
        "- Keep title <= 80 chars and caption <= 220 chars.\n"
        "- Make output social-ready and concise.\n"
        "- Include at least 3 content-specific hashtags from visual tags, transcript keywords, or filename subject.\n"
        "- Avoid generic-only hashtag sets (#fyp #viral etc alone is not allowed).\n"
        "- Hashtags must start with # and be unique.\n"
    )


@dataclass
class ParsedOutput:
    title: str
    caption: str
    hashtags: list[str]


def parse_model_output(text: str, hashtag_count: int = 7) -> ParsedOutput:
    obj = _extract_json_object(text)
    if obj:
        title = _clean_text(str(obj.get("title", "")))
        caption = _clean_text(str(obj.get("caption", "")))
        hashtags = normalize_hashtags(obj.get("hashtags"), fallback_text=text)
        if title and caption and hashtags:
            return ParsedOutput(title=title, caption=caption, hashtags=hashtags[:hashtag_count])

    title = _extract_labeled(text, ["title", "headline"]) or _clean_text(text.splitlines()[0] if text.strip() else "")
    caption = _extract_labeled(text, ["caption", "description"]) or _clean_text(text)
    hashtags = normalize_hashtags(_extract_labeled(text, ["hashtags", "tags"]), fallback_text=text)

    if not title:
        title = "Fresh short-form moment"
    if not caption:
        caption = "Built for short-form social."
    if not hashtags:
        hashtags = ["#shortvideo", "#contentcreator", "#video"]

    return ParsedOutput(title=title, caption=caption, hashtags=hashtags[:hashtag_count])


def normalize_hashtags(source: Any, fallback_text: str = "") -> list[str]:
    raw_items: list[str] = []
    if isinstance(source, str):
        raw_items.extend(source.replace(",", " ").split())
    elif isinstance(source, Iterable) and not isinstance(source, (dict, bytes)):
        for item in source:
            if isinstance(item, str):
                raw_items.extend(item.replace(",", " ").split())
    raw_items.extend(re.findall(r"#[A-Za-z0-9_]+", fallback_text))

    normalized: list[str] = []
    seen = set()
    for item in raw_items:
        clean = "".join(ch for ch in item.lower() if ch.isalnum() or ch == "#")
        if not clean:
            continue
        if not clean.startswith("#"):
            clean = f"#{clean}"
        tag_body = clean[1:]
        if len(tag_body) < 3:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        normalized.append(clean)
    return normalized


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None

    direct = _try_json(text)
    if isinstance(direct, dict):
        return direct

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = text[start : end + 1]
    parsed = _try_json(candidate)
    if isinstance(parsed, dict):
        return parsed
    return None


def _try_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_labeled(text: str, keys: list[str]) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        for key in keys:
            prefix = f"{key}:"
            if lowered.startswith(prefix):
                return _clean_text(stripped[len(prefix) :])
    return ""


def _clean_text(value: str) -> str:
    clean = re.sub(r"\s+", " ", (value or "").strip())
    return clean.strip('"')


def _post_json(url: str, payload: dict[str, Any], timeout_sec: int, method: str = "POST") -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=None if method == "GET" else json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            body = response.read().decode("utf-8")
            parsed = json.loads(body) if body else {}
            return parsed if isinstance(parsed, dict) else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise OllamaProviderError(f"HTTP {exc.code} from Ollama {url}. {detail}".strip()) from exc
    except urllib.error.URLError as exc:
        raise OllamaProviderError(f"Could not reach Ollama at {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OllamaProviderError(f"Request to {url} timed out after {timeout_sec}s") from exc
    except json.JSONDecodeError as exc:
        raise OllamaProviderError(f"Invalid JSON from Ollama: {exc}") from exc
