from __future__ import annotations

from paperless_review_companion.renderers import render_focus, render_full_report, render_triage


ROWS = [
    {
        "status": "reviewed",
        "document": {"id": 1, "title": "invoice.pdf"},
        "review": {
            "primary_category": "finance_tax",
            "sensitivity": "sensitive",
            "document_type": "invoice",
            "confidence": 0.9,
            "action_needed": True,
            "action_reason": "Due date.",
            "keep_in_paperless": True,
            "summary": "Invoice with due date.",
            "suggested_tags": ["invoice"],
        },
    }
]


def test_reports_render_key_sections() -> None:
    assert "Paperless Review Report" in render_full_report("demo.jsonl", ROWS)
    assert "Tier 1" in render_triage("demo.jsonl", ROWS)
    assert "Focus Queue" in render_focus("demo.jsonl", ROWS)

