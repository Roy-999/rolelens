from functools import lru_cache

from pymongo import MongoClient
from pymongo.collection import Collection

from .config import Settings, get_settings


@lru_cache
def get_mongo_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(
        settings.mongodb_uri, serverSelectionTimeoutMS=3000, connectTimeoutMS=3000
    )


def get_candidate_collection(
    settings: Settings | None = None,
) -> Collection:
    active_settings = settings or get_settings()
    return get_mongo_client()[active_settings.mongodb_db_name][
        active_settings.mongodb_candidates_collection
    ]


def get_job_order_collection(
    settings: Settings | None = None,
) -> Collection:
    active_settings = settings or get_settings()
    return get_mongo_client()[active_settings.mongodb_db_name][
        active_settings.mongodb_job_orders_collection
    ]


def get_email_intake_collection(
    settings: Settings | None = None,
) -> Collection:
    active_settings = settings or get_settings()
    return get_mongo_client()[active_settings.mongodb_db_name][
        active_settings.mongodb_email_intakes_collection
    ]


def ensure_indexes(settings: Settings | None = None) -> None:
    candidate_collection = get_candidate_collection(settings)
    candidate_collection.create_index("candidate_id", unique=True, sparse=True)
    candidate_collection.create_index("email_id")
    candidate_collection.create_index("created_at")
    candidate_collection.create_index("updated_at")
    candidate_collection.create_index("source_file_name")

    job_collection = get_job_order_collection(settings)
    job_collection.create_index("job_order_id", unique=True, sparse=True)
    job_collection.create_index("created_at")
    job_collection.create_index("updated_at")
    job_collection.create_index("source_file_name")
    job_collection.create_index("source_attachment_hashes")
    job_collection.create_index("job_title_normalized")
    job_collection.create_index("organization_name_normalized")
    job_collection.create_index("domain")
    job_collection.create_index("location.city")
    job_collection.create_index("location.state")
    job_collection.create_index("location.country")

    email_collection = get_email_intake_collection(settings)
    email_collection.create_index("gmail_message_id", unique=True, sparse=True)
    email_collection.create_index("gmail_thread_id")
    email_collection.create_index("status")
    email_collection.create_index("classification")
    email_collection.create_index("received_at")
    email_collection.create_index("created_at")
    email_collection.create_index("dedupe_key")
    email_collection.create_index("attachment_hashes")
