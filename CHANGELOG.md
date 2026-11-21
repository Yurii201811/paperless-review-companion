# Changelog

All notable changes to this project are documented here.

## 0.2.0 - 2026-11-21

- Hardened write-back plan validation so malformed or manually altered safety
  fields, non-object JSONL rows, and mismatched controlled tags fail closed
  before Paperless is contacted.
- Enforced the local-model privacy boundary by blocking non-loopback Ollama
  endpoints unless `--allow-remote-ollama` is supplied for that run, and by
  bypassing environment/system proxies for loopback model requests.
- Added public repository polish: README quality signals, package project URLs,
  GitHub issue templates, and a pull request template.
- Expanded CI coverage to Python 3.11 and 3.12.

## 0.1.0 - 2026-05-31

- Initial public MVP for local-first Paperless-ngx document review, rules-only
  fixture classification, report rendering, and guarded tag write-back planning.
- Added fake sample data, privacy documentation, security policy, setup docs, and
  tests for the core CLI behavior.
