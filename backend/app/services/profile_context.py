from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..schemas import CandidateExtraction


def build_profile_context(profile: CandidateExtraction) -> str:
    return _build_context(
        education_entries=[
            entry.model_dump(mode="json") for entry in profile.education
        ],
        experience_entries=[
            entry.model_dump(mode="json") for entry in profile.experience
        ],
        skills=profile.skills,
        tools=profile.tools,
        certifications=profile.certifications,
        licenses=profile.licenses,
        languages=profile.languages,
    )


def build_profile_context_from_mapping(document: Mapping[str, Any]) -> str:
    return _build_context(
        education_entries=document.get("education"),
        experience_entries=document.get("experience"),
        skills=document.get("skills"),
        tools=document.get("tools"),
        certifications=document.get("certifications"),
        licenses=document.get("licenses"),
        languages=document.get("languages"),
    )


def _build_context(
    *,
    education_entries: Any,
    experience_entries: Any,
    skills: Any,
    tools: Any,
    certifications: Any,
    licenses: Any,
    languages: Any,
) -> str:
    education = " | ".join(
        filter(
            None,
            [
                " ".join(
                    part
                    for part in [
                        str(entry.get("degree", "")).strip(),
                        str(entry.get("institution", "")).strip(),
                        str(entry.get("graduation_year", "")).strip(),
                    ]
                    if part
                ).strip()
                for entry in _as_dict_entries(education_entries)
            ],
        )
    )
    experience = " | ".join(
        filter(
            None,
            [
                " ".join(
                    part
                    for part in [
                        str(entry.get("title", "")).strip(),
                        str(entry.get("company", "")).strip(),
                        str(entry.get("start_date", "")).strip(),
                        str(entry.get("end_date", "")).strip(),
                        str(entry.get("summary", "")).strip(),
                    ]
                    if part
                ).strip()
                for entry in _as_dict_entries(experience_entries)
            ],
        )
    )
    normalized_skills = ", ".join(
        str(item).strip() for item in (skills or []) if str(item).strip()
    )
    normalized_tools = ", ".join(
        str(item).strip() for item in (tools or []) if str(item).strip()
    )
    normalized_certifications = ", ".join(
        str(item).strip() for item in (certifications or []) if str(item).strip()
    )
    normalized_licenses = ", ".join(
        str(item).strip() for item in (licenses or []) if str(item).strip()
    )
    normalized_languages = ", ".join(
        str(item).strip() for item in (languages or []) if str(item).strip()
    )

    return "\n".join(
        filter(
            None,
            [
                f"Education: {education}" if education else "",
                f"Experience: {experience}" if experience else "",
                f"Skills: {normalized_skills}" if normalized_skills else "",
                f"Tools: {normalized_tools}" if normalized_tools else "",
                f"Certifications: {normalized_certifications}"
                if normalized_certifications
                else "",
                f"Licenses: {normalized_licenses}" if normalized_licenses else "",
                f"Languages: {normalized_languages}" if normalized_languages else "",
            ],
        )
    ).strip()


def _as_dict_entries(entries: Any) -> list[dict[str, Any]]:
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]
