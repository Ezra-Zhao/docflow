"""Field extraction / summarization — pluggable.

Two backends behind one interface `analyze(text, meta) -> dict`:

1. Rule-based (default, no API key needed): title heuristic, word/char
   counts, and regex extraction of emails, money amounts and dates.
2. OpenAI-compatible LLM: active when DOCFLOW_LLM_API_KEY is set.
   Configure with DOCFLOW_LLM_BASE_URL (default https://api.openai.com/v1)
   and DOCFLOW_LLM_MODEL (default gpt-4o-mini). Any OpenAI-compatible
   endpoint works (OpenAI, Azure OpenAI, local vLLM/Ollama gateways...).
   If the call fails, we fall back to the rule-based result and say so.
"""
import json
import os
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MONEY_RE = re.compile(
    r"(?:\$|USD\s?|EUR\s?|€)\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d{1,3}(?:,\d{3})*\.\d{2}\s?(?:USD|dollars?)",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b"
)

MAX_ITEMS = 20


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for it in items:
        it = it.strip()
        if it and it not in seen:
            seen.append(it)
        if len(seen) >= MAX_ITEMS:
            break
    return seen


def rule_based(text: str, meta: dict) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0][:120] if lines else None
    words = len(text.split())
    # A one-line "summary": first non-title sentence-ish line.
    summary = None
    for ln in lines[1:]:
        if len(ln) >= 40:
            summary = ln[:300]
            break
    return {
        "backend": "rules",
        "title": title,
        "word_count": words,
        "char_count": len(text),
        "emails": _unique(EMAIL_RE.findall(text)),
        "amounts": _unique(MONEY_RE.findall(text)),
        "dates": _unique(DATE_RE.findall(text)),
        "summary": summary,
        **{k: v for k, v in meta.items() if k in ("pages", "paragraphs", "tables")},
    }


def llm_based(text: str, meta: dict) -> dict:
    import httpx

    base = os.environ.get("DOCFLOW_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("DOCFLOW_LLM_MODEL", "gpt-4o-mini")
    key = os.environ["DOCFLOW_LLM_API_KEY"]
    prompt = (
        "Extract structured fields from the document below. Reply with JSON only: "
        '{"title": str|null, "summary": str (max 60 words), "emails": [str], '
        '"amounts": [str], "dates": [str], "key_points": [str]}\n\n'
        + text[:12000]
    )
    resp = httpx.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    data["backend"] = f"llm:{model}"
    data["word_count"] = len(text.split())
    data["char_count"] = len(text)
    return data


def analyze(text: str, meta: dict) -> dict:
    """Pluggable entry point used by the pipeline."""
    if not text.strip():
        result = rule_based(text, meta)
        result["note"] = "no extractable text"
        return result
    if os.environ.get("DOCFLOW_LLM_API_KEY"):
        try:
            return llm_based(text, meta)
        except Exception as exc:  # fall back, but say so honestly
            result = rule_based(text, meta)
            result["llm_error"] = f"{type(exc).__name__}: {exc}"[:200]
            return result
    return rule_based(text, meta)
