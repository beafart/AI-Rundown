from __future__ import annotations

import json
import re
from typing import Any
from urllib import request


SYSTEM_PROMPT = """
You are an English reading tutor for a Korean learner.
Analyze the given English sentence.
Return valid JSON only. Do not include markdown.
Schema:
{
  "sentence": "original sentence",
  "translation": "natural Korean translation",
  "chunks": [
    {"text": "English chunk", "meaning": "Korean meaning", "note": "short grammar/usage note or empty string"}
  ],
  "vocabulary": [
    {"term": "word or phrase", "meaning": "Korean meaning with useful note or example in parentheses if helpful"}
  ]
}
Pick useful vocabulary and expressions only. Avoid obvious words unless important.
""".strip()

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "sentence": {"type": "string"},
        "translation": {"type": "string"},
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meaning": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["text", "meaning", "note"],
            },
        },
        "vocabulary": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["term", "meaning"],
            },
        },
    },
    "required": ["sentence", "translation", "chunks", "vocabulary"],
}


def analyze_sentence(sentence: str, env: dict[str, str]) -> dict[str, Any]:
    base_url = env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = env.get("OLLAMA_MODEL", "qwen3:4b")
    timeout = int(env.get("OLLAMA_TIMEOUT_SECONDS", "120"))
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": ANALYSIS_SCHEMA,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "/no_think\n" + sentence},
        ],
        "options": {"temperature": 0.2, "num_predict": 700},
    }
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        f"{base_url}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    content = raw.get("message", {}).get("content", "")
    try:
        parsed = parse_json(content)
    except json.JSONDecodeError:
        parsed = fallback_analysis(sentence, content)
    parsed.setdefault("sentence", sentence)
    parsed.setdefault("translation", "")
    parsed.setdefault("chunks", [{"text": sentence, "meaning": parsed.get("translation", ""), "note": ""}])
    parsed.setdefault("vocabulary", [])
    return parsed


def parse_json(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def fallback_analysis(sentence: str, content: str) -> dict[str, Any]:
    return {
        "sentence": sentence,
        "translation": "",
        "chunks": [{"text": sentence, "meaning": "", "note": "Model did not return valid JSON. Try re-analyze."}],
        "vocabulary": [],
        "raw": content[:1000],
    }
