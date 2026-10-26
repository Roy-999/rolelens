"""Explicit local maintenance commands. Run with python -m app.cli."""

import argparse
import hashlib
from .config import get_settings
from .database import get_mongo_client, get_candidate_collection, ensure_indexes
from .demo import seed_database
from .services.ai_service import AIService
from .services.profile_context import build_profile_context_from_mapping


def main():
    parser = argparse.ArgumentParser(description="RoleLens demo maintenance")
    parser.add_argument("command", choices=["seed", "reset-demo", "reindex"])
    args = parser.parse_args()
    settings = get_settings()
    if args.command == "reset-demo":
        if settings.mongodb_db_name != "rolelens_demo":
            parser.error("Reset is restricted to the rolelens_demo database.")
        get_mongo_client().drop_database("rolelens_demo")
        ensure_indexes(settings)
        print(seed_database(settings))
    elif args.command == "seed":
        print(seed_database(settings))
    else:
        if settings.ai_mode != "gemini":
            parser.error("Reindex requires AI_MODE=gemini and GEMINI_API_KEY.")
        ai = AIService(settings)
        collection = get_candidate_collection(settings)
        indexed, failed = 0, 0
        for doc in collection.find():
            context = build_profile_context_from_mapping(doc)
            digest = hashlib.sha256(context.encode()).hexdigest()
            if (
                doc.get("embedding_content_hash") == digest
                and doc.get("embedding_model") == settings.gemini_embedding_model
                and doc.get("embedding_dimensions") == settings.embedding_dimensions
                and len(doc.get("profile_embedding") or [])
                == settings.embedding_dimensions
            ):
                continue
            vector = ai.create_embedding(context)
            if vector:
                collection.update_one(
                    {"_id": doc["_id"]},
                    {
                        "$set": {
                            "profile_context": context,
                            "profile_embedding": vector,
                            **ai.embedding_metadata(context, vector),
                        }
                    },
                )
                indexed += 1
            else:
                failed += 1
        print(
            f"Indexed: {indexed}; failed: {failed}. Re-run safely after quota recovery."
        )
        if failed:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
