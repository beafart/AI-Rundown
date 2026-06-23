from __future__ import annotations

import json
from typing import Any
from urllib import error, parse, request


def is_supabase_configured(env: dict[str, str]) -> bool:
    return bool(env.get("SUPABASE_URL", "").strip() and env.get("SUPABASE_SERVICE_ROLE_KEY", "").strip())


class SupabaseStore:
    def __init__(self, env: dict[str, str]) -> None:
        self.base_url = env["SUPABASE_URL"].strip().rstrip("/")
        self.service_key = env["SUPABASE_SERVICE_ROLE_KEY"].strip()

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        prefer: str | None = None,
    ) -> Any:
        data = None
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Accept": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if prefer:
            headers["Prefer"] = prefer
        req = request.Request(f"{self.base_url}/rest/v1/{path}", data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase {method} {path} failed: HTTP {exc.code} {body}") from exc
        if not raw.strip():
            return None
        return json.loads(raw)

    def select(self, table: str, query: str) -> list[dict[str, Any]]:
        result = self.request("GET", f"{table}?{query}")
        return result if isinstance(result, list) else []

    def upsert_article(self, message: dict[str, Any], force: bool = False) -> int | None:
        uid = quote(message["uid"])
        existing = self.select("articles", f"uid=eq.{uid}&select=id,status")
        if existing and not force:
            return None if existing[0].get("status") == "ready" else int(existing[0]["id"])
        if existing and force:
            self.request("DELETE", f"articles?id=eq.{existing[0]['id']}")
        payload = {
            "uid": message["uid"],
            "subject": message["subject"],
            "sender": message["sender"],
            "received_at": message["received_at"],
            "html": message.get("html", ""),
            "text": message.get("text", ""),
            "status": "new",
        }
        inserted = self.request("POST", "articles", payload, "return=representation")
        return int(inserted[0]["id"])

    def update_article_status(self, article_id: int, status: str, error_text: str | None) -> None:
        self.request(
            "PATCH",
            f"articles?id=eq.{article_id}",
            {"status": status, "error": error_text},
            "return=minimal",
        )

    def list_articles(self) -> list[dict[str, Any]]:
        return self.select(
            "articles",
            "select=id,uid,subject,sender,received_at,status,error,created_at,updated_at&order=received_at.desc&limit=50",
        )

    def get_article(self, article_id: int) -> dict[str, Any] | None:
        rows = self.select("articles", f"id=eq.{article_id}&select=*")
        return rows[0] if rows else None

    def replace_sections(self, article_id: int, sections: list[dict[str, Any]]) -> None:
        self.request("DELETE", f"sentences?article_id=eq.{article_id}")
        self.request("DELETE", f"sections?article_id=eq.{article_id}")
        if not sections:
            return
        payload = [
            {
                "article_id": article_id,
                "ordinal": section["ordinal"],
                "heading": section["heading"],
                "body": section["body"],
            }
            for section in sections
        ]
        self.request("POST", "sections", payload, "return=representation")

    def list_sections(self, article_id: int) -> list[dict[str, Any]]:
        return self.select("sections", f"article_id=eq.{article_id}&select=*&order=ordinal.asc")

    def find_sentence(self, article_id: int, section_id: int, ordinal: int) -> dict[str, Any] | None:
        rows = self.select(
            "sentences",
            f"article_id=eq.{article_id}&section_id=eq.{section_id}&ordinal=eq.{ordinal}&select=*",
        )
        return rows[0] if rows else None

    def add_sentence(
        self,
        article_id: int,
        section_id: int,
        ordinal: int,
        source_text: str,
        translation: str,
        natural_paraphrase: str,
        key_point: str,
        chunks: list[dict[str, Any]],
        vocabulary: list[dict[str, Any]],
    ) -> int:
        payload = {
            "article_id": article_id,
            "section_id": section_id,
            "ordinal": ordinal,
            "source_text": source_text,
            "translation": translation,
            "natural_paraphrase": natural_paraphrase,
            "key_point": key_point,
            "chunks": chunks,
            "vocabulary": vocabulary,
        }
        inserted = self.request("POST", "sentences", payload, "return=representation")
        return int(inserted[0]["id"])

    def get_article_full(self, article_id: int) -> dict[str, Any] | None:
        article = self.get_article(article_id)
        if not article:
            return None
        sections = self.list_sections(article_id)
        sentences = self.select(
            "sentences",
            f"article_id=eq.{article_id}&select=*&order=section_id.asc,ordinal.asc",
        )
        by_section: dict[int, list[dict[str, Any]]] = {}
        for sentence in sentences:
            by_section.setdefault(int(sentence["section_id"]), []).append(sentence)
        for section in sections:
            section["sentences"] = by_section.get(int(section["id"]), [])
        article["sections"] = sections
        return article

    def add_vocab(
        self,
        article_id: int | None,
        sentence_id: int | None,
        term: str,
        meaning: str,
        note: str,
    ) -> int:
        if not term:
            raise ValueError("term is required")
        inserted = self.request(
            "POST",
            "vocab",
            {
                "article_id": article_id,
                "sentence_id": sentence_id,
                "term": term,
                "meaning": meaning,
                "note": note,
            },
            "return=representation",
        )
        return int(inserted[0]["id"])

    def export_vocab_tsv(self) -> str:
        rows = self.select("vocab", "select=term,meaning,note&order=id.asc")
        lines = []
        for row in rows:
            meaning = row["meaning"]
            if row.get("note"):
                meaning = f"{meaning} ({row['note']})"
            lines.append(f"{clean_tsv(row['term'])}\t{clean_tsv(meaning)}")
        return "\n".join(lines) + ("\n" if lines else "")


def quote(value: Any) -> str:
    return parse.quote(str(value), safe="")


def clean_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
