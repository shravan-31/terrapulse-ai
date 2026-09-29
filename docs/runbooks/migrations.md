# SatQuery AI — Database Migrations Runbook

## Overview
SatQuery AI uses Alembic with asynchronous SQLAlchemy (`asyncpg`) to manage schema evolutions across all 13 canonical tables:
- `aois`
- `scenes`
- `scene_assets`
- `tiles`
- `embeddings`
- `index_generations`
- `index_outbox`
- `analyses`
- `changes`
- `analyst_decisions`
- `provenance`
- `jobs`
- `job_events`

## Running Migrations

Always run migrations via the automated migration runner:
```bash
python scripts/migrate.py
```

This script:
1. Validates PostgreSQL connectivity.
2. Creates the target database if it does not already exist.
3. Escapes URL percent-encoding for configparser safety.
4. Executes `alembic upgrade head`.

## Rollback Procedures

To roll back the last applied migration:
```bash
cd backend
alembic downgrade -1
```

To roll back to base schema:
```bash
cd backend
alembic downgrade base
```

## Schema Invariants
- Vector IDs in `embeddings` are strictly `BIGINT` to ensure stable int64 mapping for FAISS `IndexIDMap2` (ADR-003).
- Spatial columns use PostGIS geometries when available, with conditional PL/pgSQL guards for systems without PostGIS C-extensions.
