# NOTES

## 1. Design

State lives in PostgreSQL. The UI is a thin client over the API; the API is the source of truth for authorization and workflow.

```
users 1──* dataset_requests 1──* assignments *──1 episodes
                      │
                      └──* status_events (who, when, from → to)
```

An assignment unique constraint on `episode_pk` is what makes “an episode belongs to at most one request” a database fact, not a hope. Status is a column on the request plus an append-only event log. The column is for “where is it now?” queries; the log is for audit and for the median fulfilment-time query.

Hardest decisions:

1. **First row wins on import.** `EP-00011` appears twice in the seed file with different quality (`bad` then `good`). Updating in place would make a re-import non-deterministic depending on file order. Skipping duplicates (in-file and already in the DB) is idempotent and explainable. Operators can correct a record later if we add an edit path.
2. **Keep assignments on reject.** Rework means “this delivery was not accepted,” not “throw the clips away.” Operators can unassign during `in_progress` / `rejected` if they need to reshuffle. They cannot unassign after `delivered`/`accepted`.
3. **Normalise messy CSV instead of rejecting every inconsistency.** Whitespace, `Good`/`USABLE`, mixed date formats, `EP-` vs `ep-`, and `45.5` seconds are recoverable. Unknown robots, missing ids, `excellent` quality, negative/huge durations, and future timestamps are not — those are skipped with a reason.

Known robots: `arm-01`, `arm-02`, `arm-03`, `mobile-01`, `humanoid-01`. Duration must be in `(0, 600]` seconds (seed clips are 8–120s; `999999` is treated as corrupt). `recorded_at` in the future is skipped (`2031-01-01` in the seed file).

## 2. Left out / next two days

Left out: episode video files (the brief is metadata), pagination beyond a 200/1000 cap, request comments, multi-worker SSE (in-process pub/sub), password-reset, and a public deploy.

With two more days: Postgres `LISTEN/NOTIFY` so SSE works across API replicas; cursor pagination on episodes; a request-level activity feed in the UI; and a second stretch (retryable export jobs) once live updates exist.

## 3. Something that went wrong

The seed CSV looks like a header plus clean rows until you tally it. Duplicates are not always identical (`EP-00011` quality flip; `ep-00003` vs `EP-00003`). A unique index on the raw string would have stored both. Normalising ids to uppercase before insert made idempotency real. I diagnosed it by grepping `episode_id` frequencies and writing parser tests against the ugly rows rather than a cleaned fixture.

A second trap: holding a SQLAlchemy session open for the lifetime of an SSE connection would leak pool connections. Auth for `/api/events` loads the user, closes the session, then streams.

## 4. Security

- Passwords: bcrypt hashes only. Seed JSON is a bootstrap file, not the database.
- Tokens: HS256 JWTs, expiry from config, `SECRET_KEY` from the environment. The UI stores the token in `localStorage` (XSS would steal it; httpOnly cookies would be the production default).
- Validation: Pydantic on write paths; CSV cells are parsed, not `eval`’d; task names are stripped/lowercased; file import requires a `.csv` name and operator/admin role.
- Server-side authz: clients get 404 on other people’s request ids (no existence leak). Operators cannot accept/reject. Clients cannot assign or import.

Two vulnerabilities I would worry about most in this kind of system:

1. **IDOR / confused deputy on requests and assignments** if a future endpoint takes a client id from the body. Always take the client from the session.
2. **Data exfiltration of the episode catalogue.** Operators see all metadata. If a later version exposes video URLs, those must be short-lived signed URLs, not a world-readable bucket. XSS on the ops UI plus `localStorage` tokens is the practical steal path today.

## 5. Scale

At 10× users the first pain is not Postgres, it is the operator episode table (unpaginated scan + filters) and the in-memory SSE fan-out (one process, no replay).

At 100× episodes (tens of millions of rows) the import `SELECT existing ids` plus bulk insert still works if you batch (e.g. 5k rows) and keep the unique index. Analytics is the query that breaks first without indexes: `recorded_at` + `robot_id` (already added), and `quality` + `task_name` for the top-5. Median fulfilment uses `status_events` grouped by `request_id`; that stays small compared with episodes. I would **not** `SELECT *` into Python at 5 million rows — `PERCENTILE_CONT` and `GROUP BY` stay on the server. After that: partition `episodes` by `recorded_at`, and consider a daily rollup table for the per-robot chart.

SQLite would lose `PERCENTILE_CONT`, `ON CONFLICT` bulk insert of this shape, and decent concurrent writes from two operators. The migration path is “use Postgres,” which is why the take-home does.

## 6. AI tooling

I used Cursor (Grok) to scaffold FastAPI/React/Docker boilerplate, draft tests, and pressure-check import edge cases against `seed/episodes.csv`. I specified the domain rules, import policy, and evaluation trade-offs, then read and adjusted the generated code (SSE session lifetime, first-wins import, assignment uniqueness, analytics SQL). I can change any of this in a live session.

**Stretch picked:** real-time operator desk via SSE.
