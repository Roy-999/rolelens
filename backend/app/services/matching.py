from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from pymongo.collection import Collection

from ..schemas import AgeEntry, MatchResult
from .location_utils import normalize_location_value
from .extraction import cosine_similarity, keyword_overlap_score
from .profile_context import build_profile_context_from_mapping


def rank_profiles_for_job(
    *, collection, job_order, job_embedding, settings, limit=3, documents=None
):
    source = documents if documents is not None else list(collection.find())
    keywords = [
        item
        for item in _keyword_rankings(source, job_order)
        if item["keyword_score"] > 0
    ]
    compatible = [
        d
        for d in source
        if d.get("embedding_model") == settings.gemini_embedding_model
        and d.get("embedding_dimensions") == settings.embedding_dimensions
        and len(d.get("profile_embedding") or []) == settings.embedding_dimensions
    ]
    vectors = []
    if job_embedding and len(job_embedding) == settings.embedding_dimensions:
        if settings.atlas_vector_enabled:
            vectors = _atlas_vector_rankings(
                collection=collection,
                documents=compatible,
                job_embedding=job_embedding,
                index_name=settings.mongodb_vector_index,
                limit=max(limit * 4, 10),
            )
        if not vectors:
            vectors = _vector_rankings(compatible, job_embedding)
        vectors = [item for item in vectors if item["vector_score"] > 0]
    fused = {}
    for ranking in (keywords, vectors):
        for rank, item in enumerate(ranking, 1):
            key = item["resume_id"]
            fused[key] = fused.get(key, 0) + 1 / (60 + rank)
    kw = {i["resume_id"]: i for i in keywords}
    vec = {i["resume_id"]: i for i in vectors}
    result = []
    for d in source:
        key = str(d["_id"])
        if key not in fused:
            continue
        result.append(
            MatchResult(
                resume_id=key,
                candidate_id=d.get("candidate_id", ""),
                name=d.get("name", ""),
                email_id=d.get("email_id", ""),
                phone_no=d.get("phone_no", ""),
                location=normalize_location_value(d.get("location")),
                years_of_experience=d.get("years_of_experience"),
                skills=d.get("skills", []),
                tools=d.get("tools", []),
                certifications=d.get("certifications", []),
                licenses=d.get("licenses", []),
                languages=d.get("languages", []),
                education=d.get("education", []),
                experience=d.get("experience", []),
                profile_context=build_profile_context_from_mapping(d),
                keyword_score=kw.get(key, {}).get("keyword_score", 0),
                vector_score=vec.get(key, {}).get("vector_score", 0),
                rrf_score=fused[key],
                matched_terms=kw.get(key, {}).get("matched_terms", []),
                source=(
                    "keyword+vector+rrf"
                    if key in kw and key in vec
                    else "vector"
                    if key in vec
                    else "keyword"
                ),
            )
        )
    return sorted(result, key=lambda r: (-r.rrf_score, r.candidate_id or r.resume_id))[
        :limit
    ]


def _keyword_rankings(
    documents: list[dict[str, Any]], job_order: str
) -> list[dict[str, Any]]:
    rankings = []
    for document in documents:
        context = build_profile_context_from_mapping(document)
        keyword_score, matched_terms = keyword_overlap_score(job_order, context)
        rankings.append(
            {
                "resume_id": str(document["_id"]),
                "keyword_score": keyword_score,
                "vector_score": 0.0,
                "matched_terms": matched_terms,
            }
        )
    rankings.sort(key=lambda item: item["keyword_score"], reverse=True)
    return rankings


def _vector_rankings(
    documents: list[dict[str, Any]],
    job_embedding: list[float] | None,
) -> list[dict[str, Any]]:
    rankings = []
    for document in documents:
        vector_score = cosine_similarity(
            job_embedding, document.get("profile_embedding")
        )
        rankings.append(
            {
                "resume_id": str(document["_id"]),
                "keyword_score": 0.0,
                "vector_score": vector_score,
                "matched_terms": [],
            }
        )
    rankings.sort(key=lambda item: item["vector_score"], reverse=True)
    return rankings


def _normalize_age_value(document: dict[str, Any]) -> AgeEntry:
    age = document.get("age")
    if isinstance(age, dict):
        return AgeEntry(
            group=str(age.get("group", "") or "").strip(),
            source=str(age.get("source", "") or "").strip(),
            confidence=_to_optional_float(age.get("confidence")),
        )

    return AgeEntry(
        group=str(document.get("age_group", "") or "").strip(),
        source=str(document.get("age_source", "") or "").strip(),
        confidence=_to_optional_float(document.get("age_confidence")),
    )


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _skill_recency_rankings(
    documents: list[dict[str, Any]],
    job_order: str,
) -> list[dict[str, Any]]:
    rankings = []
    for document in documents:
        latest_entry = _latest_experience_entry(document.get("experience", []))
        recent_context = _experience_entry_context(latest_entry)
        overlap_score, matched_terms = keyword_overlap_score(job_order, recent_context)
        recency_weight = _experience_recency_weight(latest_entry)
        rankings.append(
            {
                "resume_id": str(document["_id"]),
                "skill_recency_score": overlap_score * recency_weight,
                "matched_terms": matched_terms,
            }
        )
    return rankings


def _atlas_vector_rankings(
    *,
    collection: Collection,
    documents: list[dict[str, Any]],
    job_embedding: list[float] | None,
    index_name: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not job_embedding:
        return []

    allowed_ids = {str(document["_id"]) for document in documents}
    if not allowed_ids:
        return []

    try:
        pipeline = [
            {
                "$vectorSearch": {
                    "index": index_name,
                    "path": "profile_embedding",
                    "queryVector": job_embedding,
                    "filter": {
                        "_id": {"$in": [document["_id"] for document in documents]}
                    },
                    "numCandidates": max(limit * 5, 20),
                    "limit": limit,
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "vector_score": {"$meta": "vectorSearchScore"},
                }
            },
        ]
        results = list(collection.aggregate(pipeline))
    except Exception:
        return []

    return [
        {
            "resume_id": str(item["_id"]),
            "keyword_score": 0.0,
            "vector_score": float(item.get("vector_score", 0.0)),
            "matched_terms": [],
        }
        for item in results
        if str(item["_id"]) in allowed_ids
    ]


def _latest_experience_entry(experiences: Any) -> dict[str, Any]:
    if not isinstance(experiences, list):
        return {}

    candidates = [
        entry
        for entry in experiences
        if isinstance(entry, dict) and _experience_entry_context(entry)
    ]
    if not candidates:
        return {}

    dated_candidates: list[tuple[tuple[int, datetime], dict[str, Any]]] = []
    for entry in candidates:
        end_text = str(entry.get("end_date", "")).strip()
        start_text = str(entry.get("start_date", "")).strip()
        end_date = _parse_experience_date(end_text) or _parse_experience_date(
            start_text
        )
        if end_date is None:
            continue
        dated_candidates.append(((_is_current_role(end_text), end_date), entry))

    if dated_candidates:
        dated_candidates.sort(key=lambda item: item[0], reverse=True)
        return dated_candidates[0][1]

    return candidates[0]


def _experience_entry_context(entry: dict[str, Any]) -> str:
    if not isinstance(entry, dict):
        return ""

    return " ".join(
        part
        for part in [
            str(entry.get("title", "")).strip(),
            str(entry.get("company", "")).strip(),
            str(entry.get("summary", "")).strip(),
        ]
        if part
    ).strip()


def _experience_recency_weight(entry: dict[str, Any]) -> float:
    if not entry:
        return 0.0

    end_text = str(entry.get("end_date", "")).strip()
    if _is_current_role(end_text):
        return 1.0

    end_date = _parse_experience_date(end_text) or _parse_experience_date(
        str(entry.get("start_date", "")).strip()
    )
    if end_date is None:
        return 0.7

    now = datetime.now(timezone.utc)
    months_since_role = max(
        0, (now.year - end_date.year) * 12 + (now.month - end_date.month)
    )
    if months_since_role <= 6:
        return 1.0
    if months_since_role <= 12:
        return 0.95
    if months_since_role <= 24:
        return 0.85
    if months_since_role <= 36:
        return 0.75
    if months_since_role <= 60:
        return 0.6
    return 0.45


def _is_current_role(value: str) -> int:
    normalized = value.strip().lower()
    if not normalized:
        return 0

    current_markers = ("present", "current", "ongoing", "till date", "today", "now")
    return int(any(marker in normalized for marker in current_markers))


def _parse_experience_date(value: str) -> datetime | None:
    normalized = re.sub(r"\s+", " ", value.strip())
    if not normalized:
        return None
    if _is_current_role(normalized):
        return datetime.now(timezone.utc)

    formats = [
        "%b %Y",
        "%B %Y",
        "%m/%Y",
        "%m-%Y",
        "%Y-%m",
        "%Y/%m",
        "%b %d %Y",
        "%B %d %Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y",
    ]
    for fmt in formats:
        try:
            parsed = datetime.strptime(normalized, fmt)
            if fmt == "%Y":
                return parsed.replace(month=12, day=31, tzinfo=timezone.utc)
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    match = re.search(r"(19|20)\d{2}", normalized)
    if match:
        return datetime(int(match.group(0)), 12, 31, tzinfo=timezone.utc)

    return None
