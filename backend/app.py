from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
import traceback
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from mail_client import fetch_rundown_messages
from newsletter_parser import parse_newsletter
from ollama_client import analyze_sentence
from storage import Storage
from supabase_store import SupabaseStore, is_supabase_configured


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "rundown.sqlite3"


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        env.setdefault(key, value)
    return env


ENV = load_env(ROOT.parent / ".env")
DATA_DIR.mkdir(parents=True, exist_ok=True)


def build_store(env: dict[str, str]) -> Any:
    backend = env.get("STORAGE_BACKEND", "sqlite").strip().lower()
    if backend == "supabase" or (backend == "auto" and is_supabase_configured(env)):
        if not is_supabase_configured(env):
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase storage")
        return SupabaseStore(env)
    return Storage(DB_PATH)


STORE = build_store(ENV)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def text_response(handler: BaseHTTPRequestHandler, status: int, body: str, content_type: str = "text/plain") -> None:
    data = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", f"{content_type}; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if length <= 0:
        return {}
    raw = handler.rfile.read(length).decode("utf-8")
    if not raw.strip():
        return {}
    return json.loads(raw)


def auth_ok(handler: BaseHTTPRequestHandler) -> bool:
    expected = ENV.get("APP_API_TOKEN", "").strip()
    if not expected or expected == "change-me":
        return True
    header = handler.headers.get("Authorization", "")
    token = handler.headers.get("X-App-Token", "")
    if header.startswith("Bearer "):
        token = header[7:]
    return token == expected


def analyze_article(article_id: int) -> None:
    article = STORE.get_article(article_id)
    if not article:
        return
    STORE.update_article_status(article_id, "analyzing", None)
    sections = parse_newsletter(article["text"])
    STORE.replace_sections(article_id, sections)

    for section in STORE.list_sections(article_id):
        sentences = split_sentences(section["body"])
        for index, sentence in enumerate(sentences):
            existing = STORE.find_sentence(article_id, section["id"], index)
            if existing:
                continue
            try:
                result = analyze_sentence(sentence, ENV)
            except Exception as exc:
                result = {
                    "sentence": sentence,
                    "translation": "",
                    "chunks": [{"text": sentence, "meaning": "", "note": f"analysis failed: {exc}"}],
                    "vocabulary": [],
                }
            STORE.add_sentence(
                article_id=article_id,
                section_id=section["id"],
                ordinal=index,
                source_text=sentence,
                translation=result.get("translation", ""),
                chunks=result.get("chunks", []),
                vocabulary=result.get("vocabulary", []),
            )
    STORE.update_article_status(article_id, "ready", None)


def split_sentences(text: str) -> list[str]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", cleaned)
    return [part.strip() for part in parts if len(part.strip()) > 12]


def sync_mail() -> dict[str, Any]:
    messages = fetch_rundown_messages(ENV)
    created: list[int] = []
    failed: list[int] = []
    skipped = 0
    for message in messages:
        article_id = STORE.upsert_article(message)
        if article_id is None:
            skipped += 1
            continue
        created.append(article_id)
        try:
            analyze_article(article_id)
        except Exception as exc:
            failed.append(article_id)
            STORE.update_article_status(article_id, "failed", str(exc))
            traceback.print_exc()
    return {
        "created": created,
        "failed": failed,
        "skipped": skipped,
        "count": len(messages),
        "fetch_days": int(ENV.get("FETCH_DAYS", "14")),
        "storage": STORE.__class__.__name__,
    }


def seed_sample() -> int:
    sample_text = """
AI coding tools get more autonomous

The Rundown: AI coding startups are racing to build agents that can plan, edit, test, and review code with less human guidance. The new wave of tools focuses on long-running workflows rather than one-off autocomplete suggestions.

Why it matters: Developers may spend less time on repetitive glue work, but they still need to review architecture, security, and product intent carefully.

Open models keep improving

The Rundown: Smaller open-weight models are becoming more useful on consumer laptops, especially for translation, summarization, and structured extraction. Local inference gives learners more privacy and predictable costs.

Why it matters: Personal study tools can now run useful AI features without sending every article to a paid cloud API.
""".strip()
    message = {
        "uid": f"sample-{int(time.time())}",
        "subject": "Sample AI Rundown",
        "sender": "sample@local",
        "received_at": now_iso(),
        "html": "",
        "text": sample_text,
    }
    article_id = STORE.upsert_article(message, force=True)
    assert article_id is not None
    analyze_article(article_id)
    return article_id


class Handler(BaseHTTPRequestHandler):
    server_version = "AIRundownBackend/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{now_iso()}] {self.address_string()} {fmt % args}")

    def do_GET(self) -> None:
        try:
            self.route_get()
        except Exception as exc:
            traceback.print_exc()
            json_response(self, 500, {"error": str(exc)})

    def do_POST(self) -> None:
        try:
            if not auth_ok(self):
                json_response(self, 401, {"error": "unauthorized"})
                return
            self.route_post()
        except Exception as exc:
            traceback.print_exc()
            json_response(self, 500, {"error": str(exc)})

    def route_get(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            json_response(self, 200, {"ok": True, "time": now_iso(), "model": ENV.get("OLLAMA_MODEL", "qwen3:4b")})
            return
        if path == "/api/articles":
            json_response(self, 200, {"articles": STORE.list_articles()})
            return
        if path.startswith("/api/articles/"):
            article_id = int(path.rsplit("/", 1)[-1])
            article = STORE.get_article_full(article_id)
            if not article:
                json_response(self, 404, {"error": "article not found"})
                return
            json_response(self, 200, article)
            return
        if path == "/api/vocab.tsv":
            text_response(self, 200, STORE.export_vocab_tsv(), "text/tab-separated-values")
            return
        json_response(self, 404, {"error": "not found"})

    def route_post(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/sync":
            result = sync_mail()
            json_response(self, 200, result)
            return
        if path == "/api/sample":
            article_id = seed_sample()
            json_response(self, 200, {"article_id": article_id})
            return
        if path == "/api/vocab":
            data = read_json(self)
            vocab_id = STORE.add_vocab(
                article_id=int(data.get("article_id") or 0) or None,
                sentence_id=int(data.get("sentence_id") or 0) or None,
                term=str(data.get("term", "")).strip(),
                meaning=str(data.get("meaning", "")).strip(),
                note=str(data.get("note", "")).strip(),
            )
            json_response(self, 200, {"id": vocab_id})
            return
        if path.startswith("/api/articles/") and path.endswith("/reanalyze"):
            article_id = int(path.split("/")[-2])
            analyze_article(article_id)
            json_response(self, 200, {"article_id": article_id, "status": "ready"})
            return
        json_response(self, 404, {"error": "not found"})


def schedule_loop() -> None:
    target = ENV.get("SCHEDULE_TIME", "19:05")
    match = re.match(r"^(\d{1,2}):(\d{2})$", target)
    if not match:
        print(f"Invalid SCHEDULE_TIME={target}; scheduler disabled")
        return
    hour, minute = int(match.group(1)), int(match.group(2))
    last_run = ""
    while True:
        now = datetime.now()
        stamp = now.strftime("%Y-%m-%d")
        if now.hour == hour and now.minute == minute and last_run != stamp:
            try:
                print("Scheduled sync started")
                sync_mail()
                last_run = stamp
                print("Scheduled sync finished")
            except Exception:
                traceback.print_exc()
        time.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-sample", action="store_true")
    parser.add_argument("--sync-once", action="store_true")
    args = parser.parse_args()
    if args.seed_sample:
        article_id = seed_sample()
        print(f"Seeded sample article {article_id}")
        return
    if args.sync_once:
        print(json.dumps(sync_mail(), ensure_ascii=False, indent=2))
        return

    if ENV.get("SCHEDULE_ENABLED", "true").lower() == "true":
        threading.Thread(target=schedule_loop, daemon=True).start()

    host = ENV.get("HOST", "0.0.0.0")
    port = int(ENV.get("PORT", "8787"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"AI Rundown backend listening on http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
