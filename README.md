# Architecture Portfolio Backend

Architecture portfolio API with Python 3.12+, FastAPI and PostgreSQL.

Start with the [local setup guide](docs/development.md), then the
[Angular handoff](docs/api/frontend-handoff.md) and
[complete endpoint inventory](docs/api/endpoints.md). Live contracts are available
at `/docs`, `/redoc` and `/openapi.json`.

## Local setup (PowerShell)

Run commands from the repository root:

```powershell
if (-not (Test-Path .venv)) { py -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Configure DATABASE_URL and a random JWT_SECRET_KEY in .env before startup.
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.modules.auth.create_admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --loop app.core.event_loop:selector_loop_factory
```

Create `.venv` only if it is missing. If the Windows launcher cannot locate
Python, invoke an installed Python 3.12+ executable by its full path with
`-m venv .venv`. All subsequent Python commands must use `.venv`.
On Linux/macOS, use `.venv/bin/python` after creating `.venv` with Python 3.12+.

`GET http://127.0.0.1:8000/api/v1/health` returns `{"status":"ok"}`.
OpenAPI documentation is available at `/docs`.

## Configuration

Settings load from `.env` in the working directory; environment variables take
precedence. `.env` is ignored by Git. Available settings:

| Variable | Default | Purpose |
| --- | --- | --- |
| `APP_NAME` | `Architecture Portfolio API` | OpenAPI application title |
| `APP_ENV` | `development` | `development`, `test` or `production` |
| `DEBUG` | `false` | Debug behavior and application log level |
| `CORS_ORIGINS` | `[]` | JSON array of exact allowed origins |
| `DATABASE_URL` | Required | `postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE` |
| `JWT_SECRET_KEY` | Required | Random signing secret, at least 32 bytes; placeholders rejected |
| `JWT_ALGORITHM` | `HS256` | Only HS256 is accepted |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access lifetime, between 1 and 60 minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Absolute session lifetime, between 1 and 90 days |

CORS allows GET/POST/PUT/PATCH/DELETE and Authorization/Content-Type headers for configured origins,
without cookie credentials. Authentication uses explicit bearer headers and JSON bodies.
Production rejects wildcard origins and debug mode. Application lifecycle logs
include timestamp, level and logger; request bodies and configuration are not logged.
The health endpoint is a liveness check and does not verify external dependencies.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
```

Tests isolate environment settings and use temporary directories for `.env` files.
## PostgreSQL infrastructure (Phase 1)

Provide an existing PostgreSQL database and credentials through `.env` or environment
variables. Percent-encode special characters in the username/password. The URL is
stored as a Pydantic secret and rejected unless it selects the Psycopg 3 driver.
Never paste real credentials into tracked files or commands committed to the repository.

Each application lifespan owns an asynchronous engine and session factory. Startup
validates configuration without connecting; shutdown disposes the engine. Connections
are opened on demand, with pool pre-ping and a five-second connection timeout.
Services can request `SessionDependency`; each request gets its own `AsyncSession`.
Services own transaction boundaries and must explicitly commit successful writes.
Uncommitted work is rolled back on exit, including exceptions and cancellation,
and the session is closed. There is no automatic commit at request teardown.

Verify connectivity independently of the liveness endpoint:

```powershell
.\.venv\Scripts\python.exe -m app.core.check_database
```

This executes only `SELECT 1`, closes the connection and returns exit code 0 on
success or 1 on configuration/connection failure. It does not print driver errors
or credentials. No domain tables are created.

Use the documented Uvicorn `--loop` option on Windows both with and without reload:
[Psycopg requires a selector loop](https://www.psycopg.org/psycopg3/docs/advanced/async.html).
The custom factory uses the standard library and requires Uvicorn 0.36+.
The connectivity command and Alembic also create compatible selector loops.

## Alembic

```powershell
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

`current` checks the live database; `heads` and offline SQL generation do not connect.
Alembic reads the same `DATABASE_URL`, passes it directly to SQLAlchemy (preserving
percent-encoded credentials), and uses `NullPool` for online migrations. Metadata
comes from `Base` and reflection is limited to `auth`, `portfolio`, `media`,
`content`, and `contact`. The Alembic version table belongs to `public`.

Phase 2 registers all 17 domain models through `app.models`, which Alembic imports.
Revision `0001_initial_schema` creates the schemas, tables, PostgreSQL indexes,
constraints, pgcrypto extension, timestamp function, ten triggers and comments.
Run `upgrade head` against an empty domain database; `check` detects differences
between the migrated database and ORM metadata. Database credentials must have
permission to create the schemas, function and pgcrypto extension. The initial
migration fails on an existing timestamp function instead of replacing it.
The approved SQL/DBML documentation is unchanged.

The optional infrastructure integration test performs read-only queries and verifies transaction
recovery without creating permanent objects. Supply `TEST_DATABASE_URL` securely
in the process environment, then run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database_integration.py
```

Without that variable the integration test is skipped. Unit tests use isolated
settings and never connect to a database. Follow `PLANS.md` for subsequent phases.

## ORM models (Phase 2)

Typed models live in `app/modules/{auth,portfolio,media,content,contact}/models.py`.
Import models from `app.models` before ORM use to register all cross-module relationships.
The SQL document supplies the exact constraints, index expressions and partial predicates;
DBML provides the relationship overview and simplifies some unique/index annotations.
Neither design document was changed.

Relationships use `lazy="raise"`: services must load needed relationships explicitly
(for example with `selectinload`) to avoid implicit database I/O in asynchronous code.
Association objects preserve their own timestamps, roles, captions and ordering fields.
Collections use `passive_deletes="all"` and no ORM delete cascade: PostgreSQL enforces
the documented `CASCADE`, `RESTRICT` and `SET NULL` rules even for loaded collections.
After a physical parent deletion, expire/reload affected loaded objects before reusing
them; their in-memory state may be stale. Removing an association from a collection
does not delete its database row; future services must delete association rows explicitly.
Normal project deletion will remain a `deleted_at` update in the service layer.

`MediaAsset.asset_metadata` maps to the database column `metadata`, avoiding the
reserved declarative attribute. Its Python `None` maps to SQL NULL. `SiteSetting.value`
accepts any JSON value, including JSON null, while the column remains SQL NOT NULL.
Replace JSON values to persist changes; in-place JSON mutation is not tracked.
INET values use Psycopg's native `ipaddress` objects; areas use `Decimal`.

UUIDs and timestamp defaults are database-generated. `updated_at` declares
`server_onupdate=FetchedValue()` to describe the approved database triggers; it does
not install them or substitute an ORM timestamp hook. Revision `0001_initial_schema`
installs the approved function and triggers.
The Phase 2 tests compare columns, defaults, constraints and indexes with the approved
SQL, configure every mapper and exercise association synchronization without a database.

## Migration validation (Phase 3)

Supply `MIGRATION_TEST_ADMIN_URL` securely in the process environment using the
`postgresql+psycopg` URL format. This is a test-only setting, not an application
setting. The PostgreSQL role needs CREATEDB and permission to install pgcrypto
in databases it owns. Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_migrations_integration.py
```

These tests create two empty databases with random `portfolio_migration_` names.
They never migrate or clear the database named in the administrator URL. One
temporary database runs upgrade/downgrade/upgrade; the other runs the approved
SQL document. Tests compare their schemas, tables, columns, defaults, constraints,
indexes, comments, function and triggers through PostgreSQL catalogs. They also
run Alembic's drift check and exercise uniqueness, soft-delete slug reuse, allowed
values, media constraints, FK delete actions, native types and timestamp updates.
Each behavioral test rolls back its data, and the two databases are removed on
normal teardown, including test failures. Abrupt process termination can leave
temporary databases behind; the tests never automatically remove previous runs.
Without `MIGRATION_TEST_ADMIN_URL`, these migration tests are skipped.

The initial migration's downgrade **permanently deletes domain data**. It drops
the 17 tables, timestamp function and five schemas in dependency order, without
`CASCADE`. It retains pgcrypto because other objects may use it. Test downgrade
only in a disposable database; never use it to reset a populated development or
production database. No downgrade is needed during normal setup.

## Administrator authentication (Phase 4)

All `auth.app_user` records represent administrators; the approved schema has no
separate roles or public user registration. After configuring the environment and
running `alembic upgrade head`, provision an administrator locally:

```powershell
.\.venv\Scripts\python.exe -m app.modules.auth.create_admin
```

The command prompts for email, names and a password of 12–1024 characters using
hidden input. It stores an Argon2id hash and rejects existing emails without
overwriting the account. It has no HTTP endpoint and accepts no password argument.
No default administrator or password is created automatically.

Generate `JWT_SECRET_KEY` with a cryptographically secure generator such as
`secrets.token_urlsafe(48)` and save it only in the local `.env` or environment.
Keep the same key across application instances. Changing it invalidates existing
JWTs; revoke refresh sessions too if a signing key is compromised.

| Endpoint | Request | Success |
| --- | --- | --- |
| `POST /api/v1/auth/login` | JSON `email`, `password` | 200: `access_token`, `refresh_token`, `token_type`, `expires_in` |
| `POST /api/v1/auth/refresh` | JSON `refresh_token` | 200: replacement token pair |
| `POST /api/v1/auth/logout` | JSON `refresh_token` | 204, empty body |
| `GET /api/v1/auth/me` | `Authorization: Bearer <access_token>` | 200: `id`, `email`, `first_name`, `last_name`, `is_active` |

Login trims surrounding email whitespace and compares email case-insensitively;
it does not trim or normalize passwords. Unknown users, incorrect passwords and
inactive users receive the same 401 response and password verification work.
Successful login records `last_login_at` and upgrades older Argon2 parameters when
needed. Hashing and verification run in a worker thread, outside the async event loop.

Access tokens have fixed issuer/audience/type claims, required timestamps, a user
UUID, a refresh-session UUID and a unique token ID. `expires_in` is the access TTL
in seconds. The reusable `CurrentUser` dependency validates the JWT and checks the
active user and unexpired, unrevoked session in PostgreSQL on every request.
Future administrative routers must use this dependency.

Refresh tokens contain 48 random bytes encoded as 64 URL-safe characters. Only
their SHA-256 hashes are persisted. Refresh locks the existing row, validates the
session and active user, revokes it and inserts a replacement in one transaction.
Only one concurrent refresh can succeed. Rotation preserves the original absolute
expiry deadline. The old refresh token **and its access token** become invalid.
The frontend must serialize refresh attempts and replace both tokens after success.
An interrupted refresh response may require login again; rotation has no grace period.

Logout revokes the session identified by the supplied refresh token and immediately
invalidates its JWTs. It is idempotent for unknown/already-revoked tokens and does
not affect other logins. Clients must finish any in-flight refresh before logging
out and supply the latest token. The schema has no token-family linkage: replay
of an older token is rejected but does not revoke its replacement session.
Disabling an administrator blocks both refresh and authenticated requests.

Authentication failures return `401` with `WWW-Authenticate: Bearer` and
`{"detail":"Authentication required or invalid credentials"}`. Invalid request
bodies return `422` with `loc`, `msg` and `type`, omitting submitted values and
validation context to prevent secret disclosure. Auth responses use `no-store`.
Passwords, hashes and raw tokens are never logged or included in `/me` responses.
Use HTTPS outside local development. Phase 12 adds request rate limits. Password recovery,
MFA, session-list management and expired-session cleanup remain unimplemented.

Security/configuration/API tests run without PostgreSQL. For authentication
integration tests, provide `MIGRATION_TEST_ADMIN_URL` as described above and run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_auth_integration.py
```

They provision disposable databases, seed isolated users and test login, token
storage, expiry, inactive users, rotation, concurrent refresh, rollback and logout.

## Media metadata administration (Phase 5)

Every endpoint below requires a valid administrator bearer token. Responses are
administrative contracts, including storage identifiers and internal metadata.
Phase 14 adds guarded public delivery without exposing storage identity.

| Endpoint | Purpose | Success |
| --- | --- | --- |
| `GET /api/v1/admin/media` | Paginated list, optionally filtered by `type` | 200 |
| `GET /api/v1/admin/media/{id}` | Retrieve metadata | 200 |
| `POST /api/v1/admin/media` | Register an existing storage object's metadata | 201 |
| `PATCH /api/v1/admin/media/{id}` | Edit descriptive metadata | 200 |
| `DELETE /api/v1/admin/media/{id}` | Remove an unused metadata record | 204 |

Listings accept `limit` (default 20, range 1–100), `offset` (default 0, nonnegative),
and optional `type`. The envelope is `{"items": [...], "total": 0, "limit": 20,
"offset": 0}`. Ordering is newest first by `created_at`, then UUID as a stable tie
breaker. The count uses the same type filter as the page. Concurrent writes can
change totals or positions between offset-based requests.

Creation requires `type`, `original_filename`, `storage_provider`, `storage_key`,
`url`, `mime_type` and `file_size`. Types are IMAGE, VIDEO, PDF, MODEL_3D and DOCUMENT.
Optional fields are `thumbnail_url`, `width`, `height`, `alt_text`, `title`,
`description` and `metadata`. Dimensions can be absent for every type; supplied
dimensions must be positive PostgreSQL integers. Size must be a nonnegative
PostgreSQL bigint. URLs must use HTTP(S). MIME types must have type/subtype syntax
and are normalized to lowercase. These are declared metadata values; registering
them does not fetch URLs, inspect file bytes or verify MIME/content correspondence.
Filenames, provider names and opaque storage keys are preserved, including case.

PATCH accepts only `alt_text`, `title`, `description` and `metadata`. Omitted values
remain unchanged, explicit null clears a field, and metadata objects are replaced
as a whole. File identity, URLs, size, type and dimensions cannot be changed by
PATCH. An empty PATCH is a no-op. Titles and alt text are limited to 255 characters,
descriptions to 20,000, and metadata to a JSON object of at most 64 KiB in its
serialized representation. Invalid Unicode, NULs and nonfinite JSON numbers are
rejected before persistence. Unknown input fields return 422.

Duplicate `(storage_provider, storage_key)` pairs return 409; missing assets return
404. Deletion locks the media row and checks project media, section media, profile
photos and CVs. Any reference returns 409, including references from soft-deleted
projects or inactive profiles. The application deliberately treats profile assets
as in use even though their database FKs permit SET NULL. The row lock serializes
deletion against concurrent FK references; PostgreSQL remains the final integrity
guard. Writes commit the request transaction already opened by authentication and
roll back on failure.

Phase 14 extends this metadata module with `StoragePort` in `storage_port.py`,
R2 and local adapters, verified direct upload and durable deletion/cleanup intents.
`storage.py` retains the `StorageLocation` contract for legacy external metadata.
New R2/local registration requires the upload workflow; external-provider POST
keeps its metadata-only behavior. Managed metadata PATCH preserves server-owned
storage policy. Managed DELETE records a durable intent before removing bytes and
can return 204 while provider cleanup remains pending. Repeated managed DELETE is
safe; references still return 409. Legacy external DELETE removes metadata only.
See the [complete upload handoff](docs/api/frontend-handoff.md#direct-media-upload-phase-14).

Run metadata/HTTP tests with `tests/test_media_schemas.py` and
`tests/test_media_api.py`. `tests/test_media_integration.py` uses the same
`MIGRATION_TEST_ADMIN_URL` convention and disposable database lifecycle as the
authentication integration tests, including concurrent reference/deletion checks.

## Portfolio administration (Phase 6)

All routes below start with `/api/v1/admin`, require an active administrator's
Bearer token and return `Cache-Control: no-store`. OpenAPI contains the complete
request and response schemas.

| Route | Methods and purpose |
| --- | --- |
| `/projects` | GET paginated projects; POST create (201) |
| `/projects/{id}` | GET detail; PATCH editable fields; DELETE soft delete (204) |
| `/projects/order` | PUT project ordering (204) |
| `/categories`, `/tags` | GET paginated taxonomy; POST create (201) |
| `/categories/{id}`, `/tags/{id}` | GET detail; PATCH; DELETE when unused (204) |
| `/projects/{id}/categories`, `/projects/{id}/tags` | GET paginated assignments; PUT replace assignments (204) |
| `/projects/{id}/attributes` | GET paginated attributes; POST add (201) |
| `/projects/{id}/attributes/{item_id}` | PATCH; DELETE (204) |
| `/projects/{id}/attributes/order` | PUT attribute ordering (204) |
| `/projects/{id}/media` | GET paginated links; POST attach existing media (201) |
| `/projects/{id}/media/{item_id}` | PATCH role/order; DELETE link (204) |
| `/projects/{id}/media/order` | PUT media ordering (204) |
| `/projects/{id}/cover` | PUT select or replace cover (200) |

Creation requires a title and explicit slug. Slugs are trimmed and lowercased,
then validated against the approved lowercase words/digits separated by single
hyphens. Conflicts return 409 without generating a different slug. Titles, taxonomy
names and attribute labels/values are trimmed and must be nonblank. Project
descriptions are limited to 50,000 characters and category descriptions to 20,000.
Area uses a positive decimal with at most two fractional digits and is serialized
as a string. PATCH changes only submitted fields; null clears nullable fields and
is rejected for required fields. Managed timestamps cannot be supplied by clients.

Set `status`, `visibility`, `is_featured` and `sort_order` through project PATCH.
Status accepts DRAFT, PUBLISHED and ARCHIVED; visibility accepts PUBLIC, UNLISTED
and PRIVATE. Create a draft, attach/select an IMAGE cover, then publish. Publishing
without an image cover returns 400. `published_at` records the first publication
and remains unchanged when unpublishing or republishing. Administrators may manage
all visibility values; public project delivery is documented under Phase 10 below.

Published projects cannot lose their cover through detach or role changes (409).
Use `PUT /projects/{id}/cover` with `{"media_id": "<uuid>"}` to replace it atomically.
Selecting the existing cover is a no-op. Replacement removes only the old COVER
link, preserves other roles, and never deletes the asset. Attaching a second COVER
through POST returns 409. Other roles are GALLERY, PLAN, RENDER, DOCUMENT and MODEL.
Link responses contain media IDs and relationship fields; fetch asset metadata
through the media API. Section media have the additional type restrictions
documented below.

Assignment PUT accepts `{"ids": ["<uuid>"]}` and replaces the entire category or
tag set; an empty list clears it. Unknown IDs return 404 and leave prior assignments
intact. Duplicate IDs return 422. Categories can be disabled using
`{"is_active": false}`; they remain available for administrative assignment.
Deleting a category or tag assigned to any project returns 409, including
soft-deleted projects whose historical relationships are retained.

Ordering PUT accepts `{"items": [{"id": "<uuid>", "sort_order": 2}]}`. It updates
only listed records, permits tied positions and rolls back the entire batch when
any record is missing or belongs to another project. Assignment and ordering
requests are limited to 100 IDs; ordering requires at least one item. Parent row
locks serialize project changes, publication, cover operations and child edits.
Taxonomy/media reference locks prevent deletion races; PostgreSQL unique indexes
and foreign keys remain authoritative.

Every listing uses the media pagination envelope and the same limit/offset bounds.
Projects can be filtered by `status`, `visibility`, `is_featured`, `category_id`
and `tag_id`. Project order is `sort_order`, newest creation, UUID; categories,
attributes and media links use `sort_order`, UUID; tags use lowercase name, UUID.
Offset pages can shift during concurrent changes. Deleted projects return 404
from normal detail and child operations and never appear in administrative lists;
their slugs become reusable. Restore/purge operations are not implemented.

Phase 6 tests are in `tests/test_portfolio_schemas.py`, `tests/test_portfolio_api.py`
and `tests/test_portfolio_integration.py`. Integration tests use the same disposable
PostgreSQL convention as the media tests. No dependencies or migrations were added.

## Dynamic project sections (Phase 7)

Section routes use `/api/v1/admin/projects/{project_id}/sections` as their base.
They inherit portfolio authentication and no-store responses. All operations
require a non-deleted parent project and verify section ownership.

| Suffix | Operations |
| --- | --- |
| (base) | GET paginated sections; POST create (201) |
| `/order` | PUT partial batch order (204) |
| `/{section_id}` | GET; PATCH; DELETE (204) |
| `/{section_id}/media` | GET paginated links; POST attach asset (201) |
| `/{section_id}/media/order` | PUT partial batch media order (204) |
| `/{section_id}/media/{media_id}` | PATCH caption/order; DELETE link (204) |

Create with `section_type` and optional `title`, `content`, `sort_order`,
`is_visible` (default true) and `media`. Media is a list of objects containing
`media_id`, optional `caption` and `sort_order`. For example:

```json
{
  "section_type": "SPLIT",
  "title": "Courtyard",
  "content": "Natural light connects the living spaces.",
  "is_visible": true,
  "media": [{"media_id": "<existing-image-uuid>", "caption": "South elevation"}]
}
```

| Type | Requirements when visible | Compatible media |
| --- | --- | --- |
| TEXT, QUOTE | Nonblank content | None |
| IMAGE | Exactly one asset | IMAGE |
| GALLERY | At least one asset, at most 100 | IMAGE |
| VIDEO | Exactly one asset | VIDEO |
| MODEL_3D | Exactly one asset | MODEL_3D |
| SPLIT | Nonblank content and exactly one asset | IMAGE |

Hidden sections may lack content/assets while being composed. Type compatibility,
maximum counts and duplicate prevention apply even when hidden. Titles do not
substitute for required content. Content is stored as text without interpreting
HTML or enforcing a frontend layout. Limits are 200 characters for titles, 50,000
for content and 255 for captions; NULs and invalid Unicode are rejected.

PATCH can change type, content, visibility and the entire media set atomically.
Omitting `media` preserves the links; supplying a list replaces them, including
captions/order and link creation timestamps. An empty list clears links when
the resulting section state permits it. Use this operation to replace a visible
single-asset section's media or change its type without an invalid intermediate
state. Null clears title/content/caption, but cannot clear type, order, visibility
or the media list. Unknown input fields return 422.

Section responses contain scalar section fields; the media listing returns
`section_id`, `media_id`, `sort_order`, `caption` and `created_at`. Assets need not
be attached separately to project media. The actual database key is
`(section_id, media_id)`, so media ordering uses asset UUIDs as the `id` values in
the usual `{"items": [{"id": "<media-uuid>", "sort_order": 1}]}` body.
Section ordering instead uses section UUIDs. Both allow tied positions and
atomically reject batches containing an unknown or incorrectly scoped ID.

Listings use the standard pagination envelope with limit 20 (maximum 100) and
offset 0 by default. Administrative listings include hidden sections. Section
order is `sort_order`, then section UUID; media order is `sort_order`, then asset
UUID. Media sets are limited to 100 assets per section.

Invalid content/media combinations return 400; unknown projects, sections or
assets return 404; duplicate attachments return 409. Parent row locks serialize
edits, including concurrent removal of gallery assets, to preserve visible-section
requirements. Asset locks protect against concurrent metadata deletion. A section
DELETE physically removes the section and cascades its links, preserving assets;
project soft deletion retains sections but makes their routes unavailable.

Tests in `tests/test_section_schemas.py` and `tests/test_sections_integration.py`
cover all seven types, compatibility, visibility, atomic replacements, rollback,
ownership, ordering, deletion and concurrent last-asset removal. The portfolio
API test also checks authentication on all eleven new section operations. No
dependencies, schema changes or migrations were needed. Public rendering and
filtering are implemented by Phase 10 below.

## Global content administration (Phase 8)

All routes start with `/api/v1/admin`, require an active administrator's Bearer
token and return `Cache-Control: no-store`.

| Route | Operations |
| --- | --- |
| `/profile` | GET active profile; POST initialize (201); PATCH update |
| `/profile/social-links` | GET paginated links; POST create (201) |
| `/profile/social-links/order` | PUT partial batch ordering (204) |
| `/profile/social-links/{id}` | GET; PATCH; DELETE (204) |
| `/services` | GET paginated services; POST create (201) |
| `/services/order` | PUT partial batch ordering (204) |
| `/services/{id}` | GET; PATCH; DELETE (204) |
| `/site-settings` | GET configured allowlisted settings |
| `/site-settings/{key}` | GET configured value; PUT create or replace value |

Initialize the profile with `first_name` and `last_name`. GET/PATCH return 404
until an active profile exists. POST returns 409 if one already exists, including
concurrent initialization attempts, backed by the approved PostgreSQL partial
unique index. The API edits the active profile in place; profile activation,
deactivation, history management and deletion are not exposed in this phase.

Optional profile fields are `professional_title`, `short_bio`, `biography`,
`email`, `phone`, `location`, `profile_media_id` and `cv_media_id`. Names are trimmed
and nonblank. Bios are plain text, limited to 2,000 and 50,000 characters
respectively. Email validation checks basic mailbox shape without DNS verification.
The photograph must reference IMAGE metadata; the CV may reference PDF or DOCUMENT.
Missing assets return 404 and incompatible types return 400. These checks validate
declared metadata, not file bytes. Null clears optional fields and media references.
Referenced assets remain protected by the media module's deletion rules.

Social links belong to the active profile. Creation requires `platform` and an
HTTP(S) `url`; optional values are `username`, `sort_order` and `is_visible`.
URLs are normalized by Pydantic, limited to 2,048 characters and reject embedded
credentials. Platform names are trimmed and case-insensitively unique per profile;
duplicates return 409. IDs belonging to an inactive profile return 404. The active
profile row serializes social mutations and ordering.

Services require `name` and `slug`; optional fields are `short_description`,
`description`, `icon`, `sort_order` and `is_visible`. Slugs follow the portfolio
normalization and format rules; duplicates return 409. Descriptions are limited
to 300 and 20,000 characters. Icons are identifiers containing letters, digits,
underscores or hyphens, starting with a letter/digit; raw SVG/HTML is not accepted.
DELETE physically removes the service, allowing its slug to be reused.

Social links and services support show/hide through `PATCH {"is_visible": false}`.
Administrative listings include hidden records and use the standard pagination
envelope, default limit 20, maximum 100, offset 0. Ordering is `sort_order`, UUID;
ties are allowed. Reorder accepts the same `{"items": [{"id": "<uuid>",
"sort_order": 1}]}` body as portfolio operations, at most 100 unique IDs. Failure
on any item rolls back the entire batch. Service rows are locked in UUID order to
avoid deadlocks between overlapping batches. PATCH preserves omitted fields;
null only clears nullable fields. Unknown body fields return 422.

Site settings have this explicit initial allowlist:

| Key | Value |
| --- | --- |
| `site_title` | Nonblank plain text, at most 200 characters |
| `site_description` | Nonblank plain text, at most 500 characters |
| `contact_enabled` | Strict JSON boolean |

PUT accepts `{"value": "Architecture portfolio"}` or `{"value": true}` as
appropriate for the key. No implicit defaults are persisted: an unconfigured key
returns 404 and is absent from the list. Responses contain `key`, `value` and
`updated_at`. The list is bounded to the three allowlisted keys, including when
the database contains unrelated legacy settings. Unknown keys return 422; wrong
per-key types, blank/oversized text, markup delimiters or control characters
return 400. Arbitrary objects, arrays, null and numbers are rejected with 422.
Allowed values are validated on reads as well as writes. Concurrent PUTs use
PostgreSQL upsert; the last committed update wins without duplicate rows.

These are presentation settings intended for public use, never a secrets store.
They do not override environment configuration, JWT settings or database settings.
`contact_enabled` controls public contact submission in Phase 9; an absent key
allows submissions, while false or an invalid legacy value disables them.
Content strings must be rendered as text by frontend clients. Public retrieval
and visibility filtering are documented under Phase 10 below.

Run `tests/test_content_schemas.py`, `tests/test_content_api.py` and
`tests/test_content_integration.py` for Phase 8 checks. Integration tests use a
fresh disposable PostgreSQL database per test, with the existing
`MIGRATION_TEST_ADMIN_URL` convention. No dependencies or migrations were added.

## Contact messages (Phase 9)

`POST /api/v1/public/contact` accepts `name`, `email`, `message`, and optional
`phone` and `subject`. It returns HTTP 201 with `{"detail": "Message received"}`
only after the transaction commits. The public response includes no message ID,
sender data, state, timestamps, IP address or user agent. There is no public
message retrieval endpoint.

Names and messages must be nonblank. Limits are 150 characters for name, 320 for
email, 50 for phone, 200 for subject and 10,000 for message. Text is trimmed and
rejects NULs and invalid Unicode. Optional phone/subject may be omitted or null;
supplied blank strings are rejected. Phone is free-form international contact text.
Pydantic EmailStr uses `email-validator` for email syntax and normalization without
DNS checks; this does not verify ownership or delivery. Unknown fields, including
attempts to supply status or metadata, return 422. Content is stored as text and
must be rendered as text by clients, never interpreted as HTML.

New submissions always start as NEW, with no read/reply timestamps. The existing
`contact_enabled` site setting is enforced: missing or true permits submission;
false or an invalid legacy value returns 400 without inserting a message. A change
to this setting does not cancel submissions already in progress.

All administrative operations require an active administrator's Bearer token:

| Route | Operation |
| --- | --- |
| `/api/v1/admin/contact-messages` | GET paginated messages; optional `status` filter |
| `/api/v1/admin/contact-messages/{id}` | GET detail without changing read state |
| `/api/v1/admin/contact-messages/{id}/status` | PATCH `{"status": "READ"}` |

Pagination uses the existing `items`, `total`, `limit`, `offset` envelope, default
limit 20 and maximum 100. Messages sort newest first, with UUID as a stable tie
breaker. Status filters accept NEW, READ, REPLIED, ARCHIVED and SPAM. Administrative
responses include sender fields, ID, status and timestamps; IP/user-agent metadata
is excluded from these API responses as well. Success responses use `no-store`.

PATCH accepts READ, REPLIED, ARCHIVED or SPAM from any current state, allowing
administrators to recover misclassified messages. NEW is reserved for submissions.
READ records the first read time; REPLIED records the first reply time and, if
needed, the first read time. These historical timestamps survive reclassification
and repeated requests. ARCHIVED/SPAM do not imply reading or replying. A row lock
serializes concurrent updates; timestamps use the database clock. Missing IDs
return 404. Marking REPLIED records an administrative action; it sends no email.

`get_submission_context` is the dependency boundary where future spam checks or
CAPTCHA validation can reject a submission before persistence. Tests exercise
replacement with a 429 policy. Phase 12 adds body and peer rate limits in request
middleware; no CAPTCHA provider is enabled. The dependency captures the ASGI peer IP and a
user agent capped at 1,024 characters, ignoring invalid metadata and forwarded
headers. Configure trusted proxy handling at the server before deployment; a
proxy can otherwise appear as the peer. Rate counters belong to each application
worker. Infrastructure limits remain necessary for distributed abuse protection.

Run `tests/test_contact_schemas.py`, `tests/test_contact_api.py` and
`tests/test_contact_integration.py` for this phase. PostgreSQL tests follow the
existing disposable-database convention and require `MIGRATION_TEST_ADMIN_URL`.
The approved contact model and initial migration are unchanged.

## Public portfolio API (Phase 10)

These read-only routes require no authentication. They always apply public rules,
even when a request happens to carry an administrator token.

| GET route under `/api/v1/public` | Response |
| --- | --- |
| `/projects` | Paginated project cards |
| `/featured-projects` | Paginated featured project cards |
| `/projects/{slug}` | Complete project presentation |
| `/categories` | Paginated active categories used by discoverable projects |
| `/tags` | Paginated tags used by discoverable projects |
| `/profile` | Active professional profile with photo and CV |
| `/services` | Paginated visible services |
| `/social-links` | Paginated visible links belonging to the active profile |
| `/site-settings` | Configured, allowlisted public settings |

Collections use `{"items": [...], "total": 0, "limit": 20, "offset": 0}`.
`limit` defaults to 20 and is capped at 100; `offset` defaults to 0. Site settings
are a plain array bounded by the three approved keys. An absent profile returns
404; social links return an empty page if there is no active profile. Empty
collections and filters without matches return 200 with total 0.

Project listings and featured listings require PUBLISHED, PUBLIC and no soft
deletion. Detail allows PUBLISHED PUBLIC or UNLISTED projects by their exact
lowercase slug. Unlisted projects never enter discovery, even when featured;
their unique taxonomy does not appear in global category/tag lists. DRAFT,
ARCHIVED, PRIVATE, deleted and unknown projects all return the same 404 response.
An administrator token does not relax these rules. Slug reuse resolves only the
nondeleted replacement. Featured discovery has a separate `/featured-projects`
path so `featured` remains a valid project slug.

Both project listing routes accept `category` and `tag` slug filters, combined
with AND. Filter values follow the existing slug normalization rules. Inactive
categories never appear in responses and cannot be used to discover projects.
Unknown query fields such as `status`, `visibility` or `include_deleted` return
422 on collection routes. Projects sort by administrative order, publication
date descending (null last), then slug for stable ties. Categories and services
use order then slug; tags use name then slug; social links use order then UUID
internally. UUIDs and ordering fields are omitted from public responses.

Project cards include title, slug, summary, location, year, cover and active
categories. Detail adds description, area, client name, SEO fields, tags,
attributes, project media and visible sections. Arrays follow authored order
with deterministic ties. Each section includes its type, title, content and
ordered assets with captions, supporting all seven section types. Hidden sections
are excluded in the database query. Single-project detail returns its complete
authored composition; nested arrays are not silently truncated or paginated.
The frontend renders supplied text safely rather than interpreting it as HTML.

Media projections include type, URL, optional thumbnail, MIME type, nullable
dimensions, alt text, title and description. Storage keys/providers, original
filenames, arbitrary metadata, database IDs and administrative timestamps are
excluded, including inside sections and profile photo/CV. A legacy published
project without a cover returns `cover: null`; publication through the existing
administrative API still requires a valid image cover. URLs are the registered
delivery URLs; this phase does not download files or generate signed URLs.
Publishing a project or attaching profile media assumes those delivery URLs are
intended for public consumption. Asset access at the storage provider remains
independent of API project visibility.

Public settings reuse the approved allowlist and value validators from Phase 8,
but expose only `key` and `value`. Unconfigured keys are absent; unrelated legacy
keys cannot be returned. Invalid legacy values fail validation instead of being
published. Profile contact fields belong to the professional profile, not an
administrator account. Only the active profile is exposed.

Public reads use `Cache-Control: no-store` so visibility changes do not leave
previous responses in HTTP caches. Responses already delivered cannot be revoked.
Repositories eagerly load relationships: a nonempty project page uses four SELECTs
(count, projects, covers/assets, category links/categories), independent of page
size up to 100. Detail uses seven SELECTs for the tested multi-section composition,
with section assets batched rather than queried per section. Profile uses one
query including photo/CV. Tests assert query counts as well as response privacy.

Phase checks are in `tests/test_public_api.py` and `tests/test_public_integration.py`.
Integration tests cover every combination of publication status, visibility and
soft deletion, plus slug reuse, live visibility changes, filtering, ordering,
pagination, section composition and public content. They use disposable PostgreSQL
databases through `MIGRATION_TEST_ADMIN_URL`. No dependencies or migrations were
added for this phase.

## Administrative API conventions (Phase 11)

All `/api/v1/admin` operations require an active administrator's Bearer token.
Successful administrative responses and handled application/validation errors use
`Cache-Control: no-store`. Collection responses have the shape
`{"items": [], "total": 0, "limit": 20, "offset": 0}`. `total` counts matching
records before pagination; `limit` accepts 1–100 and `offset` starts at zero.
Unknown query parameters return 422.

The main collections accept `q`, `sort` and `direction=asc|desc`. Search trims
surrounding whitespace, accepts 1–200 characters, and matches case-insensitive
literal substrings: `%` and `_` are not wildcard operators. Blank searches should
be omitted. Text sorting is case-insensitive; stable ID tie breakers make ordering
deterministic for unchanged data. Offset pages can shift when records change.

| Collection under `/api/v1/admin` | Search fields | Filters | Sort fields (default) |
| --- | --- | --- | --- |
| `projects` | title, slug, client_name, location | status, visibility, is_featured, category_id, tag_id | sort_order (asc), title, created_at, updated_at |
| `categories` | name, slug | is_active | sort_order (asc), name, created_at |
| `tags` | name, slug | — | name (asc), created_at |
| `media` | original_filename, title, alt_text | type | created_at (desc), original_filename, file_size |
| `services` | name, slug | is_visible | sort_order (asc), name, created_at |
| `profile/social-links` | platform, username | is_visible | sort_order (asc), platform, created_at |
| `contact-messages` | name, email, subject, message | status | created_at (desc), name |

Filters combine with search using AND. Project categories/tags use the same query
conventions as their global collections. Attributes, project media, sections and
section media use pagination and their authored order; change that order through
the existing transactional `/order` operations. Site settings are a bounded
allowlist and therefore return a list without pagination. Soft-deleted projects
are excluded from administrative listings and normal detail operations.

For example, `GET /api/v1/admin/projects?q=house&status=DRAFT&sort=title&direction=asc&limit=20&offset=0`
returns a filtered page. GET/PATCH normally return 200, creation returns 201, and
deletion/reordering/assignment without a response body returns 204. Expected
errors use `{"detail": "message"}` with 400 for invalid operations, 401 for absent
or invalid authentication, 404 for missing resources and 409 for conflicts.
Validation returns 422 with `detail` containing `loc`, `msg` and `type` per error;
submitted values are omitted. OpenAPI describes each operation's concrete models.

Cross-module tests are in `tests/test_admin_api.py` and
`tests/test_admin_integration.py`, alongside each module's CRUD/conflict tests.
There is no dashboard endpoint because no frontend aggregate requirement has
been specified. Existing list totals support counts with the corresponding filters.

## Request protection and error handling (Phase 12)

The API limits actual request-body bytes before parsing (1 MiB by default), and
applies per-peer/per-worker limits to authentication POSTs (30/minute shared by
login, refresh and logout) and contact submissions (10/minute). `.env.example`
documents the configurable limits. Oversize bodies return 413; throttled attempts
return 429 with `Retry-After`. Invalid attempts count toward the limits.

Unexpected failures return `{"detail":"Internal server error"}` with an
`X-Error-ID` correlating to sanitized application logs. Expected domain errors
retain their existing contracts. CORS exposes `Retry-After` and `X-Error-ID` to
configured frontend origins. Internal tracebacks are not sent to clients, including
in development debug mode.

Media and social-link delivery URLs must be HTTP(S), at most 2,048 characters and
contain no username/password. Unsafe legacy public URL records fail closed and
require correction before their responses can be served.

See [the Phase 12 review](docs/security/phase12-review.md) for the verified controls,
regression coverage and deployment responsibilities, including trusted proxies,
distributed rate limits, slow-upload protection and sanitized infrastructure logs.
