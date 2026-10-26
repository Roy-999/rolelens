import pytest
from app.config import Settings
from app.services.matching import rank_profiles_for_job


def document(key, skills, vector=None, model="gemini-embedding-2"):
    return {
        "_id": key,
        "candidate_id": key,
        "name": key,
        "skills": skills,
        "profile_embedding": vector,
        "embedding_model": model if vector else None,
        "embedding_dimensions": len(vector) if vector else None,
    }


def rank(docs, embedding=None, **kwargs):
    return rank_profiles_for_job(
        collection=None,
        documents=docs,
        job_order="Python",
        job_embedding=embedding,
        settings=Settings(embedding_dimensions=2, **kwargs),
    )


def test_missing_vectors_and_zero_evidence_do_not_add_ranks():
    result = rank(
        [
            document("a", ["Python"]),
            document("b", ["Welding"]),
            document("c", ["Python"]),
        ]
    )
    assert [r.candidate_id for r in result] == ["a", "c"]
    assert result[0].rrf_score == pytest.approx(1 / 61)
    assert all(r.source == "keyword" for r in result)


def test_incompatible_embeddings_are_excluded():
    docs = [
        document("a", ["Python"], [1, 0], "old-model"),
        document("b", ["Welding"], [1, 0]),
        document("c", ["Other"], [1, 0, 0]),
    ]
    result = rank(docs, [1, 0])
    assert result[0].candidate_id == "a" and result[0].vector_score == 0
    assert result[1].candidate_id == "b" and result[1].source == "vector"
    assert len(result) == 2


def test_atlas_and_local_semantic_evidence_count_once(monkeypatch):
    docs = [document("a", ["Python"], [1, 0])]
    monkeypatch.setattr(
        "app.services.matching._atlas_vector_rankings",
        lambda **_: [{"resume_id": "a", "vector_score": 0.9}],
    )
    result = rank(docs, [1, 0], atlas_vector_enabled=True)
    assert result[0].rrf_score == pytest.approx(2 / 61)
    assert result[0].vector_score == 0.9


def test_atlas_unavailable_uses_local_cosine(monkeypatch):
    monkeypatch.setattr("app.services.matching._atlas_vector_rankings", lambda **_: [])
    result = rank(
        [document("a", ["Python"], [1, 0])], [1, 0], atlas_vector_enabled=True
    )
    assert result[0].vector_score == 1 and result[0].rrf_score == pytest.approx(2 / 61)
