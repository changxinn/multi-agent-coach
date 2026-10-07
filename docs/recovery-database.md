# Recovery database

Recovery owns PostgreSQL `recoverydb`, with schema `recovery`, credentials `RECOVERY_DB_USER` / `RECOVERY_DB_PASSWORD`, and persistent volume `recovery_postgres_data`.

Start with `docker compose up -d --build`. The Recovery Agent receives `RECOVERY_DATABASE_URL` and `RECOVERY_DATABASE_SCHEMA`; it never inherits the main application's database settings. Its schema is initialized at startup. User IDs are external references, so a local users table is not required.

The frontend Recovery Table keeps its authenticated `/api/recovery/sleep-logs`, `/check-ins`, and `/assessments` endpoints. The API forwards all list/create/update/delete requests to token-protected Recovery Agent endpoints. The dashboard also reads from this service. The browser receives no database credentials or internal service token.

## Existing records

Legacy tables in `systemdb` are retained. To copy their records, pause recovery writes and back up both databases. Set `RECOVERY_LEGACY_DATABASE_URL` to the source database and `RECOVERY_DATABASE_URL` to the destination, then run:

```powershell
python -m services.recovery_agent.migrate_legacy
```

Use `RECOVERY_LEGACY_SCHEMA` if the source schema is not `systemdb`. The copy preserves IDs/timestamps, advances sequences, skips identical records, and rolls back on conflicting IDs. Both databases must be reachable from the machine running the command. Compose databases are private to the Docker network by default.
