from __future__ import annotations

import json
import re
from typing import Any
from urllib import request


SYSTEM_PROMPT = """
You are an English reading tutor for a Korean learner.
Analyze the given English sentence.
Return valid JSON only. Do not include markdown.
Write Korean explanations in a clear chunk-by-chunk tutoring style.
Use common Korean tech translations and preserve named entities accurately:
- Microsoft AI CEO Mustafa Suleyman = 마이크로소프트 AI 부문 CEO 무스타파 술레이만
- Anthropic = 앤트로픽
- Claude = 클로드
- instructions = 지침서 or 지침
- constitution docs = 헌장 문서 or Constitution 문서
- consciousness = 의식 or 자각
- call A B = A를 B라고 부르다/평가하다
Never mistranslate Claude as cloud, instructions as instance, or Anthropic as Android/andropic.
Schema:
{
  "sentence": "original sentence",
  "translation": "full natural Korean translation",
  "natural_paraphrase": "more natural Korean paraphrase, with inferred nuance if helpful",
  "key_point": "one or two Korean sentences explaining the core point or nuance",
  "chunks": [
    {
      "text": "English chunk in sentence order",
      "meaning": "Korean chunk meaning",
      "notes": ["word/grammar/context explanation in Korean"]
    }
  ],
  "vocabulary": [
    {"term": "word or phrase", "meaning": "Korean meaning with useful note or example in parentheses if helpful"}
  ]
}
Chunk the sentence into meaningful units, not word-by-word fragments.
Use the style:
English chunk -> Korean meaning -> useful words, expressions, grammar, and context notes.
Include named entities if they matter. Avoid obvious words unless important.
""".strip()

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "sentence": {"type": "string"},
        "translation": {"type": "string"},
        "natural_paraphrase": {"type": "string"},
        "key_point": {"type": "string"},
        "chunks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "meaning": {"type": "string"},
                    "notes": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["text", "meaning", "notes"],
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
    "required": ["sentence", "translation", "natural_paraphrase", "key_point", "chunks", "vocabulary"],
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
        "options": {"temperature": 0.2, "num_predict": 1200},
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
    parsed.setdefault("natural_paraphrase", "")
    parsed.setdefault("key_point", "")
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
        "natural_paraphrase": "",
        "key_point": "",
        "chunks": [{"text": sentence, "meaning": "", "notes": ["Model did not return valid JSON. Try re-analyze."]}],
        "vocabulary": [],
        "raw": content[:1000],
    }
