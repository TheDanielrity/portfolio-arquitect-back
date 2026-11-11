# Local development

Use Python 3.12+ (validated locally with 3.13), PostgreSQL with the `pgcrypto`
extension available, and PowerShell. No containers are required. Run from the
repository root. Python dependencies belong exclusively to `.venv`.

## First installation

1. Install Python and PostgreSQL locally. Start the PostgreSQL service.
2. In psql as a database administrator, create the application owner and database:

   ```sql
   CREATE ROLE portfolio LOGIN;
   \password portfolio
   CREATE DATABASE portfolio OWNER portfolio;
   ```

   `\password` prompts without placing a password in SQL history. The owner needs
   permission to create schemas/functions and install `pgcrypto` in this database.
   If extension installation is restricted, have the database administrator install
   `pgcrypto` in `portfolio` before migrating. Do not run the design SQL separately.

3. Create the environment only if missing and install declared dependencies:

   ```powershell
   if (-not (Test-Path .venv)) { py -m venv .venv }
   .\.venv\Scripts\python.exe --version
   .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

4. Edit the ignored `.env`. Set `DATABASE_URL` to your PostgreSQL database using
   `postgresql+psycopg://portfolio:PASSWORD@localhost:5432/portfolio` and percent-encode
   special characters in credentials. Set `JWT_SECRET_KEY` to a cryptographically
   random secret of at least 32 bytes (for example, generated with Python's
   `secrets.token_urlsafe(48)`); keep it out of source control and shared output.
   Configure exact `CORS_ORIGINS`, e.g. `["http://localhost:4200","http://localhost:4201"]`.
   The example JWT placeholder intentionally fails validation. Environment variables
   override `.env`; execute commands from the root so the file is found.

5. Check connectivity, migrate, and provision your administrator:

   ```powershell
   .\.venv\Scripts\python.exe -m app.core.check_database
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m alembic current
   .\.venv\Scripts\python.exe -m alembic check
   .\.venv\Scripts\python.exe -m app.modules.auth.create_admin
   ```

   Provisioning uses hidden password prompts; no default account exists. Use an empty
   domain database for the initial migration. Never use downgrade to reset real data.

6. Start the API:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.core.event_loop:selector_loop_factory
   ```

   The loop factory supports Psycopg async connections on Windows. On Linux/macOS,
   create `.venv` with `python3 -m venv .venv` and use `.venv/bin/python` for each
   command. The same loop factory can be used there.

7. Check `/api/v1/health`, `/docs`, `/redoc` and `/openapi.json` at
   `http://127.0.0.1:8000`. Health is liveness only. Login via Swagger with the account
   just created, then authorize with its access token. An empty database returns
   empty lists and 404 for the absent profile; this is expected.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pip check
```

Without test connection variables, PostgreSQL tests skip. For the full suite,
provide `TEST_DATABASE_URL` and `MIGRATION_TEST_ADMIN_URL` securely in the process
environment, using `postgresql+psycopg` URLs. These are not application settings and
are not loaded from `.env` by pytest. The first performs connectivity/transaction
checks; the second needs a test role with CREATEDB and pgcrypto permissions.
Domain/migration tests create randomly named disposable databases and remove only
their own databases during teardown. Do not use production credentials. Run the
same pytest command and confirm there are no skips. See the README's migration
validation section for lifecycle details.

## Configuration and troubleshooting

The complete configuration template is [`.env.example`](../.env.example).
Request limits default to 1,048,576 bytes, 30 auth POSTs/minute and 10 contact
POSTs/minute per peer per worker. Configure trusted proxies and deployment quotas
as described in the [security review](security/phase12-review.md).

- Configuration failure: check required URL/secret and JSON syntax for origins.
- Connection failure: check the local service, host/port, role, password and database.
- Missing tables: run `alembic upgrade head`; startup does not apply migrations.
- Windows event-loop error: use the documented `--loop` argument.
- Browser CORS failure: origins must match scheme, hostname and port exactly;
  `localhost` and `127.0.0.1` differ. Include both frontend origins if needed.
- 429: honor `Retry-After`; invalid submissions also consume quota.

See [frontend handoff](api/frontend-handoff.md) for application workflows.

## Media storage (Phase 14)

The default `STORAGE_PROVIDER=local` needs no R2 credentials. Set
`LOCAL_STORAGE_PATH` to a directory outside source control and `MEDIA_BASE_URL`
to the externally reachable backend origin (including any reverse-proxy prefix).
Local PUT uses authenticated backend requests and its existing body-size cap;
R2 transfers bytes directly from the browser.

For R2 use a private bucket, object read/write API credentials and the account ID.
Fill `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
and set `STORAGE_PROVIDER=r2`. No bucket is created or made public by the backend.
Blank optional environment entries use safe configuration defaults. Missing R2
credentials fail configuration when R2 is selected. Do not set public bucket
domains for mixed private/public data. `R2_PUBLIC_BASE_URL` is reserved and does
not enable public delivery; `MEDIA_BASE_URL` identifies authorized backend delivery.

Run the additive migration with `.\.venv\Scripts\python.exe -m alembic upgrade head`.
Revision `0002_storage_operations` adds one technical table without changing the
original 17 tables. Use `.\.venv\Scripts\python.exe -m alembic check` to check drift.
Set type/global size budgets and authorization/grace settings using `.env.example`.

Run `.\.venv\Scripts\python.exe -m app.modules.media.cleanup --limit 100` repeatedly
or schedule it with the operating system. It needs the application database and
the same configured provider. Retain provider credentials until outstanding intents
are reconciled. The batch limit is 1–1000. Expired staging/unconfirmed files are
cleaned only after the grace; DELETE intents are retried immediately. No Redis,
Celery or containers are used. Downgrade refuses unresolved work and discards
terminal technical history only after reconciliation.

Monitor storage usage, failed intents and provider availability. Configure transfer
timeouts shorter than `MEDIA_CLEANUP_GRACE_SECONDS`. As a fallback for unusually
late provider transfers, consider an R2 lifecycle expiration scoped ONLY to
`staging/`, with an age longer than the complete upload-plus-grace window (for
example two days with the default budgets). Never apply that rule to `objects/`.
This is manual provider configuration, not a substitute for reconciliation.

`tests/test_storage.py` uses local files and botocore stubs without network access.
`tests/test_upload_api.py` checks protected routes and declaration policy without
PostgreSQL. `tests/test_upload_integration.py` exercises disposable PostgreSQL
databases and local storage, including concurrency and partial failures. No normal
test accesses a real R2 bucket; a real smoke test must be explicitly configured
outside the default suite. Follow the bucket CORS/browser steps in the handoff.
