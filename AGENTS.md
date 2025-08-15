# Repository Guidelines

## Project Structure & Module Organization
- Backend (Python): `src/python/role_play/*` (API, chat, voice, evaluation, common). Entry point: `src/python/run_server.py`.
- Frontend (Vue + TS): `src/ts/role_play/ui` (Vite app: `src`, `components`, `composables`, `services`).
- Tests: `test/python/{unit,integration}` with shared fixtures in `test/python/fixtures`.
- Config: environment YAMLs in `config/{dev,beta,prod}.yaml` (env vars can override). Data/resources in `data/`.
- Tooling: `Makefile` (build/test/deploy), `Dockerfile`, `pytest.ini`, `.env(.example)`.

## Build, Test, and Development Commands
- Backend setup: `python -m venv venv && source venv/bin/activate && pip install -r src/python/requirements-dev.txt`.
- Run API locally: `source venv/bin/activate && python src/python/run_server.py` (ensure `STORAGE_PATH` exists; defaults to `./data`).
- Frontend dev: `cd src/ts/role_play/ui && npm i && npm run dev` (Vite at http://localhost:5173).
- Test suite: `make test` (pytest with coverage) or `pytest -q` (see markers below).
- Docker (local): `make run-local-docker DATA_DIR=./data` (serves on http://localhost:8080).
- Build/Deploy: `make build-docker`, `make push-docker`, `make deploy ENV=dev` (requires GCP config; see `ENVIRONMENTS.md`).

## Coding Style & Naming Conventions
- Python: format with Black; imports via isort; prefer type hints. Naming: `snake_case` (functions/modules), `PascalCase` (classes), `UPPER_SNAKE` (constants).
- TypeScript/Vue: `PascalCase` for components (`*.vue`), `camelCase` for composables/services (e.g., `useChatData.ts`). Two-space indent.
- Keep modules under existing namespaces (do not create parallel roots).

## Testing Guidelines
- Framework: pytest. Coverage target: 25%+ (HTML at `test/python/htmlcov/index.html`).
- Discovery: files `test_*.py`; classes `Test*`; functions `test_*`.
- Markers: `unit`, `integration`, `e2e`, `slow`, `auth`, `storage`, `cloud`. Example: `pytest -m unit`.

## Commit & Pull Request Guidelines
- Style: Conventional Commits when possible (e.g., `feat: ...`, `fix(deps): ...`).
- Commits: small, descriptive, present tense; reference issues (e.g., `#42`).
- PRs: include summary, rationale, test plan, and screenshots for UI changes. Link issues and note any config/devops changes.
- CI: ensure `make test` passes locally before requesting review.

## Security & Configuration Tips
- Never commit secrets. Use `.env` for local dev; production secrets live in GCP Secret Manager.
- Adjust runtime via `config/*.yaml` and env vars (`PORT`, `STORAGE_PATH`, `CORS_ALLOWED_ORIGINS`, etc.). See `ENVIRONMENTS.md` and `STORAGE_CONFIG.md`.

## Agent-Specific Instructions (Claude/Gemini)
- Architecture: layered modules; handlers are stateless and created per request/connection. Register handlers via YAML in `config/*.yaml`.
- Dependency Injection: use FastAPI `Depends()`; cache singletons with `functools.lru_cache` (e.g., ContentLoader, ChatLogger). Avoid mutable state on handler instances.
- Storage & Locking: abstract through `StorageBackend` (file/GCS/S3). Use key paths without extensions (e.g., `users/{user_id}/profile`). Separate lock lease duration from acquisition timeout; wrap blocking I/O with `asyncio.to_thread`.
- Chat System: persist messages as JSONL under `users/{user_id}/chat_logs/{session_id}`; create a fresh ADK runner per message; drive prompts by user language. See `/GEMINI.md` and root `/CLAUDE.md` for ADK notes.
- Evaluation Reports: store at `users/{user_id}/eval_reports/{session_id}/{timestamp_uuid}` with metadata; expose GET latest/all and POST re-evaluate endpoints.
- Frontend Patterns: domain-based Vue structure, composables for async ops and confirmations, sync TS types with Pydantic models, inject JWT via `Authorization: Bearer <token>`; i18n supports `en` and `zh-TW`.
- Testing: prefer fast unit tests; mark `integration`, `e2e`, `slow`, `cloud` selectively. Use `make test-chat` for chat-only coverage.

For deeper guidance, refer to: `GEMINI.md` (model/runtime, storage/locking overview), `CLAUDE.md` (repo-wide workflows), `src/python/CLAUDE.md` (Python DI/stateless patterns), `src/ts/CLAUDE.md` (frontend patterns), and `test/CLAUDE.md` (test layout and conventions).
