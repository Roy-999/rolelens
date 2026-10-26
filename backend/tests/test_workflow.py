import io
import zipfile
from app.config import Settings
from app.demo import seed_database, candidate_document


def test_seed_is_idempotent_and_preserves_edits(client):
    api, mongo = client
    assert api.get("/api/candidates").json()["total_candidates"] == 12
    assert api.get("/api/job-orders").json()["total_jobs"] == 4
    mongo.rolelens_demo.candidates.update_one(
        {"candidate_id": "RL-DEMO-001"}, {"$set": {"name": "Reviewed name"}}
    )
    assert seed_database(Settings()) == {"candidates": 0, "jobs": 0}
    assert (
        mongo.rolelens_demo.candidates.find_one({"candidate_id": "RL-DEMO-001"})["name"]
        == "Reviewed name"
    )
    assert seed_database(Settings(mongodb_db_name="other")) == {
        "candidates": 0,
        "jobs": 0,
    }
    assert mongo.other.candidates.count_documents({}) == 0


def test_candidate_extract_review_save_edit_match(client):
    api, mongo = client
    raw = candidate_document(0)[1].replace("Maya Chen", "Quinn Taylor")
    response = api.post(
        "/api/candidates/extract", files={"file": ("resume.txt", raw, "text/plain")}
    )
    assert response.status_code == 200, response.text
    extracted = response.json()
    assert extracted["extraction_method"] == "demo_heuristic"
    assert extracted["extracted_fields"]["name"] == "Quinn Taylor"
    assert "Python" in extracted["extracted_fields"]["skills"]
    payload = dict(
        source_file_name="resume.txt",
        source_file_type=".txt",
        raw_text=raw,
        extraction_method=extracted["extraction_method"],
        extracted_fields=extracted["extracted_fields"],
    )
    payload["extracted_fields"]["name"] = "Quinn Taylor Reviewed"
    saved = api.post("/api/candidates/submit", json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["embedding_created"] is False
    cid = saved.json()["candidate_id"]
    payload["extracted_fields"]["skills"].append("Testing")
    updated = api.put(f"/api/candidates/{cid}", json=payload)
    assert updated.status_code == 200 and "Testing" in updated.json()["skills"]
    result = api.post(
        "/api/jobs/match",
        data={"job_order": "Python SQL Airflow dbt Snowflake", "limit": 3},
    )
    assert result.status_code == 200, result.text
    assert result.json()["matching_mode"] == "keyword"
    assert len(result.json()["candidates"]) == 3
    assert all(c["vector_score"] == 0 for c in result.json()["candidates"])
    filtered = api.post(
        "/api/jobs/match",
        data={"job_order": "Python SQL", "city_filter": "Austin", "limit": 10},
    )
    assert all(c["location"]["city"] == "Austin" for c in filtered.json()["candidates"])


def test_job_review_save_edit_and_salary(client):
    api, _ = client
    raw = "Job Title: Platform Engineer\nCompany: Fictional Works\nLocation: Austin, Texas, United States\nSkills\nPython, Docker\nSalary: USD 120,000 - 150,000 annually"
    response = api.post("/api/job-orders/extract", data={"job_order": raw})
    assert response.status_code == 200, response.text
    fields = response.json()["extracted_fields"]
    fields["job_title"] = "Reviewed Platform Engineer"
    payload = dict(
        source_file_name="pasted.txt",
        source_file_type=".txt",
        raw_text=raw,
        extraction_method="demo_heuristic",
        extracted_fields=fields,
    )
    saved = api.post("/api/job-orders/submit", json=payload)
    assert saved.status_code == 200, saved.text
    fields["organization_name"] = "Reviewed Fictional Works"
    updated = api.put("/api/job-orders/" + saved.json()["job_order_id"], json=payload)
    assert (
        updated.status_code == 200
        and updated.json()["organization_name"] == "Reviewed Fictional Works"
    )
    salary = api.post("/api/jobs/salary", data={"job_order": raw}).json()[
        "salary_range"
    ]
    assert "explicitly stated" in salary


def test_file_types_and_invalid_inputs(client):
    api, _ = client
    assert (
        api.post(
            "/api/candidates/extract", files={"file": ("x.txt", b"", "text/plain")}
        ).status_code
        == 400
    )
    assert (
        api.post(
            "/api/candidates/extract",
            files={"file": ("x.exe", b"bad", "application/octet-stream")},
        ).status_code
        == 400
    )
    assert (
        api.post(
            "/api/candidates/extract",
            files={"file": ("x.png", b"fake image", "image/png")},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/candidates/extract",
            files={"file": ("x.txt", b"x" * (10 * 1024 * 1024 + 1), "text/plain")},
        ).status_code
        == 400
    )
    assert api.post("/api/jobs/match", data={"job_order": ""}).status_code == 400
    assert (
        api.post(
            "/api/jobs/match", data={"job_order": "Python", "limit": 0}
        ).status_code
        == 400
    )
    assert api.post("/api/candidates/submit", json={}).status_code == 422
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as doc:
        doc.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Quinn Taylor Python SQL resume content for the test.</w:t></w:r></w:p></w:body></w:document>',
        )
    assert (
        api.post(
            "/api/candidates/extract", files={"file": ("x.docx", buffer.getvalue())}
        ).status_code
        == 200
    )
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text(
        (50, 50),
        "Quinn Taylor\nquinn@example.com\nSkills\nPython, SQL\nExperience\nSix years building data systems and analytical pipelines.",
    )
    assert (
        api.post(
            "/api/candidates/extract", files={"file": ("x.pdf", pdf.tobytes())}
        ).status_code
        == 200
    )
    pdf.close()


def test_health_readiness_and_disabled_gmail(client, monkeypatch):
    api, mongo = client
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/ready").status_code == 200
    assert api.get("/api/capabilities").json()["ai_mode"] == "demo"
    assert api.get("/api/gmail/login").status_code == 409
    assert api.get("/auth/callback").status_code == 409
    assert api.get("/api/openapi.json").status_code == 200
    monkeypatch.setattr(
        mongo.admin,
        "command",
        lambda *_: (_ for _ in ()).throw(RuntimeError("offline")),
    )
    assert api.get("/api/ready").status_code == 503
    assert api.get("/api/health").status_code == 200


def test_reset_refuses_other_database(monkeypatch):
    import sys
    from app import cli

    monkeypatch.setattr(
        cli, "get_settings", lambda: Settings(mongodb_db_name="production")
    )
    monkeypatch.setattr(sys, "argv", ["cli", "reset-demo"])
    import pytest

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 2
