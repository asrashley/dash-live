# Repository guide

This repository implements **dash-live**, an MPEG-DASH streaming service.
It serves audio-video streams that are compliant with the 5th edition of
ISO/IEC 23009-1 "Information technology — Dynamic adaptive streaming over HTTP (DASH)".

The backend is Python (Flask, SQLAlchemy, and SQLite); the browser
application is TypeScript with Preact. Some of the browser frontend is uses server-rendered HTML pages, but those are scheduled to be
replaced. Do not add new features to server-rendered HTML pages, but
inform the operator that the page needs to be migrated to client-side
Typescript Preact components.

Keep changes focused on the relevant stack, and use the established patterns in nearby code. Create unit tests when adding new functionality and when fixing bugs.

## Repository layout

- `dashlive/` — Python application and libraries:
  - `server/` — Flask application, routes, request handlers, and models.
  - `mpeg/` — MP4 parsing and DASH-related code.
  - `drm/`, `scte35/`, `components/`, `utils/`, and `testcase/` — supporting
    domain logic and shared helpers.
- `frontend/src/` — TypeScript/Preact application, grouped by feature. Shared
  components, hooks, types, and test helpers live alongside feature code.
- `frontend/config/` — frontend webpack and TypeScript configuration.
- `tests/` — Python tests, organised as `test_*.py`.
- `static/` — static assets, including JavaScript and compiled CSS.
- `templates/` — server-rendered templates and frontend build output.
- `templates/manifests` — server-rendered templates of DASH XML manifests.
- `alembic/` — database migration environment and versions.
- `docs/` — user and operator documentation.

## Environment setup

Requirements: Python 3.12 or newer, Node.js 22 or newer, npm 10 or newer,
and [uv](https://docs.astral.sh/uv/).

### Python

Install the locked project dependencies and development tools:

```sh
uv sync --locked --group dev
```

Use `uv run <command>` to run tools from the project environment without
activating it, for example `uv run pytest`. If you prefer activation on Linux:

```sh
. .venv/bin/activate
```

The development server requires a `.env` in the repository root. Generate
one with `python gen-settings.py`, or provide the settings documented in
[README.md](README.md). Do not commit local secrets or the generated `.env`.

### TypeScript / frontend

Install dependencies from the lockfile:

```sh
npm ci
```

Compile styles and the production frontend bundle when needed:

```sh
npm run all-css
npm run build
```

## Common tasks

### Run the server

After Python setup and `.env` configuration:

```sh
./runserver.sh
```

On Windows, use `.\runserver.ps1`. The development server listens on port
5000 by default.

### Run tests

Run the Python suite in parallel:

```sh
uv run pytest -n auto
```

Run a specific Python test module or test:

```sh
uv run pytest tests/test_mp4.py
uv run pytest tests/test_views.py::TestHandlers::test_availability_start_time
```

Run TypeScript tests once (rather than entering Vitest's watch mode):

```sh
npm run test -- --run
```

Run the TypeScript suite with coverage:

```sh
npm run coverage
```

Python coverage can be collected with:

```sh
uv run coverage run -m pytest
uv run coverage html
```

### Lint

Run the repository's Python syntax/name-error checks:

```sh
uv run flake8 dashlive tests alembic/versions --count --select=E9,F63,F7,F82 --show-source --statistics
```

The project also has a warnings-only Python style pass:

```sh
uv run flake8 dashlive tests alembic/versions --count --ignore E302,E402,C901,W504 --exit-zero --max-complexity=10 --max-line-length=127 --statistics
```

Run frontend lint after `npm ci`:

```sh
npm run lint
```

## Code and test conventions

### Python

- Always add type hints when modifying or adding Python code.
- Use `snake_case` for modules, functions, and variables; use `PascalCase` for
  classes.
- Put application code under `dashlive/` and tests under `tests/`. Name test
  modules `test_*.py` and follow nearby test classes and fixture patterns.
- Use the shared Flask test support in `tests/mixins/flask_base.py` for Flask
  endpoint tests.
- Keep Python formatting and lint settings consistent with `tox.ini` and the
  commands above.
- Database migrations belong in `alembic/versions/`. When creating a
  new migration, add tests to `tests/test_migrations.py` to check both
  forward upgrade and backwards downgrade.

### TypeScript / Preact

- Put frontend code under `frontend/src/`, keeping files in the relevant
  feature directory.
- Use `PascalCase` names for Preact components and their `.tsx` files;
  use `camelCase` for functions, variables, and hooks (custom hooks start
  with `use`). Keep type names in `PascalCase`.
- Name component tests alongside the component (for example,
  `Component.test.tsx`) and utility/hook tests alongside their `.ts` source.
- Use Preact and the existing JSX configuration; do not introduce React
  runtime assumptions.
- Keep imports, lint rules, and TypeScript settings consistent with
  `eslint.config.js` and `frontend/config/tsconfig.common.json`.

## Additional documentation

- [docs/testing.md](docs/testing.md) — test and coverage details.
- [docs/deploy.md](docs/deploy.md) — deployment options.
- [docs/streams.md](docs/streams.md) and [docs/media.md](docs/media.md) — stream
  and media behaviour.
- [docs/validate.md](docs/validate.md) — DASH stream validation.
