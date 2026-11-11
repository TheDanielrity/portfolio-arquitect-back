# Phase 14: approved storage persistence and recovery design

The user approved the additive technical table on 2026-10-03 with historical
operations, active-operation uniqueness, idempotency and recovery requirements.
The implementation is represented by revision `0002_storage_operations` and the
updated SQL/DBML. The original 17 tables remain unchanged.

## Confirmed gaps

The approved 17 tables have no durable upload authorization or storage-operation
record. `media.media_asset` requires a URL, MIME type and size and represents a
registered asset, so inserting pending assets there would violate the requested
verify-before-registration flow. Its unique provider/key constraint only protects
existing rows: deleting a row also removes that replay protection.

A signed token alone cannot record consumption or cancellation. Process memory
does not survive restarts or coordinate workers. PostgreSQL and object storage
cannot atomically commit confirmation, promotion or deletion together.

## Proposed additive change

Add one technical table, `media.storage_operation`, without changing columns,
constraints or foreign keys of the original 17 tables.

Proposed fields:

| Field | Purpose |
| --- | --- |
| `id` UUID primary key | Server-generated operation/upload identifier |
| `kind` | UPLOAD or DELETE |
| `status` | PENDING, PROCESSING, COMPLETED, CANCELLED, CLEANUP_PENDING |
| `created_by` UUID | Administrator identity snapshot; no FK, so history survives account deletion |
| `storage_provider`, `storage_key` | Unique destination object identity |
| `temporary_key` nullable | Staging object for direct upload |
| `expected_metadata` JSONB | Server-validated filename, type, MIME, size and access policy |
| `media_id` UUID nullable | Asset identity retained without a FK so deletion preserves recovery history |
| `expires_at`, `created_at`, `updated_at` | Authorization deadline and recovery timestamps |

Add allowed-value checks, nonblank identity checks, a JSON-object check, a partial
unique provider/key index for PENDING/PROCESSING/CLEANUP_PENDING, and an index on
status/expiry for bounded cleanup. Terminal UPLOAD and later DELETE records can
coexist for the same object. Upload requests
authenticate the administrator and use row locks to serialize consumption. No raw
tokens, credentials, signed URLs or file bytes are stored here.

Confirmation creates the definitive asset and completes the operation in one
PostgreSQL transaction. Keep terminal records at least until upload authorization
expiry plus a documented cleanup margin. Cancellation/expiry must also account for
an already-issued PUT URL remaining usable until its own expiry.

## Recovery and immutable destination

Direct PUT targets staging only. Confirmation verifies the object, then promotes
it to a different backend-generated destination key inaccessible through the PUT
authorization. This prevents a still-valid upload URL from changing a confirmed
asset. Provider copy/promotion therefore belongs to the storage port.

Persist operation intent before remote mutations. A bounded explicit maintenance
command reconciles pending operations against assets and objects, removes expired
staging objects and retries cleanup. It must serialize with confirmation and must
never remove a destination referenced by a committed asset. No Redis or scheduler
service is required.

For deletion, lock the asset, check all four existing reference paths and remove
the asset together with a durable DELETE intent in one transaction. Only then
delete the object; failures leave an unreferenced object tracked for retry, rather
than a surviving asset pointing to a deleted object. Document asynchronous cleanup
semantics when the provider fails.

## Existing contracts and access

Keep list/detail/PATCH/DELETE routes. Existing metadata POST cannot authorize
arbitrary managed R2/local objects; managed-provider registration must use upload
confirmation. Preserve external legacy registration explicitly, without treating
it as verified storage or attempting provider deletion.

No access-policy column is required in `media_asset`: retain protected policy in
server-owned metadata and prevent descriptive PATCH from changing it. Persist a
stable backend delivery URL in the existing nonnullable `url`; authorize delivery
using administrative context or current published project/profile references.
Generate private GET URLs at access time. Optional public CDN delivery must be
explicit and restricted to public objects; CDN caching can delay revocation.

## Implemented boundaries

The small StoragePort uses presign, HEAD, prefix read, conditional promotion,
access and deletion. Existing StorageLocation remains the legacy external metadata
contract; the unused streaming protocol was replaced rather than duplicated.

Completed confirmation returns the same existing asset. After asset deletion it
returns a conflict and cannot recreate the asset. Repeated managed DELETE returns
204 using the durable operation history. External legacy DELETE keeps its existing
metadata-only behavior. Server-owned `_storage` metadata is preserved by PATCH.

Private buckets are required. Both public and private objects stay in private
storage; public delivery requires upload policy plus a live PUBLIC/UNLISTED project
or active-profile reference. R2 GET redirects expire after 60 seconds. Arbitrary
public custom domains on the same bucket are deliberately unsupported: they
would expose staging/private content. A CDN can front authorized backend delivery
while honoring no-store, but an R2 public-domain deployment needs separate design.

Object checks compare actual size/MIME and inspect at most 64 header bytes with
ETag preconditions. This is not decoding, malware scanning or complete file/bundle
validation. GLTF is disabled; GLB still requires sensible authoring of embedded
resources. Per-type budgets and local backend size limits are documented in the
frontend handoff.

The explicit cleanup command uses row locks and bounded batches. No additional
services or full-bucket scans are required. Terminal history is retained. Clock
skew and in-flight upload duration must fit the configured grace; an indefinitely
delayed provider upload cannot be bounded by expiration alone. Downgrade refuses
unresolved operations or staged cleanup before removing technical history.
