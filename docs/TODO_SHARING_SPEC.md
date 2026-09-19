# Technical Specification: Todo List Sharing

> Status: Proposed
>
> Scope: Specification only; no implementation is included in this document.

## 1. Overview & Objective

### Feature summary

Allow an authenticated owner to grant an existing user access to the owner's todo list as either:

- `viewer`: may read the owner's todos.
- `editor`: may read, create, update, and delete todos in the owner's list.

The owner may change a collaborator's permission or revoke access at any time. A grant applies to the owner's entire implicit todo list, including todos created after the grant.

### Problem statement

The current system scopes every todo to its owner and has no controlled collaboration mechanism. Users cannot share a list without sharing credentials or copying data. This feature introduces explicit, least-privilege access while preserving a single authoritative owner for every todo.

### Objective

- Enable read-only and editable list collaboration between registered users.
- Preserve owner control over permissions and revocation.
- Prevent permission escalation, transitive sharing, and cross-user data disclosure.
- Make revocation effective immediately, including in the presence of Redis response caches and concurrent requests.
- Keep the first release compatible with the current one-list-per-user data model.

### Target roles

- **Owner**: User identified by `todos.user_id`; has full control over todos and sharing.
- **Editor**: User with an active `editor` grant from the owner.
- **Viewer**: User with an active `viewer` grant from the owner.
- **Unshared user**: Authenticated user with no grant for the owner's list.

Ownership and shared permissions are distinct. A share never transfers ownership, and no share row is created for the owner.

## 2. User Stories & Acceptance Criteria

### User Story 1: Share with a viewer

- **As an** owner
- **I want to** share my todo list with another registered user as a viewer
- **So that** they can follow the list without changing it.
- **Acceptance Criteria**:
  - [ ] Given the recipient is registered, is not the owner, and has no existing grant, when the owner grants `viewer`, then one active share is created and returned with HTTP 201.
  - [ ] Given the viewer has an active grant, when the viewer opens the shared list, then the viewer can read the owner's current and subsequently created todos.
  - [ ] Given the viewer grant, when the viewer attempts any create, update, or delete operation, then the API rejects it without changing data.

### User Story 2: Share with an editor

- **As an** owner
- **I want to** share my todo list with another registered user as an editor
- **So that** they can help maintain the list.
- **Acceptance Criteria**:
  - [ ] Given an eligible registered recipient, when the owner grants `editor`, then the grant becomes active immediately.
  - [ ] Given an active editor grant, when the editor creates, updates, or deletes a todo in the owner's list, then the mutation succeeds and the todo remains owned by the owner.
  - [ ] Given an editor grant, when the editor attempts to share, change permissions, revoke access, or transfer ownership, then the operation is rejected.

### User Story 3: Change collaborator permission

- **As an** owner
- **I want to** upgrade a viewer to editor or downgrade an editor to viewer
- **So that** access continues to match the collaborator's responsibilities.
- **Acceptance Criteria**:
  - [ ] Given an active viewer grant, when the owner changes it to `editor` with the current version, then subsequent mutations by that user are authorized.
  - [ ] Given an active editor grant, when the owner changes it to `viewer`, then subsequent mutations are rejected while reads remain allowed.
  - [ ] Given a stale version, when the owner attempts a permission change, then the API returns HTTP 409 and does not overwrite the newer grant.

### User Story 4: Revoke access

- **As an** owner
- **I want to** revoke a viewer or editor
- **So that** the former collaborator immediately loses access.
- **Acceptance Criteria**:
  - [ ] Given an active grant, when the owner revokes it, then the share is deleted and HTTP 204 is returned only after the revocation transaction commits.
  - [ ] Given a completed revocation, when the former collaborator reads or mutates the list, then the request is denied even if an old Redis response exists.
  - [ ] Given a completed revocation, when the former collaborator uses an already-open UI, then its next API request cannot obtain private list data and the stale shared-list query is removed or invalidated.

### User Story 5: Preserve owner authority

- **As an** owner
- **I want to** retain full control of my todos while sharing
- **So that** collaborators cannot displace or restrict me.
- **Acceptance Criteria**:
  - [ ] The owner can always read, create, update, delete, share, change permissions, and revoke while the account and list exist.
  - [ ] No collaborator can change `todos.user_id`, create a share, or alter another collaborator's grant.
  - [ ] Removing a share never deletes or transfers the owner's todos.

### User Story 6: Protect unshared data

- **As an** authenticated but unshared user
- **I want** other users' lists to remain undisclosed
- **So that** identifiers cannot be used to discover private data.
- **Acceptance Criteria**:
  - [ ] Given no grant, when a user requests another owner's list or todo, then the API returns HTTP 404 with the standard not-found payload.
  - [ ] The response does not distinguish a nonexistent resource from an existing but unauthorized resource.
  - [ ] No cached response is returned before authorization succeeds.

## 3. Scope

### In scope

- Sharing one user's entire implicit todo list with an existing registered user.
- `viewer` and `editor` permissions.
- Listing grants issued by the current owner.
- Listing todo lists shared with the current user.
- Changing a grant between `viewer` and `editor`.
- Revoking a grant.
- Shared-list read operations and editor todo mutations.
- Database-enforced uniqueness and self-sharing prevention.
- Optimistic concurrency for share changes and todo mutations.
- User-scoped and owner-scoped cache invalidation.

### Out of scope

- Sharing individual todos or arbitrary subsets of a list.
- Multiple independently named lists per owner.
- Ownership transfer, co-owners, custom roles, or per-field permissions.
- Transitive sharing or allowing collaborators to manage grants.
- Invitations to unregistered email addresses, invitation acceptance, or email delivery.
- Public links, anonymous access, organization/team sharing, or domain-wide sharing.
- Collaborator audit history, activity feeds, comments, notifications, and presence indicators.
- Offline editing, conflict-merging UI, or real-time WebSocket synchronization.
- Restoring a grant or todo after hard deletion.

## 4. Database Design

### Existing ownership model

The existing `todos.user_id UUID NOT NULL` remains the authoritative owner and must reference `users(id) ON DELETE CASCADE`. The current foreign key has no explicit delete action, so the sharing implementation migration must replace that constraint with the cascade definition; this document does not apply that migration. A todo created by an editor is written with `user_id = owner_id` from the URL and authorization context; the client cannot submit or override `user_id`.

The first release treats each user's todos as one implicit list, so no separate `todo_lists` table is introduced.

### New type and table

#### `todo_list_shares`

| Column | Suggested PostgreSQL type | Null | Default | Purpose |
|---|---|---:|---|---|
| `id` | `UUID` | No | `gen_random_uuid()` | Primary key exposed as the share identifier. |
| `owner_id` | `UUID` | No | None | User who owns the shared todo list. |
| `grantee_id` | `UUID` | No | None | Existing user receiving access. |
| `permission` | `VARCHAR(10)` | No | None | `viewer` or `editor`. |
| `version` | `INTEGER` | No | `1` | Optimistic-lock version for permission changes and revocation. |
| `created_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Grant creation time in UTC. |
| `updated_at` | `TIMESTAMPTZ` | No | `CURRENT_TIMESTAMP` | Last permission-change time in UTC. |

Constraints:

- Primary key: `PRIMARY KEY (id)`.
- Owner foreign key: `FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE`.
- Grantee foreign key: `FOREIGN KEY (grantee_id) REFERENCES users(id) ON DELETE CASCADE`.
- One grant per owner/grantee pair: `UNIQUE (owner_id, grantee_id)`.
- Self-sharing prevention: `CHECK (owner_id <> grantee_id)`.
- Permission domain: `CHECK (permission IN ('viewer', 'editor'))`.
- Version validity: `CHECK (version >= 1)`.

Indexes:

- The unique constraint creates an index beginning with `owner_id`, supporting owner grant listings and authorization lookup by owner/grantee.
- Create `ix_todo_list_shares_grantee_owner` on `todo_list_shares (grantee_id, owner_id)` in ascending order with no predicate. It supports received-share listings and authorization lookups that begin with `grantee_id`. The `(owner_id, grantee_id)` unique index cannot efficiently serve that grantee-leading access pattern, and the existing todo index is on a different table.
- Reuse the existing non-unique Tier 3C index `ix_todos_user_created_id_desc` on `todos (user_id, created_at DESC, id DESC)` for owner and shared-list queries using `WHERE user_id = :owner_id ORDER BY created_at DESC, id DESC`. Shared access does not change the stored `user_id`, so the same equality prefix and ordering apply. No additional todo-list pagination index is proposed.
- Single-todo access continues to use the `todos` primary-key index for `id = :todo_id` and verifies `user_id = :owner_id` on the fetched row; a second `(id, user_id)` or duplicate `(user_id, created_at, id)` index is not justified for this one-row lookup.

Delete behavior:

- Deleting the owner cascades through the owner's todos and issued shares.
- Deleting the grantee cascades only that user's received share rows; it does not delete the owner's todos.
- Deleting a todo has no effect on a list-level share.
- Revoking access deletes the share row and does not modify any todo.
- No user/share foreign key uses `RESTRICT` in this release because hard account deletion must not leave orphaned grants; ownership transfer is intentionally unsupported.

### Altered `todos` table

Add an optimistic-lock column:

| Column | Suggested PostgreSQL type | Null | Default | Purpose |
|---|---|---:|---|---|
| `version` | `INTEGER` | No | `1` | Detects concurrent owner/editor updates and deletes. |

Constraint: `CHECK (version >= 1)`. Updates use `WHERE id = :todo_id AND user_id = :owner_id AND version = :expected_version`, then increment `version`. A zero-row update means the todo was removed, authorization changed, or the version is stale; the service rechecks authorization/existence to return the appropriate standardized error.

### Timestamp behavior

- The application writes UTC values.
- `updated_at` changes whenever permission or todo content changes.
- Permission updates atomically increment `todo_list_shares.version` and update `updated_at`.
- Todo updates atomically increment `todos.version` and update `updated_at`.

## 5. API Contracts & Endpoints

All endpoints require a valid access token in the standard `Authorization: Bearer <token>` header. Raw tokens must never appear in logs, cache keys, or error payloads.

### Endpoint summary

| Method | Endpoint | Description | Auth required |
|---|---|---|---|
| `POST` | `/api/v1/todo-shares` | Create a viewer/editor grant owned by the current user. | Yes |
| `GET` | `/api/v1/todo-shares` | List grants issued by the current owner. | Yes |
| `PATCH` | `/api/v1/todo-shares/{share_id}` | Change a grant's permission. | Yes; owner only |
| `DELETE` | `/api/v1/todo-shares/{share_id}` | Revoke a grant. | Yes; owner only |
| `GET` | `/api/v1/shared-todo-lists` | List grants received by the current user. | Yes |
| `GET` | `/api/v1/todo-lists/{owner_id}/todos` | Read an owner or shared todo list. | Yes; owner/viewer/editor |
| `POST` | `/api/v1/todo-lists/{owner_id}/todos` | Create a todo in the specified list. | Yes; owner/editor |
| `GET` | `/api/v1/todo-lists/{owner_id}/todos/{todo_id}` | Read one todo in the specified list. | Yes; owner/viewer/editor |
| `PATCH` | `/api/v1/todo-lists/{owner_id}/todos/{todo_id}` | Partially update one todo. | Yes; owner/editor |
| `DELETE` | `/api/v1/todo-lists/{owner_id}/todos/{todo_id}` | Delete one todo. | Yes; owner/editor |

Existing `/api/v1/todos` endpoints continue to represent the authenticated user's own list. They may delegate internally to the same authorization-aware service with `owner_id = current_user.id`; their external behavior remains backward compatible.

### Shared schemas

`TodoListShareResponse`:

```json
{
  "id": "7f41031f-742d-4d42-88d1-544f79ee5adc",
  "owner_id": "11111111-1111-4111-8111-111111111111",
  "grantee": {
    "id": "22222222-2222-4222-8222-222222222222",
    "email": "collaborator@example.com"
  },
  "permission": "viewer",
  "version": 1,
  "created_at": "2026-09-18T10:00:00Z",
  "updated_at": "2026-09-18T10:00:00Z"
}
```

All todo responses add `version` while retaining the existing todo fields.

### `POST /api/v1/todo-shares`

- **Authentication**: Required; authenticated user becomes `owner_id`.
- **Request body**:

```json
{
  "recipient_email": "collaborator@example.com",
  "permission": "viewer"
}
```

- **Validation**:
  - `recipient_email` must be syntactically valid and normalized consistently with user registration.
  - Recipient must be an existing active user.
  - `permission` must be exactly `viewer` or `editor`.
  - Recipient must not be the owner.
  - No `(owner_id, grantee_id)` grant may already exist.
- **Success**: HTTP 201 with `TodoListShareResponse`; include `ETag: "<version>"`.
- **Errors**: 401 invalid authentication; 409 `SHARE_ALREADY_EXISTS`; 422 `SELF_SHARE_NOT_ALLOWED`, `RECIPIENT_UNAVAILABLE`, or request validation error.
- **Privacy**: `RECIPIENT_UNAVAILABLE` uses a generic message for nonexistent, disabled, or otherwise ineligible recipients to limit account enumeration.

### `GET /api/v1/todo-shares`

- **Authentication**: Required.
- **Request body**: None.
- **Query validation**: `page >= 1`; `1 <= size <= 100`; optional `permission` must be `viewer` or `editor`.
- **Success**: HTTP 200 with `{ "items": [...], "total": 1, "page": 1, "size": 20 }`, containing only grants where `owner_id` is the current user.
- **Errors**: 401 invalid authentication; 422 invalid query parameters.

### `PATCH /api/v1/todo-shares/{share_id}`

- **Authentication**: Required; only the share owner may call it.
- **Request body**:

```json
{
  "permission": "editor"
}
```

- **Headers**: `If-Match: "<current-version>"` is required.
- **Validation**: UUID path; permission enum; current positive integer version; requested permission must differ from the stored value.
- **Success**: HTTP 200 with the updated `TodoListShareResponse`, incremented `version`, updated `ETag`, and invalidated collaborator caches.
- **Errors**: 401 invalid authentication; 404 `SHARE_NOT_FOUND`; 409 `SHARE_VERSION_CONFLICT`; 422 invalid permission or missing/invalid precondition.

### `DELETE /api/v1/todo-shares/{share_id}`

- **Authentication**: Required; only the share owner may call it.
- **Request body**: None.
- **Headers**: `If-Match: "<current-version>"` is required.
- **Validation**: UUID path and positive integer version.
- **Success**: HTTP 204 after the delete transaction commits and synchronous invalidation is attempted.
- **Errors**: 401 invalid authentication; 404 `SHARE_NOT_FOUND`; 409 `SHARE_VERSION_CONFLICT`; 422 invalid precondition.

### `GET /api/v1/shared-todo-lists`

- **Authentication**: Required; current user is the grantee.
- **Request body**: None.
- **Query validation**: `page >= 1`; `1 <= size <= 100`; optional permission enum.
- **Success**: HTTP 200 with paginated entries containing owner ID, owner display email, permission, share version, and timestamps.
- **Errors**: 401 invalid authentication; 422 invalid query parameters.

### `GET /api/v1/todo-lists/{owner_id}/todos`

- **Authentication**: Required; owner, viewer, or editor.
- **Request body**: None.
- **Query validation**: UUID owner; `page >= 1`; `1 <= size <= 100`.
- **Success**: HTTP 200 with the existing paginated todo-list response, ordered by `created_at DESC, id DESC`.
- **Errors**: 401 invalid authentication; 404 `TODO_LIST_NOT_FOUND` for nonexistent or unauthorized lists; 422 invalid parameters.

### `POST /api/v1/todo-lists/{owner_id}/todos`

- **Authentication**: Required; owner or editor.
- **Request body**: Existing `TodoCreate` schema, for example `{ "title": "Review draft", "description": "Optional details" }`.
- **Validation**: UUID owner; existing title and description bounds; reject client-supplied `user_id`, completion state, or version.
- **Success**: HTTP 201 with the created todo; `user_id` equals `owner_id`, regardless of the actor.
- **Errors**: 401 invalid authentication; 403 `INSUFFICIENT_PERMISSION` for an authenticated viewer; 404 `TODO_LIST_NOT_FOUND` for unshared/nonexistent list; 422 request validation error.

### `GET /api/v1/todo-lists/{owner_id}/todos/{todo_id}`

- **Authentication**: Required; owner, viewer, or editor.
- **Request body**: None.
- **Validation**: Both path values must be UUIDs; the todo must satisfy both `id = todo_id` and `user_id = owner_id`.
- **Success**: HTTP 200 with the todo response and current version.
- **Errors**: 401 invalid authentication; 404 `TODO_NOT_FOUND` for nonexistent, mismatched-owner, or unauthorized resources; 422 invalid UUID.

### `PATCH /api/v1/todo-lists/{owner_id}/todos/{todo_id}`

- **Authentication**: Required; owner or editor.
- **Request body**: Partial `TodoUpdate`; at least one of `title`, `description`, or `completed` must be supplied. Omitted fields remain unchanged; explicit `null` is accepted only where the current schema allows it.
- **Headers**: `If-Match: "<current-todo-version>"` is required.
- **Validation**: UUID paths; existing field bounds; no `user_id`, owner, or version field in the body.
- **Success**: HTTP 200 with the updated todo and incremented version.
- **Errors**: 401 invalid authentication; 403 `INSUFFICIENT_PERMISSION` for a viewer; 404 `TODO_NOT_FOUND`; 409 `TODO_VERSION_CONFLICT`; 422 invalid payload/precondition.

### `DELETE /api/v1/todo-lists/{owner_id}/todos/{todo_id}`

- **Authentication**: Required; owner or editor.
- **Request body**: None.
- **Headers**: `If-Match: "<current-todo-version>"` is required.
- **Validation**: UUID paths and positive integer version.
- **Success**: HTTP 204.
- **Errors**: 401 invalid authentication; 403 `INSUFFICIENT_PERMISSION` for a viewer; 404 `TODO_NOT_FOUND`; 409 `TODO_VERSION_CONFLICT`; 422 invalid precondition.

### Standard error payload

All new endpoints use one machine-readable shape:

```json
{
  "error": {
    "code": "SHARE_ALREADY_EXISTS",
    "message": "This user already has access to the todo list.",
    "details": {
      "field": "recipient_email"
    },
    "request_id": "req_01J7EXAMPLE"
  }
}
```

Validation example:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request is invalid.",
    "details": {
      "fields": {
        "permission": "Must be one of: viewer, editor."
      }
    },
    "request_id": "req_01J7EXAMPLE"
  }
}
```

Status semantics:

- `400`: Semantically malformed request not covered by field validation.
- `401`: Missing, expired, malformed, or otherwise invalid access token.
- `403`: Authenticated caller can discover the list through a valid grant but lacks the required permission, such as a viewer attempting a mutation.
- `404`: Resource does not exist or its existence must not be disclosed to an unshared caller.
- `409`: Duplicate grant or optimistic concurrency conflict.
- `422`: Schema, field, or precondition validation failed.

## 6. Business Logic & Security Considerations

### Authorization matrix

“Delete” means deleting a todo, not deleting another user's account or list.

| Operation | Owner | Editor | Viewer | Unshared user |
|---|---:|---:|---:|---:|
| Read list/todo | Allow | Allow | Allow | Deny (404) |
| Create todo | Allow | Allow | Deny (403) | Deny (404) |
| Update todo | Allow | Allow | Deny (403) | Deny (404) |
| Delete todo | Allow | Allow | Deny (403) | Deny (404) |
| Create share | Allow | Deny | Deny | Deny |
| Change permission | Allow | Deny | Deny | Deny |
| Revoke access | Allow | Deny | Deny | Deny |
| Transfer ownership | Not in scope | Deny | Deny | Deny |

Rules:

- The authenticated user ID is the only source for the actor identity.
- `owner_id` comes from the validated path/current owner, never from a mutation body.
- Every shared request checks owner status or the current database grant before reading Redis or executing SQL.
- Todo lookup always includes both `todo_id` and `owner_id`.
- Collaborators cannot re-share, manage other collaborators, or change ownership.
- The owner's rights are intrinsic and cannot be downgraded or revoked through this feature.

### Edge cases

#### Self-sharing

- Prevented by request validation and `CHECK (owner_id <> grantee_id)` as defense in depth.
- Returns HTTP 422 `SELF_SHARE_NOT_ALLOWED`.

#### Duplicate invite/share

- This release creates immediate grants only for registered users; there is no pending invitation state.
- Repeating a grant for the same owner/grantee returns HTTP 409 `SHARE_ALREADY_EXISTS`.
- Concurrent duplicate creates are resolved by `UNIQUE (owner_id, grantee_id)`; the losing transaction maps the database constraint error to the same 409 response.
- A duplicate request with a different permission does not silently upgrade or downgrade access; the owner must use `PATCH`.

#### Permission upgrades and downgrades

- Owner-only and optimistic-lock protected.
- Upgrades take effect after commit and relevant caches are invalidated.
- Downgrades remove mutation authority after commit. Authorization is database-backed, so an old cache entry cannot preserve editor rights.

#### Concurrent owner/editor todo changes

- Mutations require the current todo version.
- The first committed mutation increments the version; later writes using the old version return HTTP 409 `TODO_VERSION_CONFLICT`.
- No last-write-wins overwrite is performed silently.

#### Concurrent revoke and editor mutation

- A shared mutation reads and locks the grant row within the mutation transaction before changing a todo.
- Revocation deletes the same grant row under a conflicting row lock.
- If the editor transaction acquires the lock first, it may commit before revocation; the revoke waits and returns only after deletion commits.
- If revocation acquires the lock first, the editor request finds no grant after the lock is released and is denied.
- Therefore, after the revoke response is returned, no new editor mutation can be authorized under the deleted grant.

#### Deleted users and todos

- Deleting an owner cascades owned todos and all issued shares.
- Deleting a grantee cascades received shares without touching owner data.
- A deleted todo returns the same 404 as an unauthorized or unknown todo.
- A user deletion racing with share creation is resolved by foreign keys; no orphan grant can commit.

#### Owner behavior

- Owner access does not depend on a share row.
- Owners cannot create a share to themselves.
- Revoking or changing a collaborator never changes `todos.user_id`.
- Only account deletion removes ownership in this release; ownership transfer is out of scope.

#### Immediate access removal

- Revocation is considered successful only after the database delete commits.
- Shared endpoint authorization never trusts a cached permission decision.
- Former collaborators receive 404 for subsequent list/todo reads and cannot receive cached data.
- The frontend treats a 403/404 from a previously shared list as access removal, removes that owner's private queries, and navigates back to the shared-list index.

## 7. Caching & Invalidation Strategy

### Authorization boundary

Redis is never the source of truth for access. Before any shared list cache lookup, the backend verifies one of:

1. `current_user.id == owner_id`, or
2. a current `todo_list_shares(owner_id, grantee_id)` row with sufficient permission.

Permission decisions and negative authorization results are not cached in the first release. This guarantees a committed revoke or downgrade is observed by the next request even if stale response data remains in Redis.

### Cache keys

Owner list responses:

```text
todos:list:owner:{owner_id}:actor:{actor_id}:version:{data_version}:page:{page}:size:{size}
```

Received-share index:

```text
todo-shares:received:user:{grantee_id}:page:{page}:size:{size}:permission:{permission_or_all}
```

Issued-share index:

```text
todo-shares:issued:owner:{owner_id}:page:{page}:size:{size}:permission:{permission_or_all}
```

Rules:

- Keys contain stable UUIDs and response-scope parameters only; never bearer tokens, passwords, emails, or secrets.
- `actor_id` prevents owner and collaborator cache aliasing and permits targeted revocation cleanup.
- `data_version` is an owner-scoped Redis integer incremented after a committed todo mutation. Old versions expire naturally and are no longer referenced.
- Cache TTL remains bounded; five minutes is acceptable for response storage because authorization is always rechecked.

### Invalidation events

| Event | Required invalidation |
|---|---|
| Todo create/update/delete by owner or editor | After commit, increment owner `data_version`; invalidate any non-versioned compatibility keys. |
| Share create | Invalidate owner's issued-share index and grantee's received-share index. |
| Permission change | Invalidate both share indexes and all list response keys for that owner/grantee actor pair. |
| Revoke | After commit, synchronously invalidate both share indexes and all owner/grantee list response keys before returning where Redis is available. |
| Owner deletion | Delete owner list/share namespaces; database authorization prevents access if cleanup is delayed. |
| Grantee deletion | Delete grantee received-share and actor-specific namespaces. |

If Redis invalidation fails after a committed revoke, the endpoint records an operational error and schedules retry, but access remains denied because database authorization occurs before cache reads. Cached payloads must not be returned by a background or fallback path that skips authorization.

## 8. Concurrency & Consistency

### Transaction boundaries

- Share create, permission change, and revoke each run in one database transaction.
- Todo mutations and their optimistic version increments run in one transaction.
- Cache invalidation occurs only after a successful commit; rollback leaves the prior cache valid.
- API success is not returned before the database state is durable.

### Share concurrency

- `UNIQUE (owner_id, grantee_id)` is the final guard against duplicate grants.
- `PATCH` and `DELETE` compare `If-Match` to `todo_list_shares.version`.
- Version mismatch returns 409 without changing state; clients refetch before retrying.
- Grant rows are locked during authorization for shared mutations to serialize safely with downgrade/revoke operations.

### Todo concurrency

- Owner and editor mutations require the current `todos.version`.
- SQL conditions include todo ID, owner ID, and expected version.
- A successful update increments the version exactly once.
- A conflict returns the current resource version only if the caller is still authorized; otherwise it returns the authorization-safe 404/403 response.

### Isolation and response ordering

- Recommended database isolation is PostgreSQL `READ COMMITTED` plus explicit row locks and version predicates; full serializable isolation is not required.
- A mutation that acquired the grant lock before a revoke may finish before the revoke completes. The revoke response defines the point after which the removed user can no longer authorize new work.
- Cache invalidation follows commit to prevent a concurrent reader from repopulating data that was not yet visible. Database authorization before every shared cache read prevents revoked access during any invalidation window.

### Observability

- Emit structured audit events for share creation, permission changes, revocation, and denied shared mutations without logging tokens or todo contents.
- Include actor ID, owner ID, share ID, old/new permission when applicable, request ID, outcome, and timestamp.
- Monitor authorization-denial rates, cache invalidation failures, and optimistic-lock conflict rates.

## 9. Rollout and Migration Safety

- Add `todos.version` as non-null with a safe default in a backward-compatible migration.
- Create `todo_list_shares` and indexes before deploying endpoints that reference them.
- Deploy authorization-aware backend code before enabling frontend sharing controls.
- Existing owner-only `/todos` behavior remains available throughout rollout.
- Rollback removes feature exposure first; retain the table during rollback to avoid destructive data loss until a later reviewed migration.

## 10. Test Strategy

Minimum automated coverage:

- Owner creates viewer/editor grants successfully.
- Self-share and duplicate concurrent share attempts are rejected.
- Viewer can read but cannot create, update, or delete.
- Editor can read and perform allowed todo mutations while ownership remains unchanged.
- Editor/viewer cannot manage shares.
- Permission upgrade and downgrade take effect after commit.
- Revocation immediately blocks cached reads and mutations.
- Unshared users receive authorization-safe 404 responses.
- Owner and editor concurrent updates produce one success and one version conflict.
- Concurrent revoke/editor mutation obeys the defined lock ordering.
- Owner/grantee deletion cascades only the intended rows.
- Cache keys are scoped by owner, actor, pagination, and data version.

Manual validation should include two independent sessions, visible permission transitions, revocation while the collaborator page is open, and confirmation that no stale private todo remains visible after the next API response.
