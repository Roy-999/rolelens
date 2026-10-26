from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


_EMPTY_TEXT_MARKERS = {"", "unknown", "n/a", "na", "none", "null"}


def calculate_candidate_completion(document: Mapping[str, Any]) -> int:
    checks = [
        _has_text(document.get("name")),
        _has_text(document.get("email_id")),
        _has_text(document.get("phone_no")),
        _has_location(document.get("location")),
        _has_value(document.get("years_of_experience")),
        _has_age(document.get("age")),
        _has_list_content(document.get("education")),
        _has_list_content(document.get("experience")),
        _has_list_content(document.get("skills")),
        _has_list_content(document.get("tools")),
        _has_list_content(document.get("certifications")),
        _has_list_content(document.get("licenses")),
        _has_list_content(document.get("languages")),
    ]
    return _percentage(checks)


def calculate_job_order_completion(document: Mapping[str, Any]) -> int:
    checks = [
        _has_text(document.get("job_title")),
        _has_text(document.get("domain")),
        _has_text(document.get("organization_name")),
        _has_location(document.get("location")),
        _has_text(document.get("work_arrangement")),
        _has_text(document.get("employment_type")),
        _has_value(document.get("hours_per_week"))
        or _has_text(document.get("hours_of_operation")),
        _has_value(document.get("duration_weeks"))
        or _has_text(document.get("start_date"))
        or _has_text(document.get("end_date")),
        _has_value(document.get("years_required")),
        _has_known_boolean(document.get("will_sponsor"))
        or _has_known_boolean(document.get("will_relocate"))
        or _has_known_boolean(document.get("travel_required")),
        _has_compensation(document.get("compensation")),
        _has_text(document.get("summary")),
        _has_list_content(document.get("responsibilities")),
        _has_list_content(document.get("qualifications")),
        _has_list_content(document.get("skills")),
        _has_list_content(document.get("certifications")),
        _has_list_content(document.get("benefits")),
        _has_list_content(document.get("additional_details")),
        _has_compliance(document.get("compliance")),
        _has_list_content(document.get("physical_requirements")),
    ]
    return _percentage(checks)


def _percentage(checks: list[bool]) -> int:
    if not checks:
        return 0
    return round((sum(1 for check in checks if check) / len(checks)) * 100)


def _has_text(value: Any) -> bool:
    if value is None:
        return False
    normalized = str(value).strip()
    return normalized.casefold() not in _EMPTY_TEXT_MARKERS


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _has_known_boolean(value: Any) -> bool:
    return isinstance(value, bool)


def _has_location(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return any(_has_text(item) for item in value.values())


def _has_age(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return (
        _has_text(value.get("group"))
        or _has_text(value.get("source"))
        or _has_value(value.get("confidence"))
    )


def _has_list_content(value: Any) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return False
    for item in value:
        if isinstance(item, Mapping):
            if any(_has_text(entry) or _has_value(entry) for entry in item.values()):
                return True
        elif _has_text(item):
            return True
    return False


def _has_compensation(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    per_diem = value.get("per_diem")
    return any(
        [
            _has_value(value.get("pay_rate_min")),
            _has_value(value.get("pay_rate_max")),
            _has_text(value.get("pay_frequency")),
            _has_text(value.get("pay_text")),
            _has_text(value.get("overtime")),
            isinstance(per_diem, Mapping)
            and any(
                [
                    _has_value(per_diem.get("amount_per_day")),
                    _has_text(per_diem.get("frequency")),
                    _has_text(per_diem.get("conditions")),
                ]
            ),
        ]
    )


def _has_compliance(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    work_authorization = value.get("work_authorization")
    return any(
        [
            _has_known_boolean(value.get("drug_test")),
            _has_known_boolean(value.get("background_check")),
            _has_text(work_authorization)
            and str(work_authorization).strip().casefold() != "unknown",
        ]
    )
