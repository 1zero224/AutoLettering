from __future__ import annotations

from collections.abc import Iterable


def normalize_record_ids(record_ids: Iterable[str] | None) -> set[str] | None:
    if record_ids is None:
        return None
    normalized = {value.strip() for value in record_ids if value and value.strip()}
    return normalized or None


def row_matches_record_ids(row: dict, record_ids: set[str] | None) -> bool:
    if record_ids is None:
        return True
    return str(row.get("record_id", "")) in record_ids
