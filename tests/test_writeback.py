from __future__ import annotations

import pytest

from paperless_review_companion.writeback import apply_tag_plan, plan_rows, validate_plan_for_apply


def good_review_row() -> dict:
    return {
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
    planned = plan_rows([good_review_row()])

    assert planned[0]["safe_to_apply"] is True
    assert not validate_plan_for_apply(planned)


@pytest.mark.parametrize("field", ["dry_run", "safe_to_apply", "keep_in_paperless", "no_delete"])
@pytest.mark.parametrize("value", [1, "true"])
def test_writeback_validation_requires_literal_safety_booleans(field: str, value: object) -> None:
    row = plan_rows([good_review_row()])[0]
    row[field] = value

    failures = validate_plan_for_apply([row])

    assert any(field in failure and "literal true" in failure for failure in failures)


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("document_id", True, "positive integer"),
        ("document_id", "8", "positive integer"),
        ("review_status", "error", "not reviewed"),
        ("issues", ["low_confidence"], "unresolved safety issues"),
        ("confidence", True, "number from 0.75 to 1"),
        ("confidence", 0.74, "number from 0.75 to 1"),
        ("document_type", "unknown", "not safe to apply"),
        ("document_type", "Unknown", "not safe to apply"),
        ("document_type", " unknown ", "not safe to apply"),
        ("document_type", "   ", "not safe to apply"),
        ("document_type", ["invoice"], "not safe to apply"),
        ("tags_to_add", "ai_review:reviewed", "non-empty list"),
        ("tags_to_add", ["ai_review:reviewed", 7], "invalid tag"),
    ],
)
def test_writeback_validation_rechecks_plan_schema(field: str, value: object, expected: str) -> None:
    row = plan_rows([good_review_row()])[0]
    row[field] = value

    assert any(expected in failure for failure in validate_plan_for_apply([row]))


class NoNetworkClient:
    def list_tags(self) -> dict[str, int]:
        raise AssertionError("an invalid plan must be blocked before Paperless is contacted")


def test_tampered_plan_is_blocked_before_network_access() -> None:
    row = plan_rows([good_review_row()])[0]
    row["safe_to_apply"] = "true"

    result = apply_tag_plan(NoNetworkClient(), [row], apply=False, yes=False)

    assert result["blocked"] is True
    assert result["apply"] is False


def test_non_object_plan_entry_is_blocked_before_network_access() -> None:
    result = apply_tag_plan(NoNetworkClient(), ["not-an-object"], apply=False, yes=False)

    assert result["blocked"] is True
    assert result["failures"] == ["row 1: plan entry must be an object"]
    assert result["apply"] is False


@pytest.mark.parametrize(
    "tampered_tags",
    [
        [
            "ai_review:reviewed",
            "ai_review:no_delete",
            "ai_review:category:finance_tax",
            "ai_review:type:unknown",
            "ai_review:sensitivity:sensitive",
            "ai_review:action_needed",
        ],
        ["ai_review:reviewed"],
    ],
)
def test_writeback_validation_rejects_tags_that_do_not_match_review_fields(
    tampered_tags: list[str],
) -> None:
    row = plan_rows([good_review_row()])[0]
    row["tags_to_add"] = tampered_tags

    failures = validate_plan_for_apply([row])

    assert any("does not match the reviewed safety fields" in failure for failure in failures)
