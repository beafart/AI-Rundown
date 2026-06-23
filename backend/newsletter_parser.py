from __future__ import annotations

import html
import re
from html.parser import HTMLParser


class TextExtractor(HTMLParser):
    block_tags = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "ul", "ol"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned + " ")


def html_to_text(raw_html: str) -> str:
    parser = TextExtractor()
    parser.feed(raw_html)
    text = html.unescape("".join(parser.parts))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip()


def parse_newsletter(text: str) -> list[dict[str, str | int]]:
    cleaned = normalize(text)
    if not cleaned:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", cleaned) if block.strip()]
    sections: list[dict[str, str | int]] = []
    current_heading = "Today's Rundown"
    current_body: list[str] = []

    for block in blocks:
        plain = block.strip()
        if looks_like_heading(plain):
            if current_body:
                sections.append({"heading": current_heading, "body": "\n\n".join(current_body), "ordinal": len(sections)})
                current_body = []
            current_heading = trim_heading(plain)
        else:
            current_body.append(plain)

    if current_body:
        sections.append({"heading": current_heading, "body": "\n\n".join(current_body), "ordinal": len(sections)})

    if not sections:
        sections.append({"heading": "Today's Rundown", "body": cleaned, "ordinal": 0})

    return sections[:12]


def normalize(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(
        r"(?is)######\s*TOGETHER WITH\b.*?(?=\n-{5,}\n-{5,}\n######|\Z)",
        "\n",
        text,
    )
    text = re.sub(r"(?mi)^.*Read Online.*Sign Up.*Advertise.*$", "\n", text)
    text = re.sub(r"(?mi)^View image:\s*\([^)]+\).*$", " ", text)
    text = re.sub(r"(?mi)^Follow image link:\s*\([^)]+\).*$", " ", text)
    text = re.sub(r"(?mi)^Caption:.*$", " ", text)
    text = re.sub(
        r"\*\*In today[’']s AI rundown:\*\*.*?\*\*LATEST DEVELOPMENTS\*\*",
        "\nLATEST DEVELOPMENTS\n",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^[\s\^\|\-–—_]+$", "\n", text)
    text = re.sub(r"(?:\^\s*\|\s*)+\^?", " ", text)
    text = re.sub(r"\^+", " ", text)
    text = re.sub(r"-{3,}", " ", text)
    text = re.sub(r"\*{1,3}([^*\n]+)\*{1,3}", r"\1", text)
    text = re.sub(r"(?m)^#{2,6}\s*", "", text)
    text = re.sub(r"[_`]+", "", text)
    text = re.sub(r"(?mi)^\s*LATEST DEVELOPMENTS\s*$", "\n", text)
    text = re.sub(r"\bGood morning,\s*AI enthusiasts\.\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def looks_like_heading(block: str) -> bool:
    if len(block) > 90:
        return False
    if block.count(".") > 1:
        return False
    lower = block.lower()
    heading_markers = [
        "the rundown",
        "why it matters",
        "quick hits",
        "ai tools",
        "research",
        "also",
        "sponsored",
    ]
    if any(marker == lower or lower.startswith(marker + ":") for marker in heading_markers):
        return True
    words = block.split()
    return 2 <= len(words) <= 9 and block[:1].isupper() and not block.endswith(".")


def trim_heading(value: str) -> str:
    value = re.sub(r"^[#*\- ]+", "", value).strip()
    return value.rstrip(":").strip() or "Section"
