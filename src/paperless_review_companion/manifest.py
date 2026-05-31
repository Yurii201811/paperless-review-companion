from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Could not parse {path}:{line_number}: {exc}") from exc
            if isinstance(value, dict):
                rows.append(value)
    return rows


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def document_id(row: dict[str, Any]) -> int | None:
    if isinstance(row.get("document"), dict):
        value = row["document"].get("id")
    else:
        value = row.get("id") or row.get("document_id")
    return value if isinstance(value, int) else None


def latest_by_document(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[int, dict[str, Any]] = {}
    no_id: list[dict[str, Any]] = []
    for row in rows:
        doc_id = document_id(row)
        if doc_id is None:
            no_id.append(row)
        else:
            by_id[doc_id] = row
    return no_id + [by_id[key] for key in sorted(by_id)]


def review_of(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("review")
    return value if isinstance(value, dict) else {}


def document_of(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("document")
    if isinstance(value, dict):
        return value
    return row

