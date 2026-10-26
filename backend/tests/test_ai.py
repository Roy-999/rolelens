from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from app.config import Settings
from app.services.ai_service import AIService


def service(response='{"name":"Maya Chen", "skills":["Python"]}'):
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(text=response)
    return AIService(
        Settings(ai_mode="gemini", gemini_api_key="fake-key", embedding_dimensions=2),
        client,
    ), client


def test_demo_never_calls_provider():
    client = Mock()
    ai = AIService(Settings(ai_mode="demo"), client)
    assert (
        ai.extract_candidate_fields("Maya Chen\nSkills\nPython", [], ".txt")[1]
        == "demo_heuristic"
    )
    assert ai.create_embedding("Python") is None
    client.assert_not_called()
    assert client.mock_calls == []


def test_valid_output_and_image_input():
    ai, client = service()
    fields, method = ai.extract_candidate_fields("", [b"\x89PNG image"], ".png")
    assert method == "gemini_vision" and fields.name == "Maya Chen"
    assert (
        client.models.generate_content.call_args.kwargs["contents"][
            1
        ].inline_data.mime_type
        == "image/png"
    )


@pytest.mark.parametrize("response", ["not json", '{"years_of_experience":{}}', None])
def test_malformed_output_falls_back(response):
    ai, _ = service(response)
    fields, method = ai.extract_candidate_fields(
        "Maya Chen\nSkills\nPython", [], ".txt"
    )
    assert method == "heuristic_fallback" and fields.name == "Maya Chen"


@pytest.mark.parametrize(
    "failure", [TimeoutError(), type("QuotaError", (Exception,), {"code": 429})()]
)
def test_provider_retry_is_bounded(failure, monkeypatch):
    ai, client = service()
    monkeypatch.setattr("app.services.ai_service.time.sleep", lambda _: None)
    client.models.generate_content.side_effect = failure
    assert (
        ai.extract_job_order_fields("Job Title: Engineer", [], ".txt")[1]
        == "heuristic_fallback"
    )
    assert client.models.generate_content.call_count == 2


def test_unreadable_image_does_not_become_empty_profile():
    ai, client = service("invalid")
    with pytest.raises(ValueError, match="working Gemini access"):
        ai.extract_candidate_fields("", [b"image"], ".png")


def test_embedding_validation_and_metadata():
    ai, client = service()
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[3.0, 4.0])]
    )
    assert ai.create_embedding("Python") == [0.6, 0.8]
    metadata = ai.embedding_metadata("Python", [0.6, 0.8])
    assert (
        metadata["embedding_dimensions"] == 2
        and len(metadata["embedding_content_hash"]) == 64
    )
    client.models.embed_content.return_value = SimpleNamespace(
        embeddings=[SimpleNamespace(values=[1.0])]
    )
    assert ai.create_embedding("Python") is None
    client.models.embed_content.side_effect = ValueError("provider error")
    assert ai.create_embedding("Python") is None


def test_email_classification_and_salary():
    ai, _ = service(
        '{"classification":"job_order","confidence":0.9,"reason":"Hiring request"}'
    )
    assert (
        ai.classify_job_order_email(
            subject="Hiring",
            cleaned_body="Engineer needed",
            attachment_text="",
            attachment_names=[],
        )[0]
        == "job_order"
    )
    assert "explicitly stated" in ai.extract_salary(
        "Salary: USD 100,000 - 120,000 annually"
    )
    assert ai.extract_salary(
        "Engineer in Austin with 5 years of experience"
    ).startswith("Unverified estimate")


def test_live_mode_requires_key():
    with pytest.raises(ValueError, match="requires GEMINI_API_KEY"):
        Settings(ai_mode="gemini", gemini_api_key=None)
