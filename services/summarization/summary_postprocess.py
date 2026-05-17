"""Post-processing for abstractive summaries (summary_short / ViT5)."""
import re

# Colloquial fillers / discourse markers — common ViT5 hallucinations when forced long.
_FILLER_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bờ+\b", re.IGNORECASE),
    re.compile(r"\bà+\b", re.IGNORECASE),
    re.compile(r"\bừm+\b", re.IGNORECASE),
    re.compile(r"\buh+\b", re.IGNORECASE),
    re.compile(r"\bum+\b", re.IGNORECASE),
    re.compile(r"\bthì là\b", re.IGNORECASE),
    re.compile(r"\bkiểu như\b", re.IGNORECASE),
    re.compile(r"\bnói chung là\b", re.IGNORECASE),
    re.compile(r"\bcó thể nói rằng\b", re.IGNORECASE),
]

# Leading junk before the first real sentence.
_LEADING_JUNK = re.compile(
    r"^[\s,.:;!?\-–—…]*(?:ờ|à|ừm|uh|um|thì|và|nhưng|nên|vậy|chắc|kiểu)\b[\s,]*",
    re.IGNORECASE,
)


def count_filler_hits(text: str) -> int:
    """Rough count of filler tokens (for quality gate)."""
    if not text:
        return 0
    return sum(len(p.findall(text)) for p in _FILLER_PATTERNS)


def postprocess_abstractive_summary(summary: str) -> str:
    """
    Clean ViT5 output for news-style reading and TTS.

    - Strip invalid chars
    - Remove colloquial fillers
    - Normalize whitespace and punctuation
    - Trim incomplete trailing fragment
    """
    if not summary:
        return ""

    summary = re.sub(r"[^\x00-\x7F\u00C0-\u1EF9\s.,!?:;\"'()\[\]–—-]", "", summary)
    summary = re.sub(r"\s+", " ", summary).strip()

    for pattern in _FILLER_PATTERNS:
        summary = pattern.sub(" ", summary)

    # Repeated leading fillers after token removal
    for _ in range(3):
        cleaned = _LEADING_JUNK.sub("", summary).strip()
        if cleaned == summary:
            break
        summary = cleaned

    summary = re.sub(r"\s+([,.:;!?])", r"\1", summary)
    summary = re.sub(r"([,.!?])\1+", r"\1", summary)
    summary = re.sub(r"\s+", " ", summary).strip()
    summary = re.sub(r"(.+?)\1{2,}", r"\1", summary)

    summary = _trim_incomplete_tail(summary)
    return summary


def _trim_incomplete_tail(text: str) -> str:
    """Drop a short dangling tail without sentence-ending punctuation."""
    text = text.strip()
    if not text or text[-1] in ".!?":
        return text

    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) >= 2 and len(parts[-1]) < 40:
        return " ".join(parts[:-1]).strip()

    if len(text) > 80 and text[-1] not in ".!?":
        last_stop = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
        if last_stop > len(text) // 3:
            return text[: last_stop + 1].strip()

    if text and text[-1] not in ".!?":
        text += "."
    return text
