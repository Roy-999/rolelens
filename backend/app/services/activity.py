from __future__ import annotations

import random
from typing import Any

import numpy as np
from bson import ObjectId
from pymongo.collection import Collection
from pymongo import UpdateOne
from sklearn.cluster import KMeans
from sklearn.preprocessing import MinMaxScaler


SYSTEM_RANDOM = random.SystemRandom()

ACTIVE_PROFILES = (
    {
        "visits": (60, 160),
        "last_login_days": (0, 10),
        "applications_count": (6, 22),
        "profile_updates": (2, 10),
    },
    {
        "visits": (30, 90),
        "last_login_days": (0, 21),
        "applications_count": (3, 14),
        "profile_updates": (1, 7),
    },
    {
        "visits": (45, 120),
        "last_login_days": (0, 14),
        "applications_count": (4, 18),
        "profile_updates": (1, 9),
    },
)

PASSIVE_PROFILES = (
    {
        "visits": (0, 18),
        "last_login_days": (35, 180),
        "applications_count": (0, 3),
        "profile_updates": (0, 2),
    },
    {
        "visits": (5, 35),
        "last_login_days": (21, 120),
        "applications_count": (0, 5),
        "profile_updates": (0, 3),
    },
    {
        "visits": (10, 42),
        "last_login_days": (14, 90),
        "applications_count": (0, 6),
        "profile_updates": (0, 4),
    },
)

ACTIVITY_FIELDS = (
    "visits",
    "last_login_days",
    "applications_count",
    "profile_updates",
    "activity_score",
    "activity_label",
)


def classify_candidate_activity_by_percentile(
    collection: Collection,
    candidate_id: str,
    percentile: float = 70.0,
) -> dict[str, Any]:
    documents = list(collection.find({}, {"visits": 1}))
    if not documents:
        raise ValueError("No candidate profiles found in MongoDB.")

    candidate = _get_candidate_document(collection, candidate_id)
    visits = _safe_int(candidate.get("visits"))
    all_visits = np.array(
        [_safe_int(document.get("visits")) for document in documents], dtype=float
    )
    threshold = float(np.percentile(all_visits, percentile))
    activity_label = "Active" if visits >= threshold else "Passive"

    return {
        "candidate_id": candidate_id,
        "visits": visits,
        "threshold": threshold,
        "method": "percentile",
        "activity_label": activity_label,
    }


def build_random_activity_profile(
    collection: Collection | None = None,
    preferred_label: str | None = None,
) -> dict[str, Any]:
    label = preferred_label or _choose_balanced_label(collection)
    template = SYSTEM_RANDOM.choice(
        ACTIVE_PROFILES if label == "Active" else PASSIVE_PROFILES
    )

    visits = _random_int(template["visits"])
    last_login_days = _random_int(template["last_login_days"])
    applications_count = _random_int(template["applications_count"])
    profile_updates = _random_int(template["profile_updates"])
    activity_score = _compute_activity_score(
        visits=visits,
        last_login_days=last_login_days,
        applications_count=applications_count,
        profile_updates=profile_updates,
    )

    return {
        "visits": visits,
        "last_login_days": last_login_days,
        "applications_count": applications_count,
        "profile_updates": profile_updates,
        "activity_score": activity_score,
        "activity_label": label,
    }


def ensure_activity_fields(collection: Collection) -> int:
    documents = list(
        collection.find(
            {
                "$or": [{field: {"$exists": False}} for field in ACTIVITY_FIELDS],
            }
        )
    )
    if not documents:
        return 0

    start_label = _choose_balanced_label(collection)
    operations: list[UpdateOne] = []

    for index, document in enumerate(documents):
        label = start_label if index % 2 == 0 else _opposite_label(start_label)
        generated_profile = build_random_activity_profile(None, preferred_label=label)
        operations.append(
            UpdateOne(
                {"_id": document["_id"]},
                {
                    "$set": generated_profile,
                },
            )
        )

    if operations:
        collection.bulk_write(operations, ordered=False)

    return len(operations)


def classify_candidate_activity_weighted(
    collection: Collection,
    candidate_id: str,
) -> dict[str, Any]:
    documents = list(collection.find())
    if not documents:
        raise ValueError("No candidate profiles found in MongoDB.")
    if len(documents) < 2:
        raise ValueError(
            "Weighted clustering requires at least two candidate profiles."
        )

    candidate = _get_candidate_document(collection, candidate_id)
    ordered_ids, score_matrix = _build_activity_score_matrix(documents)

    scaler = MinMaxScaler()
    normalized_matrix = scaler.fit_transform(score_matrix)

    weights = np.array([0.4, 0.3, 0.2, 0.1], dtype=float)
    scores = normalized_matrix @ weights

    clustering = KMeans(n_clusters=2, random_state=42, n_init=10)
    clusters = clustering.fit_predict(scores.reshape(-1, 1))
    active_cluster = int(np.argmax(clustering.cluster_centers_.reshape(-1)))

    candidate_index = ordered_ids.index(str(candidate["_id"]))
    candidate_score = float(scores[candidate_index])
    candidate_cluster = int(clusters[candidate_index])
    activity_label = "Active" if candidate_cluster == active_cluster else "Passive"

    return {
        "candidate_id": candidate_id,
        "activity_score": candidate_score,
        "cluster": candidate_cluster,
        "method": "weighted_clustering",
        "activity_label": activity_label,
    }


def _get_candidate_document(
    collection: Collection, candidate_id: str
) -> dict[str, Any]:
    candidate = collection.find_one({"candidate_id": candidate_id})
    if candidate is not None:
        return candidate

    try:
        object_id = ObjectId(candidate_id)
    except Exception as exc:
        raise ValueError(
            "candidate_id must be a valid candidate ID or MongoDB ObjectId."
        ) from exc

    candidate = collection.find_one({"_id": object_id})
    if candidate is None:
        raise LookupError(f"Candidate not found: {candidate_id}")
    return candidate


def _build_activity_score_matrix(
    documents: list[dict[str, Any]],
) -> tuple[list[str], np.ndarray]:
    ordered_ids: list[str] = []
    rows: list[list[float]] = []

    for document in documents:
        ordered_ids.append(str(document["_id"]))
        visits = np.log1p(max(_safe_int(document.get("visits")), 0))
        last_login_days = np.exp(-max(_safe_int(document.get("last_login_days")), 0))
        applications_count = float(
            max(_safe_int(document.get("applications_count")), 0)
        )
        profile_updates = float(max(_safe_int(document.get("profile_updates")), 0))
        rows.append(
            [
                float(visits),
                float(last_login_days),
                applications_count,
                profile_updates,
            ]
        )

    return ordered_ids, np.asarray(rows, dtype=float)


def _choose_balanced_label(collection: Collection | None) -> str:
    if collection is None:
        return SYSTEM_RANDOM.choice(("Active", "Passive"))

    active_count = collection.count_documents({"activity_label": "Active"})
    passive_count = collection.count_documents({"activity_label": "Passive"})

    if active_count > passive_count + 1:
        return "Passive"
    if passive_count > active_count + 1:
        return "Active"
    return SYSTEM_RANDOM.choice(("Active", "Passive"))


def _opposite_label(label: str) -> str:
    return "Passive" if label == "Active" else "Active"


def _random_int(bounds: tuple[int, int]) -> int:
    low, high = bounds
    return SYSTEM_RANDOM.randint(low, high)


def _compute_activity_score(
    *,
    visits: int,
    last_login_days: int,
    applications_count: int,
    profile_updates: int,
) -> float:
    visits_component = min(visits / 160.0, 1.0)
    recency_component = 1.0 - min(last_login_days / 180.0, 1.0)
    applications_component = min(applications_count / 22.0, 1.0)
    updates_component = min(profile_updates / 10.0, 1.0)

    score = (
        (0.4 * visits_component)
        + (0.3 * recency_component)
        + (0.2 * applications_component)
        + (0.1 * updates_component)
    )
    return round(float(max(0.0, min(score, 1.0))), 4)


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
