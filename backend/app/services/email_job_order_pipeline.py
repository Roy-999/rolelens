from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo.collection import Collection

from ..config import Settings
from ..schemas import (
    EmailAttachmentRecord,
    EmailJobOrderDraftRecord,
    JobOrderExtraction,
)
from .document_parser import parse_document
from .email_cleaner import clean_email_body
from .email_parser import ParsedEmailAttachment, email_body_text, parse_gmail_message
from .gmail_client import GmailClient
from .job_order_dedupe import build_dedupe_key, find_email_dedupe
from .ai_service import AIService

SUPPORTED_ATTACHMENT_EXTENSIONS = {".pdf", ".docx", ".txt"}
ATTACHMENT_PRIORITY = {".pdf": 0, ".docx": 1, ".txt": 2}


@dataclass
class ProcessSummary:
    processed: int = 0
    created: int = 0
    duplicates: int = 0
    irrelevant: int = 0
    failed: int = 0
    drafts: list[dict[str, Any]] | None = None


class EmailJobOrderPipeline:
    def __init__(
        self,
        *,
        settings: Settings,
        gmail_client: GmailClient,
        ai_service: AIService,
        email_collection: Collection,
        job_collection: Collection,
    ) -> None:
        self.settings = settings
        self.gmail_client = gmail_client
        self.ai_service = ai_service
        self.email_collection = email_collection
        self.job_collection = job_collection

    def test_fetch(self) -> list[dict[str, Any]]:
        messages = self.gmail_client.list_messages(
            self.settings.gmail_poll_query,
            self.settings.gmail_max_messages_per_run,
        )
        summaries: list[dict[str, Any]] = []
        for message in messages:
            full_message = self.gmail_client.get_message(str(message.get("id")))
            parsed = parse_gmail_message(full_message)
            summaries.append(
                {
                    "gmail_message_id": parsed.gmail_message_id,
                    "gmail_thread_id": parsed.gmail_thread_id,
                    "subject": parsed.subject,
                    "sender": parsed.sender,
                    "received_at": parsed.received_at.isoformat()
                    if parsed.received_at
                    else None,
                    "snippet": parsed.snippet,
                }
            )
        return summaries

    def process_latest(self) -> ProcessSummary:
        summary = ProcessSummary(drafts=[])
        messages = self.gmail_client.list_messages(
            self.settings.gmail_poll_query,
            self.settings.gmail_max_messages_per_run,
        )
        for message in messages:
            message_id = str(message.get("id") or "")
            if not message_id:
                continue
            summary.processed += 1
            try:
                existing = self.email_collection.find_one(
                    {"gmail_message_id": message_id}
                )
                if existing:
                    summary.duplicates += 1
                    summary.drafts.append(existing)
                    continue

                draft = self.process_message(message_id)
                if draft.get("status") == "duplicate":
                    summary.duplicates += 1
                elif draft.get("status") == "irrelevant":
                    summary.irrelevant += 1
                elif draft.get("status") == "failed":
                    summary.failed += 1
                else:
                    summary.created += 1
                summary.drafts.append(draft)
                self.gmail_client.mark_as_read(message_id)
            except Exception as exc:
                summary.failed += 1
                summary.drafts.append(self._record_failed_message(message_id, str(exc)))
        return summary

    def process_message(self, message_id: str) -> dict[str, Any]:
        full_message = self.gmail_client.get_message(message_id)
        parsed_email = parse_gmail_message(full_message)
        raw_body = email_body_text(parsed_email)
        cleaned_body = clean_email_body(raw_body)
        attachments = self._load_attachments(
            parsed_email.gmail_message_id, parsed_email.attachments
        )
        selected_documents = [
            attachment
            for attachment in attachments
            if attachment.get("selected_for_extraction")
            and attachment.get("extracted_text")
        ]
        attachment_text = "\n\n".join(
            attachment.get("extracted_text") or "" for attachment in selected_documents
        ).strip()
        attachment_names = [
            attachment.get("file_name") or "" for attachment in attachments
        ]
        classification, confidence, confidence_reason, classifier_method = (
            self.ai_service.classify_job_order_email(
                subject=parsed_email.subject,
                cleaned_body=cleaned_body,
                attachment_text=attachment_text,
                attachment_names=attachment_names,
            )
        )

        extraction_text = attachment_text or "\n\n".join(
            part
            for part in [
                f"Subject: {parsed_email.subject}".strip(),
                cleaned_body,
            ]
            if part.strip()
        )
        selected_source = "attachment" if attachment_text else "email_body"
        extracted_fields = JobOrderExtraction()
        extraction_method = classifier_method
        status = "pending_review"
        error = ""

        if classification != "job_order":
            status = "irrelevant"
        elif not extraction_text.strip():
            status = "failed"
            error = "No extractable job order text found in attachments or email body."
        else:
            extracted_fields, extraction_method = (
                self.ai_service.extract_job_order_fields(
                    raw_text=extraction_text,
                    rendered_images=[],
                    file_type=".txt",
                )
            )

        attachment_hashes = [
            attachment.get("content_hash") or ""
            for attachment in attachments
            if attachment.get("content_hash")
        ]
        dedupe = find_email_dedupe(
            email_collection=self.email_collection,
            job_collection=self.job_collection,
            gmail_message_id=parsed_email.gmail_message_id,
            attachment_hashes=attachment_hashes,
            extracted_fields=extracted_fields,
        )
        if status == "pending_review" and dedupe.is_duplicate:
            status = "duplicate"

        now = datetime.now(timezone.utc)
        source_attachment = next(
            (item for item in selected_documents if item.get("file_name")), None
        )
        document = {
            "gmail_message_id": parsed_email.gmail_message_id,
            "gmail_thread_id": parsed_email.gmail_thread_id,
            "subject": parsed_email.subject,
            "sender": parsed_email.sender,
            "recipients": parsed_email.recipients,
            "received_at": parsed_email.received_at,
            "status": status,
            "classification": classification,
            "confidence": confidence,
            "confidence_reason": confidence_reason,
            "source_priority": selected_source,
            "source_file_name": source_attachment.get("file_name")
            if source_attachment
            else "email_body.txt",
            "source_file_type": Path(source_attachment.get("file_name")).suffix.lower()
            if source_attachment
            else ".txt",
            "raw_text": extraction_text,
            "preview_text": _trim_preview(
                extraction_text, self.settings.max_preview_chars
            ),
            "cleaned_body_text": cleaned_body,
            "extraction_method": extraction_method,
            "is_scanned_document": False,
            "extracted_fields": extracted_fields.model_dump(mode="json"),
            "attachments": attachments,
            "attachment_hashes": attachment_hashes,
            "dedupe": dedupe.model_dump(mode="json"),
            "dedupe_key": build_dedupe_key(extracted_fields),
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        result = self.email_collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def _record_failed_message(self, message_id: str, error: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        existing = self.email_collection.find_one({"gmail_message_id": message_id})
        if existing:
            return existing
        document = {
            "gmail_message_id": message_id,
            "status": "failed",
            "classification": "",
            "confidence": None,
            "confidence_reason": "",
            "source_priority": "",
            "source_file_name": "",
            "source_file_type": "",
            "raw_text": "",
            "preview_text": "",
            "cleaned_body_text": "",
            "extraction_method": "",
            "extracted_fields": JobOrderExtraction().model_dump(mode="json"),
            "attachments": [],
            "attachment_hashes": [],
            "dedupe": {"is_duplicate": False, "reasons": []},
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        result = self.email_collection.insert_one(document)
        document["_id"] = result.inserted_id
        return document

    def _load_attachments(
        self,
        message_id: str,
        attachments: list[ParsedEmailAttachment],
    ) -> list[dict[str, Any]]:
        materialized: list[dict[str, Any]] = []
        ordered_attachments = sorted(
            attachments,
            key=lambda item: ATTACHMENT_PRIORITY.get(
                Path(item.file_name).suffix.lower(), 100
            ),
        )
        for attachment in ordered_attachments:
            file_name = _safe_file_name(attachment.file_name)
            extension = Path(file_name).suffix.lower()
            if not file_name or _is_inline_noise(file_name, attachment.mime_type):
                continue

            file_bytes = attachment.body_bytes
            if not file_bytes and attachment.attachment_id:
                file_bytes = self.gmail_client.get_attachment_bytes(
                    message_id, attachment.attachment_id
                )
            if not file_bytes:
                continue

            content_hash = hashlib.sha256(file_bytes).hexdigest()
            stored_path = self._write_attachment(message_id, file_name, file_bytes)
            extracted_text = ""
            selected = extension in SUPPORTED_ATTACHMENT_EXTENSIONS
            if selected:
                try:
                    parsed_document = parse_document(
                        file_name, file_bytes, self.settings
                    )
                    extracted_text = (
                        parsed_document.raw_text or parsed_document.preview_text
                    )
                except Exception:
                    extracted_text = ""

            materialized.append(
                EmailAttachmentRecord(
                    file_name=file_name,
                    mime_type=attachment.mime_type,
                    size=len(file_bytes) or attachment.size,
                    attachment_id=attachment.attachment_id,
                    content_hash=content_hash,
                    stored_path=stored_path,
                    extracted_text=extracted_text,
                    selected_for_extraction=selected,
                ).model_dump(mode="json")
            )
        return materialized

    def _write_attachment(
        self, message_id: str, file_name: str, file_bytes: bytes
    ) -> str:
        base_dir = Path(self.settings.gmail_attachment_storage_dir)
        target_dir = base_dir / _safe_file_name(message_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{uuid.uuid4().hex}_{file_name}"
        target_path.write_bytes(file_bytes)
        return str(target_path)


def serialize_email_draft(document: dict[str, Any]) -> EmailJobOrderDraftRecord:
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    received_at = document.get("received_at")
    payload = {
        **document,
        "id": str(document.get("_id", "")),
        "received_at": received_at.isoformat()
        if hasattr(received_at, "isoformat")
        else received_at,
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else None,
        "updated_at": updated_at.isoformat()
        if hasattr(updated_at, "isoformat")
        else None,
        "extracted_fields": document.get("extracted_fields") or {},
        "attachments": document.get("attachments") or [],
        "dedupe": document.get("dedupe") or {},
    }
    return EmailJobOrderDraftRecord.model_validate(payload)


def _safe_file_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return safe or "attachment"


def _is_inline_noise(file_name: str, mime_type: str) -> bool:
    extension = Path(file_name).suffix.lower()
    if extension in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}:
        return True
    return str(mime_type or "").casefold().startswith("image/")


def _trim_preview(text: str, max_length: int) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= max_length:
        return stripped
    return f"{stripped[:max_length].rstrip()}..."
