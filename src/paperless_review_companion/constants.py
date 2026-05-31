from __future__ import annotations

CATEGORIES = {
    "legal",
    "finance_tax",
    "housing_travel",
    "health_personal",
    "identity",
    "learning_books",
    "work_product",
    "media",
    "personal_strategy",
    "other",
}

SENSITIVITIES = {"public", "internal", "sensitive", "highly_sensitive"}

PROTECTED_CATEGORIES = {
    "legal",
    "finance_tax",
    "health_personal",
    "identity",
    "personal_strategy",
}

REQUIRED_REVIEW_FIELDS = (
    "document_id",
    "source",
    "primary_category",
    "sensitivity",
    "document_type",
    "summary",
    "suggested_tags",
    "action_needed",
    "keep_in_paperless",
    "confidence",
    "rationale",
)

CONTROLLED_TAG_PREFIX = "ai_review"

