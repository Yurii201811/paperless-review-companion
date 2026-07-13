# Privacy And Safety

This project assumes your Paperless archive is private.

## What May Contain Private Data

- exported document JSONL
- review manifests
- Markdown reports
- write-back plans
- terminal logs containing document titles or summaries

Prefer `PAPERLESS_TOKEN` over `--paperless-token`; command-line arguments may be
visible in process listings or captured in shell history.

Those paths are ignored by `.gitignore`, but you should still inspect commits
before publishing.

## Local Model Default

The default model path uses Ollama. Prompts are sent to `http://127.0.0.1:11434`
unless you override `--ollama-url`.

Non-loopback model endpoints are rejected before the tool reads an export or
fetches documents from Paperless. To use a remote Ollama-compatible endpoint,
you must add `--allow-remote-ollama` for that run. This explicit override means
document metadata and OCR excerpts leave your machine; review the endpoint's
transport security, logging, privacy, and retention policy first.

Loopback Ollama requests ignore `HTTP_PROXY`, `HTTPS_PROXY`, and system proxy
configuration so private prompt bodies cannot be forwarded through a proxy. An
explicitly allowed remote endpoint uses the normal proxy-aware network path;
treat that proxy as another recipient of the document data.

Rules-only mode does not contact Ollama, so the endpoint guard does not apply.

## Write-Back Rules

- Write-back is tag-only.
- Generated tags use the `ai_review:` prefix by default.
- The tool refuses low-confidence, unknown-type, or unsafe rows.
- The tool does not delete documents.
- The tool requires `--apply --yes` and `PAPERLESS_REVIEW_APPLY=YES` for live
  tag changes.

## Recommended Workflow

1. Start with `--limit 10`.
2. Review the generated manifest locally.
3. Render triage and focus reports.
4. Generate a write-back plan.
5. Read the plan before applying.
6. Back up Paperless before the first live write-back.
