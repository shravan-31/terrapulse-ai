# SatQuery AI — Disaster Recovery & Durability Runbook

## 1. Vector Index (FAISS) Corruption or Loss

SatQuery AI implements ADR-003 Durable Vector Index Protocol. The database outbox table `index_outbox` acts as the single source of truth for vector embeddings.

### Rebuilding Index from Outbox & Database
If a `.faiss` snapshot is corrupted or deleted:
1. Stop API processes.
2. Delete the damaged snapshot in `indexes/`:
   ```bash
   rm indexes/*.faiss indexes/*.sha256
   ```
3. Run the outbox reconciler:
   ```python
   from app.services.faiss_service import FaissVectorIndex
   index = FaissVectorIndex(index_dir="indexes", dim=768)
   # On initialization, FaissVectorIndex inspects committed generations
   # and automatically replays pending rows from index_outbox into generation 1.
   ```
4. A new verified `.faiss` and `.sha256` snapshot will be atomically committed to disk.

## 2. Ingestion Job Recovery & Worker Crash

If a Celery worker dies mid-ingestion:
1. `JobRepository` flags lingering `running` jobs on startup after timeout.
2. Clients reconnecting to `GET /api/jobs/{id}/events` via Server-Sent Events (SSE) send `Last-Event-ID`.
3. The server replays all events from the durable `job_events` table before streaming new real-time updates.

## 3. Database Failure & 503 Circuit Breaking
When PostgreSQL is temporarily unavailable:
- The system immediately returns structured HTTP 503 (`DatabaseUnavailableError`) with code `UPSTREAM_FAILURE`.
- It **never** silently falls back to in-memory mocks in production mode (`APP_ENV=production`), guaranteeing that no unpersisted data is falsely reported as saved.
