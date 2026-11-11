# Architecture Portfolio Backend — Implementation Plan

## Purpose

This document defines the staged implementation plan for the Architecture Portfolio backend.

Implementation must proceed phase by phase.

The rules in `AGENTS.md` apply to every phase.

Codex must not automatically continue to the next phase after completing the current one.

---

# Status Values

Each phase must use one of the following statuses:

- `PENDING`
- `IN PROGRESS`
- `BLOCKED`
- `COMPLETED`

A phase can only be marked `COMPLETED` when all acceptance criteria and required validation checks pass.

---

# Phase 0 — Foundation / Bootstrap

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv` (Python 3.13.2):

- `python -m pytest`: 9 passed, no warnings.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed.
- `python -m mypy`: passed for all 8 application/test source files.
- `python -m pip check`: passed.

All commands above used `.venv/Scripts/python.exe`. Application startup/shutdown,
health responses, configuration loading and CORS were validated. No database,
authentication or container implementation was introduced. Phase 1 remains pending.

## Objective

Create the initial backend project foundation without introducing database infrastructure or domain functionality.

## Scope

Create the base FastAPI project and development tooling.

The project must use the local `.venv` environment.

## Deliverables

- `.venv` created locally if missing;
- `pyproject.toml`;
- base `app/` package;
- `app/main.py`;
- `app/core/`;
- application configuration using Pydantic Settings;
- `.env.example`;
- `.gitignore`;
- API version prefix;
- health endpoint;
- CORS configuration;
- basic logging configuration;
- pytest configuration;
- Ruff configuration;
- mypy configuration.

## API

Implement:

`GET /api/v1/health`

Expected response example:

```json
{
  "status": "ok"
}
```

## Dependencies

Initial dependencies should include only what is required for this phase.

Expected runtime dependencies:

- FastAPI
- Uvicorn
- Pydantic
- pydantic-settings

Expected development/testing dependencies:

- pytest
- pytest-asyncio
- httpx
- Ruff
- mypy

Database dependencies may be deferred to Phase 1.

## Tests

Required tests:

- application starts successfully;
- health endpoint returns HTTP 200;
- health endpoint returns the expected response structure.

## Acceptance Criteria

- `.venv` is used for all Python commands;
- no global dependency installation is performed;
- FastAPI application starts;
- `/api/v1/health` works;
- configuration loads correctly;
- CORS origins are configurable;
- tests pass;
- Ruff passes;
- mypy passes for implemented code;
- no database code exists yet;
- no authentication exists yet;
- no Docker files exist.

## Completion Condition

Phase is complete when the project foundation is operational and all Phase 0 validation commands pass.

---

# Phase 1 — Database Infrastructure

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv` (Python 3.13.2):

- Full pytest suite: 34 passed, including the PostgreSQL integration test.
- `python -m app.core.check_database`: live PostgreSQL connection verified.
- `python -m alembic heads`: passed; no revisions yet.
- `python -m alembic current`: passed against the configured PostgreSQL database.
- `python -m alembic upgrade head --sql`: passed offline; no migration applied.
- `python -m ruff check .` and `python -m ruff format --check .`: passed.
- `python -m mypy`: passed for all 16 application, migration and test source files.
- `python -m pip check`: passed.

All Python commands used `.venv/Scripts/python.exe`. The integration run supplied
`TEST_DATABASE_URL` in memory from the locally configured settings without printing
credentials. Sessions, transaction cleanup, request isolation, engine disposal,
Windows-compatible event loops and Alembic configuration are covered by tests.
No domain models, domain revisions, authentication or container files were added.
The approved SQL and DBML remain unchanged. Phase 2 remains pending.

## Objective

Configure PostgreSQL connectivity and asynchronous SQLAlchemy infrastructure.

## Dependencies

Requires:

- Phase 0 completed.

## Source of Truth

Before implementation, read:

- `docs/database/schema.sql`
- `docs/database/schema.dbml`

## Scope

Implement:

- SQLAlchemy 2.x;
- Psycopg 3;
- async database engine;
- async session factory;
- declarative ORM base;
- FastAPI database session dependency;
- database configuration through environment variables;
- database connection verification strategy;
- Alembic initialization and configuration.

## Required Dependencies

Expected additions:

- SQLAlchemy 2.x
- Psycopg 3
- Alembic

## Configuration

Add configuration for:

`DATABASE_URL`

Use an async-compatible PostgreSQL SQLAlchemy URL.

## Database Session Requirements

Use:

- `AsyncEngine`;
- `AsyncSession`;
- one session per request scope;
- safe rollback behavior;
- correct session closing.

Do not create a shared global `AsyncSession`.

## Alembic

Configure Alembic to support:

- PostgreSQL;
- project schemas;
- SQLAlchemy metadata;
- async application configuration where appropriate.

Do not generate the initial domain migration yet unless needed purely to validate configuration.

## Tests

Required tests should cover:

- database configuration parsing;
- database session infrastructure where practical;
- application startup without session leakage.

Integration tests requiring a live PostgreSQL database should be clearly separated if introduced.

## Acceptance Criteria

- SQLAlchemy async infrastructure is configured;
- Psycopg 3 is used;
- database sessions are injectable through FastAPI;
- Alembic is initialized;
- configuration contains no hardcoded secrets;
- no domain ORM models are implemented yet;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when the project can safely establish PostgreSQL sessions and Alembic is ready for model migrations.

---

# Phase 2 — SQLAlchemy Models

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv`:

- `python -m pytest -q`: 76 passed, 1 skipped. The optional PostgreSQL
  infrastructure integration test requires `TEST_DATABASE_URL`, absent in this run.
- Subsequent requested integration run: `tests/test_database_integration.py -q`
  passed (1 test). `TEST_DATABASE_URL` was supplied in process memory from local
  settings without printing credentials. Live connectivity, recovery after a SQL
  error and connection-pool cleanup were verified; no schema or data was changed.
- `python -m pytest tests/test_models.py -q`: all 43 model tests passed.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (33 files).
- `python -m mypy`: passed (29 source files).

All commands used `.venv/Scripts/python.exe`. All 17 typed models are registered
through `app.models` and loaded by Alembic. Tests compare the complete column,
default, constraint and index contract against the approved SQL; verify all 14
foreign-key relationships and their inverse mappings; and configure mappers in a
fresh process with warnings treated as errors.

Created `app/models.py`, module packages and `models.py` files under auth,
portfolio, media, content and contact, and `tests/test_models.py`. Updated
`app/core/database.py`, `alembic/env.py`, `tests/test_database.py`,
`tests/test_alembic.py`, `README.md` and this plan. No dependencies or migration
revisions were added, and the approved SQL/DBML remain unchanged.

Relationships require explicit loading for asynchronous use and delegate physical
delete actions to database foreign keys. Association objects preserve link data.
The README documents JSON null handling, the `asset_metadata` attribute, database
defaults and trigger-generated timestamps. No application services or API routes
were added. Phase 3 remains pending: create/review the initial migration, install
schemas/functions/triggers and validate constraints against PostgreSQL.

## Objective

Implement SQLAlchemy ORM models matching the approved relational design.

## Dependencies

Requires:

- Phase 1 completed.

## Source of Truth

Read before implementation:

- `docs/database/schema.sql`
- `docs/database/schema.dbml`

Do not alter the relational design without explicit approval.

## Schemas

Implement tables under:

- `auth`
- `portfolio`
- `media`
- `content`
- `contact`

## Required Models

### Auth

- `app_user`
- `refresh_token`

### Portfolio

- `project`
- `category`
- `project_category`
- `tag`
- `project_tag`
- `project_attribute`
- `project_media`
- `project_section`
- `project_section_media`

### Media

- `media_asset`

### Content

- `profile`
- `social_link`
- `service`
- `site_setting`

### Contact

- `contact_message`

## Model Requirements

Use SQLAlchemy 2.x typed models.

Use:

- `Mapped[...]`
- `mapped_column(...)`

Correctly implement:

- primary keys;
- composite primary keys;
- foreign keys;
- indexes;
- unique constraints;
- relationships;
- PostgreSQL schemas;
- nullable rules;
- timestamp fields;
- JSONB;
- INET;
- NUMERIC;
- UUID;
- cascade behavior.

Do not replace database constraints with ORM-only validation.

## Tests

Required tests:

- ORM metadata contains all required schemas and tables;
- important foreign keys exist;
- relationships map successfully;
- model imports do not produce mapper errors.

## Acceptance Criteria

- all approved tables are represented;
- ORM definitions match the SQL design;
- model relationships are correct;
- no migration is treated as complete yet;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when the entire relational model is faithfully represented by SQLAlchemy.

---

# Phase 3 — Initial Migration & Database Validation

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv`:

- Full pytest suite with both PostgreSQL test variables supplied securely in
  process memory: 93 passed, no skips.
- Migration integration suite: 15 passed in disposable PostgreSQL databases.
- Upgrade from an empty database, downgrade to base and upgrade again: passed.
- PostgreSQL catalog comparison against a separate database created from
  `docs/database/schema.sql`: identical schemas, tables, columns, defaults,
  constraints, indexes, comments, timestamp function, triggers and extension.
- Offline upgrade and downgrade SQL generation: passed through Alembic tests.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (37 files).
- `python -m mypy`: passed (33 source files).
- Local database: `alembic upgrade head` succeeded; `alembic current` reports
  `0001_initial_schema (head)`; `alembic check` reports no new operations.

All commands used `.venv/Scripts/python.exe`. Created the self-contained revision
`alembic/versions/0001_initial_schema.py`, `tests/migration_support.py`,
`tests/test_migrations_integration.py` and `tests/__init__.py`. Updated Alembic's
environment to accept a supplied connection, Alembic tests, the integration marker
description in `pyproject.toml`, the migration README, the main README and this
plan. Added the approved table comments to portfolio, media and content model
metadata so autogeneration does not propose removing those comments.

The migration was generated from the ORM operations and reviewed against the SQL;
schemas, pgcrypto, timestamp function, ten triggers and schema comments were added
explicitly. No application-model imports or design-file reads occur in the revision.
No dependencies or approved database design were changed.

Downgrade permanently removes domain tables/data, the timestamp function and the
five schemas without CASCADE; it retains the potentially shared pgcrypto extension.
Downgrade was executed only in disposable test databases, which were removed on
teardown. The configured local database was empty before its additive upgrade.
Migration tests require a CREATEDB-capable role and skip unless
`MIGRATION_TEST_ADMIN_URL` is supplied. No known Phase 3 blocker remains.
Phase 4 (authentication and session management) remains pending.

## Objective

Create and validate the initial Alembic migration for the complete approved database schema.

## Dependencies

Requires:

- Phase 2 completed.

## Scope

Generate and review the initial migration.

The migration must correctly create:

- schemas;
- tables;
- primary keys;
- foreign keys;
- check constraints;
- indexes;
- unique indexes;
- PostgreSQL partial indexes.

## Important PostgreSQL Rules

Verify the migration correctly implements special constraints including:

- case-insensitive user email uniqueness;
- active project slug uniqueness;
- one `COVER` per project;
- one active profile;
- project soft-delete slug behavior;
- allowed status values;
- allowed visibility values;
- allowed media types;
- allowed media roles;
- allowed project section types;
- allowed contact statuses.

## Migration Validation

Run:

- upgrade from an empty database;
- downgrade when feasible;
- upgrade again.

Compare resulting schema against:

`docs/database/schema.sql`

Do not accept Alembic autogenerate output without manual review.

## Tests

Required:

- migration upgrade succeeds;
- expected tables exist;
- expected schemas exist;
- critical indexes exist;
- representative constraint violations are rejected.

## Acceptance Criteria

- migration creates the approved schema;
- migration is reviewed;
- PostgreSQL-specific features are present;
- no unexpected schema differences remain;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when an empty PostgreSQL database can be migrated to the complete initial schema reliably.

---

# Phase 4 — Authentication & Session Management

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv`:

- Full pytest suite with PostgreSQL infrastructure, migration and authentication
  integration tests enabled: 146 passed, no skips.
- Local administrator command tests after the final typing adjustment: 4 passed.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (50 files).
- `python -m mypy`: passed (46 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

All commands used `.venv/Scripts/python.exe`. Created:

- `app/core/security.py`, `app/core/exceptions.py`, `app/core/errors.py`;
- `app/modules/auth/schemas.py`, `repository.py`, `service.py`, `dependencies.py`,
  `router.py`, `create_admin.py`;
- `tests/test_security.py`, `tests/test_auth_api.py`,
  `tests/test_auth_integration.py`, `tests/test_create_admin.py`.

Modified `app/main.py`, `app/core/config.py`, `.env.example`, `pyproject.toml`,
`tests/conftest.py`, `tests/test_config.py`, `README.md` and this plan.
Declared/installed PyJWT and pwdlib[argon2] in `.venv` (plus their transitive
dependencies). Generated a random signing secret in the ignored local `.env`
because none was configured there; it was never printed. No account was created
in the local development database, and no migration or approved schema changed.

Implemented login, refresh, logout and current-user endpoints under `/api/v1/auth`.
Business logic lives in the service, persistence in the repository, and security
primitives in core. Argon2 verification runs off the event loop, unknown-user login
performs dummy verification, and hashes are upgraded when needed. Configuration
requires a secret and explicitly restricts JWT signing to HS256. Tokens require
issuer, audience, type, timestamps, user/session UUIDs and a unique token ID.

Refresh secrets are random and only SHA-256 hashes are stored. Row locks and a
single transaction make rotation atomic; concurrent refresh has one winner, and
a failed insert rolls back revocation. Rotation keeps the original absolute
session deadline. JWTs are tied to a live refresh-session record, so rotation,
logout, expiry and user deactivation invalidate access. Logout is idempotent and
scoped to one session. Request errors omit submitted secrets, response models
exclude internal hashes, and auth responses disable caching.

The local, interactive provisioning command is a minimal way to create the first
administrator without editing password hashes or adding public registration.
It uses hidden password prompts and rejects duplicate emails. Existing accounts
are never overwritten. The README documents setup, contracts and frontend token
replacement/serialization requirements.

Known scope limits: no token-family linkage or replay grace period exists in the
approved schema; replay of a rotated token is rejected without revoking its
replacement. Clients must use the latest refresh token for logout. Rate limiting,
password recovery, MFA, session-list administration and expired-session cleanup
are not implemented in this phase. No blocking Phase 4 issue remains.
Phase 5 (media module) remains pending.

## Objective

Implement secure administrator authentication.

## Dependencies

Requires:

- Phase 3 completed.

## Scope

Implement:

- password hashing;
- administrator login;
- access token generation;
- refresh-token rotation;
- logout;
- token revocation;
- current authenticated user endpoint;
- authentication dependency;
- active-user validation.

## Security

Use Argon2 through `pwdlib`.

Use PyJWT for JWT tokens.

Do not store raw passwords.

Do not store raw refresh tokens.

Store only refresh-token hashes.

## Suggested Endpoints

```text
POST /api/v1/auth/login
POST /api/v1/auth/refresh
POST /api/v1/auth/logout
GET  /api/v1/auth/me
```

Exact request and response contracts may be refined during implementation.

## Refresh Token Requirements

Implement:

- expiration;
- revocation;
- rotation;
- database-backed session validation.

A rotated or revoked token must not remain valid.

## Tests

Required tests:

- valid login;
- invalid password;
- unknown user;
- inactive user;
- access token validation;
- refresh token success;
- revoked token rejection;
- expired token rejection;
- refresh rotation;
- logout revocation;
- protected endpoint without credentials;
- protected endpoint with valid credentials.

## Acceptance Criteria

- password security is correct;
- JWT secrets come from configuration;
- raw refresh tokens are never persisted;
- session lifecycle works;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when authenticated administrator sessions operate securely.

---

# Phase 5 — Media Module

**Status:** COMPLETED

Validation completed on 2026-09-30 using local `.venv`:

- Full pytest suite with PostgreSQL infrastructure, migrations, authentication and
  media integration tests enabled: 189 passed, no skips.
- Media coverage: 33 schema/HTTP tests and 10 PostgreSQL integration tests,
  including a concurrent profile-reference/deletion check.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (59 files).
- `python -m mypy`: passed (55 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

All commands used `.venv/Scripts/python.exe`. Created:

- `app/modules/media/schemas.py`, `repository.py`, `service.py`,
  `dependencies.py`, `router.py`, `storage.py`;
- `tests/test_media_schemas.py`, `tests/test_media_api.py`,
  `tests/test_media_integration.py`.

Modified `app/main.py`, `app/core/exceptions.py`, `app/core/errors.py`, `README.md`
and this plan. No dependencies, migrations, ORM definitions or approved database
design were changed. Tests used disposable databases; no development media data
was created or removed.

Implemented protected administrative list/detail/create/PATCH/delete operations
at `/api/v1/admin/media`. Listings use bounded limit/offset pagination, a type
filter and stable created_at/UUID ordering. Schemas validate the five approved
types, nullable positive dimensions, nonnegative size, HTTP(S) URLs, MIME syntax,
text limits and JSON object metadata. PATCH changes descriptive fields only;
omitted values are preserved and explicit null clears them. Internal storage
fields appear only in explicit administrative response models.

Services own write commits/rollback on the same request transaction used by the
authentication read. Duplicate storage objects return 409 and missing IDs 404.
Deletion locks the asset and rejects all project, section, photo and CV references,
including soft-deleted projects and inactive profiles. Profile references are
treated as in use even though their database FKs allow SET NULL. Row locks and
PostgreSQL foreign keys prevent concurrent reference creation from being silently
detached by deletion; the integration suite exercises this behavior.

The asynchronous StorageProvider protocol isolates future streaming upload and
remote-deletion adapters. Its StorageLocation contract is reused by the creation
schema; no provider-specific SDK, credentials or implementation was selected.
Known scope limit: current operations manage metadata only. They do not upload,
fetch or inspect file content, and DELETE does not remove external storage objects.
Those operations require a future provider integration. No Phase 5 blocker remains.
Phase 6 (portfolio core) remains pending.

## Objective

Implement the backend domain and administration logic for media assets.

## Dependencies

Requires:

- Phase 4 completed.

## Scope

Implement:

- media asset schemas;
- repository;
- service;
- administrative API;
- media metadata validation;
- provider abstraction.

Do not tightly couple this phase to Cloudinary, S3, or R2 unless a provider is explicitly selected.

## Administrative Operations

Support:

- list media assets;
- retrieve asset;
- create asset metadata;
- update editable metadata;
- remove unused assets where allowed.

Do not delete assets that are still referenced where database rules prohibit it.

## Media Types

Support approved values:

- IMAGE
- VIDEO
- PDF
- MODEL_3D
- DOCUMENT

## Tests

Required:

- create metadata;
- read asset;
- update metadata;
- reject invalid type;
- reject invalid dimensions;
- prevent deletion when referenced;
- authorization checks.

## Acceptance Criteria

- domain is storage-provider independent;
- database restrictions are respected;
- administrative operations are protected;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when media metadata can be safely managed through the backend.

---

# Phase 6 — Portfolio Core

**Status:** COMPLETED

## Implementation Notes

Implemented protected administrative CRUD for projects, categories and tags;
transactional category/tag assignments; project attributes; project media links;
cover selection/replacement; and partial batch ordering. All collection routes
are paginated. Project filters support status, visibility, featured flag, category
and tag. Deletes preserve project rows and relationships through soft deletion.

Publication requires an image cover and valid project input. The first publication
timestamp is retained across state changes. Published covers must be replaced
atomically or the project unpublished before removal. Taxonomy deletion refuses
any assigned record, including historical soft-deleted project references.
Row locks serialize project mutations and protect reference targets from concurrent
deletion. Database uniqueness remains authoritative; expected conflicts return 409.

Created eight implementation files in `app/modules/portfolio/`: `schemas.py`,
`repository.py`, `transactions.py`, `service.py`, `taxonomy_service.py`,
`relations_service.py`, `dependencies.py` and `router.py`, plus three
test files: `tests/test_portfolio_schemas.py`, `tests/test_portfolio_api.py`, and
`tests/test_portfolio_integration.py`. Modified `app/main.py`,
`app/core/exceptions.py`, `app/core/errors.py`, `README.md` and this plan.
No dependencies, ORM models, approved schema documents or migrations changed.

Validation: the complete suite passed with **231 tests**, including isolated
PostgreSQL authentication, media, portfolio and migration integration tests.
Ruff passed, its format check passed (70 files), mypy passed (66 source files),
and `alembic check` found no new upgrade operations. Tests cover all 31 portfolio
route operations requiring authentication, CRUD, publication, visibility, slug
reuse after soft deletion, conflicts, assignments, parent scoping, pagination,
cover restrictions and transaction rollback during failed batch operations.

API details and limits are documented in README. No public portfolio routes,
restore/purge operations or storage uploads are added. Phase 7 (dynamic project
sections) remains pending.

## Objective

Implement the core project management domain.

## Dependencies

Requires:

- Phase 5 completed.

## Scope

Implement management of:

- projects;
- categories;
- tags;
- project attributes;
- project media relationships.

## Project Operations

Support administrative operations for:

- create;
- retrieve;
- update;
- list;
- soft delete;
- feature/unfeature;
- publishing state;
- visibility state;
- ordering.

## Category Operations

Support:

- create;
- update;
- list;
- enable/disable;
- delete when safe.

## Tag Operations

Support:

- create;
- update;
- list;
- delete when safe.

## Project Attribute Operations

Support:

- add;
- edit;
- remove;
- reorder.

## Project Media

Support:

- attach asset;
- detach asset;
- assign role;
- reorder;
- select cover.

Database constraints remain authoritative.

## Publishing Rules

Before publishing a project, validate required business conditions.

At minimum evaluate:

- title;
- valid slug;
- project cover;
- publication state;
- visibility.

Additional requirements may be defined during implementation.

## Tests

Required:

- project CRUD;
- slug conflicts;
- soft deletion;
- project publication;
- visibility;
- category assignment;
- tag assignment;
- attributes;
- media attachment;
- single-cover behavior;
- authorization.

## Acceptance Criteria

- administrators can fully manage core project data;
- soft delete is respected;
- publication rules are enforced;
- relational constraints are respected;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when the project domain can be fully managed without project sections.

---

# Phase 7 — Dynamic Project Sections

**Status:** COMPLETED

## Implementation Notes

Implemented eleven authenticated administrative section/media operations under
`/api/v1/admin/projects/{project_id}/sections`. Sections support CRUD, visibility,
paginated listing and transactional partial ordering. Media support attachment,
caption/order edits, removal, pagination and ordering using the existing composite
key. Section create/PATCH can supply a complete media set for atomic type/content/
media changes. The existing database model and migrations remain unchanged.

Visible TEXT/QUOTE require nonblank content and no media; IMAGE/VIDEO/MODEL_3D
require exactly one compatible asset; GALLERY requires 1–100 images; SPLIT requires
text plus one image. Hidden sections can be incomplete, but media type and maximum
count restrictions still apply. Parent project locks serialize all edits and
prevent concurrent removal of the last visible gallery asset. Section deletion
cascades links only; project soft deletion retains sections and blocks access.

Created `app/modules/portfolio/section_schemas.py`, `section_repository.py`,
`section_service.py`, `section_router.py`, `tests/test_section_schemas.py` and
`tests/test_sections_integration.py`. Modified the portfolio `router.py` and
`transactions.py`, `tests/test_portfolio_api.py`, `README.md` and this plan.
No dependencies were added or removed; no models, schema documents or migrations
changed. README documents the contracts, validation rules and limits.

Validation: **250 tests passed** in the complete suite, including PostgreSQL
integration and migration tests. Ruff passed; format check passed (76 files);
mypy passed (72 source files); `alembic check` detected no new upgrade operations.
The new tests cover all seven section types, visibility, compatible media,
ownership, soft-deleted parents, CRUD, ordering, pagination, atomic rollback,
deletion cascades and concurrent last-asset removal. Authentication is verified
for all 42 portfolio operations, including the eleven section operations.

Public section delivery remains scoped to Phase 10. Phase 8 (profile, services,
social links and site settings) remains pending.

## Objective

Implement dynamic content sections used to compose each project page.

## Dependencies

Requires:

- Phase 6 completed.

## Scope

Implement:

- project section CRUD;
- project section ordering;
- visibility;
- section-specific validation;
- section media relationships;
- media ordering inside sections.

## Supported Types

- TEXT
- IMAGE
- GALLERY
- VIDEO
- MODEL_3D
- QUOTE
- SPLIT

## Validation

Validate requirements appropriate to each section type.

Examples:

- IMAGE should have an appropriate image asset;
- GALLERY may contain multiple media assets;
- MODEL_3D should use compatible media metadata;
- TEXT should contain meaningful textual content.

Do not hardcode frontend presentation logic into backend services.

## Tests

Required:

- create section;
- update section;
- delete section;
- reorder sections;
- hide/show section;
- assign media;
- reorder media;
- validate section types;
- reject invalid media combinations.

## Acceptance Criteria

- sections can construct flexible project content;
- ordering behaves correctly;
- database rules are respected;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when administrators can fully compose project detail pages using structured sections.

---

# Phase 8 — Profile, Services, Social Links & Site Settings

**Status:** COMPLETED

Completion validated on 2026-09-30 using `.venv/Scripts/python.exe`:

- Full pytest suite: 287 passed, no skips, including PostgreSQL integration and
  migration tests. Test database URLs were supplied from local settings in process
  memory without printing credentials; domain tests used disposable databases.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (85 files).
- `python -m mypy`: passed (81 source files).
- `python -m alembic check`: no new upgrade operations detected.

The existing Phase 8 implementation was reviewed against the approved SQL/DBML
and validated without requiring further code changes. It provides 18 authenticated
administrative operations for the active profile, photo/CV relationships, social
links, services and allowlisted site settings. Tests cover concurrent profile
initialization, media compatibility, CRUD, visibility, pagination, transactional
ordering, conflicts, authorization and settings validation/upsert.

Phase implementation files: `app/modules/content/schemas.py`, `repository.py`,
`service.py`, `settings_service.py`, `transactions.py`, `router.py`, and
`tests/test_content_schemas.py`, `tests/test_content_api.py`,
`tests/test_content_integration.py`. Integration and API documentation are in
`app/main.py` and `README.md`. This completion pass modified only `PLANS.md`.
No dependencies, models, approved schema documents or migrations changed.

Business logic and persistence remain separate from routes. PostgreSQL enforces
the single-active-profile constraint; ordering is atomic, and settings use an
explicit three-key allowlist with typed values. Media validation checks metadata,
not file contents; email validation checks basic syntax without DNS. Public
content retrieval remains scoped to Phase 10. No known Phase 8 blocker remains.
Phase 9 (contact messages) remains pending.

## Objective

Implement editable global portfolio content.

## Dependencies

Requires:

- Phase 7 completed.

## Scope

Implement:

- professional profile;
- profile media;
- CV relationship;
- social links;
- services;
- global site settings.

## Profile

Support:

- retrieve active profile;
- update profile;
- profile photograph;
- CV media relationship.

Respect the single-active-profile constraint.

## Social Links

Support:

- create;
- update;
- delete;
- reorder;
- show/hide.

## Services

Support:

- create;
- update;
- delete;
- reorder;
- show/hide.

## Site Settings

Support safe management of approved configuration keys.

Do not allow arbitrary settings to become an unsafe mechanism for storing secrets or executable content.

## Tests

Required:

- profile update;
- active profile constraint;
- social link CRUD;
- social link ordering;
- service CRUD;
- service visibility;
- site setting retrieval/update;
- authorization.

## Acceptance Criteria

- administrators can manage global site content;
- profile rules are enforced;
- public-safe configuration remains separate from secrets;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when all non-project public content can be managed through the backend.

---

# Phase 9 — Contact Messages

**Status:** COMPLETED

Implemented and validated on 2026-09-30 using `.venv/Scripts/python.exe`.

- Full pytest suite: 319 passed, no skips, including PostgreSQL and migration tests.
- Focused contact suite: 32 passed (schemas, API and PostgreSQL integration).
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (93 files).
- `python -m mypy`: passed (89 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

Created `app/modules/contact/schemas.py`, `dependencies.py`, `repository.py`,
`service.py`, `router.py`, and `tests/test_contact_schemas.py`,
`tests/test_contact_api.py`, `tests/test_contact_integration.py`. Modified
`app/main.py`, `pyproject.toml`, `README.md` and this plan. Added the runtime
dependency `email-validator>=2.2,<3` for Pydantic EmailStr; its installation also
added transitive dependency dnspython. No dependencies were removed. No models,
approved SQL/DBML or migrations changed.

Public POST returns a minimal acknowledgement after commit. Administrative routes
provide authenticated listing, status filtering, pagination, detail and explicit
READ/REPLIED/ARCHIVED/SPAM updates. GET never marks a message read. Row locks and
database time preserve first-read/first-reply timestamps across concurrent updates;
reclassification retains history. IP/user-agent metadata is absent from API
responses. The existing contact_enabled setting controls submissions.

Tests cover invalid input, metadata privacy, authorization, missing messages,
status transitions, repeated/concurrent replies, pagination, filters, disabled
submissions and a replacement submission policy returning 429. Test database URLs
were supplied in process memory without printing credentials; integration tests
used disposable PostgreSQL databases.

The submission dependency provides a boundary for future rate limiting, spam
checks and CAPTCHA. No limiter/provider is enabled yet; request-body limits and
trusted proxy configuration remain deployment/hardening work. Marking REPLIED
does not send email. No known Phase 9 blocker remains. Phase 10 (public portfolio
API) remains pending and was not started.

## Objective

Implement public contact submissions and administrative contact message management.

## Dependencies

Requires:

- Phase 8 completed.

## Public Scope

Implement a public contact endpoint.

Example:

`POST /api/v1/public/contact`

Validate:

- name;
- email;
- optional phone;
- optional subject;
- message.

## Administrative Scope

Support:

- list messages;
- retrieve message;
- mark as read;
- mark as replied;
- archive;
- mark as spam.

## Security

Prepare the design for:

- rate limiting;
- spam protection;
- CAPTCHA or equivalent provider integration if later requested.

Do not expose administrative metadata publicly.

## Tests

Required:

- valid contact submission;
- invalid email;
- empty message rejection;
- administrative listing;
- status transitions;
- unauthorized administrative access.

## Acceptance Criteria

- public submission works;
- message statuses work correctly;
- admin operations require authentication;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when contact messages can be submitted publicly and managed privately.

---

# Phase 10 — Public Portfolio API

**Status:** COMPLETED

Implemented and validated on 2026-09-30 using `.venv/Scripts/python.exe`:

- Full pytest suite: 325 passed, no skips, including PostgreSQL and migration tests.
- Initial focused public API suite: 5 passed; the subsequent full suite also
  passed the added live-publication/slug-reuse integration test.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (104 files).
- `python -m mypy`: passed (100 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

Created `public_schemas.py`, `public_repository.py`, `public_service.py` and
`public_router.py` in both `app/modules/portfolio/` and `app/modules/content/`,
plus `app/modules/media/public_schemas.py`, `tests/test_public_api.py` and
`tests/test_public_integration.py`. Modified `app/main.py`, `README.md`, this plan,
`tests/test_content_api.py` and `tests/test_portfolio_api.py`; the latter tests no
longer expect the newly implemented public routes to be absent. No dependencies,
ORM models, approved schema documents or migrations changed.

Nine read-only public routes expose project cards, featured projects, slug detail,
categories, tags, active profile, visible services/social links and allowlisted
settings. Dedicated public models omit internal IDs, storage identity, arbitrary
metadata and administrative fields. Discovery requires PUBLISHED/PUBLIC/nondeleted;
direct slug access additionally permits PUBLISHED UNLISTED projects. Categories
must be active; global categories/tags must belong to discoverable projects.
Hidden sections and inactive/hidden content do not enter public responses.

Project detail composes ordered attributes, media and all seven section types.
Queries eagerly load relationships: tests verify four SELECTs for project pages
of one and three items, seven for a composed detail and one for profile with media.
Collections are paginated; the single-project authored composition is returned
complete. Responses use no-store to avoid stale HTTP caching after visibility
changes. URLs are registered delivery URLs; storage-provider access control and
signed URL generation are outside this phase.

Tests exercise the complete status/visibility/deletion matrix, direct unlisted
access, private denial even with an admin token, live visibility changes, slug
reuse, filtering, pagination, ordering, media privacy and content visibility.
Integration databases were disposable; credentials were supplied only in process
memory. No known Phase 10 blocker remains. Phase 11 (administrative API completion)
remains pending and was not started.

## Objective

Expose optimized read-only endpoints for the Angular public website.

## Dependencies

Requires:

- Phase 9 completed.

## Scope

Create public endpoints for:

- project listings;
- project detail by slug;
- featured projects;
- categories;
- tags when appropriate;
- profile;
- services;
- social links;
- public site settings.

## Project Visibility Rules

Normal project listings must only return:

`status = PUBLISHED`

`visibility = PUBLIC`

`deleted_at IS NULL`

Unlisted projects:

- must not appear in regular listings;
- may be retrieved directly if intended by business rules.

Private projects:

- must never be accessible anonymously.

## Public Responses

Use dedicated public response models.

Do not expose:

- administrative timestamps unless useful;
- internal IDs unless needed;
- storage keys;
- user records;
- internal metadata;
- deleted state;
- unpublished state.

## Performance

Avoid N+1 queries.

Use appropriate eager loading.

Paginate project listings.

## Tests

Required:

- published public project appears;
- draft project does not appear;
- private project does not appear;
- deleted project does not appear;
- unlisted project does not appear in listing;
- direct unlisted access behavior;
- project detail structure;
- category filtering;
- pagination.

## Acceptance Criteria

- Angular can consume the complete public portfolio through this API;
- visibility rules cannot be bypassed;
- queries are reasonably efficient;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when the entire public portfolio can be rendered without direct database knowledge.

---

# Phase 11 — Administrative API Completion

**Status:** COMPLETED

Completed and validated on 2026-10-01 using `.venv/Scripts/python.exe`.

- Full pytest suite: 340 passed, no skips, including PostgreSQL and migration tests.
- After adding six nested collection validation cases, the focused administrative
  API suite passed all 14 tests. The full run had collected tests before that edit;
  together these runs cover all 346 current tests.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (107 files).
- `python -m mypy`: passed (103 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

The existing in-progress implementation was reviewed and validated. It provides
consistent limit/offset envelopes, literal case-insensitive search, allowlisted
sorting, deterministic tie breakers and resource-specific filters across seven
administrative collections. Project taxonomy collections share these conventions;
authored child collections retain pagination and transactional ordering. Routes
delegate business logic to services and persistence to repositories. All admin
operations require authentication and explicit response contracts; handled errors
and successful admin responses prevent caching.

Implementation is in `app/core/listing.py`, `app/core/errors.py` and the portfolio,
media, content and contact schemas, routers, services and repositories. Existing
cross-module tests in `tests/test_admin_api.py` and `tests/test_admin_integration.py`
cover authentication, pagination, filtering, search escaping and every allowed
sort. Module suites cover CRUD, conflicts and domain rules. This completion pass
modified `tests/test_admin_api.py`, `README.md` and `PLANS.md`; it created no files
and changed no dependencies, ORM models, approved SQL/DBML or migrations.

Added six cases for nested pagination validation and documented the administrative
contract for Angular, including search fields, filters, defaults and status codes.
Test database credentials were supplied only in process memory; domain integration
tests used disposable PostgreSQL databases. No Git metadata exists in this working
directory, so a Git diff was unavailable.

No dashboard was added because no frontend aggregate requirement was specified.
Offset pagination can shift under concurrent changes. No known Phase 11 blocker
remains. Phase 12 (testing, security and hardening) is pending and was not started.

## Objective

Complete and standardize the API used by the Angular administration panel.

## Dependencies

Requires:

- Phase 10 completed.

## Scope

Review all administrative modules for consistency.

Ensure consistent support for:

- pagination;
- filtering;
- sorting;
- administrative search where useful;
- validation errors;
- authorization;
- response schemas;
- consistent status codes.

## Administrative Dashboard

Expose aggregated data only if genuinely required by the frontend.

Possible examples:

- total projects;
- draft count;
- published count;
- unread message count;
- recent messages.

Do not introduce unnecessary analytics.

## Tests

Required:

- authenticated administrative access;
- unauthorized access;
- pagination consistency;
- filtering;
- representative validation conflicts;
- dashboard queries if implemented.

## Acceptance Criteria

- administrative endpoints follow consistent conventions;
- Angular administration panel has all required backend operations;
- no domain logic remains in routers;
- tests pass;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when the administration panel can manage all supported backend functionality.

---

# Phase 12 — Testing, Security & Hardening

**Status:** COMPLETED

Implemented and validated on 2026-10-01 using `.venv/Scripts/python.exe`.

- Final full pytest suite: 370 passed, no skips, including PostgreSQL integration
  and migration tests (225.74 seconds). The preceding full run passed 369 tests;
  the final run includes the added deployment-root-path regression.
- Initial focused security/configuration/media/API suite: 99 passed. Final focused
  request-hardening suite: 9 passed.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed.
- `python -m mypy`: passed (107 source files).
- `python -m pip check`: passed.
- `python -m alembic check`: no new upgrade operations detected.

Added actual HTTP body-size enforcement before parsing/persistence, bounded
per-peer/per-worker quotas for auth and contact POSTs, safe unexpected-error JSON
and sanitized diagnostic logging. Shared validation rejects invalid database text,
unencodable passwords and credential-bearing delivery URLs. Public URL models also
reject unsafe legacy values; JWT decoding rejects overflowing numeric claims.
The existing authentication, authorization, public visibility, query efficiency,
transactions, relational constraints and concurrency protections were reviewed
and exercised by the full suite. The added regressions raise coverage from 346
to 370 test cases.

Created (5 files):

- `app/core/error_boundary.py`
- `app/core/request_limits.py`
- `app/core/validation.py`
- `tests/test_request_hardening.py`
- `docs/security/phase12-review.md`

Modified (20 files):

- `.env.example`, `README.md`, `PLANS.md`
- `app/main.py`, `app/core/config.py`, `app/core/security.py`
- `app/modules/auth/schemas.py`
- `app/modules/contact/dependencies.py`
- `app/modules/content/schemas.py`, `app/modules/content/public_schemas.py`
- `app/modules/media/storage.py`, `app/modules/media/public_schemas.py`
- `tests/conftest.py`, `tests/test_auth_api.py`, `tests/test_auth_integration.py`
- `tests/test_config.py`, `tests/test_contact_integration.py`
- `tests/test_media_schemas.py`, `tests/test_public_integration.py`, `tests/test_security.py`

No dependencies were added or removed. No ORM models, approved SQL/DBML or
migrations changed. Infrastructure controls use pure ASGI middleware; business
logic remains in services and database operations in repositories. Body buffering
is bounded per request, counters belong to the app instance, and CORS wraps the
error/limit responses. Test credentials were supplied only in process memory;
domain tests used disposable databases. The existing configured database was used
for read-only connectivity/schema checks. Git tracking could not be inspected
because this directory has no Git metadata.

The review in `docs/security/phase12-review.md` records evidence and deployment
responsibilities. Local quotas reset on restart and are independent across workers;
distributed quotas, trusted proxies, TLS, upload timeouts and infrastructure log
sanitization require deployment configuration. CAPTCHA, binary scanning and storage
ACL/signing are not implemented. Unsafe legacy public URLs must be corrected;
they produce a generic 500 rather than exposing credentials. No known critical
application issue or Phase 12 blocker remains within the reviewed scope. This is
not a penetration test or dependency-vulnerability certification. Phase 13 (API
documentation and frontend handoff) remains pending and was not started.

## Objective

Perform backend-wide quality, security, and reliability hardening.

## Dependencies

Requires:

- Phase 11 completed.

## Scope

Review:

- authentication;
- token handling;
- authorization;
- CORS;
- validation;
- logging;
- error handling;
- database transaction handling;
- sensitive information exposure;
- query efficiency;
- concurrency-sensitive operations;
- media validation;
- contact form abuse risks.

## Test Coverage

Expand coverage for:

- domain edge cases;
- invalid state transitions;
- authentication failures;
- refresh-token attacks;
- visibility bypass attempts;
- database conflicts;
- media references;
- soft-delete edge cases.

## Static Checks

Run full:

- pytest;
- Ruff;
- mypy.

Resolve project-related failures.

## Security Review

Verify:

- no plaintext passwords;
- no plaintext refresh tokens in DB;
- no secrets in source;
- no auth data in logs;
- protected routes require authentication;
- public routes cannot expose private data;
- CORS is configurable;
- SQL injection is not possible through raw user interpolation.

## Acceptance Criteria

- full test suite passes;
- Ruff passes;
- mypy passes;
- no known critical backend security issue remains;
- error behavior is consistent;
- no sensitive values leak through API responses.

## Completion Condition

Phase is complete when the backend is considered ready for frontend integration and pre-production validation.

---

# Phase 13 — API Documentation & Frontend Handoff

**Status:** COMPLETED

Implemented and validated on 2026-10-01 using `.venv/Scripts/python.exe`.

- Final full pytest suite: 372 passed, no skips (252.93 seconds), including live
  PostgreSQL, migration and domain integration tests.
- First full run: 371 passed, one fixture connection timeout before the first
  administrative integration test. Connectivity recovered and the complete repeat
  passed without changing timeout settings or application behavior.
- Focused OpenAPI tests: 2 passed.
- `python -m ruff check .`: passed.
- `python -m ruff format --check .`: passed (117 files).
- `python -m mypy`: passed (109 source files).
- `python -m pip check`: passed.
- Database connectivity check passed; Alembic current is `0001_initial_schema`
  at head, and `alembic check` detected no new upgrade operations.

Created five files: `app/core/api_docs.py`, `tests/test_openapi.py`,
`docs/development.md`, `docs/api/frontend-handoff.md` and `docs/api/endpoints.md`.
Modified four files: `app/main.py`, `app/modules/auth/dependencies.py`, `README.md`
and this plan. No dependencies, migrations, models or approved SQL/DBML changed.

OpenAPI now describes the API conventions, bearer JWT usage and shared error
vocabulary, with explicit models for sanitized validation errors and documented
Retry-After/WWW-Authenticate/X-Error-ID headers. Error responses are declared per operation; only request middleware errors and
the unexpected-error boundary are shared globally (corrected in the final audit).
Business logic and actual HTTP behavior remain unchanged. Regression tests verify
the 83-operation inventory, security declarations, unique operation IDs, response
contracts and representative HTTP error payloads.

The handoff covers authentication/rotation, public and administrative endpoints,
pagination/search, publication/visibility, media and all seven section types,
partial updates, frontend error handling and an integration smoke workflow.
Local setup documents Python/.venv, PostgreSQL provisioning, configuration,
migrations, administrator creation, startup and validation without containers.
The README links these guides and corrects its migration startup sequence and
CORS method list. Setup commands were reviewed against the current configuration;
connectivity and migration operations were exercised on the existing installation
and empty disposable test databases. A separate clean operating-system installation
and an actual Angular client were not exercised.

No known Phase 13 blocker remains. Existing provider/upload, browser persistence
and deployment limitations are explicitly documented. All planned phases are
complete; frontend implementation and deployment require separately scoped work.

## Objective

Prepare the backend for clean integration with the Angular frontend.

## Dependencies

Requires:

- Phase 12 completed.

## Scope

Review and improve OpenAPI documentation.

Document:

- authentication flow;
- refresh-token behavior;
- public endpoints;
- administrative endpoints;
- pagination format;
- common errors;
- media model;
- project section model;
- visibility rules.

## Environment Documentation

Document local development requirements without Docker.

Include:

- supported Python version;
- `.venv` creation;
- dependency installation;
- environment configuration;
- PostgreSQL configuration;
- Alembic commands;
- application startup;
- test commands;
- Ruff;
- mypy.

## Frontend Handoff

Ensure the Angular application can identify:

- endpoint URLs;
- request schemas;
- response schemas;
- authentication requirements;
- error structures;
- pagination structures.

## Acceptance Criteria

- OpenAPI is clear and accurate;
- setup documentation works from a clean local environment;
- frontend integration requirements are documented;
- full test suite passes;
- Ruff passes;
- mypy passes.

## Completion Condition

Phase is complete when another developer can configure, run, test, and integrate with the backend using the repository documentation.

---

# Final audit corrections — 2026-10-03

Completed the scoped audit corrections without new features or architectural changes:

- Pagination rejects offsets above PostgreSQL's signed bigint maximum with 422,
  including all 19 paginated endpoints.
- PATCH OpenAPI schemas distinguish omission from explicit null using the existing
  nonnullable-field declarations; runtime update semantics are unchanged.
- Frontend handoff documents multiple roles per project/asset, uniqueness on
  `(project_id, media_id, role)` and the independent single-cover restriction.
- The generated OpenAPI inventory contains 83 operations, now regression-tested
  against this plan and the endpoint inventory.
- Ruff excludes only the inaccessible `.pytest_tmp` test artifact directory in
  addition to the existing virtual-environment exclusion; no files were deleted.
- Error responses are selected per operation. Only actual middleware errors
  (400/413) and the unexpected-error boundary (500) remain global.

Created `tests/test_audit_regressions.py`. Modified `tests/test_openapi.py`,
`app/main.py`, `app/core/api_docs.py`, `app/modules/portfolio/schemas.py`,
`app/modules/media/schemas.py`, the auth/media/contact/content/portfolio routers,
the content/portfolio public routers, `app/modules/portfolio/section_router.py`,
`pyproject.toml`, `docs/api/frontend-handoff.md` and this plan.

Validation used only `.venv/Scripts/python.exe`:

- Full pytest suite: **388 passed**, no skips (293.12 seconds), including PostgreSQL
  integration and disposable-database migration tests. Connection variables were
  supplied in process memory without printing credentials.
- Focused audit/OpenAPI suite: 18 passed.
- Ruff check: passed; Ruff format --check: 118 files already formatted.
- mypy: passed, 110 source files.
- Alembic check: no new upgrade operations detected.

No dependencies, ORM models, migrations or approved SQL/DBML changed. No Docker
configuration or subsequent phase was introduced. No known blocker remains for
these corrections. Git diff was unavailable because this directory has no Git metadata.

---

# Phase 14 — Media Storage Integration

**Status:** COMPLETED

Initial inspection and schema approval completed on 2026-10-03. Implementation
uses one additive technical table; the original 17 tables remain unchanged.
The approved design and recovery decisions are recorded in
`docs/database/phase14-storage-proposal.md`. Completion validated on 2026-10-03
using only `.venv/Scripts/python.exe`:

- Full pytest with all PostgreSQL integration enabled: **438 passed, no skips**
  (282.84 seconds), without a real R2 bucket. Tests used fresh temporary directories
  and disposable databases; credentials were supplied only in process memory.
- After the final provider-filter cleanup adjustment, the focused PostgreSQL media
  suite passed all 18 tests (19.78 seconds), and Alembic check remained clean.
- Ruff check and Ruff format --check passed (133 files formatted).
- mypy passed (123 source files); pip check passed.
- Alembic upgrade applied only `0002_storage_operations` to the local database;
  current is at head and check detected no new upgrade operations.
- Disposable migration upgrade/downgrade/upgrade, full SQL catalog comparison and
  Alembic check passed. Original 17 domain tables and their relations are unchanged.
- OpenAPI tests passed for the 89-operation inventory, including binary/redirect
  delivery contracts and authentication declarations.

See `docs/media-storage-phase14-report.md` for the file inventory, configuration,
security/recovery decisions, manual R2 setup and limitations. No later phase started.

## Objective and scope

Extend the existing modular media module with a small storage Protocol, R2/boto3
and local adapters, authenticated direct-upload authorization and confirmation,
private/public delivery, safe deletion and durable recovery. Preserve the modular
monolith and existing administrative metadata contracts where security allows.
Run synchronous provider/file operations outside the event loop. No Docker,
Redis, Celery, Angular implementation or future phase is included.

## Acceptance criteria

- Provider-specific configuration is validated with Pydantic Settings; local mode
  requires no R2 credentials. Secrets and temporary URLs are never persisted/logged.
- Backend-generated staging/destination keys prevent traversal, collisions and
  modification of confirmed objects through reusable PUT URLs.
- Authorization is administrator-bound, expiring and durably consumed; only a
  remotely verified object becomes a definitive media_asset.
- Central format/MIME/size policy validates declaration and actual object metadata.
  GLTF stays disabled until external dependency handling is safe. Document the
  precise extent of content inspection and PUT transfer-size limitations.
- Stable delivery references respect private access and explicitly configured CDN
  delivery; project visibility does not promise immediate CDN revocation.
- All project, section, profile-photo and CV references prevent deletion. Durable
  operation intent supports recovery and bounded explicit orphan cleanup.
- Angular handoff and OpenAPI explain the complete flow, errors, expiry,
  cancellation, constraints and separate bucket/backend CORS configuration.
- Full pytest, Ruff check/format, mypy, Alembic check and OpenAPI validation pass
  using only .venv. Real R2 tests require separate explicit configuration.

## Mandatory tests

Cover valid authorization; unauthenticated rejection; forbidden formats; declared
and actual size limits; unique safe keys; expiry; invalid, reused and cross-admin
authorization; existing/missing objects; MIME/metadata mismatch; correct database
registration; concurrent duplicate confirmation; deletion with/without each
reference type; provider errors; PostgreSQL/provider partial failures and recovery;
provider selection/configuration; local upload/access; existing media contracts;
staging overwrite isolation; cleanup/confirmation concurrency; private delivery
authorization and OpenAPI security declarations. Use fakes/mocks and disposable
PostgreSQL databases, without a real R2 bucket in the normal suite.

The current OpenAPI contract has the 89-operation inventory.

## Completion and limits

No blocking implementation or validation issue remains. Real R2 credentials,
private-bucket permissions, CORS, transfer-duration budgets and scheduled cleanup
remain deployment configuration. Header-only inspection is not full decoding or
malware scanning; GLTF is disabled. Public R2 bucket domains are not enabled;
authorized backend delivery can be fronted by a CDN honoring no-store. Signed GETs
can outlive a visibility change by 60 seconds. Local uploads obey the backend body
cap. Technical history is retained, and cleanup covers tracked intents rather than
arbitrary manually uploaded bucket objects. These limits are documented.

---

# Global Phase Execution Rules

For every phase:

1. Read `AGENTS.md`.
2. Read this `PLANS.md`.
3. Inspect the repository.
4. Review existing code before creating new code.
5. Read relevant database documentation.
6. Mark the current phase `IN PROGRESS`.
7. Implement only the current phase.
8. Add or update tests.
9. Run relevant tests.
10. Run Ruff.
11. Run mypy when configured for the affected code.
12. Review generated migrations when migrations are involved.
13. Fix problems introduced by the phase.
14. Mark the phase `COMPLETED` only when all acceptance criteria pass.
15. Report the work performed.
16. Stop.

Never automatically start the next phase.

---

# Current Progress

```text
Phase 0  — Foundation / Bootstrap                    COMPLETED
Phase 1  — Database Infrastructure                   COMPLETED
Phase 2  — SQLAlchemy Models                         COMPLETED
Phase 3  — Initial Migration & Database Validation   COMPLETED
Phase 4  — Authentication & Session Management       COMPLETED
Phase 5  — Media Module                              COMPLETED
Phase 6  — Portfolio Core                            COMPLETED
Phase 7  — Dynamic Project Sections                  COMPLETED
Phase 8  — Profile, Services & Site Settings         COMPLETED
Phase 9  — Contact Messages                          COMPLETED
Phase 10 — Public Portfolio API                      COMPLETED
Phase 11 — Administrative API Completion             COMPLETED
Phase 12 — Testing, Security & Hardening              COMPLETED
Phase 13 — API Documentation & Frontend Handoff      COMPLETED
Phase 14 — Media Storage Integration                COMPLETED
```
