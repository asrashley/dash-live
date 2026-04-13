# Copilot Instructions for dash-live

## What This Repository Does
dash-live is a simulated MPEG DASH streaming service. It dynamically generates DASH manifests from templates, serves media segments, and provides a DASH stream validator. Its principal use is testing live DASH streams with non-live, rights-cleared material. It supports DRM (PlayReady, ClearKey, Marlin), multi-period streams, SCTE-35 events, and a large number of CGI configuration options.

## Languages, Frameworks, Runtimes
- **Python 3.12** (see `.python-version`): Flask web server (`dashlive/server/`), MPEG/MP4 parsing (`dashlive/mpeg/`), database models (SQLAlchemy + SQLite), Alembic migrations, DRM logic.
- **TypeScript / Preact** (`frontend/src/`): SPA frontend built with webpack, tested with vitest, Node.js ≥ 20 (see `.nvmrc`: v24.11.1).
- **LESS** → CSS (`frontend/src/styles/`, `static/css/`).
- Package manager: **uv** (Python), **npm** (JS).

---

## Environment Setup (do once)

### Python
```sh
uv sync --locked --all-extras --dev   # installs all Python + dev deps into .venv
source .venv/bin/activate             # Linux; not needed for uv run commands
```
Create `.env` in repo root (required before starting server or running tests that need settings):
```
FLASK_SECRET_KEY='arandomstring'
FLASK_DASH__CSRF_SECRET='arandomstring'
FLASK_DASH__DEFAULT_ADMIN_USERNAME='admin'
FLASK_DASH__DEFAULT_ADMIN_PASSWORD='secret'
FLASK_DASH__ALLOWED_DOMAINS='*'
```
Use `python gen-settings.py` to auto-generate the `.env` file.

## Build

### Frontend production build
```sh
npm ci
npm run all-css     # creates CSS files
npm run build       # webpack production build → static/html & static/css
```

### Running the dev server
```sh
./runserver.sh      # sets LC_ALL, LANG, FLASK_APP, then: uv run -m flask run --host=0.0.0.0 --debug
```
Server runs on **port 5000**.

---

## Lint

### Python lint (must pass with zero errors on E9/F63/F7/F82)
```sh
uv run flake8 dashlive tests alembic/versions --count --select=E9,F63,F7,F82 --show-source --statistics
uv run flake8 dashlive tests alembic/versions --count --ignore E302,E402,C901,W504 --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```
Max line length is **127**. The second flake8 invocation is warnings-only (exit-zero).

### JS/TS lint
```sh
npm run lint        # eslint over frontend/src/**/*.{ts,tsx} and static/js/*.js
```
Config: `eslint.config.js`. Uses `typescript-eslint`, `eslint-config-preact`, `eslint-plugin-import`, `eslint-plugin-react`.

---

## Tests

### Python tests (recommended: parallel)
```sh
uv run pytest -n auto
```
- 832 tests; completes in ~3 minutes with `-n auto` (32 workers).
- Test config: `pyproject.toml` (`[tool.pytest.ini_options]` → `testpaths = ["tests"]`).
- Coverage minimum is **75%** (`fail_under = 75.0`).
- Tests use `pyfakefs` to sandbox the filesystem. Do NOT write tests that touch real filesystem paths without using the fake FS.
- Test base class `FlaskTestBase` is in `tests/mixins/flask_base.py`; use it for all Flask endpoint tests.

### Python coverage
```sh
uv run coverage run -m pytest
uv run coverage html   # → htmlcov/index.html
```

### JS/TS tests
```sh
npm run test        # vitest (watch mode)
npm run coverage    # vitest --coverage; 107 test files, 524 tests; thresholds: branches 80%, functions 85%, lines/statements 80%
```
Coverage config in `vite.config.js`. Note: "Websocket connection failed" and "connection refused" log lines during JS tests are expected — the tests mock server connections.

---

## CI / GitHub Workflows
Located in `.github/workflows/`. All run on push.

| Workflow | File | What it checks |
|---|---|---|
| Python | `pythonapp.yml` | `uv sync`, flake8 lint, `pytest -n auto` |
| JavaScript | `javascript.yml` | `npm ci`, `npm run lint`, `npm run coverage` |
| CodeQL | `codeql-analysis.yml` | Security analysis |

**To replicate CI locally:**
```sh
uv run flake8 dashlive tests alembic/versions --count --select=E9,F63,F7,F82 --show-source --statistics
uv run pytest -n auto
npm ci && npm run lint && npm run coverage
```

---

## Project Layout

```
dashlive/                 Core Python package
  server/
    app.py                Flask app factory (create_app)
    routes.py             All URL routes (Route class + routes/ui_routes lists)
    models/               SQLAlchemy models (stream, mediafile, user, key, token, …)
    requesthandler/       Flask view handlers (manifest_requests.py, media_requests.py, …)
    manifests.py          DASH manifest generation
  mpeg/
    mp4/                  ISO BMFF / MP4 parsing (iso_parser.py, atom.py, boxes/)
    dash/                 DASH-specific types, timing, representation, validator
    codec_strings.py      Codec string parsing/generation
  drm/                    DRM helpers (PlayReady, ClearKey, Marlin)
  scte35/                 SCTE-35 binary parsing
  utils/                  Shared utilities (json_object, binary, …)
  testcase/               Shared test generator helpers
frontend/src/             TypeScript/Preact SPA
  main.tsx                Entry point
  AppRoutes.tsx           Client-side routes
  cgi/                    CGI option types and UI
  components/             Shared UI components
  validator/              DASH validator frontend
  player/                 DASH player integration
tests/                    test suite (mirrors dashlive/ package structure)
  mixins/flask_base.py    FlaskTestBase — base class for all Flask tests
  fixtures/               JSON/binary test fixtures
templates/                Jinja2 server-side templates + dist/ (webpack output)
static/                   Static assets (CSS, legacy JS)
alembic/versions/         Database migration scripts
frontend/config/          webpack production config
```

### Key configuration files
| File | Purpose |
|---|---|
| `pyproject.toml` | Python deps, pytest config, coverage config |
| `tox.ini` | tox envs (lint, py311) |
| `package.json` | JS deps, npm scripts |
| `tsconfig.json` | TypeScript compiler options (target ES2023, jsxImportSource preact) |
| `eslint.config.js` | ESLint flat config |
| `vite.config.js` | vitest + coverage config |
| `frontend/config/webpack.prod.js` | webpack production build |
| `alembic.ini` | Alembic migrations config |

---

## Important Notes
- Always run `npm ci` before any JS build or test command.
- Always run `uv sync --locked --all-extras --dev` to ensure the Python venv matches `uv.lock`.
- The Flask entry point is `dashlive.server.app` (env var `FLASK_APP`).
- Database is SQLite; migrations are managed with Alembic (`alembic upgrade head` to apply).
- Python unit tests create a temporary SQLite database and use pyfakefs; no real filesystem access is needed to run tests.
- Trust these instructions; only search the codebase if a specific detail is missing or appears incorrect.
