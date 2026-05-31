from __future__ import annotations

from paperless_review_companion.review import normalize_review, rules_review


def test_rules_review_detects_invoice_action() -> None:
    document = {
        "id": 10,
        "title": "invoice.pdf",
        "content_excerpt": "Invoice amount due by 2026-02-01.",
    }

    review = rules_review(document)

    assert review["primary_category"] == "finance_tax"
    assert review["action_needed"] is True
    assert review["keep_in_paperless"] is True


def test_normalize_protects_identity_from_keep_false() -> None:
    document = {"id": 11, "title": "passport.pdf"}
    review = normalize_review(
        {
            "primary_category": "identity",
            "sensitivity": "highly_sensitive",
            "document_type": "passport",
            "summary": "Passport scan.",
            "suggested_tags": ["id"],
            "action_needed": False,
            "keep_in_paperless": False,
            "confidence": 0.95,
            "rationale": "Title says passport.",
        },
        document,
    )

    assert review["keep_in_paperless"] is True

