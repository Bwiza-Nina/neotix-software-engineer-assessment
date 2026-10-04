# Dataset Request Desk

Internal web platform for a robotics data-collection company. Clients submit dataset requests; operators import episode metadata, assign episodes, and move requests through fulfilment; clients accept or reject deliveries.

## Run everything

```bash
docker compose up --build
```

- UI: http://localhost:3000
- API: http://localhost:8000
- Health: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs

On startup the API runs migrations and seeds users from `seed/users.json`. Passwords are bcrypt-hashed before insert. Postgres is only on the compose network (not bound to host `5432`), so it will not collide with a local Postgres install.

## Seed logins

| Email | Password | Role |
|---|---|---|
| admin@example.com | admin123 | admin |
| ops1@example.com | ops123 | operator |
| ops2@example.com | ops123 | operator |
| client-a@example.com | client123 | client (Acme Robotics) |
| client-b@example.com | client123 | client (Beta Labs) |

After logging in as an operator, import `seed/episodes.csv` from the Episode library panel. The importer is idempotent: run it twice and the second run inserts nothing.

## Tests

```bash
docker compose up -d db
docker compose run --rm \
  -e DATABASE_URL=postgresql+psycopg://desk:desk@db:5432/desk_test \
  --entrypoint pytest api -q
```

Uses a separate `desk_test` database so the suite cannot wipe demo data. Requires Postgres (analytics uses `PERCENTILE_CONT` and `::date`). GitHub Actions runs the same suite.

## What is implemented

- JWT auth; every non-login endpoint is authenticated. Roles are enforced in the API, not only in the UI.
- Request workflow: `submitted → in_progress → delivered → accepted`, or `delivered → rejected → in_progress`.
- Assignments: one request at a time per episode; only `good`/`usable`; cannot deliver until the count is met. Every status change is stored on `status_events`.
- CSV import with normalisation, skip reasons, and idempotent upserts on `episode_id`.
- Analytics (SQL, not Python loops): episodes per day per robot, requests by status, median submitted→delivered time, top 5 tasks by good episodes.
- Structured JSON request logs (`method`, `path`, `status`, `duration_ms`, `user_id`).
- Stretch: **SSE live updates** for operators (new requests, status changes, assignments) without refreshing.

SQLite is not used. Production would keep PostgreSQL, rotate `SECRET_KEY`, and terminate TLS in front of the compose stack (or a managed equivalent).
