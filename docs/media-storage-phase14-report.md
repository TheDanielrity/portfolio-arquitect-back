# Phase 14 implementation report

Status: COMPLETED, validated 2026-10-03. No subsequent phase was implemented.

## Architecture and approved migration

The backend remains a modular monolith. StoragePort is an async Protocol limited
to upload signing, HEAD, bounded prefix reads, conditional promotion, access signing
and deletion. R2/boto3 and local adapters implement it; provider and disk blocking
I/O runs in a worker thread. Routers delegate workflow to services and repositories.
StorageLocation remains the existing external metadata contract.

Revision `0002_storage_operations` adds only `media.storage_operation`. The
original 17 table definitions, constraints and relationships are unchanged.
Provider/key uniqueness applies only to PENDING, PROCESSING and CLEANUP_PENDING
operations, allowing terminal UPLOAD and later DELETE history. Administrator and
asset UUIDs are retained identity snapshots without FKs, so deleting either does
not erase recovery/replay history or modify original relationships. Downgrade
refuses unresolved intents/staging cleanup before discarding terminal history.

## Files

Created in this phase:

- `app/modules/media/operation_models.py`
- `app/modules/media/operation_repository.py`
- `app/modules/media/storage_port.py`
- `app/modules/media/storage_adapters.py`
- `app/modules/media/upload_schemas.py`
- `app/modules/media/upload_policy.py`
- `app/modules/media/upload_service.py`
- `app/modules/media/upload_router.py`
- `app/modules/media/cleanup.py`
- `alembic/versions/0002_storage_operations.py`
- `tests/test_storage.py`
- `tests/test_upload_api.py`
- `tests/test_upload_integration.py`
- `docs/database/phase14-storage-proposal.md`
- `docs/media-storage-phase14-report.md`

Modified:

- `.env.example`, `.gitignore`, `pyproject.toml`, `README.md`, `PLANS.md`
- `app/main.py`, `app/models.py`
- `app/core/config.py`, `app/core/errors.py`, `app/core/api_docs.py`
- `app/modules/media/dependencies.py`, `router.py`, `service.py`, `storage.py`
- `tests/conftest.py`, `tests/migration_support.py`
- `tests/test_models.py`, `tests/test_alembic.py`, `tests/test_migrations_integration.py`
- `tests/test_openapi.py`, `tests/test_admin_api.py`, `tests/test_public_api.py`
- `docs/database/schema.sql`, `docs/database/schema.dbml`
- `docs/api/frontend-handoff.md`, `docs/api/endpoints.md`, `docs/development.md`

No original ORM model files were changed. No real .env or credentials were changed.
No Docker, Redis, Celery, Angular or unrelated architecture work was introduced.
There is no Git metadata in this workspace, so Git diff was unavailable.

## Dependencies and settings

Declared and installed exclusively in .venv: runtime `boto3>=1.36,<2` and development
`boto3-stubs[s3]>=1.36,<2`. Transitive SDK/type dependencies are installed by pip.
No dependency was removed and no global installation was performed.

New settings: STORAGE_PROVIDER, MEDIA_BASE_URL, LOCAL_STORAGE_PATH, R2_ACCOUNT_ID,
R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL,
R2_PRESIGNED_URL_EXPIRE_SECONDS, MEDIA_CLEANUP_GRACE_SECONDS,
MEDIA_MAX_FILE_SIZE_BYTES, MEDIA_IMAGE_MAX_BYTES, MEDIA_PDF_MAX_BYTES,
MEDIA_MODEL_MAX_BYTES and MEDIA_VIDEO_MAX_BYTES. R2_PUBLIC_BASE_URL is reserved
and does not turn on a public bucket domain. R2 credentials are SecretStr fields;
local mode needs none. Blank optional .env values use defaults.

## Endpoints and flow

All paths below start with `/api/v1`:

| Method/path | Contract |
| --- | --- |
| POST /admin/media/uploads/presign | Authenticated declaration; returns ID, PUT URL, headers, expiry, budget, provider |
| POST /admin/media/uploads/confirm | Owner-bound ID; returns the verified MediaResponse, idempotently |
| PUT /admin/media/uploads/{upload_id}/content | Authenticated bounded local raw upload; R2 requires direct PUT |
| DELETE /admin/media/uploads/{upload_id} | Idempotent pending-upload cancellation; cannot revoke an issued PUT |
| GET /admin/media/{asset_id}/content | Authenticated local bytes or R2 signed-GET redirect |
| GET /public/media/{asset_id}/content | Anonymous only for explicit public policy and live published/profile references |

Existing list/detail/PATCH/DELETE contracts remain. Existing metadata POST registers
external legacy providers only; r2/local require verified confirmation. Managed
DELETE is idempotent and may defer physical cleanup during provider outages.

Presign validates declaration and persists PENDING before signing. Browser PUT
targets a random staging key only. Confirm durably persists PROCESSING, then locks
the operation, checks actual size/MIME, reads at most 64 header bytes with an ETag
precondition and conditionally copies to a different random destination. Destination
verification precedes atomic asset registration and operation completion. Concurrent
or repeated confirmation returns one asset; consumed authorization cannot recreate
a deleted asset. Staging PUT cannot overwrite the confirmed destination.

## Security and access

Only active authenticated administrators authorize, confirm, cancel or delete.
Confirmation belongs to its requesting administrator; no caller-supplied object
paths or destination identities are accepted. Supported formats are JPEG, PNG,
WebP, AVIF, PDF, GLB, MP4 and WebM, with central extension/MIME/header rules. GLTF
is disabled because external dependencies/bundle handling are not implemented.
Per-type budgets are configurable; actual mismatches and excess size are rejected
and become tracked cleanup work. PUT cannot impose a true transfer-size limit.

Both public and private assets stay in a PRIVATE R2 bucket. Persisted URLs identify
backend delivery, not expiring capabilities. Private delivery requires admin auth;
public delivery requires explicit upload policy plus a current PUBLISHED
PUBLIC/UNLISTED project link (visible sections only) or an active profile link.
Descriptions/metadata PATCH cannot change the reserved storage policy. Signed
GETs expire after 60 seconds; changing visibility prevents new access but cannot
revoke existing downloads or an already-issued signed GET. A CDN may front backend
delivery while respecting no-store; exposing the same R2 bucket publicly is unsafe
and deliberately not enabled. Legacy external URLs retain independent policies.

## Deletion, compensation and cleanup

Lock the asset and check project, section, profile photo and CV references before
any removal. Historical/soft-deleted/inactive references also block deletion.
Commit asset removal and durable DELETE intent together before deleting bytes.
Failures before commit leave asset/object untouched. Provider failures after commit
leave an unreferenced object with retryable intent. A remote delete followed by
database completion failure is retried safely because object deletion is idempotent.
New FK references serialize against the asset lock and cannot attach to a removed
asset. No distributed transactions are used.

Run `.\.venv\Scripts\python.exe -m app.modules.media.cleanup --limit 100` explicitly
or via the OS scheduler. It locks each bounded candidate, immediately retries
pending DELETEs, and cleans expired unconfirmed/staging objects only after signature
expiry plus a configurable one-hour default grace. Confirmation failures leave a
durable promotion intent; retries verify the existing destination before reusing
staging. Cleanup never deletes a registered destination. Terminal history is kept
for idempotency/replay checks; arbitrary manually uploaded objects are outside scope.

## Validation evidence

All commands used `.venv/Scripts/python.exe`:

- Full pytest with TEST_DATABASE_URL and MIGRATION_TEST_ADMIN_URL supplied securely
  in process memory: **438 passed, no skips**, 282.84 seconds.
- After the final provider-filter cleanup adjustment, focused PostgreSQL media
  integration passed **18 tests** (19.78 seconds); Alembic check remained clean.
  The batch-selection regression ensures older intents from another provider
  cannot starve the current provider, with deterministic fixture timestamps.
- Tests cover adapters with botocore stubs, local files, authentication, unsafe
  formats/paths/sizes, signing deadlines, owner/expiry/cancellation, metadata/header
  mismatch, missing objects, uniqueness, concurrent confirmation/deletion,
  cleanup serialization, staging overwrite isolation, policy/reference delivery,
  all four reference checks and partial database/provider failures with retries.
- Migration upgrade/downgrade/upgrade and PostgreSQL catalog comparison to SQL pass;
  all original integrity and API suites remain green.
- Ruff check: pass. Ruff format --check: pass, 133 files formatted.
- mypy: pass, 123 source files. pip check: pass.
- Alembic local upgrade: pass; current 0002_storage_operations at head.
- Alembic check: no new upgrade operations detected.
- OpenAPI: 89 operations, unique IDs, declared auth/errors and binary/redirect
  responses checked against the endpoint inventory.

Initial sandbox PostgreSQL connections timed out; approved external execution
connected. Existing temporary-directory permissions required fresh isolated temp
paths and disabling pytest cache for that run. Two new fixture timestamp errors
and inventory assumptions were corrected before the successful complete run.
No live R2 bucket was accessed. Real-provider smoke verification remains explicit
deployment validation, separate from normal tests.

## Manual R2 setup and limits

Create a PRIVATE bucket; obtain scoped object read/write credentials; fill R2
settings, set STORAGE_PROVIDER=r2 and use the account S3 endpoint. Keep r2.dev and
public custom domains disabled. Configure bucket CORS separately from FastAPI,
allowing actual Angular origins, PUT/GET/HEAD, Content-Type and optional ETag
exposure. Schedule reconciliation and monitor failed intents/storage usage.
Configure transfer-duration/clock-skew budgets below the grace. A staging-only
lifecycle expiration longer than the full authorization/grace window can provide
a safety net for unusually late transfers; never apply it to definitive objects.

Known limits: header-only inspection, no malware scanning/full decoding/dimension
extraction; GLTF disabled and GLB dependencies not deeply inspected; no instant
revocation of signed GETs or downloaded files; local uploads capped by backend
body limits (1 MiB default); no automatic terminal-history pruning or full-bucket
orphan scanning. In-flight provider transfers cannot be bounded by URL expiry
alone, so an indefinitely delayed transfer needs operational timeout/lifecycle
controls. Provider switching does not automatically migrate existing assets.
The pending manual configuration and these documented limits are not failing
application tests. No blocking Phase 14 implementation issue remains.
