# Security Policy

This project handles metadata and OCR excerpts from private Paperless-ngx
archives. Treat manifests and generated reports as private data.

## Reporting

Please report vulnerabilities privately through GitHub security advisories or by
contacting the repository owner through GitHub. Do not include real document
contents, API tokens, or private archive exports in public issues.

## Secret Handling

- Use environment variables for `PAPERLESS_URL` and `PAPERLESS_TOKEN`.
- Do not commit `.env`, manifests, reports, local exports, databases, or model
  caches.
- Rotate Paperless API tokens if they are accidentally exposed.

## Data Handling

The tool is designed for local-first use. Ollama requests are sent only to the
configured Ollama URL. If you point the tool at a remote model server, you are
responsible for that server's privacy and retention behavior.

Write-back is tag-only and guarded by explicit flags. The tool does not support
document deletion.

