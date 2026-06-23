from __future__ import annotations

import email
import imaplib
import re
from datetime import datetime, timedelta
from email.header import decode_header
from email.message import Message
from email.policy import default
from typing import Any

from newsletter_parser import html_to_text


def decode_mime(value: str | None) -> str:
    if not value:
        return ""
    parts: list[str] = []
    for chunk, encoding in decode_header(value):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(encoding or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def message_body(message: Message) -> tuple[str, str]:
    html = ""
    text = ""
    if message.is_multipart():
        for part in message.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", "")).lower()
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ctype == "text/html" and not html:
                html = decoded
            elif ctype == "text/plain" and not text:
                text = decoded
    else:
        payload = message.get_payload(decode=True)
        charset = message.get_content_charset() or "utf-8"
        decoded = payload.decode(charset, errors="replace") if payload else ""
        if message.get_content_type() == "text/html":
            html = decoded
        else:
            text = decoded
    if not text and html:
        text = html_to_text(html)
    return html, normalize_text(text)


def normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def fetch_rundown_messages(env: dict[str, str]) -> list[dict[str, Any]]:
    email_addr = env.get("NAVER_EMAIL", "").strip()
    password = env.get("NAVER_APP_PASSWORD", "").strip()
    if not email_addr or not password:
        raise RuntimeError("NAVER_EMAIL and NAVER_APP_PASSWORD are required in .env")

    host = env.get("NAVER_IMAP_HOST", "imap.naver.com")
    port = int(env.get("NAVER_IMAP_PORT", "993"))
    folder = env.get("NAVER_FOLDER", "AI rundown")
    fetch_limit = int(env.get("FETCH_LIMIT", "50"))
    fetch_days = int(env.get("FETCH_DAYS", "14"))
    sender_filter = env.get("RUNDOWN_FROM", "").strip().lower()

    conn = imaplib.IMAP4_SSL(host, port)
    try:
        conn.login(email_addr, password)
        status, _ = conn.select(f'"{folder}"')
        if status != "OK":
            status, _ = conn.select(folder)
        if status != "OK":
            raise RuntimeError(f"Cannot select IMAP folder: {folder}")

        since = (datetime.now() - timedelta(days=fetch_days)).strftime("%d-%b-%Y")
        status, data = conn.search(None, "SINCE", since)
        if status != "OK":
            raise RuntimeError("IMAP search failed")
        ids = data[0].split()[-fetch_limit:]
        messages: list[dict[str, Any]] = []
        for item in ids:
            status, fetched = conn.fetch(item, "(RFC822)")
            if status != "OK" or not fetched:
                continue
            raw = fetched[0][1]
            parsed = email.message_from_bytes(raw, policy=default)
            sender = decode_mime(parsed.get("From"))
            if sender_filter and sender_filter not in sender.lower():
                continue
            html, text = message_body(parsed)
            subject = decode_mime(parsed.get("Subject"))
            received = parsed.get("Date")
            try:
                received_at = email.utils.parsedate_to_datetime(received).isoformat() if received else datetime.now().isoformat()
            except Exception:
                received_at = datetime.now().isoformat()
            uid_status, uid_data = conn.fetch(item, "(UID)")
            uid = item.decode("ascii", errors="ignore")
            if uid_status == "OK" and uid_data and uid_data[0]:
                match = re.search(rb"UID\s+(\d+)", uid_data[0])
                if match:
                    uid = match.group(1).decode("ascii")
            messages.append(
                {
                    "uid": uid,
                    "subject": subject,
                    "sender": sender,
                    "received_at": received_at,
                    "html": html,
                    "text": text,
                }
            )
        return messages
    finally:
        try:
            conn.logout()
        except Exception:
            pass
