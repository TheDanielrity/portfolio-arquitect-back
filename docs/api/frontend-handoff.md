# Angular integration contract

Base URL locally: `http://127.0.0.1:8000/api/v1`. Keep it in frontend environment
configuration. `/docs` is interactive, `/redoc` is the reference, and
`/openapi.json` is the machine-readable contract for request/response types and
allowed query values. Request JSON with `Content-Type: application/json`.
The [endpoint inventory](endpoints.md) lists every method and path.

## Authentication and browser state

1. `POST /auth/login` with `{"email":"architect@example.com","password":"..."}`.
   Success returns `access_token`, `refresh_token`, `token_type: "bearer"` and
   `expires_in` in seconds. There is no public registration.
2. Send `Authorization: Bearer <access_token>` to `/admin/...` and `/auth/me`.
   Swagger's Authorize dialog takes only the token, without a `Bearer` prefix.
3. `POST /auth/refresh` with `{"refresh_token":"..."}` replaces both tokens.
   Rotation immediately invalidates the old access token. Share one in-flight
   refresh operation across concurrent requests and coordinate browser tabs if
   they share a session. Replace the pair together before resuming requests.
4. On a 401, retry at most once after a successful refresh. Exclude login/refresh/
   logout from automatic refresh interception. A failed refresh requires login;
   a lost successful refresh response may also require login. Do not loop retries.
5. `POST /auth/logout` with the latest refresh token returns 204. Finish any pending
   refresh first. Clear local state after logout; failed network delivery means
   server-side revocation is unconfirmed. Other independent logins remain active.

Refresh keeps the original absolute session deadline (default seven days).
Access lifetime defaults to 15 minutes; a live database session and active user
are also required. No cookies are set; do not enable `withCredentials`. Prefer
in-memory token state; persistent browser storage exposes tokens to scripts and
requires an explicit frontend security decision. Never log tokens or passwords.
Attach bearer headers only to this API origin, never to external asset URLs.

## Public rendering

| GET path | Result |
| --- | --- |
| `/public/projects` | Paginated cards; `category` and `tag` slug filters |
| `/public/featured-projects` | Same contract, featured projects only |
| `/public/projects/{slug}` | Full project, ordered attributes/media/visible sections |
| `/public/categories`, `/public/tags` | Paginated taxonomy used by discoverable projects |
| `/public/profile` | Active profile, photo and CV; 404 if absent |
| `/public/services`, `/public/social-links` | Paginated visible content |
| `/public/site-settings` | Plain list of configured allowlisted key/value pairs |

Discovery requires PUBLISHED + PUBLIC + not deleted. Exact slug detail additionally
allows PUBLISHED UNLISTED projects; unlisted is link-accessible, not confidential.
PRIVATE, DRAFT, ARCHIVED, deleted and unknown projects return 404 even with an
administrator token. Public project URLs use slugs, administrative routes use UUIDs.
Render text safely as text; no HTML/Markdown execution contract is provided.
Keep decimal `area_m2` response strings precise; timestamps are ISO 8601 with timezone.
Respect null media dimensions and absent cover/profile media.

`POST /public/contact` accepts name, email, message and optional phone/subject.
Success is 201 with `{"detail":"Message received"}`. It returns no message ID or
tracking metadata. Disabled contact submissions return 400. Honor 429 cooldowns.

## Administrative editing

All admin methods require authentication. Use OpenAPI's separate input/output
models rather than sending entire response objects back as updates. Unknown input
fields are rejected. PATCH omission leaves a field unchanged; null clears only
nullable fields. Optional nonnullable fields (e.g. project title/status) may be
omitted, but reject explicit null as documented in OpenAPI.

Create a project with `{"title":"Courtyard House","slug":"courtyard-house"}`.
It starts as DRAFT. Register an existing image through `/admin/media`, attach it
or select it using `PUT /admin/projects/{project_id}/cover` with `{"media_id":"UUID"}`,
then PATCH the project with `{"status":"PUBLISHED","visibility":"PUBLIC"}`.
Publication requires an image cover; direct creation as PUBLISHED fails with 400.
Cover selection replaces the previous cover link. The same asset may remain attached
under other roles; no detachment is needed. Only a duplicate combination of
`(project_id, media_id, role)` returns 409, respecting
`UNIQUE(project_id, media_id, role)` and the separate one-COVER-per-project rule.
A published project's current cover cannot be detached directly.
Project DELETE performs soft deletion and returns 204. There is no restore API.

Taxonomy assignment PUT bodies are `{"ids":["UUID"]}` and replace the complete
assignment set. Ordering PUT bodies are `{"items":[{"id":"UUID","sort_order":0}]}`.
Only supplied entries change, transactionally; positions need not be unique.
Section-media ordering uses the asset UUID, while project-media ordering uses the
project-media link UUID. Follow the inventory for exact nested paths.

Profile uses singleton `/admin/profile`. Services and profile social links have
CRUD and ordering. Site settings use PUT by allowlisted key (see OpenAPI);
`contact_enabled` requires boolean, text settings require bounded plain text.
Contact management uses `/admin/contact-messages` and PATCH `/{item_id}/status`
with READ, REPLIED, ARCHIVED or SPAM. GET does not mark read. REPLIED records state;
it does not send email. IP/user-agent metadata is omitted even from admin responses.

## Media and sections

Managed local/R2 files use the upload workflow below. Legacy `POST /admin/media`
still registers external-provider metadata: type, original_filename,
storage_provider, storage_key, url, mime_type and file_size. It rejects providers
`r2` and `local`, which require verified confirmation. External objects are not
verified or remotely deleted by this integration. Managed DELETE removes metadata
and records a durable deletion intent before deleting bytes. A 204 may leave
provider cleanup pending; retrying the same managed DELETE is safe. All four
project/section/profile-photo/CV references (including historical references)
prevent deletion. Public responses omit storage identity and internal metadata.

Project-media roles are COVER, GALLERY, PLAN, RENDER, DOCUMENT and MODEL. Only one
COVER link per project is allowed, and it must reference an IMAGE. Section media
instead use captions and section-specific type rules; they have no project role.

Create sections at `/admin/projects/{project_id}/sections`. Include initial `media`
entries (`media_id`, optional sort_order/caption), or create hidden sections while
authoring. PATCH with `media` replaces the whole section media set atomically.
Section responses contain section fields; retrieve its assets from the nested
`/{section_id}/media` collection. Public detail embeds the full visible composition.

| Section type | Visible-state requirements |
| --- | --- |
| TEXT, QUOTE | Nonblank content, no media |
| IMAGE | Exactly one IMAGE |
| GALLERY | 1–100 IMAGE assets |
| VIDEO | Exactly one VIDEO |
| MODEL_3D | Exactly one MODEL_3D |
| SPLIT | Nonblank content and exactly one IMAGE |

Hidden sections may omit required content/media; type and maximum-count checks
still apply. Removing the last asset from a visible media section fails. Hide it
or replace its assets atomically first. Hidden sections never appear publicly.

## Pagination, search and errors

Paginated responses: `{"items":[],"total":0,"limit":20,"offset":0}`.
Limit is 1–100, offset is 0–9223372036854775807, total counts all matches. Use offset + limit for the
next page; stop when it reaches total. Concurrent changes can shift pages.
Public detail composition and bounded settings lists are not paginated.
Admin main collections support `q`, `sort`, `direction` and resource filters;
the [README comparison](../../README.md#administrative-api-conventions-phase-11)
lists supported fields. Search is a literal case-insensitive substring; omit blank
search. Unknown query fields fail on collections. Public filters combine with AND.

| Status | Frontend handling |
| --- | --- |
| 200 / 201 | Parse the documented response model |
| 204 | Empty body; do not parse JSON |
| 400 | Business rule, e.g. publish without cover |
| 401 | Invalid credentials/session; bounded refresh flow above |
| 404 | Missing or inaccessible resource |
| 409 | Duplicate slug/storage identity or conflicting reference |
| 413 | Request body exceeds configured byte limit |
| 422 | Display field/general validation errors |
| 429 | Wait the `Retry-After` number of seconds |
| 500 | Generic error; retain `X-Error-ID` for support |

Domain/middleware failures use `{"detail":"message"}`. Validation uses:

```json
{"detail":[{"loc":["body","email"],"msg":"Invalid email","type":"value_error"}]}
```

The example message is illustrative, not a stable error code. Locations can refer
to body, query, path, nested list indices or an entire body. Submitted input and
validation context are omitted. Handle errors by status/structure rather than
matching English messages. CORS exposes Retry-After and X-Error-ID to configured
origins. Auth/admin/public content responses disable caching. Do not blindly retry
non-idempotent writes after an uncertain network result.

## Integration smoke test

After [local setup](../development.md), login, fetch `/auth/me`, create a draft,
register/select a cover and publish. Verify its public card and slug detail.
Switch to UNLISTED: listing disappears, direct detail remains. Switch to PRIVATE:
public detail returns 404. Rotate tokens: new pair works and old access gets 401.
Submit contact, then explicitly mark it READ in admin. Use disposable authored
content for this manual exercise; automated tests create isolated databases.

## Direct media upload (Phase 14)

All upload, confirmation, cancellation, metadata and administrative delivery
operations require the active administrator bearer token. Only explicitly public
media with a currently published PUBLIC/UNLISTED project reference, visible section of such
a project, or active profile reference can use anonymous delivery. Assets uploaded
as private remain inaccessible anonymously even if attached to a published project.
Upload public covers/profile images with `access: "public"`; this does not make
the bucket public. For confidential assets use `access: "private"` (the default).
UNLISTED delivery is link-accessible like its project; it is not confidential.

1. Authorize with `POST /admin/media/uploads/presign`:

   ```json
   {"original_filename":"house.jpg","mime_type":"image/jpeg",
    "file_size":123456,"access":"public","alt_text":"Courtyard view"}
   ```

   Example response (IDs and URL are illustrative):

   ```json
   {"upload_id":"11111111-1111-4111-8111-111111111111",
    "upload_url":"https://ACCOUNT.r2.cloudflarestorage.com/BUCKET/staging/UUID.jpg?SIGNED_QUERY",
    "method":"PUT","headers":{"Content-Type":"image/jpeg"},
    "expires_at":"2026-10-03T18:05:00Z","max_file_size":20971520,"provider":"r2"}
   ```

2. PUT the raw `File` bytes to `upload_url`, with exactly the returned headers.
   Do not use multipart/FormData. Do not attach the backend bearer token to R2.
   Ensure the Angular authentication interceptor restricts bearer headers to the
   backend origin. Bypass JSON defaults for this request. Use upload progress and
   cancel the browser transfer when requested. Signed URLs are bearer capabilities:
   do not log them, persist them or send them to analytics.

3. After PUT succeeds, `POST /admin/media/uploads/confirm`:

   ```json
   {"upload_id":"11111111-1111-4111-8111-111111111111"}
   ```

   Success returns the existing `MediaResponse` contract, including `id`, type,
   stable `url`, MIME, actual size, nullable dimensions and presentation fields.
   Backend HEAD, bounded header inspection, conditional copy to a distinct
   destination and destination verification precede database registration.
   Width/height stay null: this phase does not decode dimensions.

4. GET `/admin/media/{id}` to consult metadata; associate the returned ID with
   project-media/section-media or the profile/CV using the existing endpoints.
   `PUT /admin/projects/{project_id}/cover` accepts `{"media_id":"UUID"}`.
   Use the stable asset URL for public rendering. For an administrator preview,
   GET `/admin/media/{id}/content` with bearer authentication. Local mode returns
   bytes; R2 returns 307 to a private signed GET valid for 60 seconds. Fetch binary
   responses as blobs, do not parse JSON. Ordinary img URLs cannot supply an admin
   bearer header. Do not cache private previews or signed redirects in a service
   worker. R2 bucket CORS must allow GET as well as PUT for browser fetch previews.

Confirmation is bound to the administrator that requested authorization. Repeating
a completed confirmation returns the same asset while it exists, including after
authorization expiry; it never creates another asset. Confirmation after deletion
returns 409. Pending/processing confirmations expire; do not request a new upload
merely because a confirmation response was lost: retry the same upload_id first.
Unknown/cross-admin IDs return 404; expired or incompatible data return 400;
cancelled/consumed-deleted operations return 409; storage outages return 503.
Uncertain 500/network failures can leave a durable PROCESSING operation; retry
confirmation within the authorization deadline. Do not submit arbitrary keys.

Cancel using `DELETE /admin/media/uploads/{upload_id}` (idempotent 204 before
completion). It records cancellation, but cannot revoke an issued R2 PUT URL.
After expiry request a new authorization and upload again. Only the staged object
can be overwritten by that PUT; it never overwrites a confirmed destination.
Do not reuse staging objects as public identifiers.

Formats: JPEG (.jpg/.jpeg), PNG, WebP, AVIF, PDF, GLB, MP4 and WebM, with their exact
standard MIME types. GLTF is rejected: external buffers/textures and safe bundle
handling are not implemented. GLB header inspection does not prove it is a complete
self-contained scene; prepare embedded models in your authoring pipeline. The
inspection checks up to 64 header bytes, not complete decoding, malware scanning
or validity of documents/scenes/videos. Avoid presenting this as full validation.

Default operating budgets: images 20 MiB, PDF 50 MiB, models 100 MiB, video 512 MiB,
global cap 512 MiB. These balance typical portfolio sizes against transfer/storage
costs; operators can change the per-type and global settings. PUT signatures bind
Content-Type but do not enforce a transfer-size limit. Confirmation checks actual
size and rejects mismatches/over-budget objects; cleanup occurs after expiry plus
grace, so malicious uploads can consume temporary storage before cleanup.

Local mode returns a backend PUT URL instead of a signed external URL. Send the
administrator bearer token on that local PUT. The maximum is also bounded by
MAX_REQUEST_BODY_BYTES (default 1 MiB); local development deliberately uses bounded
buffering. It requires no R2 credentials and is not a large-file production proxy.

### Bucket CORS and private delivery

Configure an R2 PRIVATE bucket, scoped object read/write API credentials and the
account S3 endpoint. Disable r2.dev and public bucket custom domains. Setting
R2_PUBLIC_BASE_URL alone does not enable CDN access: this phase deliberately uses
private storage plus authorized signed delivery. A public custom domain on the
same bucket would expose private and staging files. A future CDN can front the
stable backend delivery route, preserving authorization and `no-store`; do not
cache redirects. Anonymous access is re-evaluated on each backend request. Already
issued signed GETs remain usable for up to 60 seconds; downloaded files cannot be
revoked. Legacy external URLs and any manually enabled CDN retain their own access
and cache policies; changing PostgreSQL visibility does not revoke those copies.

The bucket CORS policy is separate from FastAPI CORS_ORIGINS. A minimal browser
policy (replace origins with your actual public/admin application origins):

```json
[{"AllowedOrigins":["http://localhost:4200"],"AllowedMethods":["PUT","GET","HEAD"],
  "AllowedHeaders":["Content-Type"],"ExposeHeaders":["ETag"],"MaxAgeSeconds":300}]
```

Do not use wildcard production origins. R2 presigned URLs use the S3 account
hostname; do not rewrite them to a CDN hostname. Follow Cloudflare's official
[presigned URL](https://developers.cloudflare.com/r2/api/s3/presigned-urls/) and
[bucket CORS](https://developers.cloudflare.com/r2/buckets/cors/) documentation.
Expired signatures may appear as a browser CORS/network failure; use the returned
expires_at to determine when to request a new upload authorization.

### Maintenance and recovery

Run `.\.venv\Scripts\python.exe -m app.modules.media.cleanup --limit 100`
explicitly or from Windows Task Scheduler. It processes bounded durable intents,
serializes with confirmation/deletion and is safe to repeat. Only the configured
provider is processed; retain its credentials/path until all its intents settle.
Pending DELETE objects are retried immediately; temporary/unconfirmed uploads
are cleaned after authorization expiry plus MEDIA_CLEANUP_GRACE_SECONDS (one hour
by default). This also catches signed URLs never used, successful PUTs never
confirmed and copies followed by database failure. No full-bucket scans or
untracked/manual object deletion occur. Keep operation history for replay and
deletion idempotency; automatic history pruning is not implemented.

Enforce an operational maximum transfer duration below the cleanup grace and
allow for clock/network skew: requests accepted before signature expiry can still
be in flight afterwards. The grace alone cannot bound an indefinitely delayed
provider transfer. Monitor staging storage and retry maintenance after outages.
Do not configure an R2 lifecycle rule deleting definitive objects. Downgrade refuses
to discard unresolved intents or staged cleanup history; reconcile first.
