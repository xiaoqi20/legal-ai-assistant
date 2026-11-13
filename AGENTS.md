# Repository Guidelines

## Project Structure & Module Organization

- `PRD.md` is the product requirements source of truth; update it when scope or technical decisions change.
- `ui-screens/` contains exported screen references and a searchable gallery (`index.html`).
- `pratice/` contains the interactive prototype: `index.html`, `css/style.css`, `js/app.js`, `js/data.js`, `assets/`, and `功能模块清单.xlsx`.
- `database-schema.sql` is the initial PostgreSQL 17 DDL; `compose.yaml` runs the local database, and `database/` contains usage and constraint verification.
- `backend/` is the phase-one FastAPI modular monolith: `app/api/` routes, `app/services/` explicit RAG/AI/document workflows, `app/worker.py` durable PostgreSQL task worker, `migrations/` Alembic baseline and increments, and `tests/` PostgreSQL integration tests. See `backend/README.md` for local setup and SSE contracts.
- `frontend/` is the production mini-program: uni-app Vue 3 + TypeScript + Pinia, WeChat-first. It is based on the official `dcloudio/uni-preset-vue#vite-ts` template at commit `f747e3b11c51b3bff6c05e2b54f9a3173a590044`. Pages are grouped under `src/pages/`: `splash` (启动引导页), `auth` (一键登录、手机号验证码登录、角色选择与信息完善), `index` (案件/助手双核首页), `case` (详情、证据清单、材料、材料详情、案情梳理、文档、证据清单梳理), `chat`, `history`, `profile`, and `agreement`. Shared UI lives in `src/components/` (`AppHeader`, `AppDrawer`, `ChatConversation`, `ComposerBar`, `ConfirmDialog`, `FileBadge`, `PageNav`, `SearchInput`, `WinRateDonut`), and module-private components live under `src/pages/<module>/components/` (`auth/components/` for `AgreementBar`, `AgreementModal`; `index/components/` for `CasesHome`, `AssistantHome`, `CaseCard`; `case/components/` for `FloatingReturn`, `FilePreviewModal`); mock/API data in `src/services/`; Pinia stores in `src/stores/`; platform adapters in `src/platform/wechat/`; domain contracts in `src/types/`. Build output under `frontend/dist/` is generated.

## Build, Test, and Development Commands

- Open `pratice/index.html` in a browser to review the interactive prototype; no build step is required.
- Open `ui-screens/index.html` to browse screen references.
- Start the local database with `docker compose --env-file .env.local up -d --wait`; see `database/README.md` for initial DDL and verification commands.
- Backend expects Python `3.12.14` and locked dependencies via `cd backend && uv sync --frozen`. Run `uv run ruff check .` and `uv run pytest -q` against an explicitly configured disposable `*_test` database before handoff. Start API with `uv run uvicorn app.main:app --no-access-log` and Worker with `uv run python -m app.worker`; migrate separately with Alembic.
- Frontend expects Node.js `22.22.1` and pnpm `11.18.0` (see `frontend/.nvmrc` and `packageManager`).
- `cd frontend && pnpm install` restores dependencies. `pnpm dev:h5` serves the H5 preview at `http://localhost:5173`; `pnpm dev:mp-weixin` writes the dev bundle to `frontend/dist/dev/mp-weixin` for WeChat DevTools.
- Run `pnpm type-check` and `pnpm build:mp-weixin` (output `frontend/dist/build/mp-weixin`) before handoff. There is still no automated UI test suite or linter.
- `frontend/.env` controls `VITE_USE_MOCK` and `VITE_API_BASE_URL`. Mock data is enabled by default; the FastAPI backend now exists in `backend/`, but most frontend flows still require real service integration. Do not describe Mock data as live data.
- `frontend/pnpm-workspace.yaml` sets `nodeLinker: hoisted`; uni-app forces `preserveSymlinks`, so pnpm's default isolated layout breaks H5 module resolution. Keep this setting when changing dependencies.
- H5 rpx is pinned to a 375 base through `rpxCalcMaxDeviceWidth` / `rpxCalcBaseDeviceWidth` in `frontend/src/pages.json`, so the 430px preview matches the fixed-px prototype. Mini-program rpx still scales with the device width; do not remove these values while the prototype is the visual source.

## Coding Style & Naming Conventions

- For the prototype, keep markup in `index.html`, styles in `css/`, behavior in `js/app.js`, and fixtures in `js/data.js`.
- For `frontend/`, use Vue SFCs with `<script setup lang="ts">` and SCSS, `rpx` for layout, and design tokens from `src/uni.scss`. Put platform-specific code in `src/platform/wechat/` instead of scattering `wx.*` calls through components.
- Use UTF-8, two-space indentation, descriptive names, and focused changes. User-facing copy should be Simplified Chinese.
- Follow the PRD and prototype. Mark mock data and simulated integrations clearly; do not describe them as live backend capabilities.

## Product References

- Drive feature work from `PRD.md`, the screens in `ui-screens/`, and `pratice/功能模块清单.xlsx` together. Use the PRD for requirements, the prototype for flows and visual behavior, and the inventory for module scope and traceability.
- If these references conflict or leave a behavior unclear, surface the discrepancy before making a product-level assumption.

## Testing Guidelines

- Manually check affected flows in a browser, including mobile layout, navigation, empty states, and dialogs.
- Verify assets load and check the console. No coverage requirement exists until a test runner is added.
- For frontend changes, run `pnpm type-check` and `pnpm build:mp-weixin`, and smoke-test the H5 flow at mobile width. WeChat-only behavior still needs validation in WeChat DevTools or on a real device before release.

## Commit & Pull Request Guidelines

- No Git history is available to infer a convention. Use concise Conventional Commit subjects, e.g. `feat(prototype): add evidence detail state` or `docs: clarify mini-program setup`.
- Pull requests should summarize the change, link relevant PRD sections, list validation, and include UI screenshots. Call out mock behavior and new dependencies.

## Security & Configuration

- Never commit secrets, personal case data, or real user documents. Use synthetic fixtures; store future credentials in local environment configuration.
- Confirm usage rights before replacing or redistributing prototype screenshots.
