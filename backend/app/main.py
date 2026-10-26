from __future__ import annotations

import logging
from contextlib import asynccontextmanager
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from .config import get_settings
from .database import (
    ensure_indexes,
    get_email_intake_collection,
    get_job_order_collection,
    get_mongo_client,
    get_candidate_collection,
)
from .schemas import (
    ActivityPercentileResponse,
    ActivityWeightedResponse,
    CandidateStatsResponse,
    CandidateListResponse,
    CandidateRecord,
    CandidateSubmission,
    CandidateSubmissionResponse,
    ExtractedCandidateResponse,
    ExtractedJobOrderResponse,
    EmailDraftSaveRequest,
    EmailDraftSaveResponse,
    EmailJobOrderDraftListResponse,
    EmailJobOrderDraftRecord,
    GmailProcessLatestResponse,
    GmailStatusResponse,
    GmailTestFetchResponse,
    HealthResponse,
    JobOrderListResponse,
    JobOrderRecord,
    JobOrderStatsResponse,
    JobOrderSubmission,
    JobOrderSubmissionResponse,
    JobSalaryResponse,
    MatchResponse,
)
from .services.activity import (
    build_random_activity_profile,
    classify_candidate_activity_by_percentile,
    classify_candidate_activity_weighted,
    ensure_activity_fields,
)
from .services.completion import (
    calculate_candidate_completion,
    calculate_job_order_completion,
)
from .services.document_parser import ParsedDocument, parse_document
from .services.email_job_order_pipeline import (
    EmailJobOrderPipeline,
    serialize_email_draft,
)
from .services.gmail_client import GmailClient
from .services.job_order_dedupe import normalized_title_company_fields
from .services.location_utils import build_location_hierarchy, location_matches_filter
from .services.matching import rank_profiles_for_job
from .services.ai_service import AIService
from .services.profile_context import build_profile_context

settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    on_startup()
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ai_service = AIService(settings)
gmail_client = GmailClient(settings)
logger = logging.getLogger(__name__)

health_router = APIRouter(prefix=settings.api_prefix, tags=["Health"])
auth_router = APIRouter(prefix=f"{settings.api_prefix}/auth", tags=["Auth"])
oauth_callback_router = APIRouter(prefix="/auth", tags=["Auth"])
gmail_router = APIRouter(prefix=f"{settings.api_prefix}/gmail", tags=["Gmail"])
candidates_router = APIRouter(
    prefix=f"{settings.api_prefix}/candidates", tags=["Candidates"]
)
job_orders_router = APIRouter(
    prefix=f"{settings.api_prefix}/job-orders", tags=["Job Orders"]
)
jobs_router = APIRouter(prefix=f"{settings.api_prefix}/jobs", tags=["Jobs"])
activity_router = APIRouter(prefix=f"{settings.api_prefix}/activity", tags=["Activity"])


async def _read_upload_file(file: UploadFile, *, empty_message: str) -> bytes:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail=empty_message)

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds the {settings.max_file_size_mb} MB limit.",
        )

    return file_bytes


def _parse_uploaded_document(
    *,
    file_name: str,
    file_bytes: bytes,
    upload_label: str,
) -> ParsedDocument:
    try:
        document = parse_document(file_name, file_bytes, settings)
        if document.is_scanned_document and settings.ai_mode == "demo":
            raise HTTPException(
                status_code=422,
                detail="Scanned documents need Gemini vision. Use a text-based PDF, DOCX, TXT, or pasted text in sample mode.",
            )
        return document
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected document parsing failure for %s upload: %s", upload_label, exc
        )
        raise HTTPException(
            status_code=500,
            detail=f"Unable to parse the uploaded {upload_label} due to a server-side parsing error.",
        ) from exc


def _trim_preview_text(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= settings.max_preview_chars:
        return stripped
    return f"{stripped[: settings.max_preview_chars].rstrip()}..."


async def _resolve_job_text(
    *,
    file: UploadFile | None,
    job_order: str | None,
) -> str:
    # Keep job order parsing/transcription behavior consistent for matching and salary extraction.
    job_text = (job_order or "").strip()
    if file is not None:
        file_bytes = await _read_upload_file(
            file, empty_message="Uploaded job order file is empty."
        )
        parsed_document = _parse_uploaded_document(
            file_name=file.filename or "job_order",
            file_bytes=file_bytes,
            upload_label="job order",
        )
        job_text = parsed_document.raw_text or parsed_document.preview_text
        if parsed_document.is_scanned_document and not job_text:
            job_text = ai_service.transcribe_images(
                parsed_document.rendered_images,
                parsed_document.file_type,
            )

    if not job_text:
        raise HTTPException(
            status_code=400,
            detail="Provide a job order file or paste the job order text.",
        )
    return job_text


async def _parse_job_order_input(
    *,
    file: UploadFile | None,
    job_order: str | None,
) -> ParsedDocument:
    job_text = (job_order or "").strip()
    if file is not None:
        file_bytes = await _read_upload_file(
            file, empty_message="Uploaded job order file is empty."
        )
        parsed_document = _parse_uploaded_document(
            file_name=file.filename or "job_order",
            file_bytes=file_bytes,
            upload_label="job order",
        )
        preview_text = parsed_document.preview_text
        raw_text = parsed_document.raw_text
        if parsed_document.is_scanned_document and not preview_text:
            preview_text = ai_service.transcribe_images(
                parsed_document.rendered_images,
                parsed_document.file_type,
            )
            raw_text = preview_text
        return ParsedDocument(
            file_name=parsed_document.file_name,
            file_type=parsed_document.file_type,
            raw_text=raw_text,
            preview_text=preview_text,
            is_scanned_document=parsed_document.is_scanned_document,
            rendered_images=parsed_document.rendered_images,
        )

    if not job_text:
        raise HTTPException(
            status_code=400,
            detail="Provide a job order file or paste the job order text.",
        )

    return ParsedDocument(
        file_name="pasted_job_order.txt",
        file_type=".txt",
        raw_text=job_text,
        preview_text=_trim_preview_text(job_text),
    )


def _serialize_job_order(document: dict) -> JobOrderRecord:
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    payload = {
        "id": str(document.get("_id", "")),
        "job_order_id": document.get("job_order_id") or str(document.get("_id", "")),
        "profile_completion_percentage": calculate_job_order_completion(document),
        "source_file_name": document.get("source_file_name") or "",
        "source_file_type": document.get("source_file_type") or "",
        "raw_text": document.get("raw_text") or "",
        "preview_text": document.get("preview_text") or "",
        "extraction_method": document.get("extraction_method") or "",
        "is_scanned_document": bool(document.get("is_scanned_document")),
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else None,
        "updated_at": updated_at.isoformat()
        if hasattr(updated_at, "isoformat")
        else None,
    }
    for key in [
        "job_title",
        "domain",
        "organization_name",
        "number_of_openings",
        "location",
        "work_arrangement",
        "employment_type",
        "hours_per_week",
        "hours_of_operation",
        "duration_weeks",
        "start_date",
        "end_date",
        "years_required",
        "will_sponsor",
        "will_relocate",
        "travel_required",
        "compensation",
        "summary",
        "responsibilities",
        "qualifications",
        "skills",
        "certifications",
        "benefits",
        "additional_details",
        "compliance",
        "physical_requirements",
    ]:
        value = document.get(key)
        if value is not None:
            payload[key] = value
    return JobOrderRecord.model_validate(payload)


def _serialize_candidate(document: dict) -> CandidateRecord:
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    payload = {
        **document,
        "id": str(document.get("_id", "")),
        "candidate_id": document.get("candidate_id") or str(document.get("_id", "")),
        "profile_completion_percentage": calculate_candidate_completion(document),
        "source_file_name": document.get("source_file_name") or "",
        "source_file_type": document.get("source_file_type") or "",
        "raw_text": document.get("raw_text") or "",
        "preview_text": document.get("preview_text") or "",
        "extraction_method": document.get("extraction_method") or "",
        "is_scanned_document": bool(document.get("is_scanned_document")),
        "profile_context": document.get("profile_context") or "",
        "created_at": created_at.isoformat()
        if hasattr(created_at, "isoformat")
        else None,
        "updated_at": updated_at.isoformat()
        if hasattr(updated_at, "isoformat")
        else None,
    }
    return CandidateRecord.model_validate(payload)


def _generate_candidate_id(now: datetime) -> str:
    return f"CAN-{now:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _generate_job_order_id(now: datetime) -> str:
    return f"JO-{now:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"


def _candidate_lookup_filter(candidate_identifier: str) -> dict:
    filters: list[dict] = [{"candidate_id": candidate_identifier}]
    try:
        filters.append({"_id": ObjectId(candidate_identifier)})
    except Exception:
        pass
    return filters[0] if len(filters) == 1 else {"$or": filters}


def _ensure_candidate_ids(collection) -> int:
    updated_count = 0
    for document in collection.find(
        {"candidate_id": {"$exists": False}}, {"_id": 1, "created_at": 1}
    ):
        created_at = document.get("created_at")
        base_time = (
            created_at
            if isinstance(created_at, datetime)
            else datetime.now(timezone.utc)
        )
        for _ in range(3):
            candidate_id = _generate_candidate_id(base_time)
            try:
                result = collection.update_one(
                    {"_id": document["_id"], "candidate_id": {"$exists": False}},
                    {"$set": {"candidate_id": candidate_id}},
                )
            except Exception:
                continue
            if result.modified_count:
                updated_count += 1
                break
    return updated_count


def _service_unavailable(
    detail: str = "A required backend service is currently unavailable.",
) -> HTTPException:
    return HTTPException(status_code=503, detail=detail)


def _get_email_pipeline() -> EmailJobOrderPipeline:
    try:
        email_collection = get_email_intake_collection(settings)
        job_collection = get_job_order_collection(settings)
    except Exception as exc:
        logger.exception("MongoDB collection unavailable during email intake: %s", exc)
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    return EmailJobOrderPipeline(
        settings=settings,
        gmail_client=gmail_client,
        ai_service=ai_service,
        email_collection=email_collection,
        job_collection=job_collection,
    )


def _email_draft_lookup_filter(draft_id: str) -> dict:
    filters: list[dict] = [{"gmail_message_id": draft_id}]
    try:
        filters.append({"_id": ObjectId(draft_id)})
    except Exception:
        pass
    return filters[0] if len(filters) == 1 else {"$or": filters}


def on_startup() -> None:
    try:
        ensure_indexes(settings)
        from .demo import seed_database

        if settings.seed_demo:
            seed_database(settings)
        collection = get_candidate_collection(settings)
        migrated_count = ensure_activity_fields(collection)
        if migrated_count:
            logger.info(
                "Backfilled activity fields for %s existing candidate profiles.",
                migrated_count,
            )
        candidate_id_count = _ensure_candidate_ids(collection)
        if candidate_id_count:
            logger.info(
                "Backfilled candidate IDs for %s existing candidate profiles.",
                candidate_id_count,
            )
    except Exception as exc:
        logger.warning("MongoDB startup initialization failed: %s", exc)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.middleware("http")
async def optional_gmail(request: Request, call_next):
    if (
        request.url.path.startswith("/api/gmail")
        or request.url.path in ("/auth/callback", "/api/auth/callback")
    ) and not settings.gmail_enabled:
        return JSONResponse(
            status_code=409,
            content={
                "detail": "Gmail is optional and disabled. Configure GMAIL_ENABLED and OAuth credentials to connect."
            },
        )
    return await call_next(request)


@health_router.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", message="RoleLens API is running.")


@health_router.get("/ready")
def readiness():
    try:
        get_mongo_client().admin.command("ping")
        return {"status": "ready"}
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "detail": "MongoDB is not ready."},
        )


@health_router.get("/capabilities")
def capabilities():
    collection = get_candidate_collection(settings)
    compatible = collection.count_documents(
        {
            "embedding_model": settings.gemini_embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
        }
    )
    return {
        "ai_mode": settings.ai_mode,
        "gmail_enabled": settings.gmail_enabled,
        "vision_available": settings.ai_mode == "gemini",
        "embedding_model": settings.gemini_embedding_model
        if settings.ai_mode == "gemini"
        else None,
        "indexed_candidates": compatible if settings.ai_mode == "gemini" else 0,
        "sample_data": settings.mongodb_db_name == "rolelens_demo",
    }


@gmail_router.get("/login")
def gmail_login() -> RedirectResponse:
    try:
        return RedirectResponse(gmail_client.authorization_url())
    except Exception as exc:
        logger.exception("Unable to start Gmail OAuth: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@auth_router.get("/callback")
@oauth_callback_router.get("/callback")
def gmail_auth_callback(request: Request) -> RedirectResponse:
    try:
        gmail_client.complete_authorization(str(request.url))
    except Exception as exc:
        logger.exception("Unable to complete Gmail OAuth: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to complete Gmail authorization."
        ) from exc
    return RedirectResponse(f"{settings.frontend_redirect_url}?gmail=connected")


@gmail_router.get("/status", response_model=GmailStatusResponse)
def gmail_status() -> GmailStatusResponse:
    if not gmail_client.is_authorized():
        return GmailStatusResponse(authorized=False)
    try:
        return GmailStatusResponse(
            authorized=True, email=gmail_client.connected_email()
        )
    except Exception:
        return GmailStatusResponse(authorized=False)


@gmail_router.post("/disconnect", response_model=GmailStatusResponse)
def gmail_disconnect() -> GmailStatusResponse:
    try:
        gmail_client.disconnect()
    except Exception as exc:
        logger.exception("Unable to disconnect Gmail: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to disconnect Gmail right now."
        ) from exc
    return GmailStatusResponse(authorized=False)


@gmail_router.post("/test-fetch", response_model=GmailTestFetchResponse)
def gmail_test_fetch() -> GmailTestFetchResponse:
    try:
        messages = _get_email_pipeline().test_fetch()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Gmail test fetch failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to fetch Gmail messages right now."
        ) from exc
    return GmailTestFetchResponse(messages=messages, total_messages=len(messages))


@gmail_router.post("/process-latest", response_model=GmailProcessLatestResponse)
def gmail_process_latest() -> GmailProcessLatestResponse:
    try:
        summary = _get_email_pipeline().process_latest()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Gmail latest processing failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Unable to process Gmail messages right now."
        ) from exc

    drafts = [serialize_email_draft(document) for document in summary.drafts or []]
    return GmailProcessLatestResponse(
        processed=summary.processed,
        created=summary.created,
        duplicates=summary.duplicates,
        irrelevant=summary.irrelevant,
        failed=summary.failed,
        drafts=drafts,
    )


@gmail_router.get("/job-order-drafts", response_model=EmailJobOrderDraftListResponse)
def list_email_job_order_drafts(
    status_filter: str | None = Query(default=None),
) -> EmailJobOrderDraftListResponse:
    try:
        collection = get_email_intake_collection(settings)
        query = {"status": status_filter} if status_filter else {}
        documents = list(collection.find(query).sort("created_at", -1))
    except Exception as exc:
        logger.exception("Failed to query email job order drafts: %s", exc)
        raise _service_unavailable(
            "Unable to load email job order drafts right now."
        ) from exc

    return EmailJobOrderDraftListResponse(
        drafts=[serialize_email_draft(document) for document in documents],
        total_drafts=len(documents),
    )


@gmail_router.get(
    "/job-order-drafts/{draft_id}", response_model=EmailJobOrderDraftRecord
)
def get_email_job_order_draft(draft_id: str) -> EmailJobOrderDraftRecord:
    try:
        collection = get_email_intake_collection(settings)
        document = collection.find_one(_email_draft_lookup_filter(draft_id))
    except Exception as exc:
        logger.exception("Failed to load email job order draft %s: %s", draft_id, exc)
        raise _service_unavailable(
            "Unable to load this email job order draft right now."
        ) from exc

    if document is None:
        raise HTTPException(
            status_code=404, detail=f"Email job order draft not found: {draft_id}"
        )
    return serialize_email_draft(document)


@gmail_router.post(
    "/job-order-drafts/{draft_id}/save", response_model=EmailDraftSaveResponse
)
def save_email_job_order_draft(
    draft_id: str,
    payload: EmailDraftSaveRequest,
) -> EmailDraftSaveResponse:
    try:
        draft_collection = get_email_intake_collection(settings)
        job_collection = get_job_order_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during email draft save: %s", exc
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    draft = draft_collection.find_one(_email_draft_lookup_filter(draft_id))
    if draft is None:
        raise HTTPException(
            status_code=404, detail=f"Email job order draft not found: {draft_id}"
        )
    if draft.get("status") == "saved":
        raise HTTPException(
            status_code=400, detail="This email job order draft has already been saved."
        )
    if draft.get("status") in {"irrelevant", "failed"}:
        raise HTTPException(
            status_code=400, detail="Only reviewable job order drafts can be saved."
        )

    now = datetime.now(timezone.utc)
    job_order_id = _generate_job_order_id(now)
    extracted_payload = payload.extracted_fields.model_dump(mode="json")
    source_attachment_hashes = draft.get("attachment_hashes") or []
    document = {
        "_id": job_order_id,
        "job_order_id": job_order_id,
        **extracted_payload,
        **normalized_title_company_fields(payload.extracted_fields),
        "source_file_name": draft.get("source_file_name") or "email_body.txt",
        "source_file_type": draft.get("source_file_type") or ".txt",
        "raw_text": draft.get("raw_text") or "",
        "preview_text": draft.get("preview_text") or "",
        "extraction_method": draft.get("extraction_method") or "",
        "is_scanned_document": bool(draft.get("is_scanned_document")),
        "source_channel": "email",
        "source_gmail_message_id": draft.get("gmail_message_id") or "",
        "source_gmail_thread_id": draft.get("gmail_thread_id") or "",
        "source_email_subject": draft.get("subject") or "",
        "source_email_sender": draft.get("sender") or "",
        "source_attachment_hashes": source_attachment_hashes,
        "email_draft_id": str(draft.get("_id")),
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = job_collection.insert_one(document)
        draft_collection.update_one(
            {"_id": draft["_id"]},
            {
                "$set": {
                    "status": "saved",
                    "saved_job_order_id": job_order_id,
                    "extracted_fields": extracted_payload,
                    "updated_at": now,
                }
            },
        )
    except Exception as exc:
        logger.exception("MongoDB insert failed during email draft save: %s", exc)
        raise _service_unavailable(
            "Unable to save the email job order draft right now."
        ) from exc

    return EmailDraftSaveResponse(
        id=str(result.inserted_id),
        job_order_id=job_order_id,
        draft_id=str(draft.get("_id")),
    )


@gmail_router.post(
    "/job-order-drafts/{draft_id}/dismiss", response_model=EmailJobOrderDraftRecord
)
def dismiss_email_job_order_draft(draft_id: str) -> EmailJobOrderDraftRecord:
    try:
        collection = get_email_intake_collection(settings)
        now = datetime.now(timezone.utc)
        result = collection.update_one(
            _email_draft_lookup_filter(draft_id),
            {"$set": {"status": "ignored", "updated_at": now}},
        )
        if result.matched_count == 0:
            raise HTTPException(
                status_code=404, detail=f"Email job order draft not found: {draft_id}"
            )
        document = collection.find_one(_email_draft_lookup_filter(draft_id))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to dismiss email job order draft %s: %s", draft_id, exc
        )
        raise _service_unavailable(
            "Unable to dismiss this email job order draft right now."
        ) from exc

    if document is None:
        raise HTTPException(
            status_code=404, detail=f"Email job order draft not found: {draft_id}"
        )
    return serialize_email_draft(document)


@candidates_router.post("/extract", response_model=ExtractedCandidateResponse)
async def extract_candidate(file: UploadFile = File(...)) -> ExtractedCandidateResponse:
    file_bytes = await _read_upload_file(file, empty_message="Uploaded file is empty.")
    parsed_document = _parse_uploaded_document(
        file_name=file.filename or "candidate_document",
        file_bytes=file_bytes,
        upload_label="candidate document",
    )

    extracted_fields, extraction_method = ai_service.extract_candidate_fields(
        raw_text=parsed_document.raw_text,
        rendered_images=parsed_document.rendered_images,
        file_type=parsed_document.file_type,
    )

    raw_text = parsed_document.raw_text
    preview_text = parsed_document.preview_text
    if parsed_document.is_scanned_document and not raw_text:
        raw_text = ai_service.transcribe_images(
            parsed_document.rendered_images,
            parsed_document.file_type,
        )
        preview_text = _trim_preview_text(raw_text)

    return ExtractedCandidateResponse(
        file_name=parsed_document.file_name,
        file_type=parsed_document.file_type,
        raw_text=raw_text,
        preview_text=preview_text,
        extraction_method=extraction_method,
        is_scanned_document=parsed_document.is_scanned_document,
        extracted_fields=extracted_fields,
        warnings=(
            [
                "Live AI was unavailable or returned invalid output; review the heuristic extraction carefully."
            ]
            if extraction_method == "heuristic_fallback"
            else []
        ),
    )


@candidates_router.post("/submit", response_model=CandidateSubmissionResponse)
def submit_candidate(payload: CandidateSubmission) -> CandidateSubmissionResponse:
    try:
        collection = get_candidate_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during candidate submission: %s", exc
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    profile_context = build_profile_context(payload.extracted_fields)
    profile_embedding = ai_service.create_embedding(profile_context)
    now = datetime.now(timezone.utc)
    candidate_id = _generate_candidate_id(now)
    activity_profile = build_random_activity_profile(collection)
    extracted_payload = payload.extracted_fields.model_dump(mode="json")

    document = {
        **extracted_payload,
        **activity_profile,
        "candidate_id": candidate_id,
        "source_file_name": payload.source_file_name,
        "source_file_type": payload.source_file_type,
        "raw_text": payload.raw_text,
        "preview_text": payload.preview_text,
        "extraction_method": payload.extraction_method,
        "is_scanned_document": payload.is_scanned_document,
        "profile_context": profile_context,
        "profile_embedding": profile_embedding,
        **ai_service.embedding_metadata(profile_context, profile_embedding),
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = collection.insert_one(document)
    except Exception as exc:
        logger.exception("MongoDB insert failed during candidate submission: %s", exc)
        raise _service_unavailable(
            "Unable to save the candidate right now. Please try again."
        ) from exc

    return CandidateSubmissionResponse(
        id=str(result.inserted_id),
        candidate_id=candidate_id,
        profile_context=profile_context,
        embedding_created=profile_embedding is not None,
    )


@candidates_router.get("/stats", response_model=CandidateStatsResponse)
def get_candidate_stats() -> CandidateStatsResponse:
    try:
        collection = get_candidate_collection(settings)
        documents = list(collection.find({}, {"location": 1}))
    except Exception as exc:
        logger.exception("Failed to load candidate stats from MongoDB: %s", exc)
        raise _service_unavailable("Unable to load candidate stats right now.") from exc

    return CandidateStatsResponse(
        total_candidates=len(documents),
        location_hierarchy=build_location_hierarchy(
            [document.get("location") for document in documents]
        ),
    )


@candidates_router.get("", response_model=CandidateListResponse)
def list_candidates() -> CandidateListResponse:
    try:
        collection = get_candidate_collection(settings)
        documents = list(collection.find().sort("created_at", -1))
    except Exception as exc:
        logger.exception("Failed to query candidates: %s", exc)
        raise _service_unavailable("Unable to load candidates right now.") from exc

    return CandidateListResponse(
        candidates=[_serialize_candidate(document) for document in documents],
        total_candidates=len(documents),
    )


@candidates_router.put("/{candidate_id}", response_model=CandidateRecord)
def update_candidate(
    candidate_id: str, payload: CandidateSubmission
) -> CandidateRecord:
    try:
        collection = get_candidate_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during candidate update: %s", exc
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    profile_context = build_profile_context(payload.extracted_fields)
    profile_embedding = ai_service.create_embedding(profile_context)
    now = datetime.now(timezone.utc)
    extracted_payload = payload.extracted_fields.model_dump(mode="json")
    update_fields = {
        **extracted_payload,
        "source_file_name": payload.source_file_name,
        "source_file_type": payload.source_file_type,
        "raw_text": payload.raw_text,
        "preview_text": payload.preview_text,
        "extraction_method": payload.extraction_method,
        "is_scanned_document": payload.is_scanned_document,
        "profile_context": profile_context,
        "profile_embedding": profile_embedding,
        **ai_service.embedding_metadata(profile_context, profile_embedding),
        "updated_at": now,
    }

    try:
        result = collection.update_one(
            _candidate_lookup_filter(candidate_id),
            {"$set": update_fields},
        )
    except Exception as exc:
        logger.exception(
            "MongoDB update failed during candidate update for %s: %s",
            candidate_id,
            exc,
        )
        raise _service_unavailable(
            "Unable to update the candidate right now. Please try again."
        ) from exc

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Candidate not found: {candidate_id}"
        )

    document = collection.find_one(_candidate_lookup_filter(candidate_id))
    if document is None:
        raise HTTPException(
            status_code=404, detail=f"Candidate not found: {candidate_id}"
        )
    return _serialize_candidate(document)


@job_orders_router.post("/extract", response_model=ExtractedJobOrderResponse)
async def extract_job_order(
    file: UploadFile | None = File(default=None),
    job_order: str | None = Form(default=None),
) -> ExtractedJobOrderResponse:
    parsed_document = await _parse_job_order_input(
        file=file,
        job_order=job_order,
    )

    extracted_fields, extraction_method = ai_service.extract_job_order_fields(
        raw_text=parsed_document.raw_text,
        rendered_images=parsed_document.rendered_images,
        file_type=parsed_document.file_type,
    )

    return ExtractedJobOrderResponse(
        file_name=parsed_document.file_name,
        file_type=parsed_document.file_type,
        raw_text=parsed_document.raw_text,
        preview_text=parsed_document.preview_text,
        extraction_method=extraction_method,
        is_scanned_document=parsed_document.is_scanned_document,
        extracted_fields=extracted_fields,
        warnings=(
            [
                "Live AI was unavailable or returned invalid output; review the heuristic extraction carefully."
            ]
            if extraction_method == "heuristic_fallback"
            else []
        ),
    )


@job_orders_router.post("/submit", response_model=JobOrderSubmissionResponse)
def submit_job_order(payload: JobOrderSubmission) -> JobOrderSubmissionResponse:
    try:
        collection = get_job_order_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during job order submission: %s", exc
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    now = datetime.now(timezone.utc)
    job_order_id = _generate_job_order_id(now)
    extracted_payload = payload.extracted_fields.model_dump(mode="json")
    document = {
        "_id": job_order_id,
        "job_order_id": job_order_id,
        **extracted_payload,
        **normalized_title_company_fields(payload.extracted_fields),
        "source_file_name": payload.source_file_name,
        "source_file_type": payload.source_file_type,
        "raw_text": payload.raw_text,
        "preview_text": payload.preview_text,
        "extraction_method": payload.extraction_method,
        "is_scanned_document": payload.is_scanned_document,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = collection.insert_one(document)
    except Exception as exc:
        logger.exception("MongoDB insert failed during job order submission: %s", exc)
        raise _service_unavailable(
            "Unable to save the job order right now. Please try again."
        ) from exc

    return JobOrderSubmissionResponse(
        id=str(result.inserted_id), job_order_id=job_order_id
    )


@job_orders_router.get("/stats", response_model=JobOrderStatsResponse)
def get_job_order_stats() -> JobOrderStatsResponse:
    try:
        collection = get_job_order_collection(settings)
        documents = list(collection.find({}, {"location": 1, "domain": 1}))
    except Exception as exc:
        logger.exception("Failed to load job order stats from MongoDB: %s", exc)
        raise _service_unavailable("Unable to load job order stats right now.") from exc

    domains = sorted(
        {
            str(document.get("domain") or "").strip()
            for document in documents
            if str(document.get("domain") or "").strip()
        }
    )
    return JobOrderStatsResponse(
        total_jobs=len(documents),
        location_hierarchy=build_location_hierarchy(
            [document.get("location") for document in documents]
        ),
        domains=domains,
    )


@job_orders_router.get("", response_model=JobOrderListResponse)
def list_job_orders(
    country_filter: str | None = Query(default=None),
    state_filter: str | None = Query(default=None),
    city_filter: str | None = Query(default=None),
    domain_filter: str | None = Query(default=None),
) -> JobOrderListResponse:
    try:
        collection = get_job_order_collection(settings)
        documents = [
            document
            for document in collection.find().sort("created_at", -1)
            if location_matches_filter(
                document.get("location"),
                country=country_filter,
                state=state_filter,
                city=city_filter,
            )
            and (
                not domain_filter
                or str(document.get("domain") or "").casefold()
                == domain_filter.strip().casefold()
            )
        ]
    except Exception as exc:
        logger.exception("Failed to query job orders: %s", exc)
        raise _service_unavailable("Unable to load job orders right now.") from exc

    return JobOrderListResponse(
        jobs=[_serialize_job_order(document) for document in documents],
        total_jobs=len(documents),
    )


@job_orders_router.put("/{job_order_id}", response_model=JobOrderRecord)
def update_job_order(job_order_id: str, payload: JobOrderSubmission) -> JobOrderRecord:
    try:
        collection = get_job_order_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during job order update: %s", exc
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    now = datetime.now(timezone.utc)
    extracted_payload = payload.extracted_fields.model_dump(mode="json")
    update_fields = {
        **extracted_payload,
        **normalized_title_company_fields(payload.extracted_fields),
        "source_file_name": payload.source_file_name,
        "source_file_type": payload.source_file_type,
        "raw_text": payload.raw_text,
        "preview_text": payload.preview_text,
        "extraction_method": payload.extraction_method,
        "is_scanned_document": payload.is_scanned_document,
        "updated_at": now,
    }

    try:
        result = collection.update_one(
            {"job_order_id": job_order_id},
            {"$set": update_fields},
        )
    except Exception as exc:
        logger.exception(
            "MongoDB update failed during job order update for %s: %s",
            job_order_id,
            exc,
        )
        raise _service_unavailable(
            "Unable to update the job order right now. Please try again."
        ) from exc

    if result.matched_count == 0:
        raise HTTPException(
            status_code=404, detail=f"Job order not found: {job_order_id}"
        )

    document = collection.find_one({"job_order_id": job_order_id})
    if document is None:
        raise HTTPException(
            status_code=404, detail=f"Job order not found: {job_order_id}"
        )
    return _serialize_job_order(document)


@jobs_router.post("/match", response_model=MatchResponse)
async def match_job_profiles(
    file: UploadFile | None = File(default=None),
    job_order: str | None = Form(default=None),
    limit: int = Form(default=3),
    country_filter: str | None = Form(default=None),
    state_filter: str | None = Form(default=None),
    city_filter: str | None = Form(default=None),
) -> MatchResponse:
    job_text = await _resolve_job_text(file=file, job_order=job_order)

    try:
        collection = get_candidate_collection(settings)
        filtered_documents = [
            document
            for document in collection.find()
            if location_matches_filter(
                document.get("location"),
                country=country_filter,
                state=state_filter,
                city=city_filter,
            )
        ]
    except Exception as exc:
        logger.exception("Failed to query candidates for matching: %s", exc)
        raise _service_unavailable(
            "Unable to load candidates for matching right now."
        ) from exc

    available_candidates = len(filtered_documents)
    if available_candidates == 0:
        if country_filter or state_filter or city_filter:
            selected_filters = ", ".join(
                filter(
                    None,
                    [
                        f"country={country_filter}" if country_filter else "",
                        f"state={state_filter}" if state_filter else "",
                        f"city={city_filter}" if city_filter else "",
                    ],
                )
            )
            raise HTTPException(
                status_code=400,
                detail=f"No candidates are available for the selected location filter: {selected_filters}.",
            )
        raise HTTPException(
            status_code=400, detail="No candidates are available to match yet."
        )
    if limit < 1:
        raise HTTPException(
            status_code=400, detail="Candidate count must be at least 1."
        )
    limit = min(limit, available_candidates)

    job_embedding = ai_service.create_embedding(job_text)
    try:
        candidates = rank_profiles_for_job(
            collection=collection,
            documents=filtered_documents,
            job_order=job_text,
            job_embedding=job_embedding,
            settings=settings,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Profile ranking failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Unable to rank profiles for this job order right now.",
        ) from exc

    active_semantic = any("vector" in item.source for item in candidates)
    return MatchResponse(
        matching_mode="hybrid" if active_semantic else "keyword",
        warnings=[]
        if active_semantic or settings.ai_mode == "demo"
        else [
            "Semantic retrieval unavailable or no compatible indexed candidates; using keyword evidence. Run the reindex command after enabling Gemini."
        ],
        job_order=job_text,
        requested_limit=limit,
        available_candidates=available_candidates,
        candidates=candidates,
    )


@jobs_router.post("/salary", response_model=JobSalaryResponse)
async def extract_job_salary(
    file: UploadFile | None = File(default=None),
    job_order: str | None = Form(default=None),
) -> JobSalaryResponse:
    job_text = await _resolve_job_text(file=file, job_order=job_order)
    salary_range = ai_service.extract_salary(job_text)
    return JobSalaryResponse(salary_range=salary_range)


@activity_router.get(
    "/percentile/{candidate_id}", response_model=ActivityPercentileResponse
)
def classify_activity_by_percentile(candidate_id: str) -> ActivityPercentileResponse:
    try:
        collection = get_candidate_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during percentile activity classification: %s",
            exc,
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    try:
        result = classify_candidate_activity_by_percentile(collection, candidate_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Percentile activity classification failed for %s: %s", candidate_id, exc
        )
        raise HTTPException(
            status_code=500, detail="Unable to classify candidate activity right now."
        ) from exc

    return ActivityPercentileResponse(**result)


@activity_router.get(
    "/weighted/{candidate_id}", response_model=ActivityWeightedResponse
)
def classify_activity_by_weighted_clustering(
    candidate_id: str,
) -> ActivityWeightedResponse:
    try:
        collection = get_candidate_collection(settings)
    except Exception as exc:
        logger.exception(
            "MongoDB collection unavailable during weighted activity classification: %s",
            exc,
        )
        raise _service_unavailable(
            "Database service is unavailable. Please try again."
        ) from exc

    try:
        result = classify_candidate_activity_weighted(collection, candidate_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "Weighted activity classification failed for %s: %s", candidate_id, exc
        )
        raise HTTPException(
            status_code=500, detail="Unable to classify candidate activity right now."
        ) from exc

    return ActivityWeightedResponse(**result)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(oauth_callback_router)
app.include_router(gmail_router)
app.include_router(candidates_router)
app.include_router(job_orders_router)
app.include_router(jobs_router)
app.include_router(activity_router)
