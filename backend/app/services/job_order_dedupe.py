from __future__ import annotations

import re
from typing import Any

from pymongo.collection import Collection

from ..schemas import EmailDedupeResult, JobOrderExtraction


def build_dedupe_key(fields: JobOrderExtraction) -> str:
    title = _normalize_token(fields.job_title)
    organization = _normalize_token(fields.organization_name)
    city = _normalize_token(fields.location.city)
    state = _normalize_token(fields.location.state)
    return "|".join(part for part in [title, organization, city, state] if part)


def find_email_dedupe(
    *,
    email_collection: Collection,
    job_collection: Collection,
    gmail_message_id: str,
    attachment_hashes: list[str],
    extracted_fields: JobOrderExtraction,
    current_draft_id: Any | None = None,
) -> EmailDedupeResult:
    reasons: list[str] = []
    matched_job_order_id: str | None = None
    matched_draft_id: str | None = None

    message_match = email_collection.find_one({"gmail_message_id": gmail_message_id})
    if message_match and message_match.get("_id") != current_draft_id:
        reasons.append("same_gmail_message")
        matched_draft_id = str(message_match.get("_id"))

    hashes = [value for value in attachment_hashes if value]
    if hashes:
        draft_hash_match = email_collection.find_one(
            {
                "attachment_hashes": {"$in": hashes},
                **(
                    {"_id": {"$ne": current_draft_id}}
                    if current_draft_id is not None
                    else {}
                ),
            }
        )
        if draft_hash_match:
            reasons.append("same_attachment_hash")
            matched_draft_id = matched_draft_id or str(draft_hash_match.get("_id"))

        job_hash_match = job_collection.find_one(
            {"source_attachment_hashes": {"$in": hashes}}
        )
        if job_hash_match:
            reasons.append("same_attachment_hash_saved_job")
            matched_job_order_id = str(
                job_hash_match.get("job_order_id") or job_hash_match.get("_id")
            )

    title = _normalize_token(extracted_fields.job_title)
    organization = _normalize_token(extracted_fields.organization_name)
    if title and organization:
        title_pattern = _exact_ci_pattern(title)
        org_pattern = _exact_ci_pattern(organization)
        saved_match = job_collection.find_one(
            {
                "job_title_normalized": title,
                "organization_name_normalized": organization,
            }
        ) or job_collection.find_one(
            {
                "job_title": {"$regex": title_pattern},
                "organization_name": {"$regex": org_pattern},
            }
        )
        if saved_match:
            reasons.append("same_title_company_saved_job")
            matched_job_order_id = matched_job_order_id or str(
                saved_match.get("job_order_id") or saved_match.get("_id")
            )

        draft_match = email_collection.find_one(
            {
                "extracted_fields.job_title": {"$regex": title_pattern},
                "extracted_fields.organization_name": {"$regex": org_pattern},
                **(
                    {"_id": {"$ne": current_draft_id}}
                    if current_draft_id is not None
                    else {}
                ),
            }
        )
        if draft_match:
            reasons.append("same_title_company_draft")
            matched_draft_id = matched_draft_id or str(draft_match.get("_id"))

    return EmailDedupeResult(
        is_duplicate=bool(reasons),
        reasons=sorted(set(reasons)),
        matched_job_order_id=matched_job_order_id,
        matched_draft_id=matched_draft_id,
    )


def normalized_title_company_fields(fields: JobOrderExtraction) -> dict[str, str]:
    return {
        "job_title_normalized": _normalize_token(fields.job_title),
        "organization_name_normalized": _normalize_token(fields.organization_name),
    }


def _normalize_token(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", normalized).strip()


def _exact_ci_pattern(normalized_value: str) -> str:
    escaped = re.escape(normalized_value)
    return f"(?i)^{escaped}$"
