"""Deterministic fictional fixtures; never reads documents from the private source."""

from datetime import datetime, timezone, timedelta
from .config import Settings
from .database import get_candidate_collection, get_job_order_collection
from .schemas import CandidateExtraction, JobOrderExtraction
from .services.profile_context import build_profile_context

PEOPLE = [
    (
        "Maya Chen",
        "Data Engineer",
        "Austin",
        "Texas",
        6,
        ["Python", "SQL", "Airflow", "dbt", "Snowflake"],
        "Built dependable ingestion pipelines and analytics models.",
    ),
    (
        "Arjun Mehta",
        "ML Engineer",
        "Austin",
        "Texas",
        5,
        ["Python", "PyTorch", "FastAPI", "Docker", "SQL"],
        "Deployed machine learning inference services and evaluation pipelines.",
    ),
    (
        "Sofia Rivera",
        "Analytics Engineer",
        "Denver",
        "Colorado",
        4,
        ["SQL", "dbt", "Snowflake", "Python", "Looker"],
        "Designed dimensional models and monitored data quality.",
    ),
    (
        "Theo Brooks",
        "Backend Engineer",
        "Austin",
        "Texas",
        7,
        ["Python", "FastAPI", "PostgreSQL", "Docker", "Redis"],
        "Built APIs and reliable asynchronous processing systems.",
    ),
    (
        "Nina Okafor",
        "Frontend Engineer",
        "Denver",
        "Colorado",
        4,
        ["React", "TypeScript", "CSS", "Playwright"],
        "Created accessible product interfaces and browser tests.",
    ),
    (
        "Elias Park",
        "Platform Engineer",
        "Seattle",
        "Washington",
        8,
        ["Docker", "Kubernetes", "Terraform", "Python", "Linux"],
        "Built developer platforms and deployment automation.",
    ),
    (
        "Amara Singh",
        "Data Scientist",
        "Seattle",
        "Washington",
        3,
        ["Python", "SQL", "XGBoost", "pandas", "Statistics"],
        "Evaluated demand forecasting models against seasonal baselines.",
    ),
    (
        "Lucas Bennett",
        "Data Engineer",
        "Denver",
        "Colorado",
        3,
        ["Python", "SQL", "Spark", "Airflow"],
        "Maintained batch ingestion jobs and data validation checks.",
    ),
    (
        "Isla Morgan",
        "Electrician",
        "Austin",
        "Texas",
        9,
        ["Electrical", "Blueprints", "Troubleshooting", "Safety"],
        "Installed commercial electrical systems and inspected circuits.",
    ),
    (
        "Owen Ellis",
        "Welder",
        "Denver",
        "Colorado",
        6,
        ["Welding", "MIG", "TIG", "Blueprints", "Safety"],
        "Fabricated structural assemblies and verified weld quality.",
    ),
    (
        "Zara Mitchell",
        "HVAC Technician",
        "Austin",
        "Texas",
        5,
        ["HVAC", "Maintenance", "Troubleshooting", "Safety"],
        "Serviced cooling systems and documented preventive maintenance.",
    ),
    (
        "Finn Walker",
        "Electrician",
        "Seattle",
        "Washington",
        4,
        ["Electrical", "Wiring", "Safety", "Maintenance"],
        "Performed wiring installation and equipment maintenance.",
    ),
]

JOBS = [
    (
        "Data Engineer",
        "Meridian Grove Labs",
        "Austin",
        "Texas",
        "Technology",
        ["Python", "SQL", "Airflow", "dbt", "Snowflake"],
        4,
        "USD 120,000 - 150,000 annually",
    ),
    (
        "Backend Engineer",
        "Northstar Vale Systems",
        "Austin",
        "Texas",
        "Technology",
        ["Python", "FastAPI", "PostgreSQL", "Docker"],
        4,
        "USD 125,000 - 155,000 annually",
    ),
    (
        "Commercial Electrician",
        "Copperleaf Works",
        "Austin",
        "Texas",
        "Construction",
        ["Electrical", "Blueprints", "Troubleshooting", "Safety"],
        5,
        "USD 30 - 40 per hour",
    ),
    (
        "Structural Welder",
        "Ironwood Harbor Fabrication",
        "Denver",
        "Colorado",
        "Manufacturing",
        ["Welding", "MIG", "TIG", "Blueprints"],
        3,
        "USD 28 - 36 per hour",
    ),
]


def candidate_document(index):
    name, title, city, state, years, skills, summary = PEOPLE[index]
    fields = CandidateExtraction(
        name=name,
        email_id=name.lower().replace(" ", ".") + "@example.com",
        location={"city": city, "state": state, "Country": "United States"},
        years_of_experience=years,
        skills=skills,
        tools=skills[:3],
        languages=["English"],
        experience=[
            {
                "company": "Fictional Fieldstone Studio",
                "title": title,
                "start_date": "2022-01",
                "end_date": "Present",
                "summary": summary,
            }
        ],
        visits=4 + index,
        last_login_days=index % 8,
        applications_count=index % 5,
        profile_updates=2,
    )
    raw = f"{name}\n{fields.email_id}\nLocation: {city}, {state}, United States\n{years} years of experience\n\nSkills\n{', '.join(skills)}\n\nExperience\n{title} at Fictional Fieldstone Studio. {summary}\n\nLanguages\nEnglish\n"
    return fields, raw


def job_document(index):
    title, company, city, state, domain, skills, years, pay = JOBS[index]
    summary = f"Join {company} as a {title}. Build reliable systems and collaborate with a small delivery team."
    fields = JobOrderExtraction(
        job_title=title,
        organization_name=company,
        domain=domain,
        location={"city": city, "state": state, "country": "United States"},
        skills=skills,
        years_required=years,
        work_arrangement="On-site",
        employment_type="Full-time",
        compensation={"pay_text": pay},
        summary=summary,
        responsibilities=[
            "Deliver quality work with clear documentation.",
            "Collaborate with the team and improve reliability.",
        ],
        qualifications=[
            f"{years}+ years of relevant experience",
            "Experience with " + ", ".join(skills),
        ],
    )
    raw = f"Job Title: {title}\nCompany: {company}\nLocation: {city}, {state}, United States\nSalary: {pay}\n\nSummary\n{summary}\n\nSkills\n{', '.join(skills)}\n\nQualifications\n{years}+ years of experience\n\nResponsibilities\nDeliver quality work and documentation. Collaborate with the team.\n"
    return fields, raw


def seed_database(settings: Settings):
    if settings.mongodb_db_name != "rolelens_demo":
        return {"candidates": 0, "jobs": 0}
    candidates, jobs = (
        get_candidate_collection(settings),
        get_job_order_collection(settings),
    )
    now = datetime(2026, 10, 1, 9, tzinfo=timezone.utc)
    counts = {"candidates": 0, "jobs": 0}
    for i in range(len(PEOPLE)):
        fields, raw = candidate_document(i)
        record = dict(
            **fields.model_dump(),
            candidate_id=f"RL-DEMO-{i + 1:03d}",
            source_file_name=f"sample-candidate-{i + 1}.txt",
            source_file_type=".txt",
            raw_text=raw,
            preview_text=raw,
            extraction_method="synthetic_fixture",
            profile_context=build_profile_context(fields),
            profile_embedding=None,
            created_at=now + timedelta(hours=i),
            updated_at=now + timedelta(hours=i),
            synthetic=True,
        )
        result = candidates.update_one(
            {"candidate_id": record["candidate_id"]},
            {"$setOnInsert": record},
            upsert=True,
        )
        counts["candidates"] += int(result.upserted_id is not None)
    for i in range(len(JOBS)):
        fields, raw = job_document(i)
        record = dict(
            **fields.model_dump(),
            job_order_id=f"RL-JOB-{i + 1:03d}",
            source_file_name=f"sample-job-{i + 1}.txt",
            source_file_type=".txt",
            raw_text=raw,
            preview_text=raw,
            extraction_method="synthetic_fixture",
            created_at=now + timedelta(hours=i),
            updated_at=now + timedelta(hours=i),
            synthetic=True,
        )
        result = jobs.update_one(
            {"job_order_id": record["job_order_id"]},
            {"$setOnInsert": record},
            upsert=True,
        )
        counts["jobs"] += int(result.upserted_id is not None)
    return counts
