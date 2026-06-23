from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Storage:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                create table if not exists articles (
                    id integer primary key autoincrement,
                    uid text unique not null,
                    subject text not null,
                    sender text not null,
                    received_at text not null,
                    html text not null,
                    text text not null,
                    status text not null default 'new',
                    error text,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp
                );
                create table if not exists sections (
                    id integer primary key autoincrement,
                    article_id integer not null references articles(id) on delete cascade,
                    ordinal integer not null,
                    heading text not null,
                    body text not null
                );
                create table if not exists sentences (
                    id integer primary key autoincrement,
                    article_id integer not null references articles(id) on delete cascade,
                    section_id integer not null references sections(id) on delete cascade,
                    ordinal integer not null,
                    source_text text not null,
                    translation text not null,
                    chunks_json text not null,
                    vocabulary_json text not null
                );
                create table if not exists vocab (
                    id integer primary key autoincrement,
                    article_id integer,
                    sentence_id integer,
                    term text not null,
                    meaning text not null,
                    note text not null default '',
                    created_at text not null default current_timestamp
                );
                """
            )

    def upsert_article(self, message: dict[str, Any], force: bool = False) -> int | None:
        with self.connect() as conn:
            existing = conn.execute("select id from articles where uid = ?", (message["uid"],)).fetchone()
            if existing and not force:
                return None
            if existing and force:
                conn.execute("delete from articles where id = ?", (existing["id"],))
            cur = conn.execute(
                """
                insert into articles(uid, subject, sender, received_at, html, text, status)
                values (?, ?, ?, ?, ?, ?, 'new')
                """,
                (
                    message["uid"],
                    message["subject"],
                    message["sender"],
                    message["received_at"],
                    message.get("html", ""),
                    message.get("text", ""),
                ),
            )
            return int(cur.lastrowid)

    def update_article_status(self, article_id: int, status: str, error: str | None) -> None:
        with self.connect() as conn:
            conn.execute(
                "update articles set status = ?, error = ?, updated_at = current_timestamp where id = ?",
                (status, error, article_id),
            )

    def list_articles(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                select id, subject, sender, received_at, status, error, created_at, updated_at
                from articles
                order by datetime(received_at) desc, id desc
                """
            ).fetchall()
            return [dict(row) for row in rows]

    def get_article(self, article_id: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute("select * from articles where id = ?", (article_id,)).fetchone()
            return dict(row) if row else None

    def replace_sections(self, article_id: int, sections: list[dict[str, Any]]) -> None:
        with self.connect() as conn:
            conn.execute("delete from sentences where article_id = ?", (article_id,))
            conn.execute("delete from sections where article_id = ?", (article_id,))
            for section in sections:
                conn.execute(
                    "insert into sections(article_id, ordinal, heading, body) values (?, ?, ?, ?)",
                    (article_id, section["ordinal"], section["heading"], section["body"]),
                )

    def list_sections(self, article_id: int) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "select * from sections where article_id = ? order by ordinal",
                (article_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def find_sentence(self, article_id: int, section_id: int, ordinal: int) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                "select * from sentences where article_id = ? and section_id = ? and ordinal = ?",
                (article_id, section_id, ordinal),
            ).fetchone()
            return dict(row) if row else None

    def add_sentence(
        self,
        article_id: int,
        section_id: int,
        ordinal: int,
        source_text: str,
        translation: str,
        chunks: list[dict[str, Any]],
        vocabulary: list[dict[str, Any]],
    ) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                """
                insert into sentences(article_id, section_id, ordinal, source_text, translation, chunks_json, vocabulary_json)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article_id,
                    section_id,
                    ordinal,
                    source_text,
                    translation,
                    json.dumps(chunks, ensure_ascii=False),
                    json.dumps(vocabulary, ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def get_article_full(self, article_id: int) -> dict[str, Any] | None:
        article = self.get_article(article_id)
        if not article:
            return None
        with self.connect() as conn:
            sections = conn.execute(
                "select * from sections where article_id = ? order by ordinal",
                (article_id,),
            ).fetchall()
            full_sections: list[dict[str, Any]] = []
            for section in sections:
                sentences = conn.execute(
                    "select * from sentences where section_id = ? order by ordinal",
                    (section["id"],),
                ).fetchall()
                section_dict = dict(section)
                section_dict["sentences"] = [
                    {
                        **dict(sentence),
                        "chunks": json.loads(sentence["chunks_json"]),
                        "vocabulary": json.loads(sentence["vocabulary_json"]),
                    }
                    for sentence in sentences
                ]
                for sentence in section_dict["sentences"]:
                    sentence.pop("chunks_json", None)
                    sentence.pop("vocabulary_json", None)
                full_sections.append(section_dict)
        article["sections"] = full_sections
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
        with self.connect() as conn:
            cur = conn.execute(
                "insert into vocab(article_id, sentence_id, term, meaning, note) values (?, ?, ?, ?, ?)",
                (article_id, sentence_id, term, meaning, note),
            )
            return int(cur.lastrowid)

    def export_vocab_tsv(self) -> str:
        with self.connect() as conn:
            rows = conn.execute("select term, meaning, note from vocab order by id").fetchall()
        lines = []
        for row in rows:
            meaning = row["meaning"]
            if row["note"]:
                meaning = f"{meaning} ({row['note']})"
            lines.append(f"{clean_tsv(row['term'])}\t{clean_tsv(meaning)}")
        return "\n".join(lines) + ("\n" if lines else "")


def clean_tsv(value: str) -> str:
    return value.replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()
