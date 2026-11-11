# Architecture Portfolio Backend

## Project Overview

This repository contains the backend for a professional architecture portfolio platform.

The platform will be consumed by:

- a public Angular application;
- a private Angular administration panel.

The backend is built with Python and FastAPI.

The system manages:

- architecture projects;
- project categories;
- project tags;
- project attributes;
- project sections;
- images and multimedia assets;
- professional profile information;
- social links;
- services;
- site configuration;
- contact messages;
- administrator authentication.

---

# Core Technology Stack

Use the following technologies unless explicitly changed by the user:

- Python 3.12+
- FastAPI
- Pydantic v2
- Pydantic Settings
- SQLAlchemy 2.x
- PostgreSQL
- Psycopg 3
- Alembic
- PyJWT
- pwdlib with Argon2
- pytest
- pytest-asyncio
- httpx
- Ruff
- mypy

Do not introduce alternative libraries for the same responsibility unless there is a clear technical reason.

---

# Docker

Docker is intentionally excluded from the current development phase.

Do not create or introduce:

- `Dockerfile`
- `docker-compose.yml`
- container configuration
- Docker-specific scripts
- Docker-specific development instructions

unless the user explicitly requests Docker later.

---

# Python Virtual Environment

This project must ALWAYS use a local Python virtual environment named:

`.venv`

Never install project dependencies globally.

Before running Python-related commands, verify that `.venv` exists.

On Windows, if `.venv` does not exist, create it with:

`py -m venv .venv`

Prefer invoking the virtual environment interpreter directly instead of relying on shell activation.

Windows:

`.\.venv\Scripts\python.exe`

Linux/macOS:

`.venv/bin/python`

Use:

`.\.venv\Scripts\python.exe -m pip`

instead of:

`pip`

Use:

`.\.venv\Scripts\python.exe -m pytest`

instead of:

`pytest`

Use:

`.\.venv\Scripts\python.exe -m alembic`

instead of:

`alembic`

Use the equivalent `.venv/bin/python` commands on Linux/macOS.

Do not assume that virtual environment activation persists across tool calls or shell commands.

Never use a globally installed Python interpreter for project commands when `.venv` is available.

---

# Architecture

Build the backend as a modular monolith.

Do not use microservices.

Favor clear module boundaries and separation of responsibilities without introducing unnecessary enterprise complexity.

The application should separate:

- API routes;
- request and response schemas;
- business logic;
- persistence logic;
- configuration;
- security;
- infrastructure concerns.

Business logic must not live inside API route handlers.

API routers should primarily:

1. receive HTTP requests;
2. validate input;
3. call application services;
4. map expected exceptions;
5. return HTTP responses.

Database access must not be scattered throughout routers.

Persistence logic should live in repositories or clearly defined persistence services.

Avoid unnecessary abstraction layers.

Do not create interfaces or base classes unless they solve an actual problem.

---

# Suggested Project Structure

Use the following structure as the architectural reference:

```text
app/
├── main.py
│
├── core/
│   ├── config.py
│   ├── database.py
│   ├── security.py
│   ├── exceptions.py
│   └── logging.py
│
└── modules/
    ├── auth/
    ├── portfolio/
    ├── media/
    ├── content/
    └── contact/
```

A module may contain:

```text
models.py
schemas.py
repository.py
service.py
router.py
dependencies.py
```

Create only the files that are actually needed.

Do not create empty files only to satisfy the suggested structure.

Large modules may be split into submodules when necessary.

---

# Module Responsibilities

## Auth

Responsible for:

- administrator users;
- password hashing;
- access tokens;
- refresh-token sessions;
- authentication dependencies;
- authorization checks.

## Portfolio

Responsible for:

- projects;
- categories;
- tags;
- project attributes;
- project media relationships;
- project sections;
- project section media.

## Media

Responsible for:

- media asset metadata;
- upload abstractions;
- storage provider integration;
- media validation;
- future image/document/model storage.

## Content

Responsible for:

- professional profile;
- social links;
- services;
- global site settings.

## Contact

Responsible for:

- public contact form submissions;
- administrative contact message management.

---

# Database

PostgreSQL is the official project database.

The database design source of truth is:

`docs/database/schema.sql`

and:

`docs/database/schema.dbml`

Always inspect the relevant database documentation before implementing or changing SQLAlchemy models.

Do not silently modify the database design.

If implementation requires changing the relational model:

1. identify the problem;
2. explain why a schema change is required;
3. identify affected tables and relationships;
4. propose the change;
5. do not modify the approved database design unless the user authorizes it.

---

# SQLAlchemy

Use SQLAlchemy 2.x style.

Use modern declarative typing:

`Mapped[...]`

and:

`mapped_column(...)`

Prefer explicit relationships.

ORM relationships must match the actual database foreign keys.

Do not invent relationships that are not supported by the relational model.

Use asynchronous SQLAlchemy infrastructure.

Use:

- `AsyncEngine`
- `AsyncSession`

Do not share a global database session between requests.

Transactions must be handled correctly.

Rollback transactions when necessary.

Database sessions must be properly closed.

---

# Database Driver

Use Psycopg 3.

Use SQLAlchemy's async PostgreSQL integration with Psycopg.

Do not introduce:

- `psycopg2`
- deprecated PostgreSQL drivers

unless required for a documented compatibility reason.

---

# Alembic

Database schema evolution must be managed with Alembic.

Do not use:

`Base.metadata.create_all()`

as the normal schema deployment strategy.

All structural database changes must be represented by migrations.

Review generated Alembic migrations before considering them complete.

Do not trust autogenerate blindly.

Verify:

- foreign keys;
- constraints;
- indexes;
- partial indexes;
- schema names;
- cascade rules;
- PostgreSQL-specific types.

---

# Configuration

Use `pydantic-settings` for application configuration.

Never hardcode secrets.

Never commit real credentials.

Use environment variables.

The real `.env` file must not be committed.

Maintain:

`.env.example`

with safe placeholder values.

Expected settings may include:

- `APP_NAME`
- `APP_ENV`
- `DEBUG`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`
- `CORS_ORIGINS`

Add new configuration values only when required.

---

# Authentication

Use JWT access tokens.

Use the `auth.refresh_token` table for refresh-token sessions.

Never store raw refresh tokens in PostgreSQL.

Only store cryptographic hashes of refresh tokens.

Passwords must be hashed using Argon2.

Never store plaintext passwords.

Never log passwords or tokens.

Never return password hashes or token hashes through API responses.

Keep security-related logic centralized.

---

# API Versioning

Use:

`/api/v1`

as the base API prefix.

Organize endpoints under:

`/api/v1/auth/...`

`/api/v1/public/...`

`/api/v1/admin/...`

Do not expose administrative operations through public routes.

---

# Public API

The public API must never expose:

- draft projects;
- archived projects unless explicitly required;
- deleted projects;
- private projects;
- administrator information;
- password hashes;
- refresh-token hashes;
- internal storage metadata that should remain private;
- sensitive configuration values.

Normal public project listings must only include projects matching:

`status = PUBLISHED`

`visibility = PUBLIC`

`deleted_at IS NULL`

---

# Unlisted Projects

Projects with:

`visibility = UNLISTED`

must not appear in normal public listings.

They may be accessed directly through their explicit project URL if the business rules allow it.

---

# Private Projects

Projects with:

`visibility = PRIVATE`

must not be accessible through anonymous public endpoints.

They require an authorized administrative context unless the requirements change later.

---

# Soft Delete

`portfolio.project.deleted_at` implements project soft deletion.

Normal API operations must not physically delete projects.

Queries must correctly handle soft-deleted records.

Normal public queries must exclude:

`deleted_at IS NOT NULL`

Administrative restore capabilities may be implemented later if requested.

---

# Media Storage

Do not store large binary files directly in PostgreSQL.

PostgreSQL stores media metadata only.

The media architecture must allow integration with storage providers such as:

- Cloudflare R2;
- Amazon S3;
- Cloudinary.

Do not tightly couple the domain layer to a single provider.

Storage provider-specific logic must remain isolated.

---

# Media Database Records

`media.media_asset` represents media metadata.

It may represent:

- images;
- videos;
- PDFs;
- documents;
- 3D models.

Do not assume every asset has image dimensions.

Respect nullable width and height fields.

---

# Project Media

A project may contain multiple media assets.

Media relationships must respect the database role values.

A project may have only one asset with role:

`COVER`

Do not bypass the corresponding PostgreSQL unique partial index.

---

# Dynamic Project Sections

Project pages are dynamically composed using project sections.

Do not hardcode every project page into a fixed layout.

Section types must respect the approved relational model.

Examples include:

- `TEXT`
- `IMAGE`
- `GALLERY`
- `VIDEO`
- `MODEL_3D`
- `QUOTE`
- `SPLIT`

Business logic must validate media requirements when applicable.

---

# Validation

Use Pydantic for API input and output validation.

Do not rely exclusively on Python validation for integrity rules already protected by PostgreSQL.

Database constraints must remain the final line of defense for relational integrity.

Validate user input before persistence.

Normalize values where appropriate.

Do not silently mutate user input in surprising ways.

---

# Slugs

Slugs must follow the approved database format.

Generate or normalize slugs consistently.

Do not create project URLs using database UUIDs when a project slug is available.

Handle slug conflicts explicitly.

Soft-deleted projects follow the database's partial uniqueness rules.

---

# Error Handling

Do not expose internal tracebacks to API clients.

Do not leak implementation details.

Expected failures should have consistent HTTP responses.

Use appropriate status codes.

Typical mappings:

- `400` — invalid operation
- `401` — authentication required or invalid credentials
- `403` — authenticated but not authorized
- `404` — resource not found
- `409` — conflicting resource or state
- `422` — request validation failure

Create domain/application exceptions where they improve clarity.

Avoid raising generic exceptions for expected business errors.

---

# API Response Design

Use explicit Pydantic response models.

Do not return raw SQLAlchemy objects as undocumented API contracts.

Do not expose database-only fields accidentally.

Keep public and administrative response schemas separate when their requirements differ.

---

# Pagination

Any endpoint returning potentially large collections should support pagination.

Do not load an unlimited number of database records when pagination is appropriate.

Pagination conventions should remain consistent across modules.

---

# Sorting

Administrative project ordering may use `sort_order`.

Do not require `sort_order` values to be unique.

Reordering operations should be handled transactionally when multiple rows are updated.

---

# Contact Messages

Contact form endpoints are public input surfaces.

Validate:

- sender name;
- email;
- message;
- optional phone;
- optional subject.

Prepare the design for anti-spam protection.

Do not expose IP addresses or user-agent values through public endpoints.

---

# Security

Treat all external input as untrusted.

Security-sensitive code must remain explicit and reviewable.

Do not implement custom cryptography.

Use maintained libraries.

Avoid dynamic SQL.

Do not interpolate user values into SQL strings.

Use SQLAlchemy expressions and parameterized queries.

Never expose secrets through logs or exceptions.

---

# CORS

CORS origins must come from configuration.

Do not use unrestricted CORS in production.

Development defaults may be permissive only when explicitly configured.

---

# Logging

Use structured and meaningful application logging.

Do not log:

- passwords;
- access tokens;
- refresh tokens;
- secret keys;
- full authorization headers.

Log exceptions with enough context for debugging without leaking secrets.

---

# Testing

Use pytest.

Use pytest-asyncio where async testing is required.

Use httpx for FastAPI API tests.

Implement tests alongside functionality rather than postponing testing until the end.

Prioritize tests for:

- authentication;
- refresh-token lifecycle;
- permissions;
- project publication rules;
- visibility rules;
- soft deletion;
- repositories;
- business services;
- critical API endpoints;
- database constraints where application behavior depends on them.

A phase is not complete when its relevant tests are failing.

---

# Test Independence

Tests must be repeatable.

Tests should not depend on execution order.

Do not depend on existing manual development data.

Avoid shared mutable state between tests.

---

# Code Quality

Use type hints consistently.

Prefer clear names over clever abstractions.

Keep functions focused.

Keep modules cohesive.

Avoid oversized files.

Avoid unnecessary inheritance.

Avoid duplicate business logic.

Avoid mutable global application state.

Avoid unused dependencies.

Avoid commented-out dead code.

Avoid comments that simply repeat what the code already says.

---

# Ruff

Use Ruff for linting and formatting-related checks.

Do not ignore lint rules simply to make the command pass unless the exception is justified.

Fix the underlying code issue whenever possible.

---

# mypy

Use mypy for static typing.

Do not silence typing errors with broad `# type: ignore` comments unless required and justified.

Prefer correct typing over suppression.

---

# Dependency Management

Declare dependencies in:

`pyproject.toml`

Do not install project dependencies without declaring them.

Before introducing a dependency:

1. verify that it is actually necessary;
2. verify that an existing dependency does not already solve the problem;
3. prefer maintained and widely used packages;
4. avoid overlapping libraries with the same responsibility.

Development-only dependencies must be clearly separated when the project configuration supports it.

---

# Development Workflow

Backend implementation is organized into phases defined in:

`PLANS.md`

Do not implement future phases automatically.

When asked to implement a phase:

1. read the applicable `AGENTS.md`;
2. read `PLANS.md`;
3. inspect the current repository state;
4. inspect relevant database documentation;
5. inspect existing implementation before creating new abstractions;
6. implement only the requested phase;
7. add or update tests;
8. run relevant validation commands;
9. fix issues introduced by the phase;
10. update `PLANS.md` status only when completion criteria are satisfied;
11. report the final result.

Do not begin the next phase automatically.

---

# Scope Control

If the user requests:

`Phase X`

implement only:

`Phase X`

Do not implement:

`Phase X + 1`

unless Phase X cannot function without a minimal prerequisite.

If such a prerequisite is required, explain it and keep the change narrowly scoped.

---

# Existing Code

Inspect before replacing.

Do not rewrite working modules simply because another implementation style is possible.

Preserve established project conventions unless they conflict with these instructions or an explicit user requirement.

---

# Refactoring

Refactor only when:

- required for the current feature;
- necessary to fix a confirmed design problem;
- necessary to preserve maintainability;
- explicitly requested.

Do not perform unrelated repository-wide refactors during scoped phase work.

---

# Documentation

Document architecture decisions that are not obvious from the code.

Public functions and classes should have documentation when their purpose is not self-explanatory.

Do not write excessive docstrings for trivial functions.

Keep API documentation compatible with FastAPI/OpenAPI.

---

# Git Safety

Do not remove unrelated user changes.

Do not reset the repository.

Do not use destructive Git operations unless explicitly requested.

Do not modify generated or unrelated files unnecessarily.

---

# Database Safety

Do not drop schemas, tables, or production data unless explicitly requested.

Do not create destructive migrations without clearly identifying their consequences.

Migration downgrade logic should be reasonable where applicable.

---

# Phase Completion Requirements

A phase may only be marked `COMPLETED` when:

- its required functionality exists;
- its acceptance criteria are satisfied;
- relevant tests pass;
- Ruff passes for affected code;
- mypy passes for affected code when configured;
- required migrations are valid;
- no known blocking issue directly related to the phase remains.

If something cannot be completed, keep the phase incomplete and document the blocker.

---

# Final Report After Each Phase

At the end of each implementation phase, report:

- phase implemented;
- files created;
- files modified;
- dependencies added or removed;
- migrations created or changed;
- tests executed;
- test results;
- Ruff result;
- mypy result;
- relevant architectural decisions;
- known limitations;
- remaining work for the next phase.

Do not claim success when validation commands are failing.