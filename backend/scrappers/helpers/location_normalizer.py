import re
import unicodedata
import json
from pathlib import Path


_BASE_CITY_ALIASES: dict[str, set[str]] = {
    "bucharest": {"bucharest", "bucuresti", "bucurești"},
    "cluj-napoca": {"cluj", "cluj napoca", "cluj-napoca"},
    "timisoara": {"timisoara", "timișoara"},
    "iasi": {"iasi", "iași"},
    "constanta": {"constanta", "constanța"},
    "craiova": {"craiova"},
    "brasov": {"brasov", "brașov"},
    "remote": {"remote", "work from home", "home", "de acasa", "de acasă"},
}

_BASE_CITY_DISPLAY: dict[str, str] = {
    "bucharest": "Bucharest",
    "cluj-napoca": "Cluj-Napoca",
    "timisoara": "Timisoara",
    "iasi": "Iasi",
    "constanta": "Constanta",
    "craiova": "Craiova",
    "brasov": "Brasov",
    "remote": "Remote",
}

_BASE_CITY_RO_DISPLAY: dict[str, str] = {
    "bucharest": "București",
    "cluj-napoca": "Cluj-Napoca",
    "timisoara": "Timișoara",
    "iasi": "Iași",
    "constanta": "Constanța",
    "craiova": "Craiova",
    "brasov": "Brașov",
    "remote": "Remote",
}


def _strip_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_text(value: str) -> str:
    value = _strip_diacritics(value.lower())
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _ascii_city_display(value: str) -> str:
    compact = re.sub(r"\s+", " ", _strip_diacritics(value)).strip()
    if not compact:
        return ""
    return compact


def _load_romanian_cities() -> list[str]:
    data_path = Path(__file__).resolve().parents[1] / "romanian_cities.json"
    if not data_path.exists():
        return []

    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    cities = payload.get("cities", [])
    if not isinstance(cities, list):
        return []

    return [str(city).strip() for city in cities if str(city).strip()]


def _build_location_indexes() -> tuple[dict[str, set[str]], dict[str, str], dict[str, str], dict[str, str]]:
    canonical_to_aliases: dict[str, set[str]] = {
        key: {normalize_text(alias) for alias in aliases}
        for key, aliases in _BASE_CITY_ALIASES.items()
    }
    city_display = dict(_BASE_CITY_DISPLAY)
    city_ro_display = dict(_BASE_CITY_RO_DISPLAY)

    alias_to_canonical: dict[str, str] = {}
    for canonical_key, aliases in canonical_to_aliases.items():
        for alias in aliases:
            alias_to_canonical[alias] = canonical_key

    for city in _load_romanian_cities():
        normalized_city = normalize_text(city)
        if not normalized_city:
            continue

        canonical_key = alias_to_canonical.get(normalized_city, normalized_city)
        canonical_to_aliases.setdefault(canonical_key, set()).add(normalized_city)

        if canonical_key not in city_ro_display:
            city_ro_display[canonical_key] = city

        if canonical_key not in city_display:
            city_display[canonical_key] = _ascii_city_display(city)

        raw_aliases = {
            city,
            _strip_diacritics(city),
            city.replace("-", " "),
            _strip_diacritics(city).replace("-", " "),
        }

        for raw_alias in raw_aliases:
            normalized_alias = normalize_text(raw_alias)
            if not normalized_alias:
                continue
            canonical_to_aliases.setdefault(canonical_key, set()).add(normalized_alias)
            alias_to_canonical.setdefault(normalized_alias, canonical_key)

    return canonical_to_aliases, alias_to_canonical, city_display, city_ro_display


CITY_ALIASES, _ALIAS_TO_CANONICAL, CITY_DISPLAY, CITY_RO_DISPLAY = _build_location_indexes()


def canonical_city_key(location: str) -> str:
    normalized = normalize_text(location)
    return _ALIAS_TO_CANONICAL.get(normalized, normalized)


def english_city(location: str) -> str:
    canonical = canonical_city_key(location)
    if canonical in CITY_DISPLAY:
        return CITY_DISPLAY[canonical]
    return location.strip()


def romanian_city(location: str) -> str:
    canonical = canonical_city_key(location)
    if canonical in CITY_RO_DISPLAY:
        return CITY_RO_DISPLAY[canonical]
    return location.strip()


def alias_candidates(location: str) -> set[str]:
    canonical = canonical_city_key(location)
    if canonical in CITY_ALIASES:
        return {normalize_text(alias) for alias in CITY_ALIASES[canonical]}
    return {normalize_text(location)}


def is_known_city(location: str) -> bool:
    return canonical_city_key(location) in CITY_DISPLAY


def translate_location_to_english(location_value: str) -> str:
    parts = [part.strip() for part in location_value.split(",") if part.strip()]
    if not parts:
        return ""

    city = english_city(parts[0])

    if len(parts) == 1:
        return city

    translated_tail: list[str] = []
    for part in parts[1:]:
        normalized_part = normalize_text(part)
        if normalized_part == "romania":
            translated_tail.append("Romania")
        else:
            translated_tail.append(part)

    return ", ".join([city, *translated_tail])


def translate_location_with_city_scan(location_value: str) -> str:
    parts = [part.strip() for part in location_value.split(",") if part.strip()]
    if not parts:
        return ""

    selected_city = ""
    for part in parts:
        if is_known_city(part):
            selected_city = english_city(part)
            break

    if not selected_city:
        selected_city = english_city(parts[0])

    has_romania = any(normalize_text(part) == "romania" for part in parts)
    if has_romania and selected_city and normalize_text(selected_city) != "remote":
        return f"{selected_city}, Romania"

    return selected_city
