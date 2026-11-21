from __future__ import annotations

import json

from paperless_review_companion import cli


def test_remote_ollama_is_blocked_before_private_input_is_read(tmp_path, capsys) -> None:
    missing_input = tmp_path / "private-export.jsonl"
    output = tmp_path / "review.jsonl"

    status = cli.main(
        [
            "review",
            "--input",
            str(missing_input),
            "--output",
            str(output),
            "--ollama-url",
            "https://models.example.test/api/generate",
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "Refusing a non-loopback Ollama endpoint" in captured.err
    assert not output.exists()


def test_rules_only_mode_never_requires_remote_model_consent(tmp_path) -> None:
    input_path = tmp_path / "documents.jsonl"
    output = tmp_path / "review.jsonl"
    input_path.write_text(json.dumps({"id": 1, "title": "invoice.pdf"}) + "\n", encoding="utf-8")

    status = cli.main(
        [
            "review",
            "--input",
            str(input_path),
            "--output",
            str(output),
            "--rules-only",
            "--ollama-url",
            "https://models.example.test/api/generate",
        ]
    )

    assert status == 0
    assert output.exists()


def test_remote_ollama_override_is_explicitly_forwarded(tmp_path, monkeypatch) -> None:
    input_path = tmp_path / "documents.jsonl"
    output = tmp_path / "review.jsonl"
    input_path.write_text(json.dumps({"id": 2, "title": "letter.pdf"}) + "\n", encoding="utf-8")

    def fake_review_document(document, **kwargs):
        assert document["id"] == 2
        assert kwargs["allow_remote_ollama"] is True
        return {"status": "reviewed", "document": document, "review": {}}

    monkeypatch.setattr(cli, "review_document", fake_review_document)

    status = cli.main(
        [
            "review",
            "--input",
            str(input_path),
            "--output",
            str(output),
            "--ollama-url",
            "https://models.example.test/api/generate",
            "--allow-remote-ollama",
        ]
    )

    assert status == 0
    assert output.exists()


def test_apply_writeback_rejects_mixed_object_and_non_object_rows_before_client(
    tmp_path, monkeypatch, capsys
) -> None:
    plan = tmp_path / "writeback-plan.jsonl"
    plan.write_text('{"document_id": 1}\n"not-an-object"\n', encoding="utf-8")
    client_constructed = False

    def fail_if_constructed(*args, **kwargs):
        nonlocal client_constructed
        client_constructed = True
        raise AssertionError("Paperless client must not be constructed for a malformed plan")

    monkeypatch.setattr(cli, "PaperlessClient", fail_if_constructed)

    status = cli.main(
        [
            "apply-writeback",
            str(plan),
            "--paperless-url",
            "http://127.0.0.1:8000",
            "--paperless-token",
            "test-token",
        ]
    )

    captured = capsys.readouterr()
    assert status == 1
    assert "Expected a JSON object" in captured.err
    assert client_constructed is False
