from __future__ import annotations

import math
import re
from typing import Any


from ..services.location_utils import normalize_location_value
from ..schemas import (
    CandidateExtraction,
    EducationEntry,
    ExperienceEntry,
    JobOrderExtraction,
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "with",
}

JOB_EMAIL_CLASSIFICATIONS = {
    "job_order",
    "candidate_resume",
    "sales_email",
    "internal_thread",
    "irrelevant",
}


def _find_explicit_salary_range(raw_text: str) -> str | None:
    text = raw_text or ""
    currency_pattern = r"(?:inr|rs\.?|₹|usd|\$|eur|€|gbp|£)"
    patterns = [
        rf"(?i){currency_pattern}\s?\d[\d,\.]*\s?(?:k|lakh|lakhs|lpa|cr|crore|hour|hr|month|mo|year|yr|annum|pa)?\s?(?:-|to)\s?{currency_pattern}?\s?\d[\d,\.]*\s?(?:k|lakh|lakhs|lpa|cr|crore|hour|hr|month|mo|year|yr|annum|pa)?",
        r"(?i)\bctc\b[^\n\r]{0,50}\d[\d,\.]*\s?(?:lpa|lakh|lakhs|cr|crore)",
        rf"(?i)\bsalary\b[^\n\r]{{0,50}}{currency_pattern}?\s?\d[\d,\.]*",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip(" .")
    return None


def _bounded_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except Exception:
        return 0.5
    return max(0.0, min(1.0, numeric))


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def keyword_overlap_score(
    job_order: str, profile_context: str
) -> tuple[float, list[str]]:
    job_tokens = _tokenize(job_order)
    profile_tokens = set(_tokenize(profile_context))
    if not job_tokens:
        return 0.0, []

    matched = sorted(token for token in set(job_tokens) if token in profile_tokens)
    score = len(matched) / len(set(job_tokens))
    return score, matched


def heuristic_extract_resume(raw_text: str) -> CandidateExtraction:
    text = raw_text.strip()
    if not text:
        return CandidateExtraction()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    email = _first_match(r"[\w\.-]+@[\w\.-]+\.\w+", text)
    phone = _normalize_phone(
        _first_match(r"(\+?1[\s\-\.]?)?(\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})", text)
    )
    years = _extract_years_of_experience(text)
    name = ""

    for line in lines[:5]:
        if email and email.lower() in line.lower():
            continue
        if any(char.isdigit() for char in line):
            continue
        if len(line.split()) in {2, 3, 4}:
            name = line
            break

    sections = _split_sections(text)
    skills = _split_skill_like_values(sections.get("skills", ""))
    tools = _split_skill_like_values(sections.get("tools", "")) or _extract_known_tools(
        text
    )
    certifications = _split_skill_like_values(sections.get("certifications", ""))
    licenses = _split_skill_like_values(sections.get("licenses", ""))
    languages = _split_skill_like_values(sections.get("languages", ""))
    location_text = _find_labeled_value(
        text, [r"location", r"address", r"current\s+location"]
    )
    location = normalize_location_value(location_text or "")

    education_entries = [
        EducationEntry(degree=entry)
        for entry in _split_section_lines(sections.get("education", ""), max_lines=8)
    ]
    experience_entries = [
        ExperienceEntry(summary=entry)
        for entry in _split_section_lines(sections.get("experience", ""), max_lines=12)
    ]

    return CandidateExtraction(
        name=name,
        email_id=email or "",
        phone_no=phone or "",
        location=location,
        years_of_experience=years,
        education=education_entries,
        experience=experience_entries,
        skills=skills,
        tools=tools,
        certifications=certifications,
        licenses=licenses,
        languages=languages,
    )


def heuristic_extract_job_order(raw_text: str) -> JobOrderExtraction:
    text = raw_text.strip()
    if not text:
        return JobOrderExtraction()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = _find_labeled_value(
        text,
        [
            r"job\s*title",
            r"position",
            r"role",
        ],
    )

    if not title and lines:
        title = lines[0] if len(lines[0]) <= 100 else None

    organization = _find_labeled_value(
        text,
        [
            r"company",
            r"organization",
            r"employer",
            r"client",
        ],
    )
    location_text = _find_labeled_value(
        text, [r"location", r"job\s*site", r"work\s*site"]
    )
    location = normalize_location_value(location_text or "")
    pay_details = _extract_pay_details(text)
    per_diem = _extract_per_diem(text)
    responsibilities = _extract_job_section_items(
        text,
        [
            "what you'll do",
            "what you\u2019ll do",
            "key responsibilities",
            "responsibilities",
        ],
    )
    qualifications = _extract_job_section_items(
        text,
        [
            "what you'll bring",
            "what you\u2019ll bring",
            "qualifications",
            "required qualifications",
            "desired qualifications",
            "requirements",
        ],
    )
    benefits = _extract_job_section_items(text, ["benefits", "why join us"])
    additional_details = _extract_job_section_items(
        text,
        [
            "location & schedule",
            "location & work environment",
            "schedule",
            "work environment",
        ],
    )
    skills = _dedupe_strings(
        _extract_job_skills(text, preferred=False)
        + _extract_job_skills(text, preferred=True)
        + _extract_known_tools(text)
    )

    return JobOrderExtraction(
        job_title=title,
        domain=_infer_job_domain(text),
        organization_name=organization,
        number_of_openings=_extract_number_of_openings(text),
        location={
            "address_line_1": location.address_line_1 or None,
            "address_line_2": location.address_line_2 or None,
            "city": location.city or None,
            "state": location.state or None,
            "country": location.Country or None,
            "zip_code": location.zip_code or None,
        },
        work_arrangement=_normalize_work_arrangement(text),
        employment_type=_normalize_employment_type(text),
        hours_per_week=_extract_hours_per_week(text),
        hours_of_operation=_find_labeled_value(
            text, [r"hours", r"schedule", r"hours\s+of\s+operation"]
        ),
        duration_weeks=_extract_duration_weeks(text),
        start_date=_find_labeled_value(text, [r"start\s*date", r"start"]),
        end_date=_find_labeled_value(text, [r"end\s*date", r"date\s*end", r"end"]),
        years_required=_extract_experience_years(text),
        will_sponsor=_extract_will_sponsor(text),
        will_relocate=_extract_boolean_requirement(
            text, [r"\brelocation\b", r"\brelocate\b"]
        ),
        travel_required=_extract_boolean_requirement(
            text, [r"\btravel\b", r"\b\d{1,3}%\s+travel"]
        ),
        compensation={
            **pay_details,
            "overtime": _extract_overtime(text),
            "per_diem": per_diem,
        },
        summary=_extract_job_summary(lines),
        responsibilities=responsibilities,
        qualifications=qualifications,
        skills=skills,
        certifications=_extract_certifications(text),
        benefits=benefits,
        additional_details=additional_details,
        compliance={
            "drug_test": _extract_boolean_requirement(
                text, [r"\bdrug\s+test", r"\bdrug\s+screen"]
            ),
            "background_check": _extract_boolean_requirement(
                text, [r"\bbackground\s+check", r"\bbackground\s+screen"]
            ),
            "work_authorization": _find_work_authorization(text) or "Unknown",
        },
        physical_requirements=_extract_physical_requirements(text),
    )


def heuristic_classify_job_order_email(
    *,
    subject: str,
    cleaned_body: str,
    attachment_text: str,
    attachment_names: list[str],
) -> tuple[str, float, str]:
    text = "\n".join(
        [subject or "", cleaned_body or "", attachment_text or ""]
    ).casefold()
    attachment_blob = " ".join(attachment_names).casefold()
    job_score = 0
    resume_score = 0
    sales_score = 0

    for pattern in [
        r"\bjob\s*(description|order|opening|requisition|req|posting)\b",
        r"\bposition\b",
        r"\brole\b",
        r"\bresponsibilities\b",
        r"\bqualifications\b",
        r"\brequirements\b",
        r"\byears?\s+(?:of\s+)?experience\b",
        r"\bstart\s+date\b",
        r"\basap\b",
        r"\bhiring\b",
    ]:
        if re.search(pattern, text):
            job_score += 1
    if re.search(r"\b(jd|job|description|req)\b", attachment_blob):
        job_score += 2

    for pattern in [r"\bresume\b", r"\bcv\b", r"\bcandidate\b", r"\bwork history\b"]:
        if re.search(pattern, text) or re.search(pattern, attachment_blob):
            resume_score += 1

    for pattern in [
        r"\bbook a demo\b",
        r"\bschedule a call\b",
        r"\bmarketing\b",
        r"\bpricing\b",
    ]:
        if re.search(pattern, text):
            sales_score += 1

    if job_score >= max(2, resume_score + 1, sales_score + 1):
        return (
            "job_order",
            min(0.95, 0.45 + job_score * 0.1),
            "Job order terms found in email or attachment.",
        )
    if resume_score >= 2 and resume_score > job_score:
        return (
            "candidate_resume",
            0.75,
            "Resume/candidate terms are stronger than job-order terms.",
        )
    if sales_score >= 2:
        return "sales_email", 0.7, "Sales/demo language found."
    if "from:" in text and "sent:" in text and job_score == 0:
        return (
            "internal_thread",
            0.6,
            "Thread metadata found without a clear job order.",
        )
    return "irrelevant", 0.5, "No strong job order signal found."


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-z0-9+#/\. ]+", " ", text.lower())
    return [
        token
        for token in cleaned.split()
        if token and token not in STOP_WORDS and len(token) > 1
    ]


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(0).strip()


def _normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone


def _extract_years_of_experience(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\+?\s+years? of experience", text, flags=re.IGNORECASE
    )
    if match:
        return float(match.group(1))
    return None


def _extract_experience_years(text: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\+?\s+years?\s+(?:of\s+)?(?:relevant\s+)?experience",
        r"minimum\s+of\s+(\d+(?:\.\d+)?)\+?\s+years?",
        r"(\d+(?:\.\d+)?)\+?\s+yrs?\s+(?:of\s+)?experience",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _extract_number_of_openings(text: str) -> int:
    patterns = [
        r"(?im)^\s*(?:number\s+of\s+openings|openings|vacancies|positions|headcount|roles|slots)\s*[:\-]\s*(\d+)\b",
        r"(?i)\b(\d+)\s*\+?\s+(?:openings|vacancies|positions|roles|slots)\b",
        r"(?i)\b(?:hiring|hire|need|needs|seeking|recruiting|looking\s+for)\s+(\d+)\s+(?:[a-z][\w/-]*\s+){0,4}(?:candidates|workers|welders|machinists|electricians|technicians|operators|people|hires|employees|contractors|positions|openings)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return max(1, int(match.group(1)))
    return 1


def _find_labeled_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        pattern = rf"(?im)^\s*{label}\s*[:\-]\s*(.+?)\s*$"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" .")
    return None


def _extract_pay_details(text: str) -> dict[str, Any]:
    pay_text = _find_labeled_value(text, [r"pay", r"compensation", r"salary", r"rate"])
    if not pay_text:
        explicit_salary = _find_explicit_salary_range(text)
        pay_text = explicit_salary

    result = {
        "pay_rate_min": None,
        "pay_rate_max": None,
        "pay_frequency": None,
        "pay_text": pay_text,
    }
    if not pay_text:
        return result

    amounts = [
        float(value.replace(",", ""))
        for value in re.findall(r"\$?\s*(\d[\d,]*(?:\.\d+)?)", pay_text)
    ]
    if amounts:
        if re.search(r"(?i)\b(up\s+to|maximum|max)\b", pay_text) and len(amounts) == 1:
            result["pay_rate_max"] = amounts[0]
        elif len(amounts) == 1:
            result["pay_rate_min"] = amounts[0]
            result["pay_rate_max"] = amounts[0]
        else:
            result["pay_rate_min"] = min(amounts[:2])
            result["pay_rate_max"] = max(amounts[:2])

    result["pay_frequency"] = _normalize_pay_frequency(pay_text)
    return result


def _normalize_pay_frequency(value: Any) -> str | None:
    lowered = str(value or "").strip().casefold()
    if not lowered:
        return None
    if any(token in lowered for token in ["/hr", " per hr", "hour", "hourly"]):
        return "hourly"
    if any(
        token in lowered
        for token in ["annual", "annually", "year", "yearly", "/yr", " per yr"]
    ):
        return "annual"
    if any(token in lowered for token in ["week", "weekly", "/wk"]):
        return "weekly"
    if any(token in lowered for token in ["day", "daily"]):
        return "daily"
    return None


def _extract_per_diem(text: str) -> dict[str, Any]:
    match = re.search(
        r"(?i)(?:per\s*diem|stipend|allowance)[^\n\r$]{0,40}\$?\s*(\d+(?:\.\d+)?)\s*(?:/|per\s*)?(day|daily|week|weekly)?|"
        r"\$?\s*(\d+(?:\.\d+)?)\s*(?:/|per\s*)?(day|daily|week|weekly)\s+(?:per\s*diem|stipend|allowance)",
        text,
    )
    if not match:
        return {"amount_per_day": None, "frequency": None, "conditions": None}

    amount_text = match.group(1) or match.group(3)
    frequency = (match.group(2) or match.group(4) or "").lower()
    raw_phrase = re.sub(r"\s+", " ", match.group(0)).strip(" .")
    amount = float(amount_text)

    if frequency in {"week", "weekly"}:
        daily = amount / 7
        if daily.is_integer():
            daily = int(daily)
        return {"amount_per_day": daily, "frequency": "daily", "conditions": raw_phrase}
    if frequency in {"day", "daily"}:
        return {
            "amount_per_day": amount,
            "frequency": "daily",
            "conditions": raw_phrase,
        }
    return {"amount_per_day": None, "frequency": None, "conditions": raw_phrase}


def _extract_overtime(text: str) -> str | None:
    match = re.search(r"(?i)\bovertime\b[^\n\r.]{0,120}", text)
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip(" .")
    return None


def _extract_hours_per_week(text: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\+?\s*(?:hours|hrs)\s*(?:/|per\s*)?(?:week|wk|weekly)",
        r"(\d+(?:\.\d+)?)\+?\s*(?:hours|hrs)\s+on\s+a\s+regular\s+weekly\s+basis",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))

    shift_match = re.search(
        r"(\d+)\s+(?:ten|10)[-\s]*hour\s+shifts",
        text,
        flags=re.IGNORECASE,
    )
    if shift_match:
        return float(int(shift_match.group(1)) * 10)
    return None


def _extract_duration_weeks(text: str) -> float | None:
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:week|weeks|wk|wks)\b", 1.0),
        (r"(\d+(?:\.\d+)?)\s*(?:month|months)\b", 4.345),
    ]
    for pattern, multiplier in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match and re.search(
            r"(?i)\b(duration|contract|assignment|temporary|temp)\b",
            text[max(0, match.start() - 80) : match.start() + 80],
        ):
            return round(float(match.group(1)) * multiplier, 2)
    return None


def _normalize_work_arrangement(text: str) -> str | None:
    lowered = text.lower()
    if "hybrid" in lowered:
        return "hybrid"
    if "remote" in lowered:
        return "remote"
    if any(
        token in lowered
        for token in ["on-site", "onsite", "on site", "in-person", "in person"]
    ):
        return "on-site"
    return None


def _normalize_work_arrangement_value(value: Any) -> str | None:
    normalized = str(value or "").strip().casefold()
    if normalized in {"on-site", "onsite", "on site", "in-person", "in person"}:
        return "on-site"
    if normalized == "hybrid":
        return "hybrid"
    if normalized == "remote":
        return "remote"
    return None


def _extract_will_sponsor(text: str) -> bool | None:
    if re.search(
        r"(?i)\b(?:visa|work authorization|work permit|immigration).{0,80}sponsor", text
    ):
        return _extract_boolean_requirement(
            text, [r"\bvisa\s+sponsor", r"\bsponsorship\b", r"\bsponsor\b"]
        )
    if re.search(r"(?i)\b(?:will|can|able to)\s+sponsor\b", text):
        return True
    if re.search(r"(?i)\b(?:no|not|unable to|will not)\s+sponsor\b", text):
        return False
    return None


def _normalize_employment_type(text: str) -> str | None:
    lowered = text.lower()
    if any(token in lowered for token in ["full-time", "full time", "fulltime"]):
        return "full-time"
    if any(token in lowered for token in ["part-time", "part time", "parttime"]):
        return "part-time"
    if "contract" in lowered:
        return "contract"
    if any(
        token in lowered
        for token in ["temporary", "temp-to-hire", "temp to hire", "seasonal"]
    ):
        return "temporary"
    return None


def _normalize_employment_type_value(value: Any) -> str | None:
    if value is None:
        return None
    return _normalize_employment_type(str(value))


def _infer_job_domain(text: str) -> str:
    lowered = text.lower()
    if any(
        token in lowered
        for token in ["machinist", "cnc", "lathe", "mill operator", "milling"]
    ):
        return "Machinist"
    if any(
        token in lowered
        for token in ["welder", "welding", "mig", "tig", "stick welding", "aws"]
    ):
        return "Welder"
    if any(
        token in lowered
        for token in ["electrician", "electrical", "journeyman electrician", "plc"]
    ):
        return "Electrician"
    return "Other"


def _normalize_domain(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized == "machinist":
        return "Machinist"
    if normalized == "welder":
        return "Welder"
    if normalized == "electrician":
        return "Electrician"
    return "Other"


def _extract_job_skills(text: str, *, preferred: bool) -> list[str]:
    if preferred:
        section_pattern = r"(?ims)^\s*(preferred|nice\s+to\s+have|desired)\s+(?:skills|qualifications|requirements)?\s*:?\s*(.*?)(?=^\s*(required|requirements|responsibilities|certifications|physical|benefits|compensation)\b|\Z)"
    else:
        section_pattern = r"(?ims)^\s*(required|requirements|qualifications|skills)\s*:?\s*(.*?)(?=^\s*(preferred|nice\s+to\s+have|responsibilities|certifications|physical|benefits|compensation)\b|\Z)"
    match = re.search(section_pattern, text)
    if not match:
        return []
    return _split_skill_like_values(match.group(2))[:30]


def _extract_certifications(text: str) -> list[str]:
    known = [
        "OSHA",
        "OSHA 10",
        "OSHA 30",
        "CDL",
        "AWS",
        "AWS Certified Welder",
        "NCCER",
        "Forklift Certification",
        "Journeyman License",
    ]
    lowered = text.lower()
    found = [item for item in known if item.lower() in lowered]
    section = _find_section(
        text, ["certifications", "certification", "licenses", "credentials"]
    )
    return _dedupe_strings(found + _split_skill_like_values(section or ""))


def _extract_physical_requirements(text: str) -> list[str]:
    section = _find_section(text, ["physical requirements", "physical demands"])
    values = _split_section_lines(section or "", max_lines=8)
    lift_matches = [
        re.sub(r"\s+", " ", match.group(0)).strip(" .")
        for match in re.finditer(r"(?i)\b(?:lift|carry|push|pull)[^\n\r.]{0,60}", text)
    ]
    return _dedupe_strings(values + lift_matches)


def _find_section(text: str, headings: list[str]) -> str | None:
    escaped = "|".join(re.escape(heading) for heading in headings)
    pattern = rf"(?ims)^\s*(?:{escaped})\s*:?\s*(.*?)(?=^\s*[A-Z][A-Za-z /&-]{{2,40}}\s*:?\s*$|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


JOB_ORDER_SECTION_HEADINGS = [
    "what you'll do",
    "what you\u2019ll do",
    "key responsibilities",
    "responsibilities",
    "what you'll bring",
    "what you\u2019ll bring",
    "qualifications",
    "required qualifications",
    "desired qualifications",
    "requirements",
    "benefits",
    "why join us",
    "location & schedule",
    "location & work environment",
    "schedule",
    "work environment",
    "ready to take the next step",
]


def _extract_job_section_items(
    text: str, headings: list[str], *, max_lines: int = 24
) -> list[str]:
    escaped_headings = "|".join(re.escape(heading) for heading in headings)
    escaped_stops = "|".join(
        re.escape(heading) for heading in JOB_ORDER_SECTION_HEADINGS
    )
    pattern = rf"(?ims)^\s*(?:{escaped_headings})\b[^\n\r]*\s*$\s*(.*?)(?=^\s*(?:{escaped_stops})\b[^\n\r]*\s*$|\Z)"
    sections = [
        match.group(1).strip()
        for match in re.finditer(pattern, text)
        if match.group(1).strip()
    ]
    items: list[str] = []
    for section in sections:
        items.extend(_split_section_lines(section, max_lines=max_lines))
    return _dedupe_strings(items)


def _extract_job_summary(lines: list[str]) -> str | None:
    skipped_prefixes = (
        "job order",
        "title:",
        "job title:",
        "pay:",
        "hours:",
        "start date:",
    )
    for line in lines:
        lowered = line.casefold()
        if lowered.startswith(skipped_prefixes):
            continue
        if lowered in JOB_ORDER_SECTION_HEADINGS:
            continue
        if len(line.split()) >= 8:
            return line
    return None


def _find_work_authorization(text: str) -> str | None:
    match = re.search(
        r"(?i)(?:work authorization|authorized to work|work visa|sponsorship)[^\n\r.]{0,120}",
        text,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(0)).strip(" .")
    return None


def _clean_optional_string(value: Any) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _extract_boolean_requirement(text: str, patterns: list[str]) -> bool | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        prefix = text[max(0, match.start() - 24) : match.start()].lower()
        if re.search(r"\b(no|not|without|no\s+required)\b", prefix):
            return False
        return True
    return None


def _dedupe_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        deduped.append(cleaned)
        seen.add(key)
    return deduped


def _to_optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_positive_int(value: Any, *, default: int = 1) -> int:
    try:
        number_value = int(float(value))
    except (TypeError, ValueError):
        return default
    return number_value if number_value >= 1 else default


def _split_sections(text: str) -> dict[str, str]:
    # Anchor section detection at the start of lines to avoid matching ordinary
    # words inside body text (for example "software" inside an experience bullet).
    patterns = {
        "education": r"(?mi)^\s*(education)\b\s*:?",
        "experience": r"(?mi)^\s*(work experience|professional experience|experience)\b\s*:?",
        "skills": r"(?mi)^\s*(skills|technical skills|core competencies|competencies)\b\s*:?",
        "tools": r"(?mi)^\s*(tools|equipment|technologies|software|machinery)\b\s*:?",
        "certifications": r"(?mi)^\s*(certifications|certification|certificates|certificate)\b\s*:?",
        "licenses": r"(?mi)^\s*(licenses|license|licences|licence)\b\s*:?",
        "languages": r"(?mi)^\s*(languages|language proficiency|language skills)\b\s*:?",
    }
    locations: list[tuple[str, int]] = []

    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            locations.append((key, match.start()))

    locations.sort(key=lambda item: item[1])
    sections: dict[str, str] = {}
    for index, (key, start) in enumerate(locations):
        end = locations[index + 1][1] if index + 1 < len(locations) else len(text)
        sections[key] = text[start:end]
    return sections


def _split_section_lines(section_text: str, max_lines: int = 6) -> list[str]:
    lines = [
        line.strip(":- ").strip() for line in section_text.splitlines() if line.strip()
    ]
    if lines and len(lines[0].split()) <= 3:
        lines = lines[1:]
    return lines[:max_lines]


def _split_skill_like_values(section_text: str) -> list[str]:
    if not section_text:
        return []
    lines = [
        line.strip(":- ").strip() for line in section_text.splitlines() if line.strip()
    ]
    if lines and len(lines[0].split()) <= 3:
        lines = lines[1:]
    values = ",".join(lines)
    tokens = [
        item.strip() for item in re.split(r"[,\|\u2022;/]+", values) if item.strip()
    ]
    return list(dict.fromkeys(tokens))


def _extract_known_tools(text: str) -> list[str]:
    known_tools = [
        "MIG",
        "TIG",
        "Stick Welding",
        "Lathe",
        "CNC",
        "Blueprint Reading",
        "Calipers",
        "Micrometer",
        "Grinder",
        "Plasma Cutter",
    ]
    lowered = text.lower()
    return [tool for tool in known_tools if tool.lower() in lowered]
