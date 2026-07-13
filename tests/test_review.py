from __future__ import annotations

import json
import urllib.request

import pytest

from paperless_review_companion.review import (
    is_loopback_ollama_url,
    normalize_review,
    ollama_review,
    review_document,
    rules_review,
    validate_ollama_endpoint,
)


class FakeOllamaResponse:
    def __init__(self, review: dict) -> None:
        self.body = json.dumps({"response": json.dumps(review)}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def read(self) -> bytes:
        return self.body


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


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434/api/generate",
        "http://localhost.:11434/api/generate",
        "http://127.0.0.1:11434/api/generate",
        "http://127.25.1.9:11434/api/generate",
        "http://[::1]:11434/api/generate",
    ],
)
def test_loopback_ollama_urls_are_private_by_default(url: str) -> None:
    assert is_loopback_ollama_url(url)
    validate_ollama_endpoint(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://models.example.test/api/generate",
        "http://192.168.1.20:11434/api/generate",
        "http://127.0.0.1.models.example.test/api/generate",
        "http://127.0.0.1@models.example.test/api/generate",
    ],
)
def test_remote_ollama_requires_explicit_opt_in(url: str) -> None:
    with pytest.raises(ValueError, match="Refusing a non-loopback Ollama endpoint"):
        validate_ollama_endpoint(url)

    validate_ollama_endpoint(url, allow_remote=True)


def test_review_document_enforces_remote_guard_before_model_request() -> None:
    with pytest.raises(ValueError, match="Refusing a non-loopback Ollama endpoint"):
        review_document(
            {"id": 12, "title": "private.pdf", "content_excerpt": "Private text."},
            rules_only=False,
            ollama_url="https://models.example.test/api/generate",
        )


@pytest.mark.parametrize("url", ["file:///tmp/ollama.sock", "http://[::1"])
def test_invalid_model_url_is_rejected_even_with_remote_opt_in(url: str) -> None:
    with pytest.raises(ValueError, match=r"must be an http\(s\) URL"):
        validate_ollama_endpoint(url, allow_remote=True)


def test_loopback_ollama_bypasses_environment_proxy(monkeypatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.test:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:8080")
    monkeypatch.setenv("http_proxy", "http://proxy.example.test:8080")
    monkeypatch.setenv("https_proxy", "http://proxy.example.test:8080")
    proxy_bodies: list[bytes | None] = []
    direct_bodies: list[bytes | None] = []

    def proxy_aware_urlopen(request, *, timeout):
        proxy_bodies.append(request.data)
        return FakeOllamaResponse({"document_id": 13})

    class DirectOpener:
        def open(self, request, *, timeout):
            direct_bodies.append(request.data)
            return FakeOllamaResponse({"document_id": 13})

    def build_direct_opener(*handlers):
        assert len(handlers) == 1
        assert isinstance(handlers[0], urllib.request.ProxyHandler)
        assert handlers[0].proxies == {}
        return DirectOpener()

    monkeypatch.setattr(urllib.request, "urlopen", proxy_aware_urlopen)
    monkeypatch.setattr(urllib.request, "build_opener", build_direct_opener)

    result = ollama_review(
        {"id": 13, "title": "private.pdf", "content_excerpt": "PRIVATE_PROXY_SENTINEL"},
        model="test-model",
        ollama_url="http://127.0.0.1:11434/api/generate",
        timeout=1,
    )

    assert result["document_id"] == 13
    assert proxy_bodies == []
    assert len(direct_bodies) == 1
    assert b"PRIVATE_PROXY_SENTINEL" in direct_bodies[0]


def test_remote_ollama_opt_in_keeps_proxy_aware_network_path(monkeypatch) -> None:
    proxy_bodies: list[bytes | None] = []

    def proxy_aware_urlopen(request, *, timeout):
        proxy_bodies.append(request.data)
        return FakeOllamaResponse({"document_id": 14})

    def unexpected_direct_opener(*handlers):
        raise AssertionError("remote opt-in should use urllib's normal proxy-aware path")

    monkeypatch.setattr(urllib.request, "urlopen", proxy_aware_urlopen)
    monkeypatch.setattr(urllib.request, "build_opener", unexpected_direct_opener)

    result = ollama_review(
        {"id": 14, "title": "remote.pdf", "content_excerpt": "REMOTE_OPT_IN_SENTINEL"},
        model="test-model",
        ollama_url="https://models.example.test/api/generate",
        timeout=1,
        allow_remote=True,
    )

    assert result["document_id"] == 14
    assert len(proxy_bodies) == 1
    assert b"REMOTE_OPT_IN_SENTINEL" in proxy_bodies[0]
