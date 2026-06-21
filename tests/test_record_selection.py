import json

from autolettering.record_selection import normalize_record_ids, row_matches_record_ids


def test_normalize_record_ids_strips_empty_values_and_preserves_ids():
    record_ids = normalize_record_ids([" page.png#2 ", "", "page.png#3"])

    assert record_ids == {"page.png#2", "page.png#3"}


def test_row_matches_record_ids_allows_everything_when_unset():
    row = {"record_id": "page.png#1"}

    assert row_matches_record_ids(row, None) is True


def test_row_matches_record_ids_filters_by_exact_record_id():
    row = {"record_id": "page.png#1"}

    assert row_matches_record_ids(row, {"page.png#2"}) is False
    assert row_matches_record_ids(row, {"page.png#1"}) is True


def test_record_selection_helpers_do_not_emit_secret_like_values():
    payload = json.dumps({"record_ids": sorted(normalize_record_ids(["page.png#2"]))})

    assert "api_key" not in payload.lower()
