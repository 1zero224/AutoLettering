from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path


CleanupRunInput = str | Path | Iterable[str | Path]


def normalize_cleanup_run_dirs(cleanup_run_dir: CleanupRunInput) -> list[Path]:
    if isinstance(cleanup_run_dir, (str, Path)):
        return [Path(cleanup_run_dir)]
    return [Path(value) for value in cleanup_run_dir]


def load_cleanup_rows_by_id(cleanup_run_dir: CleanupRunInput, status: str = "cleaned") -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for run_dir in normalize_cleanup_run_dirs(cleanup_run_dir):
        for payload in _load_jsonl(run_dir / "cleanup-results.jsonl", status):
            rows[payload["record_id"]] = payload
    return rows


def format_cleanup_run_dirs(cleanup_run_dir: CleanupRunInput) -> str:
    return ", ".join(f"`{path}`" for path in normalize_cleanup_run_dirs(cleanup_run_dir))


def _load_jsonl(path: Path, status: str) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            if payload.get("status") == status:
                rows.append(payload)
    return rows
