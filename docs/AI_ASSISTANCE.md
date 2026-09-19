# AI Assistance Disclosure

## Tools Used

- OpenAI Codex, operating as a GPT-5-based coding agent in the repository workspace.
- Codex workspace file-inspection, patching, and terminal-execution tools.
- Git for branch, diff, history, staging, and commit inspection.
- pytest for backend regression and full-suite validation.
- Playwright with Chromium for browser-level smoke, user-journey, data-isolation, and manual-plan execution support.
- Docker and Docker Compose for application services, clean builds, cold-start checks, isolated validation environments, and image inspection.
- Alembic and PostgreSQL tools, including `psql` and `EXPLAIN (ANALYZE, BUFFERS)`, for migration and measured query-performance work.
- Redis CLI for authentication, readiness, and cache-invalidation observations.
- npm, TypeScript/Vite build checks, ESLint, curl, and standard local shell utilities where appropriate.

No external application plugin was used to modify or submit the assessment.

## Areas of Assistance

AI assistance was used for:

- repository and requirement auditing;
- bug reproduction, root-cause investigation, and implementation assistance;
- authentication and authorization boundary review;
- backend regression-test design and execution;
- frontend session, cache, and optimistic-update lifecycle analysis;
- Playwright configuration and E2E scenario design;
- manual test-plan preparation and execution support;
- Todo Sharing technical-specification drafting and review;
- Docker build, readiness, secret-management, and Redis-security review;
- PostgreSQL seed, query-plan, indexing, migration-safety, and benchmark analysis; and
- final compliance, Git-scope, and documentation audits.

## Human Review / Approval

- The user approved the initial audit before implementation began and selected each subsequent task scope.
- Working-tree and staged diffs were inspected before assessment commits.
- Changes were kept in task-specific atomic commits; unrelated files and hunks were left unstaged.
- Relevant focused checks and broader test suites were run before commits when required by the task.
- Git pushes remained manually controlled and were not performed by the assistant.
- Database benchmark claims were accepted only when backed by real measured output from the preserved PostgreSQL dataset; fabricated or estimated timings were not used.
- Destructive operations, history rewriting, broad cleanup, and secret disclosure were not automatically approved.
- Final code, documentation, security decisions, and submission remain subject to human review.

## Prompt Categories

The major prompt categories were:

- initial repository and Tier 1 bug audit;
- JWT expiration, token-type, login-enumeration, and password-boundary fixes;
- todo ownership, partial-update, and data-integrity fixes;
- Redis cache isolation and mutation-invalidation fixes;
- frontend authentication-session and optimistic-mutation lifecycle fixes;
- backend regression coverage and Playwright setup/scenarios;
- manual test-plan creation and execution;
- Todo Sharing specification design;
- Docker ignore, image-size, secret, Redis-authentication, and service-readiness work;
- database seed correctness, BEFORE plans, index design, Alembic migration, AFTER plans, and benchmark documentation; and
- final Tier 1, Tier 2, Tier 3, Git, and assessment-compliance audits.

This is a category summary, not a transcript or prompt-log dump.

## Configuration

- Work was performed in the local repository on branch `assessment/le-hoang-tung`.
- The assistant used the repository's existing toolchain and project configuration except where an assessment task explicitly required adding or changing configuration.
- Commands were executed against local or disposable Docker environments; operational credentials used for validation were not recorded in assessment documentation.
- Commits were created only when explicitly requested. No remote push was performed by the assistant.

No temperature, token-count target, stop sequence, hidden model parameter, or other unknown runtime setting is claimed.

## Validation

Validation methods used during the assessment included:

- focused pytest regressions and complete backend test-suite runs;
- frontend lint and build/type checks;
- focused and complete Playwright runs in headless Chromium;
- direct browser, API, and Redis observations for the manual test plan;
- Docker image builds, startup and health checks, cold-start repetitions, and image-size/history inspection;
- authenticated and unauthenticated Redis probes;
- Docker Compose configuration validation;
- Alembic current/head, upgrade, downgrade, re-upgrade, and PostgreSQL index-metadata checks;
- reproducible seed tests and a measured one-million-todo benchmark dataset;
- repeated `EXPLAIN (ANALYZE, BUFFERS)` plans using comparable BEFORE and AFTER parameters; and
- Git status, history, complete diff, staged-diff, and whitespace checks.

## Limitations

- AI assistance does not replace independent human review, threat modeling, accessibility review, or production acceptance testing.
- The frontend has no dedicated unit/component test infrastructure. BUG-12 therefore has no focused QueryClient unit test, and BUG-13 has no automated failed-mutation rollback test; existing E2E coverage is supportive but does not directly cover those internal paths.
- During manual validation, invalid known-account and unknown-account logins returned equivalent generic HTTP 401 responses, but the global 401 redirect prevented the error toast from remaining visible. This is a known UX limitation, not an account-enumeration distinction.
- Database performance measurements describe the recorded local PostgreSQL dataset and environment; production hardware, concurrency, cache state, and data distribution may produce different absolute timings.
- Removing operational environment files from current tracking does not remove any values from earlier Git history. Any credential used outside disposable local development should be rotated separately.
- No Todo Sharing implementation was produced; that deliverable is specification-only.
