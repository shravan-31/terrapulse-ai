# Low-Resource Profile — SatQuery AI

Use this profile when GPU is unavailable or RAM is limited (e.g., ≤8 GB system RAM, CPU-only machine).

## Environment overrides

In your `.env` file:
```
DEVICE=cpu
BATCH_SIZE=2
WORKER_CONCURRENCY=1
CPU_THREADS=2
MAX_SCENES_PER_JOB=10
MAX_AOI_AREA_KM2=500
```

## Docker Compose

Run with a single worker:
```bash
docker compose up postgis redis backend -d
# Worker separately with concurrency=1:
docker compose run --rm worker celery -A app.workers.celery_app worker --concurrency=1
```

## Expected performance

- RemoteCLIP text embed: ~0.5–2 s/query on CPU (varies by batch size)
- Tile embedding: ~1–5 s/tile on CPU; 256 tiles ≈ 5–20 minutes
- ChangeFormer inference: ~5–30 s/pair on CPU depending on tile count
- Sequential model use: only one model loaded at a time (worker_concurrency=1)

These are estimates; run `scripts/evaluate.py` to measure actual performance.

## GPU OOM handling

If DEVICE=cuda and OOM occurs:
- Worker retries once with `BATCH_SIZE//2`
- On second OOM: job fails with structured error; no endless loop
- Set `DEVICE=cpu` as fallback in .env

## Note

CPU fallback is functional but slow. Measure and document actual latency for your hardware.
Do not claim GPU-level performance from CPU-only results.
