# Database Performance and Indexing Report

## 1. Objective

Tier 3C evaluates PostgreSQL query performance at scale. This report records
the required before-and-after `EXPLAIN (ANALYZE, BUFFERS)` evidence, explains
the selected index, and documents its operational tradeoffs.

The optimization was measured against the same preserved PostgreSQL database
and dataset. The database was not reseeded and query parameters were not
changed between the BEFORE and AFTER runs.

## 2. Benchmark Environment

| Property | Value |
|---|---:|
| PostgreSQL | 16.15 |
| Users | 10,000 |
| Todos | 1,000,000 |
| Completed false | 499,521 |
| Completed true | 500,479 |
| Representative-user todos | 100 |
| Representative-user distribution | 50 active, 50 completed |
| Pagination | `LIMIT 20 OFFSET 0` |
| Measurement method | Three `EXPLAIN (ANALYZE, BUFFERS)` runs; median execution time |

The representative user was
`837e9b19-5148-4c6f-8bc7-38527249865e`. Every benchmark user owned exactly
100 todos, so this user was neither unusually sparse nor dense.

## 3. Baseline Index State

Before optimization, the relevant indexes were:

```sql
CREATE UNIQUE INDEX todos_pkey ON public.todos USING btree (id);
CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id);
CREATE UNIQUE INDEX alembic_version_pkc
    ON public.alembic_version USING btree (version_num);
```

The `todos` table had no secondary index on `user_id`, `created_at`, or
`completed`. In particular, `ix_todos_user_created_id_desc` did not exist
during any BEFORE measurement.

## 4. Core Queries

### Q1 — User-filtered paginated todo list

This reflects the current application list-query shape.

```sql
SELECT id, title, description, completed, user_id, created_at, updated_at
FROM todos
WHERE user_id = '837e9b19-5148-4c6f-8bc7-38527249865e'
LIMIT 20 OFFSET 0;
```

### Q2 — User-filtered deterministic `created_at` ordering

```sql
SELECT id, title, description, completed, user_id, created_at, updated_at
FROM todos
WHERE user_id = '837e9b19-5148-4c6f-8bc7-38527249865e'::uuid
ORDER BY created_at DESC, id DESC
LIMIT 20 OFFSET 0;
```

Q2 is assessment benchmark evidence required to evaluate ordering by
`created_at`. The current application does not apply this ordering, so the
result must not be interpreted as a benchmark of existing production SQL.

### Q3 — Per-user todo count

This reflects the current application count-query shape.

```sql
SELECT count(*)
FROM todos
WHERE user_id = '837e9b19-5148-4c6f-8bc7-38527249865e';
```

## 5. BEFORE Results

### Q1

- Median execution time: **66.868 ms**
- Plan: **Parallel Sequential Scan**
- PostgreSQL launched two workers to locate 20 rows.
- The amount scanned depended on when the unordered `LIMIT` was satisfied;
  each worker discarded approximately 111,530–169,791 rows across the runs.
- No sort occurred because Q1 has no ordering clause.

### Q2

- Median execution time: **107.785 ms**
- Plan: **Parallel Sequential Scan + Sort + Gather Merge**
- PostgreSQL examined all 1,000,000 rows to find 100 matching rows.
- Approximately 999,900 rows were rejected by the filter.
- Each worker sorted its matches before `Gather Merge`.
- Sorting stayed in memory using quicksort or top-N heapsort with 31–35 kB
  per sorter; it did not spill to disk.
- The full-table scan, rather than the small sort, was the dominant cost.

### Q3

- Median execution time: **99.093 ms**
- Plan: **Parallel Sequential Scan**
- PostgreSQL examined all 1,000,000 rows to count 100 matches and discarded
  approximately 999,900 rows.
- The estimate of 100 matching rows was accurate after `ANALYZE`.
- The scan touched all 27,097 table blocks in each run.

## 6. Index Strategy

Alembic revision `b1e2f3a4c5d6` creates one non-unique index:

```sql
CREATE INDEX CONCURRENTLY ix_todos_user_created_id_desc
ON todos (user_id, created_at DESC, id DESC);
```

The column order was chosen for the measured workload:

- `user_id` is the equality prefix shared by Q1, Q2, and Q3.
- `created_at DESC` provides newest-first traversal for Q2.
- `id DESC` deterministically orders rows with identical timestamps.
- The leading `user_id` prefix remains useful to Q1 and Q3 without a
  separate, prefix-redundant `user_id` index.

Rejected alternatives:

- A narrow `(user_id)` index would support Q1 and Q3 but would retain Q2's
  explicit sort and could not directly provide deterministic ordered
  pagination.
- `(user_id, created_at DESC)` omits the `id` tie-break and therefore does not
  fully provide Q2's ordering.
- `completed` was not included because none of the measured application
  queries filters by completion status. Placing it between `user_id` and the
  ordering columns would also prevent one ordered scan across both completion
  values.
- A wide covering index containing titles or descriptions was rejected due
  to disproportionate storage, write amplification, and cache pressure.
- BRIN was rejected because the uniformly distributed user ownership is not
  physically correlated with heap ranges, and a BRIN index would neither
  efficiently satisfy the selective `user_id` lookup nor provide Q2's full
  ordering.

The migration uses Alembic's autocommit mechanism together with
`postgresql_concurrently=True`, so it emits PostgreSQL concurrent index
creation outside the normal migration transaction.

## 7. AFTER Results

### Q1

- Median execution time: **0.408 ms**
- Plan: **Index Scan** using `ix_todos_user_created_id_desc`
- The median run used 23 shared-buffer hits to return 20 rows.
- Heap access remained necessary because the query selects columns that are
  not stored in the index.

### Q2

- Median execution time: **0.061 ms**
- Plan: **Ordered Index Scan** using `ix_todos_user_created_id_desc`
- The explicit sort and `Gather Merge` were eliminated.
- PostgreSQL stopped after the first 20 matching ordered entries.
- Each run used 23 shared-buffer hits; heap access remained necessary for the
  selected non-indexed columns.

### Q3

- Median execution time: **0.083 ms**
- Plan: **Index Only Scan** using `ix_todos_user_created_id_desc`
- Actual matching rows: 100; estimated matching rows: 100.
- Heap fetches: **0**.
- Each run used five shared-buffer hits.

## 8. BEFORE / AFTER Comparison

The improvement percentage is `(Before - After) / Before * 100`.

| Query | Before | After | Delta | Improvement | Plan Change |
|---|---:|---:|---:|---:|---|
| Q1 — user-filtered page | 66.868 ms | 0.408 ms | -66.460 ms | 99.39% | Parallel Sequential Scan → Index Scan |
| Q2 — deterministic ordered page | 107.785 ms | 0.061 ms | -107.724 ms | 99.94% | Parallel Sequential Scan + Sort + Gather Merge → Ordered Index Scan |
| Q3 — per-user count | 99.093 ms | 0.083 ms | -99.010 ms | 99.92% | Parallel Sequential Scan → Index Only Scan |

The unrounded calculated improvements are 99.389843% for Q1, 99.943406% for
Q2, and 99.916240% for Q3.

## 9. Storage

| Object | Bytes | PostgreSQL display |
|---|---:|---:|
| Todos table, including TOAST | 222,068,736 | 212 MB |
| Composite index | 58,892,288 | 56 MB |
| Primary-key index | 40,181,760 | 38 MB |
| All todo indexes | 99,074,048 | 94 MB |
| Total todo relation | 321,142,784 | 306 MB |

The composite index added exactly 58,892,288 measured bytes. With unchanged
table data, the pre-index total derived from the measured components was
262,250,496 bytes, so the new index increased the total todo relation footprint
by approximately 22.46%.

PostgreSQL's `pg_size_pretty` output uses binary size boundaries while labels
such as `MB` are displayed. The byte measurements are therefore authoritative;
the displayed megabyte values are rounded human-readable representations and
must not be treated as decimal-MB conversions.

## 10. Tradeoffs

- **INSERT:** Each inserted todo now requires another B-tree entry, increasing
  CPU, page activity, and latency.
- **DELETE:** Deletes create dead index tuples that later require vacuum
  cleanup.
- **Indexed-column UPDATE:** Changing `user_id`, `created_at`, or `id` requires
  index maintenance. Updates to unrelated columns may still qualify for HOT
  updates when PostgreSQL's other HOT requirements are satisfied.
- **WAL:** Index creation and ongoing index maintenance generate additional
  write-ahead log volume, affecting replication and recovery traffic.
- **Cache pressure:** The 58,892,288-byte index competes with heap and other
  indexes for shared buffers and operating-system cache.
- **VACUUM and ANALYZE:** PostgreSQL must maintain and gather statistics for an
  additional index. Vacuum must remove dead index entries left by writes.
- **Visibility map:** Q3 achieved an index-only scan with zero heap fetches,
  but recently changed heap pages may not be all-visible. Under write-heavy
  traffic, the same plan can require heap fetches until vacuum restores
  visibility-map coverage.
- **Storage:** The index increases database, backup, snapshot, and replica
  storage requirements.

## 11. Production Migration Safety

The migration uses `CREATE INDEX CONCURRENTLY` through Alembic's
`autocommit_block()` and `postgresql_concurrently=True`. This preserves normal
insert, update, and delete availability during most of the build, unlike a
regular `CREATE INDEX` that blocks writes for the build duration.

Concurrent creation still has operational costs and coordination points:

- It performs additional table scans and consumes I/O, CPU, WAL, and temporary
  capacity.
- It waits for transactions and snapshots that could invalidate a safe build;
  long-running or old transactions can prolong migration time.
- PostgreSQL takes brief locks during setup and final catalog coordination, so
  concurrent creation does not mean lock-free creation.
- Progress should be monitored through `pg_stat_progress_create_index`.
- A failed or interrupted build can leave an invalid index. Deployment checks
  must inspect `pg_index.indisvalid` and `pg_index.indisready`; an invalid
  artifact should be removed before retrying rather than accepted by name.
- The migration deliberately does not use `IF NOT EXISTS`, because an existing
  same-name index could have incompatible columns, ordering, or validity.

Rollback uses Alembic's autocommit mechanism and concurrent index removal,
dropping only `ix_todos_user_created_id_desc`. This avoids the stronger locking
of ordinary index removal where PostgreSQL permits concurrent removal, but it
also runs outside a surrounding transactional rollback.

## 12. Limitations

- The synthetic dataset has a uniform distribution of exactly 100 todos per
  user; real workloads may be skewed.
- Measurements use one representative user.
- Pagination was measured only at `OFFSET 0`; deep offsets may behave
  differently.
- No concurrent application workload was present.
- Buffer warming influenced repeated executions; the results are neither
  strict cold-cache nor fully controlled warm-cache measurements.
- Index-only performance depends on visibility-map coverage and may require
  heap fetches after write activity.
- Write amplification was analyzed but not separately benchmarked.
- Q2 is assessment evidence rather than current production query behavior.

## 13. Validation

- BEFORE and AFTER runs used the same preserved database, one-million-row todo
  dataset, representative UUID, SQL, and pagination parameters.
- Each query used three `EXPLAIN (ANALYZE, BUFFERS)` runs and the median
  execution time; no fastest-run selection was used.
- Dataset counts and completion distribution were unchanged after migration.
- The installed index definition matched the migration and PostgreSQL reported
  it as ready and valid.
- Upgrade, downgrade, and re-upgrade were separately validated on disposable
  PostgreSQL before the AFTER benchmark.
- The migration's backend regression run completed with 40 passing tests.
