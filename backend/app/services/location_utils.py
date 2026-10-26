from __future__ import annotations

import re
from typing import Any

from ..schemas import LocationEntry


def normalize_location_value(value: Any) -> LocationEntry:
    if hasattr(value, "model_dump"):
        value = value.model_dump()

    if isinstance(value, dict):
        explicit_location = LocationEntry(
            address_line_1=str(value.get("address_line_1") or "").strip(),
            address_line_2=str(value.get("address_line_2") or "").strip(),
            city=str(value.get("city") or "").strip(),
            state=normalize_state_name(value.get("state")),
            Country=normalize_country_name(
                value.get("Country") or value.get("country")
            ),
            zip_code=normalize_zip_code(value.get("zip_code")),
        )

        if explicit_location.state and not explicit_location.Country:
            explicit_location.Country = "United States"

        return explicit_location

    if isinstance(value, str):
        if not value.strip() or value.strip().casefold() == "unavailable":
            return LocationEntry()
        return parse_location_string(value)

    return LocationEntry()


def parse_location_string(value: str) -> LocationEntry:
    # The parser is intentionally conservative: only street-like tokens become
    # address lines, while city/state/country/zip stay in their dedicated fields.
    cleaned = re.sub(r"\s+", " ", value).strip(" ,")
    if not cleaned:
        return LocationEntry()

    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    zip_code = ""
    country = ""
    state = ""
    city = ""
    address_parts: list[str] = []

    if parts:
        last_part_without_zip, zip_code = extract_zip_code(parts[-1])
        if last_part_without_zip != parts[-1]:
            parts[-1] = last_part_without_zip
        parts = [part for part in parts if part]

    if parts and is_country_value(parts[-1]):
        country = normalize_country_name(parts.pop())

    if parts:
        state_candidate, state_zip = split_state_and_zip(parts[-1])
        if state_zip and not zip_code:
            zip_code = state_zip
        if state_candidate and is_state_value(state_candidate):
            state = normalize_state_name(state_candidate)
            parts.pop()

    if len(parts) >= 2:
        city = parts.pop()
        address_parts = parts
    elif len(parts) == 1:
        candidate = parts[0]
        if state or country or zip_code:
            city = candidate
        elif looks_like_street_address(candidate):
            address_parts = [candidate]
        elif is_country_value(candidate):
            country = normalize_country_name(candidate)
        elif is_state_value(candidate):
            state = normalize_state_name(candidate)
        else:
            city = candidate

    if state and not country:
        country = "United States"

    return LocationEntry(
        address_line_1=address_parts[0] if address_parts else "",
        address_line_2=", ".join(address_parts[1:]) if len(address_parts) > 1 else "",
        city=city,
        state=state,
        Country=country,
        zip_code=zip_code,
    )


def extract_zip_code(value: str) -> tuple[str, str]:
    match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", value)
    if not match:
        return value.strip(), ""
    remaining = (value[: match.start()] + value[match.end() :]).strip(" ,")
    return remaining, match.group(1)


def split_state_and_zip(value: str) -> tuple[str, str]:
    without_zip, zip_code = extract_zip_code(value)
    return without_zip.strip(), zip_code


def looks_like_street_address(value: str) -> bool:
    return bool(re.search(r"\d", value)) or bool(
        re.search(
            r"\b(?:street|st|avenue|ave|road|rd|drive|dr|lane|ln|boulevard|blvd|suite|ste|apt|unit)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def is_country_value(value: Any) -> bool:
    if not value:
        return False
    normalized = str(value).strip().casefold()
    return normalized in {
        "us",
        "usa",
        "u.s.",
        "u.s.a.",
        "united states",
        "united states of america",
    }


def is_state_value(value: Any) -> bool:
    if not value:
        return False
    normalized = str(value).strip()
    return (
        normalized.upper() in US_STATE_ALIASES
        or normalized in US_STATE_ALIASES.values()
    )


def normalize_zip_code(value: Any) -> str:
    if not value:
        return ""
    match = re.search(r"\b(\d{5}(?:-\d{4})?)\b", str(value))
    return match.group(1) if match else str(value).strip()


def location_matches_filter(
    value: Any,
    *,
    country: str | None = None,
    state: str | None = None,
    city: str | None = None,
) -> bool:
    location = normalize_location_value(value)
    if country and location.Country.casefold() != country.strip().casefold():
        return False
    if state and location.state.casefold() != state.strip().casefold():
        return False
    if city and location.city.casefold() != city.strip().casefold():
        return False
    return True


def build_location_hierarchy(values: list[Any]) -> dict[str, dict[str, list[str]]]:
    hierarchy: dict[str, dict[str, set[str]]] = {}

    for value in values:
        location = normalize_location_value(value)
        if not location.Country:
            continue

        country_bucket = hierarchy.setdefault(location.Country, {})
        state_key = location.state or ""
        city_bucket = country_bucket.setdefault(state_key, set())
        if location.city:
            city_bucket.add(location.city)

    structured: dict[str, dict[str, list[str]]] = {}
    for country, states in sorted(hierarchy.items()):
        structured[country] = {}
        for state, cities in sorted(states.items()):
            structured[country][state] = sorted(cities)
    return structured


def normalize_country_name(country: Any) -> str:
    if not country:
        return ""

    normalized = str(country).strip()
    aliases = {
        "US": "United States",
        "U.S.": "United States",
        "USA": "United States",
        "U.S.A.": "United States",
        "UNITED STATES OF AMERICA": "United States",
    }
    return aliases.get(normalized.upper(), normalized)


US_STATE_ALIASES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
}


def normalize_state_name(state: Any) -> str:
    if not state:
        return ""

    normalized = str(state).strip()
    return US_STATE_ALIASES.get(normalized.upper(), normalized)
