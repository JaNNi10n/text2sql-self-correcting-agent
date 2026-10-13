# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added
- `eval/error_sources.py` (`results/error_sources.json`): exact-match checks for identifiers copied
  from few-shot examples (A2) and identifiers repeated after retries (A3).
- `eval/compare_runs.py` and `results/rerun/`: a full independent rerun of A0 and A3 on the
  200-question slice (61.0% and 59.0% EX against 60.5% and 60.5% in the saved runs).

### Fixed
- README: claims about few-shot copying, clean first-attempt failures (28, not 24), tables per
  database and full-dev runtime corrected to match the saved results.

## [1.0.0] - 2026-10-13

### Added
- `t2s` package: SQLite schema introspection with sample values, bge-small schema linking
  (top-4 tables + FK neighbours), few-shot retrieval from Spider train (same-db excluded),
  Ollama `/api/chat` client, sqlglot safety guard with a sandboxed read-only executor, and the
  generate -> guard -> execute -> feedback agent loop (up to 2 retries).
- CLI (`python -m t2s ask | eval | serve`) and a FastAPI service (`POST /query`, `GET /health`)
  with a db allowlist (404), guard rejections (400) and Ollama-down handling (503).
- Evaluation harness: fixed 200-question Spider-dev slice stratified by hardness (seed 42),
  execution-accuracy judge, four-arm ablation (A0-A3), Wilson CIs, McNemar tests, red-team run,
  cross-check against the official test-suite evaluator and rule-based failure categories.
- Reproducibility check (`eval/repro.py`) that re-runs slice items and compares with saved results.
- pytest suite with a mocked LLM, GitHub Actions (ruff + pytest), pinned requirements.
