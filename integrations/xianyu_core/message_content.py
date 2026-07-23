"""Shared normalization helpers for Xianyu message content."""

from __future__ import annotations

import base64
import binascii
import json
import re
from html.parser import HTMLParser
from typing import Any, Mapping


class _PlainTextHTMLParser(HTMLParser):
    _BLOCK_TAGS = {"br", "div", "li", "p"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._BLOCK_TAGS - {"br"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_plain_text(value: Any) -> str:
    """Convert the limited rich text used by message cards to readable text."""

    if not isinstance(value, str) or not value.strip():
        return ""
    parser = _PlainTextHTMLParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return re.sub(r"<[^>]*>", " ", value).strip()
    lines = [re.sub(r"\s+", " ", line).strip() for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line)


def parse_text_card_content(decoded: Mapping[str, Any]) -> str | None:
    """Return display text for Xianyu ``contentType=6`` text cards."""

    try:
        content_type = int(decoded.get("contentType"))
    except (TypeError, ValueError):
        return None
    text_card = decoded.get("textCard")
    if content_type != 6 or not isinstance(text_card, Mapping):
        return None

    title = html_to_plain_text(text_card.get("title"))
    body = html_to_plain_text(text_card.get("content") or text_card.get("memo"))
    if title and body and title != body:
        return f"{title}\n{body}"
    return title or body or "[平台通知]"


def find_text_card_content(raw_payload: Any) -> str | None:
    """Find a text card in a stored raw payload, including nested JSON strings."""

    stack = [raw_payload]
    visited: set[int] = set()
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            identity = id(value)
            if identity in visited:
                continue
            visited.add(identity)
            parsed = parse_text_card_content(value)
            if parsed is not None:
                return parsed
            stack.extend(value.values())
        elif isinstance(value, (list, tuple)):
            stack.extend(value)
        elif isinstance(value, str):
            candidate = value.strip()
            decoded: Any = None
            if candidate.startswith(("{", "[")):
                try:
                    decoded = json.loads(candidate)
                except (TypeError, ValueError):
                    pass
            elif len(candidate) >= 8 and len(candidate) % 4 == 0:
                try:
                    plain = base64.b64decode(candidate, validate=True).decode("utf-8")
                    if plain.lstrip().startswith(("{", "[")):
                        decoded = json.loads(plain)
                except (binascii.Error, UnicodeDecodeError, ValueError):
                    pass
            if decoded is not None:
                stack.append(decoded)
    return None
