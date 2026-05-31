from __future__ import annotations

from paperless_review_companion.writeback import plan_rows, validate_plan_for_apply


def test_writeback_plan_blocks_low_confidence() -> None:
    rows = [
        {
            "status": "reviewed",
            "document": {"id": 7, "title": "unknown.pdf"},
            "review": {
                "primary_category": "other",
                "sensitivity": "internal",
                "document_type": "unknown",
                "confidence": 0.4,
                "action_needed": False,
                "keep_in_paperless": True,
                "summary": "Weak result.",
            },
        }
    ]

    planned = plan_rows(rows)

    assert planned[0]["safe_to_apply"] is False
    assert "low_confidence" in planned[0]["issues"]
    assert validate_plan_for_apply(planned)


def test_writeback_plan_allows_good_row() -> None:
    rows = [
        {
            "status": "reviewed",
            "document": {"id": 8, "title": "invoice.pdf"},
            "review": {
                "primary_category": "finance_tax",
                "sensitivity": "sensitive",
                "document_type": "invoice",
                "confidence": 0.91,
                "action_needed": True,
                "keep_in_paperless": True,
                "summary": "Invoice.",
            },
        }
    ]

    planned = plan_rows(rows)

    assert planned[0]["safe_to_apply"] is True
    assert not validate_plan_for_apply(planned)

