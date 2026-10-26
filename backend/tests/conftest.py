import os
import sys
from pathlib import Path
import mongomock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["AI_MODE"] = "demo"
os.environ["MONGODB_DB_NAME"] = "rolelens_demo"


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient
    from app import database, main

    mongo = mongomock.MongoClient()
    monkeypatch.setattr(database, "get_mongo_client", lambda: mongo)
    monkeypatch.setattr(main, "get_mongo_client", lambda: mongo)
    with TestClient(main.app) as c:
        yield c, mongo
