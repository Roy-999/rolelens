from __future__ import annotations

import re

from email_reply_parser import EmailReplyParser


FOOTER_PATTERNS = [
    r"(?is)\n\s*confidentiality notice:.*$",
    r"(?is)\n\s*this message and any attachments.*confidential.*$",
    r"(?is)\n\s*this e-?mail and any files transmitted.*$",
    r"(?is)\n\s*unsubscribe\b.*$",
    r"(?is)\n\s*privacy policy\b.*$",
]

REPLY_MARKERS = [
    r"(?im)^-{2,}\s*forwarded message\s*-{2,}.*$",
    r"(?im)^from:\s+.+$",
    r"(?im)^on .+ wrote:\s*$",
    r"(?im)^sent:\s+.+$",
]


def clean_email_body(text: str) -> str:
    cleaned = text or ""
    try:
        cleaned = EmailReplyParser.parse_reply(cleaned)
    except Exception:
        pass

    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(
        r"(?im)^\s*(cid|image|logo|facebook|linkedin|twitter|instagram)\b.*$",
        " ",
        cleaned,
    )
    for pattern in FOOTER_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned)
    cleaned = _truncate_at_repeated_reply_headers(cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _truncate_at_repeated_reply_headers(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    marker_count = 0
    for line in lines:
        if any(re.search(pattern, line) for pattern in REPLY_MARKERS):
            marker_count += 1
            if marker_count >= 2 and len("\n".join(kept)) > 200:
                break
        kept.append(line)
    return "\n".join(kept)
