from __future__ import annotations

from paperless_review_companion.manifest import latest_by_document


def test_latest_by_document_keeps_last_row() -> None:
    rows = [
        {"document": {"id": 2}, "review": {"summary": "old"}},
        {"document": {"id": 1}, "review": {"summary": "only"}},
        {"document": {"id": 2}, "review": {"summary": "new"}},
    ]

    latest = latest_by_document(rows)

    assert [row["document"]["id"] for row in latest] == [1, 2]
    assert latest[1]["review"]["summary"] == "new"

