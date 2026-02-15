# Repository Guidelines

## Project Structure & Module Organization
- `src/python/role_play/` contains backend domains: `chat/`, `server/`, `common/`, `evaluation/`, `voice/`, and `dev_agents/`.
- `src/python/run_server.py` is the local backend entrypoint.
- `src/ts/role_play/ui/` is the Vue 3 + TypeScript frontend (`components/`, `services/`, `types/`, `locales/`).
- `test/python/unit/` and `test/python/integration/` hold backend tests; shared fixtures live in `test/python/fixtures/`.
- `data/resources/` stores scenario/character/script JSON content; environment settings live in `config/{dev,beta,prod}.yaml`; project utilities are in `scripts/`.
- Keep backend models and frontend API types aligned (Pydantic models in Python should be reflected in `src/ts/role_play/ui/src/types/`).

## Build, Test, and Development Commands
- `make dev-setup`: create/recreate `venv`, install Python dependencies, validate resources, and sync resource data.
- `source venv/bin/activate && JWT_SECRET_KEY=dev-secret python src/python/run_server.py`: run backend locally.
- `cd src/ts/role_play/ui && npm install && npm run dev`: run frontend (Vite dev server).
- `make test`: full Python suite with coverage (`--cov-fail-under=25`).
- `make test-unit` / `make test-integration`: targeted backend suites.
- `make validate-resources` and `make update-resource-metadata`: validate and maintain resource JSON metadata.
- `make run-local-docker DATA_DIR=./data_local`: build and run local Docker setup.

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints on public interfaces, `snake_case` functions/modules, `PascalCase` classes.
- Backend handlers are stateless: avoid request state in instance/global variables; prefer dependency injection via FastAPI `Depends(...)`.
- Storage keys are extension-free and user-scoped (for example, `users/{user_id}/profile`, not `users/{user_id}.json`).
- Vue/TypeScript: `PascalCase` for component files (for example, `ChatWindow.vue`), `use*` prefix for composables, `*Api.ts` for API service modules.
- Run formatting/type checks before submitting backend changes: `black`, `isort`, and `mypy` (listed in `src/python/requirements-dev.txt`).

## Testing Guidelines
- Pytest settings are defined in `pytest.ini` (`test_*.py`, `Test*`, `test_*` discovery patterns).
- Place isolated behavior tests in `test/python/unit/`; place cross-module/storage/auth flows in `test/python/integration/`.
- Follow naming patterns used across the tree: `test_<module>.py` files and descriptive `test_<behavior>_<condition>_<expected>()` functions.
- Use markers (`unit`, `integration`, `auth`, `storage`, `slow`) to narrow local runs during development.
- For backend PRs, run affected tests at minimum; use `make test` before merge for broad regressions.

## Commit & Pull Request Guidelines
- Follow existing commit style: Conventional Commit-like subjects such as `fix(makefile): ...`, `feat(voice): ...`, or `fix: ...`.
- Keep commits focused; reference issue/PR IDs when applicable (for example, `(#53)`).
- PRs should include scope, behavior impact, and verification commands run; add screenshots for UI changes.
- Ensure relevant GitHub checks pass: Python Unit Tests on PRs, plus Make Dry Run when touching Makefile/build/deploy paths.
