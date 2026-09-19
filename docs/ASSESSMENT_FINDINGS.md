# Confirmed Tier 1 Assessment Findings

This report contains only the Tier 1 defects that were reproduced, fixed, and verified during the assessment. Dismissed, speculative, infrastructure, documentation, and Tier 3 findings are excluded.

## BUG-01 — Expired access tokens were accepted

Location: `backend/app/core/security.py` (`verify_token`) and `backend/app/api/deps.py` (`get_current_user`).

Severity: High.

Reason: JWT decoding explicitly set `verify_exp` to `False`, so a correctly signed access token continued to authenticate after its expiration time. This defeated the configured session lifetime and extended access beyond the intended authentication boundary.

Fix Proposal: Centralize JWT verification, require an expiration claim, enable expiration validation, and have access-protected dependencies request an access token explicitly.

Implemented Fix: `verify_token` now requires an expected token type and decodes with `verify_exp=True` and `require_exp=True`; `get_current_user` requires `type=access`.

Regression Evidence: `backend/tests/test_auth.py::test_valid_access_token_is_accepted`, `test_expired_access_token_is_rejected`, `test_tampered_access_token_is_rejected`, and `test_malformed_access_token_is_rejected`. Tampered and malformed rejection are retained guards rather than newly failing baseline cases.

Commit: `b751a87` — `fix(auth): enforce JWT expiration and token type`.

## BUG-02 — Refresh tokens could authenticate access-protected endpoints

Location: `backend/app/core/security.py` (`verify_token`), `backend/app/api/deps.py` (`get_current_user`), and `backend/app/api/v1/auth.py` (`refresh_token`).

Severity: High.

Reason: The shared decoder accepted either token type, and the access dependency did not enforce the `type` claim. A longer-lived refresh token could therefore be presented directly to an access-protected endpoint.

Fix Proposal: Make token type part of centralized verification, require `access` at protected endpoints, and require `refresh` at the refresh-only flow.

Implemented Fix: Callers must pass `expected_type`; verification rejects any payload whose explicit `type` differs. Access and refresh paths now select their required types at the validation boundary.

Regression Evidence: `backend/tests/test_auth.py::test_refresh_token_is_rejected_by_access_endpoint`, `test_valid_refresh_token_is_accepted_by_refresh_flow`, and `test_access_token_is_rejected_by_refresh_flow` verify both directions of the token boundary.

Commit: `b751a87` — `fix(auth): enforce JWT expiration and token type`.

## BUG-03 — Cross-user todo read, update, and delete were possible

Location: `backend/app/services/todo_service.py` (`get_todo_by_id`) and the item handlers in `backend/app/api/v1/todos.py`.

Severity: Critical.

Reason: Single-todo lookup filtered only by todo ID. Any authenticated user who obtained another user's todo UUID could retrieve, modify, or delete that resource.

Fix Proposal: Enforce ownership in the database query by selecting with both todo ID and the authenticated user's ID, and reuse that lookup for read, update, and delete.

Implemented Fix: `get_todo_by_id` now requires `user_id` and applies both predicates. All three item endpoints pass `current_user.id` and return the same HTTP 404 used for nonexistent resources.

Regression Evidence: `backend/tests/test_todos.py::test_owner_can_read_update_and_delete_own_todo` verifies the allowed path. `test_non_owner_cannot_read_update_or_delete_todos` uses two distinct users, expects HTTP 404 for all foreign operations, and confirms the owner's resources remain accessible and unchanged.

Commit: `f6718cf` — `fix(todos): enforce ownership for item operations`.

## BUG-04 — Todo-list cache keys leaked and aliased responses

Location: `backend/app/api/v1/todos.py` (`todo_list_cache_key` and `list_todos`) and the persistent Redis test double in `backend/tests/conftest.py`.

Severity: Critical.

Reason: Every list response used the constant key `todos:list`. Cached data could cross user boundaries, and different page or page-size requests could reuse an incompatible response.

Fix Proposal: Define one deterministic key containing every response-scope dimension: authenticated user ID, page, and page size. Keep credentials and other secrets out of the key.

Implemented Fix: List responses now use `todos:list:user:{user_id}:page:{page}:size:{size}`. The Redis test fixture persists state across requests within a test so cache reuse is exercised rather than mocked away.

Regression Evidence: `backend/tests/test_todos.py::test_todo_list_cache_is_isolated_by_user`, `test_todo_list_cache_is_isolated_by_page`, and `test_todo_list_cache_is_isolated_by_page_size` populate one cache variant and verify that a differently scoped request cannot reuse it.

Commit: `197895c` — `fix(cache): scope todo lists by user and pagination`.

## BUG-05 — Todo mutations left stale list caches

Location: `backend/app/api/v1/todos.py` (`commit_and_invalidate_todo_lists` and the create/update/delete handlers) and `backend/app/core/redis.py` (`delete_pattern`).

Severity: High.

Reason: Create, update, and delete changed database state without removing cached list responses. Subsequent GET requests could return stale data until cache expiry. Invalidating before commit would also permit a concurrent GET to repopulate data that was not yet committed.

Fix Proposal: Centralize user-scoped invalidation, explicitly commit the mutation first, then delete all list variants belonging to that user.

Implemented Fix: Each mutation calls `commit_and_invalidate_todo_lists`, which commits before deleting `todos:list:user:{user_id}:*`. Redis pattern deletion uses `SCAN`-based iteration rather than a global cache flush.

Regression Evidence: `backend/tests/test_todos.py::test_create_invalidates_cached_todo_list`, `test_update_invalidates_cached_todo_list`, and `test_delete_invalidates_cached_todo_list` verify fresh responses for all mutations. `test_mutation_invalidates_all_user_pagination_variants` verifies all variants are removed, and `test_user_mutation_preserves_other_users_cache` verifies invalidation remains user-scoped.

Commit: `d4b87e5` — `fix(cache): invalidate todo lists after mutations`.

## BUG-06 — Updating `completed` to `false` was ignored

Location: `backend/app/api/v1/todos.py` (`update_existing_todo`).

Severity: Medium.

Reason: The update handler used `if todo_data.completed`, so the valid boolean value `False` was treated as if the field had not been supplied.

Fix Proposal: Apply supplied-field semantics instead of truthiness and pass all explicitly provided values to the service layer.

Implemented Fix: The handler now uses `todo_data.model_dump(exclude_unset=True)` and applies the resulting dictionary through `update_todo`, preserving explicit falsy values.

Regression Evidence: `backend/tests/test_todos.py::test_completed_can_toggle_from_false_to_true_and_back` checks both response values and subsequent GET results for `false -> true -> false` persistence.

Commit: `4496088` — `fix(todos): preserve explicit falsy partial updates`.

## BUG-07 — A title-only update erased the todo description

Location: `backend/app/api/v1/todos.py` (`update_existing_todo`).

Severity: High.

Reason: Calling `model_dump()` without excluding unset fields materialized omitted optional fields as defaults. A title-only payload therefore included `description=None` and overwrote stored data.

Fix Proposal: Distinguish omitted fields from explicitly supplied values with Pydantic's `exclude_unset` behavior.

Implemented Fix: The endpoint builds its update dictionary with `model_dump(exclude_unset=True)`. Omitted values remain unchanged, while explicit `null` is still applied where the schema permits it.

Regression Evidence: `backend/tests/test_todos.py::test_title_only_update_preserves_description` verifies the response and persisted record; `test_empty_update_preserves_all_fields` and `test_explicit_null_description_clears_description` guard the omitted-versus-explicit-null boundary.

Commit: `4496088` — `fix(todos): preserve explicit falsy partial updates`.

## BUG-10 — Login failures disclosed whether an account existed

Location: `backend/app/api/v1/auth.py` (`login`) and `backend/app/services/auth_service.py` (`authenticate_user`).

Severity: High.

Reason: An unknown email returned HTTP 404 with `User with this email not found`, while a known email with a wrong password returned HTTP 401 with `Incorrect password`. The observable distinction enabled account enumeration and skipped password-hash work for unknown users.

Fix Proposal: Return one status and generic body for both failures and perform a dummy password verification for unknown accounts to reduce the trivial timing difference.

Implemented Fix: Login delegates to `authenticate_user` and returns HTTP 401 with `Invalid email or password` for either failure. Unknown users are checked against a fixed dummy bcrypt hash before returning.

Regression Evidence: `backend/tests/test_auth.py::test_login_failure_does_not_disclose_account_existence` compares both the status code and JSON body for known/wrong-password and unknown-email attempts. The validated manual plan also observed identical HTTP 401 bodies and redirect behavior.

Commit: `749efd6` — `fix(auth): prevent login account enumeration`.

## BUG-11 — Password validation did not enforce bcrypt-safe boundaries

Location: `backend/app/schemas/user.py` (`validate_password`, `Password`, `UserCreate`, and `UserLogin`) and `frontend/src/features/auth/schemas/auth.ts` (`passwordSchema`).

Severity: High.

Reason: The backend accepted unbounded passwords even though bcrypt's effective input boundary is 72 bytes. Distinct overlong UTF-8 credentials could be reduced to the same effective bcrypt input, while frontend validation enforced only a character minimum.

Fix Proposal: Keep the existing six-character minimum, reject passwords longer than 72 UTF-8 bytes before hashing or verification, and apply the same rule to frontend registration and login validation.

Implemented Fix: Backend and frontend schemas now enforce at least six Unicode characters and at most 72 UTF-8 bytes. The hashing algorithm was not changed.

Regression Evidence: `backend/tests/test_auth.py::test_registration_rejects_password_below_minimum`, `test_registration_accepts_72_byte_password`, `test_distinct_overlong_passwords_are_rejected_before_bcrypt`, `test_registration_validates_multibyte_password_by_utf8_bytes`, and `test_login_success` cover the boundaries and normal flow. Frontend lint/build validation covered the matching schema; no frontend unit-test suite exists.

Commit: `980434f` — `fix(auth): enforce safe password boundaries`.

## BUG-12 — User-scoped React Query data survived authentication changes

Location: `frontend/src/lib/authSession.ts`, `frontend/src/features/auth/api/auth.ts`, `frontend/src/features/auth/hooks/useAuth.ts`, and the HTTP 401 interceptor in `frontend/src/lib/api.ts`.

Severity: Critical.

Reason: Login, registration, logout, logout failure, and unauthorized resets changed local tokens independently but did not remove `currentUser` or `todos` from the singleton QueryClient. A later identity could therefore observe or reuse private data cached for the previous user.

Fix Proposal: Centralize auth-session establishment and cleanup, enumerate private query keys once, and remove those queries on session end, unauthorized reset, and before establishing a new identity.

Implemented Fix: `authSession.ts` defines `USER_SCOPED_QUERY_KEYS`, removes those queries through the existing singleton QueryClient, and centralizes token establishment/removal. Login, registration, explicit logout, logout error, and HTTP 401 handling all use the helper.

Regression Evidence:

- Implementation evidence: Every identified identity transition calls `establishAuthSession` or `clearAuthSession`; both remove `currentUser` and `todos` before the next identity can use them.
- Unit-test evidence: No frontend unit or component test infrastructure exists, so no focused QueryClient unit test is claimed.
- E2E evidence: `frontend/e2e/todo-journey.spec.ts` verifies logout removes access to private UI, and `frontend/e2e/todo-isolation.spec.ts` verifies two independent users do not see each other's todos. These are supporting runtime checks; they do not directly inspect QueryClient internals or exercise same-context User A to User B login.

Commit: `97cd3af` — `fix(frontend): clear user-scoped cache on auth changes`.

## BUG-13 — Failed optimistic todo updates did not restore prior state

Location: `frontend/src/features/todos/api/todos.ts` (`useUpdateTodo`).

Severity: Medium.

Reason: `onMutate` captured and returned the previous `todos` query data, but `onError` ignored the mutation context. A failed request could leave the UI showing an optimistic state that the server never accepted until a later refetch completed.

Fix Proposal: Consume the snapshot returned by `onMutate`, restore it in `onError`, preserve the user-facing error, and retain settled invalidation for server reconciliation.

Implemented Fix: `onError` now receives the mutation context and restores `context.previousTodos` when present. The existing error toast and `onSettled` invalidation remain intact.

Regression Evidence:

- Implementation evidence: The snapshot is returned from `onMutate`, restored through `queryClient.setQueryData` on failure, and followed by the existing settled invalidation/refetch.
- Unit-test evidence: No frontend unit or component test infrastructure exists, so no focused failed-mutation rollback test is claimed.
- E2E evidence: `frontend/e2e/todo-journey.spec.ts` verifies the successful optimistic update and reload persistence path only. The E2E suite does not inject a mutation failure, so it is not claimed as rollback coverage; rollback verification is deterministic code-path inspection plus the fix-time frontend lint/build checks.

Commit: `37c6aa7` — `fix(frontend): restore todo state after failed mutations`.
