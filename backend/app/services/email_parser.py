from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import getaddresses, parsedate_to_datetime
from typing import Any

from bs4 import BeautifulSoup


@dataclass
class ParsedEmailAttachment:
    file_name: str
    mime_type: str = ""
    size: int = 0
    attachment_id: str = ""
    body_bytes: bytes = b""


@dataclass
class ParsedEmail:
    gmail_message_id: str
    gmail_thread_id: str = ""
    subject: str = ""
    sender: str = ""
    recipients: list[str] = field(default_factory=list)
    received_at: datetime | None = None
    snippet: str = ""
    plain_text: str = ""
    html_text: str = ""
    attachments: list[ParsedEmailAttachment] = field(default_factory=list)


def parse_gmail_message(message: dict[str, Any]) -> ParsedEmail:
    payload = message.get("payload") or {}
    headers = _headers_to_dict(payload.get("headers") or [])
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[ParsedEmailAttachment] = []

    _walk_payload(payload, plain_parts, html_parts, attachments)

    recipients = [
        email
        for _, email in getaddresses(
            [
                headers.get("to", ""),
                headers.get("cc", ""),
            ]
        )
        if email
    ]

    return ParsedEmail(
        gmail_message_id=str(message.get("id") or ""),
        gmail_thread_id=str(message.get("threadId") or ""),
        subject=headers.get("subject", ""),
        sender=headers.get("from", ""),
        recipients=recipients,
        received_at=_parse_received_at(
            headers.get("date"), message.get("internalDate")
        ),
        snippet=str(message.get("snippet") or ""),
        plain_text="\n\n".join(part for part in plain_parts if part.strip()).strip(),
        html_text="\n\n".join(part for part in html_parts if part.strip()).strip(),
        attachments=attachments,
    )


def email_body_text(parsed_email: ParsedEmail) -> str:
    if parsed_email.plain_text.strip():
        return parsed_email.plain_text.strip()
    if parsed_email.html_text.strip():
        return html_to_text(parsed_email.html_text)
    return parsed_email.snippet.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for element in soup(["script", "style", "img", "svg"]):
        element.decompose()
    return soup.get_text("\n", strip=True)


def _walk_payload(
    payload: dict[str, Any],
    plain_parts: list[str],
    html_parts: list[str],
    attachments: list[ParsedEmailAttachment],
) -> None:
    file_name = str(payload.get("filename") or "")
    mime_type = str(payload.get("mimeType") or "")
    body = payload.get("body") or {}
    attachment_id = str(body.get("attachmentId") or "")
    data = str(body.get("data") or "")
    size = int(body.get("size") or 0)

    if file_name and attachment_id:
        attachments.append(
            ParsedEmailAttachment(
                file_name=file_name,
                mime_type=mime_type,
                size=size,
                attachment_id=attachment_id,
            )
        )
    elif file_name and data:
        attachments.append(
            ParsedEmailAttachment(
                file_name=file_name,
                mime_type=mime_type,
                size=size,
                body_bytes=_decode_gmail_data(data),
            )
        )
    elif data and mime_type == "text/plain":
        plain_parts.append(_decode_gmail_data(data).decode("utf-8", errors="ignore"))
    elif data and mime_type == "text/html":
        html_parts.append(_decode_gmail_data(data).decode("utf-8", errors="ignore"))

    for part in payload.get("parts") or []:
        _walk_payload(part, plain_parts, html_parts, attachments)


def _headers_to_dict(headers: list[dict[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header in headers:
        name = str(header.get("name") or "").casefold()
        if name:
            result[name] = str(header.get("value") or "")
    return result


def _parse_received_at(date_header: str | None, internal_date: Any) -> datetime | None:
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except Exception:
            pass

    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
        except Exception:
            return None
    return None


def _decode_gmail_data(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))
