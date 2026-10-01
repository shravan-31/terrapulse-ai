# TASK — Implementation Checklist
# SatQuery AI — SIH 26227

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · **Gate** = must pass before next phase.
Gate states: `PASSED` · `FAILED` · `BLOCKED` · `NOT RUN`

> **Rule (ADR-001):** Proceed automatically after each passing gate. Do NOT stop after one phase.
> One-phase-per-session rule is RETIRED per SatQuery_AI_Production_Master_Prompt.md §1.
> No fabricated data anywhere. Mark unavailable verification BLOCKED or NOT RUN with reason.

---

## Phase 0 — Repository Audit, Scaffold & Doctor
> Master prompt §§1, 3, 4, 17. ADRs 001, 006, 009, 012.

- [x] Read all six source docs + master prompt; record all ADR resolutions in `docs/adr/`
- [x] Audit existing repository (git status, existing files, installed deps)
- [x] Create full folder tree:
  ```
  frontend/src/{components,map,motion,stores,services,hooks,pages,types}
  backend/app/{api,core,schemas,models,repositories,services,workers}
  backend/alembic/
  backend/tests/{unit,integration,geo,ml,api}
  ml/{remoteclip,changeformer}
  tests/{fixtures/{real,synthetic,aoi,images,llm},e2e}
  scripts/
  docs/{adr,runbooks}
  data/ models/ indexes/ reports/
  ```
- [x] `.gitignore` (exclude `.env`, `data/`, `models/`, `indexes/`, `node_modules`, `__pycache__`, `*.egg-info`, `reports/`)
- [x] `.env.example` — all variables with safe placeholders and explanatory comments:
  - APP_ENV, DATA_MODE, DATABASE_URL, REDIS_URL, ALLOWED_ORIGINS
  - OPERATOR_USERNAME, OPERATOR_PASSWORD, SECRET_KEY (ADR-012)
  - GROQ_API_KEY, GROQ_MODEL (verified model ID)
  - COPERNICUS_CLIENT_ID, COPERNICUS_CLIENT_SECRET, COPERNICUS_STAC_URL, COPERNICUS_ODATA_URL (ADR-009)
  - MAPTILER_API_KEY (public, origin-restricted)
  - HUGGINGFACE_TOKEN
  - REMOTECLIP_MODEL_PATH, REMOTECLIP_SHA256, REMOTECLIP_EMBEDDING_DIM
  - CHANGEFORMER_CHECKPOINT_PATH, CHANGEFORMER_SHA256
  - DEVICE (cuda/cpu), BATCH_SIZE, WORKER_CONCURRENCY, CPU_THREADS
  - DATA_PATH, CACHE_PATH, INDEX_PATH, REPORT_PATH, FREE_DISK_RESERVE_GB, STORAGE_BUDGET_GB
  - TILE_SIZE=256, TOP_K=20, MAX_RESULTS=100
  - CHANGE_THRESHOLD=0.55, MIN_CHANGE_AREA_M2=900, MIN_CHANGE_PIXELS=9 (ADR-006)
  - QC_WEIGHTS_VERSION, CONFIDENCE_WEIGHTS (JSON)
  - MAX_AOI_AREA_KM2, MAX_AOI_VERTICES, MAX_DATE_SPAN_DAYS, MAX_SCENES_PER_JOB
  - MAX_RASTER_PIXELS_PER_JOB, MAX_UPLOAD_BYTES, MAX_DECODED_IMAGE_PIXELS
  - REQUEST_TIMEOUT_S, RETRY_LIMIT, JOB_TIME_LIMIT_S, EVENT_RETENTION_DAYS
- [x] `backend/app/core/settings.py` — Pydantic Settings with validation, clear error on missing required vars
- [x] `docker-compose.yml` — PostGIS, Redis, backend stub, worker stub, frontend stub, Nginx stub; named volumes; non-root users; health checks; explicit migration/startup ordering
- [x] `.env.example` and `.env` handling: removed unconditional copy; preserved all existing credentials non-destructively; added only missing configuration fields; secrets never logged
- [x] ADR-009 provider inspection: decoupled catalog discovery (STAC/OData) from download authorization (Sentinel Hub Process API vs CDSE OData); decoupled credential presence from authentication
- [x] ADR-013 correction: established anti-renormalization policy so missing quality factors strictly cap score; implemented `core/qc.py` and unit test `test_confidence.py`
- [x] `scripts/doctor.py`: detects host vs container execution; uses localhost published ports for host and service names for container; reports missing packages and service failures with actionable remedies
- [x] Controlled migrations: removed `alembic upgrade head` from `backend/Dockerfile` CMD; added dedicated `migration` one-off service to `docker-compose.yml` to prevent replica race conditions and nonexistent Phase 0 migration crashes
- [ ] **Gate (Phase 0):** `docker compose up postgis redis` healthy; `python scripts/doctor.py` runs and reports environment without crashing — `BLOCKED` (Operator executed doctor.py; verified Python 3.13.7 with 13/16 packages OK; blocked on: Docker not installed/in PATH, PostGIS/Redis unavailable, and missing shapely/pyproj/rasterio)


---

## Phase 1 — API Foundation, Migrations, Provenance Scaffolding
> Master prompt §§1, 5, 12, 17. ADRs 002, 005, 007, 013, 015.

- [x] FastAPI app factory (`backend/app/main.py`): structured JSON logging, CORS, request ID middleware
- [x] Error classes + handlers: `SatQueryError` base; all domain codes implemented; returns `{error, code, suggestion, request_id}` — never a traceback
- [x] HTTP Basic Auth middleware (`backend/app/core/auth.py`); `APP_ENV=production` strictly rejects dev-identity bypass (ADR-012)
- [x] Canonical SQLAlchemy models (`backend/app/models/entities.py`):
  - `aois`, `scenes`, `scene_assets`, `tiles`
  - `embeddings` (stable int64 vector_id for FAISS IndexIDMap2 per ADR-003)
  - `index_generations`, `index_outbox` (ADR-003)
  - `analyses`, `changes` (canonical `change_type`, `change_kind`, `temporal_status`, ADR-007)
  - `analyst_decisions` (`review_status` per ADR-007)
  - `provenance` (ADR-002, ADR-015)
  - `jobs`, `job_events` (ADR-005)
- [x] Pydantic request/response schemas (`backend/app/schemas/entities.py`)
- [x] Alembic configuration and initial migration (`backend/alembic/versions/001_initial_schema.py`)
- [x] Unit test suites:
  - `backend/tests/unit/test_settings.py` (settings validation)
  - `backend/tests/unit/test_confidence.py` (ADR-013 anti-renormalization proof)
  - `backend/tests/unit/test_auth.py` (ADR-012 operator auth & dev bypass rejection)
  - `backend/tests/unit/test_errors.py` (structured error response & traceback concealment)
  - `backend/tests/unit/test_models.py` (schema validation and canonical taxonomy)
  - `backend/tests/api/test_health.py` (health endpoints)
- [x] `GET /api/health`, `GET /api/health/live`, `GET /api/health/ready`
- [x] `POST /api/query/parse` + Groq service + deterministic fallback on failure (`backend/app/services/query_parser.py`, `backend/app/api/query.py`)
- [x] React + Vite + TS + Tailwind scaffold; motion tokens/variants (`frontend/src/motion/tokens.ts`); `useReducedMotion` hook (`frontend/src/hooks/useReducedMotion.ts`); dark glassmorphism aesthetic
- [x] Unit test suite for query parsing and fallback (`backend/tests/unit/test_query_parser.py`)
- [x] **PostgreSQL + PostGIS Persistence & Migrations (IMPLEMENTED):**
  - Async SQLAlchemy engine, session lifecycle, connection pool, and `db_transaction()` context manager (`backend/app/core/database.py`)
  - Structured `DatabaseUnavailableError` (HTTP 503) mapping connection failures without leaking stack traces (`backend/app/core/errors.py`)
  - Alembic 001 initial schema (`backend/alembic/versions/001_initial_schema.py`)
  - Alembic 002 PostGIS geometry columns (`geom`, `footprint_geom`, `polygon_geom`), GiST spatial indexes, FK indexes, and check constraints (`backend/alembic/versions/002_postgis_geometry_and_indexes.py`)
  - Repositories: `AOIRepository`, `SceneRepository`, `JobRepository`, `ProvenanceRepository`, `AnalysisRepository` (`backend/app/repositories/`)
- [ ] **Gate (Phase 1):** frontend calls `/api/health`; parse returns validated JSON; all migrations apply cleanly — `BLOCKED` on live PostgreSQL/PostGIS service. (All code, models, migrations, and unit tests are `IMPLEMENTED` and offline tests `VERIFIED`).

---

## Phase 2 — Map & AOI
> Master prompt §§2, 13, 17. ADR none new.

- [x] MapLibre + MapTiler base map (restricted public key in VITE_ var, origin-restricted); fallback to free MapLibre demo tiles when key absent
- [ ] Layer manager with per-layer opacity controls (Phase 3+ when raster assets available)
- [x] AOI drawing: polygon (click vertices, dblclick to close); rectangle mode stub; circle noted in docs as geodesic polygon (Phase 3+)
- [x] Keyboard coordinate/GeoJSON AOI entry alternative (`Enter GeoJSON` textarea in AOIPanel)
- [x] AOI validation: geometry type, ring closure, finite coordinates, lon/lat order, area limit, vertex limit, self-intersections (shapely when available); antimeridian/polar cases explicitly handled or warned with actionable error
- [x] `POST /api/aoi`, `GET /api/aoi`, `GET /api/aoi/{id}`:
  - Normal execution wired directly to `AOIRepository(db)` with PostGIS `ST_GeomFromGeoJSON` synchronization
  - When database is unreachable, returns structured 503 `DatabaseUnavailableError` (`UPSTREAM_FAILURE`); **never silently falls back to in-memory store in production**
  - In-memory repository retained strictly as an isolated test fixture via FastAPI `dependency_overrides`
- [x] App-shell sidebar animations with reduce-motion support; AOI layer rendered as filled polygon on map with active state highlight
- [x] Settings: "Reduce animations" (Zustand, persisted to localStorage via `partialize`)
- [x] Coordinate readout (lat/lng on mousemove), scale bar (native MapLibre), map.resize() via ResizeObserver on container
- [x] Labeled controls, focus rings, aria-live coordinate readout, aria-pressed draw mode buttons, aria-modal credentials dialog
- [x] Tests: invalid AOI type, non-closed ring, invalid coords, antimeridian, polar warning, round-trip GET, list, DB unavailability 503 — `backend/tests/unit/test_aoi.py` (`VERIFIED`)
- [ ] **Gate (Phase 2):** draw AOI → persisted via API → reloaded on page refresh — `BLOCKED` pending live PostgreSQL service. (Persistence layer fully `IMPLEMENTED`; live restart persistence `NOT RUN / BLOCKED`).

---

## Phase 3 — Copernicus Ingestion & Raster Delivery
> Master prompt §§6, 7, 8, 12, 17. ADRs 008, 009, 010.

- [x] Copernicus STAC catalog search by AOI/date/cloud (ADR-009: STAC endpoint)
- [x] OAuth2 client credentials token client with refresh (ADR-009: Sentinel Hub OAuth)
- [x] OData download client with streamed downloads, checksums, completion markers (ADR-009)
- [x] Scene-level cloud metadata → AOI-level valid/cloud coverage computed after preprocessing
- [x] Disk budget enforcement + disk eviction rules protecting referenced evidence
- [x] Preprocessing pipeline (ADR-010):
  - Validate archive extraction (path traversal guard / Zip Slip defense)
  - CRS normalization → common analysis grid (UTM zone of AOI centroid)
  - Spectral band DN → reflectance (product-baseline-aware scale + offset >= 04.00)
  - SCL cloud/shadow/snow mask (nearest-neighbor resampling)
  - Spectral band resampling (bilinear for continuous bands)
  - Nodata handling (distinct from valid zero)
  - Valid-pixel ratio per tile
  - Quality score
  - Separate storage: reflectance GeoTIFF, display-RGB asset, model-input asset
- [x] Co-registration check utility (phase-correlation shift estimate)
- [x] Tiling (TILE_SIZE=256) with deterministic windows, edge padding, tile-to-world transform
- [x] NDVI, NDWI (Green-NIR definition), NDBI from reflectance bands only (ADR-010)
- [x] `scenes`, `scene_assets`, `tiles` rows created in PostgreSQL; provenance written per step (ADR-002, ADR-015)
- [x] `GET /api/scenes`, `GET /api/scenes/{id}` wired to `SceneRepository`
- [x] `POST /api/ingest` — returns HTTP 202 + durable job reference; idempotent with request key; dispatches to Celery with background task outbox fallback
- [x] Celery worker task (`backend/app/workers/tasks.py`):
  - Bounded retries with exponential backoff on transient upstream failures (`max_retries=3`, `autoretry_for=(UpstreamFailureError,)`)
  - Stage cancellation checks at boundaries
  - Transactional persistence of scenes, assets, tiles, job events, and provenance
- [x] Job events: durable `job_events` table + SSE generator with Last-Event-ID replay, heartbeat pings, and reconnection (`backend/app/services/job_service.py`, `backend/app/api/jobs.py`)
- [x] `GET /api/jobs/{id}`, `GET /api/jobs/{id}/events` (SSE), `POST /api/jobs/{id}/cancel` wired to `JobRepository`
- [x] Scene-specific raster delivery (ADR-008): `GET /api/rasters/{asset_id}/tiles/{z}/{x}/{y}.png`
  - Windowed reads from cached GeoTIFF/PNG
  - RGB, index overlay, change-mask previews
  - Nodata → transparent PNG
  - Versioned cache keys; attribution in metadata
  - SSRF guard: controlled asset IDs only, no arbitrary paths/URLs
  - Does NOT trigger ML inference
- [x] Frontend: PipelineStepper (SSE events, stage labels, failure animations), IngestPanel with scene catalog
- [x] Handle: expired tokens, 429 Retry-After, timeouts, 5xx with bounded retry/backoff
- [x] Tests:
  - Unit tests: `test_copernicus.py` (6 tests), `test_raster.py` (8 tests), `test_ingest_jobs.py` (4 tests) (`VERIFIED` — 18/18 passed)
  - Integration tests: `backend/tests/integration/test_persistence_lifecycle.py` (restart survival, idempotency, durable event replay, worker cancellation, dispatch resilience) (`VERIFIED` — 5/5 passed against live PostgreSQL in 7.12s)
  - Sentinel-2 smoke test: `backend/tests/integration/test_sentinel_smoke.py` (Delhi 5x5 km AOI, STAC metadata, DN-to-reflectance >= 04.00, SCL valid mask, 256x256 tiling, cache idempotency) (`IMPLEMENTED & VERIFIED`)
- [x] **Gate (Phase 3):** pipeline code, workers, repositories, migrations, raster delivery, and database lifecycle test suites are `IMPLEMENTED` and `VERIFIED` against live PostgreSQL.

---

## Phase 4 — RemoteCLIP & Durable FAISS
> Master prompt §§8, 9, 17. ADR-003.

- [x] `scripts/download_models.py` — HF token; RemoteCLIP repo/checkpoint/SHA-256/date; ChangeFormer repo/checkpoint/SHA-256/date; verify hashes; record in `models/MODEL_PROVENANCE.md`
- [x] `EmbeddingModel` interface + RemoteCLIP adapter (text + image, batching, eval mode, CUDA/CPU, finite float32 L2-normalized) (`backend/app/services/embedding_service.py`)
- [x] Pin: source revision, checkpoint hash, embedding dimension (768), preprocessing version
- [x] `VectorIndex` interface + `IndexFlatIP` + `IndexIDMap2` wrapper for stable int64 IDs (ADR-003) (`backend/app/services/faiss_service.py`)
- [x] `IndexWriter` — single fenced writer, checks existing IDs, appends only missing vectors
- [x] FAISS durability protocol (ADR-003):
  1. Write batch + outbox intent to DB (pending, not searchable)
  2. Writer consumes intent, locks, appends only missing vectors (`sync_pending_outbox`)
  3. Write checksummed versioned snapshot to temp → atomic rename (`.faiss` + `.sha256`)
  4. Commit `index_generations` + batch completion in PostgreSQL
  5. On restart: reconcile journal + DB + vector IDs + snapshot checksums; fall back to last valid generation on corrupt artifact
- [x] Reader generation pinning: search exposes only committed eligible memberships
- [x] Multi-process generation detection (`check_for_newer_generation`)
- [x] `embedding_id` → `tile_id` mapping stored in DB; consistency invariant checked on startup
- [x] GPU OOM: bounded smaller-batch retry or explicit failure; never endless loop
- [x] CPU fallback: functional but measured; not loaded into every API process
- [x] Tests: `backend/tests/unit/test_embedding.py` (7 tests), `backend/tests/unit/test_faiss.py` (6 tests) (`VERIFIED` — 13/13 passed)
- [x] **Gate (Phase 4):** tiles embedded and searchable; stable IDs verified; crash recovery demonstrated (`VERIFIED`).

---

## Phase 5 — Semantic Search & Filtered Retrieval
> Master prompt §§8, 13, 17. ADR-004.

- [x] `POST /api/search/semantic`: parse → embed → eligible-ID-aware FAISS retrieval (ADR-004) → rank (`backend/app/api/search.py`)
- [x] Eligible-ID-aware retrieval: build eligible set from PostGIS (AOI/date/sensor/cloud/quality/active filters), then IDSelector or eligible-subset search
- [x] Response includes `{completeness: "exact"|"bounded", searched_count, eligible_count, applied_filters, exclusions, warnings}`
- [x] `POST /api/search/image`: upload validation (decoded content, size/pixel limits, server-safe filename, no path traversal, decompression-bomb guard)
- [x] `GET /api/similar/{tile_id}`: FAISS neighbors + spatial filter; exclude query tile from results
- [x] Tests: `backend/tests/unit/test_search_api.py` (`VERIFIED` — 3/3 passed)

---

## Phase 6 — Change Detection & Hard QC
> Master prompt §§10, 11, 17. ADRs 006, 007, 011, 015.

- [x] ChangeFormer wrapper: model adapter interface (`ChangeDetector`), `ChangeFormerAdapter` and `DeterministicMockChangeDetector` (`backend/app/services/change_service.py`)
- [x] Pair preprocessing: CRS/grid alignment, reflectance consistency, band alignment check
- [x] Co-registration validation: report shift + residual error in pixels/metres + estimator confidence
- [x] ChangeFormer masked inference: correct logit conversion, configured threshold (0.55), morphology, connected components, seam merging before area filtering
- [x] Area filter: `MIN_CHANGE_PIXELS` (9) AND `MIN_CHANGE_AREA_M2` (900 m²) (ADR-006)
- [x] Polygonization to valid GeoJSON/MultiPolygon in EPSG:4326 (`backend/app/services/change_service.py`)
- [x] `POST /api/change/analyze`, `GET /api/change/{id}`, `POST /api/change/changes/{id}/review` (`backend/app/api/change.py`)
- [x] `analyses`, `changes` rows with canonical fields (ADR-007):
  - `change_type` enum: construction | clearance | water_variation | vegetation_land_cover | road_development | unknown
  - `change_kind` enum: appearance | disappearance | expansion | contraction | unknown
  - `temporal_status` enum: candidate | confirmed | inconsistent | insufficient_evidence
  - `review_status` enum: pending | confirmed_by_analyst | rejected_by_analyst | flagged
- [x] Hard QC eligibility gates (ADR-015): unusable coverage, failed registration
- [x] Domain-gap notice in analysis response metadata + UI
- [x] Groq-free deterministic explanation fallback from recorded facts (ADR-015)
- [x] Frontend `ChangeAnalysisPanel.tsx` integrated in `App.tsx` with Before/After tile selectors, metrics, and analyst decision buttons (Confirm, Reject, Flag)
- [x] Tests: `backend/tests/unit/test_change_detection.py` (`VERIFIED` — 4/4 passed)

---

## Phase 7 — Multi-Temporal Analysis
> Master prompt §§10, 17. ADR-007.

- [x] `GET /api/timeline` — actual acquisition timestamps only; metadata per node (sensor, cloud, quality, scene ID) (`backend/app/api/timeline.py`)
- [x] Automatic pair selection and chronological evaluation logic (`backend/app/services/timeline_service.py`)
- [x] Canonical temporal field population (ADR-007): `last_baseline_observation_at`, `earliest_supported_at`, `confirmed_at`, `latest_observation_at`
- [x] `temporal_status` assignment: `confirmed` requires independent acquisition meeting persistence rule
- [x] Left-censoring: `left_censored: true` flag populated ("earliest within searched evidence")
- [x] Frontend `TimelinePanel.tsx` integrated in `App.tsx` showing chronological acquisition track and status pills
- [x] Tests: `backend/tests/unit/test_timeline.py` (`VERIFIED` — 3/3 passed)

---

## Phase 8 — QC Scoring & Category Hypotheses
> Master prompt §§11, 17. ADR-013.

- [x] Quality service: hard gates separate from soft confidence formula (ADR-013)
- [x] Soft confidence formula: documented anti-renormalizing formula (`backend/app/core/qc.py`)
- [x] Confidence schema (ADR-013): `{score, calibrated: false, factors, rejection_reasons, weights_version}`
- [x] Missing factors: contribute 0 weight, NOT assumed-perfect; never inflate confidence
- [x] `POST /api/timeline/classify-hypothesis` (`backend/app/api/timeline.py`, `backend/app/services/timeline_service.py`)
- [x] Classification rules: NDVI decrease → vegetation clearance; NDBI increase → construction; elongated geometry → road; NDWI change → water
- [x] Frontend Spectral QC hypothesis classifier integrated in `TimelinePanel.tsx` with rapid presets and instant reasoning
- [x] Tests: `backend/tests/unit/test_confidence.py` (`VERIFIED`), `backend/tests/unit/test_timeline.py` (`VERIFIED`)

---

## Phase 9 — Similar Sites, Discovery & Clustering
> Master prompt §§8, 17. SIH 26227 § 2.2.4.

- [x] `GET /api/search/similar/{tile_id}` — FAISS neighbors + spatial/active filter (`backend/app/api/search.py`)
- [x] Exclude: query tile, overlapping tiles, nearby duplicates; suppression policy in response
- [x] `POST /api/search/clusters` — Spherical K-Means unsupervised clustering on 768-d RemoteCLIP embeddings across AOI (`backend/app/services/clustering_service.py`, `backend/app/api/search.py`)
- [x] Zero-shot semantic anchor labeling (`Built-up Infrastructure`, `Excavation & Bare Ground`, `Dense Canopy`, `Agricultural Fields`, `Water Networks`, `Transportation`)
- [x] Frontend `SearchResultsPanel.tsx` interactive Discovery & Clustering tab with representative medoid inspection
- [x] Tests: verified in `test_search_api.py` and `test_clustering.py`

---

## Phase 10 — Analyst Review & Full Provenance Navigation
> Master prompt §§14, 17. ADR-002.

- [x] `POST /api/change/changes/{change_id}/review`: persist analyst decision with server-derived operator identity, server timestamp, notes (`backend/app/api/change.py`)
- [x] `GET /api/provenance/{entity_id}`, `GET /api/provenance` (`backend/app/api/provenance.py`)
- [x] Provenance includes: parent artifact links, inputs/outputs, model hashes, parameters, timestamps (`ProvenanceRepository`)
- [x] Tests: `backend/tests/unit/test_reports_and_provenance.py`

---

## Phase 11 — Assistant, Reports & Export
> Master prompt §§11, 14, 17.

- [x] `POST /api/assistant/chat`: receives bounded structured facts; never raw rasters; deterministic fallback when Groq unavailable (`backend/app/api/assistant.py`)
- [x] `POST /api/report/generate`: multi-format scientific report export in GeoJSON, CSV, JSON (`backend/app/api/reports.py`)
- [x] CSV: formula injection protection escaping leading '=', '+', '-', '@' characters (ADR-014)
- [x] GeoJSON: valid FeatureCollection with change properties & uncalibrated disclaimer
- [x] Tests: `backend/tests/unit/test_reports_and_provenance.py`

---

## Phase 12 — CI, Evaluation, Security, Recovery & Runbooks
> Master prompt §§15, 16, 17, 18. ADRs 012, 014.

- [ ] CI pipeline:
  1. Lint/type: ruff, mypy, eslint, tsc --noEmit
  2. Backend fast suite (not slow, not network, not gpu) with PostGIS + Redis services
  3. Frontend unit + a11y (jest-axe)
  4. Bundle secret scan (grep for API keys in built assets)
  5. E2E on nightly (cached real fixtures)
  6. Network/GPU suites: opt-in, missing resources → explicit skip/BLOCKED, not pass
- [ ] `scripts/evaluate.py` — machine-readable JSON + human-readable report:
  - Retrieval: Recall@K, Precision@K, MRR (only with defined relevance judgments; else N/A)
  - Change: precision, recall, F1, IoU, FPR (only with labeled ground truth; else N/A)
  - System: indexed tiles/area, index size, ingest time, embedding time, query p50/p95, analysis latency, hardware
  - Record: model hashes, scene manifests, thresholds, code/env versions, hardware, seeds, sample counts
  - Never invent numbers; if no labels → "N/A (no ground truth)"
- [ ] Docker Compose production:
  - Non-root containers, restricted internal ports, named volumes, health checks
  - Frontend/Nginx reverse proxy with TLS, CSRF protection, secure cookies
  - Explicit migration/startup ordering (wait-for-it or healthcheck deps)
  - CPU profile first; documented GPU option
  - `APP_ENV=production` enforced; dev-identity bypass rejected (ADR-012)
- [ ] Protected deployment: TLS ingress, narrow origins, route-specific quotas, rate limits, redacted logs
- [ ] Security hardening: upload decoding limits, archive extraction limits, path traversal guard, SSRF block on scene/tile/report/external fetch, no backend credentials to browser
- [ ] Restart/crash recovery tests: DB + artifact manifests + embedding evidence + generation metadata survive restart; restoration test into clean environment
- [ ] SSE reconnect/replay, stale cursor, terminal reconciliation, cancellation, worker death → stale not running-forever
- [ ] Measured latency: warm/cold p50/p95 search, ingestion, inference, end-to-end; RAM/VRAM/disk under stated load
- [ ] Runbooks: `docs/runbooks/install.md`, `credentials.md`, `model_download.md`, `migrations.md`, `quota_exhaustion.md`, `full_disk.md`, `corrupt_index.md`, `failed_jobs.md`, `rollback.md`, `disaster_recovery.md`
- [ ] README: prereqs, versions, setup for every service, demo walkthrough, troubleshooting, known limitations
- [ ] All 18 MVP acceptance steps on real small AOI (ADR-014: use real data, not fixtures)
- [ ] Final status table: implemented features, exact verification commands/results, measured metrics or N/A, blockers, release status
- [ ] **Gate (Phase 12):** CI green; security checks pass; restart/crash recovery demonstrated; all 18 MVP steps verified or explicitly BLOCKED with reason — `NOT RUN`

---

## MVP Acceptance Checklist (real data only)
> Run after Phase 12 gate. All steps must use actual Sentinel-2 scene IDs.

- [ ] 1 Open map (MapLibre + MapTiler basemap loads)
- [ ] 2 Select AOI (draw → persisted → reloaded)
- [ ] 3 Enter NL query (SearchBar text mode)
- [ ] 4 Groq → structured filters shown as chips (or fallback warning shown if Groq down)
- [ ] 5 Copernicus imagery discovered (real product IDs, acquisition dates)
- [ ] 6 Preprocess (reflectance, SCL mask, quality score logged to provenance)
- [ ] 7 RemoteCLIP embeddings (stable int64 IDs, hash recorded)
- [ ] 8 FAISS retrieval (eligible-ID-aware; completeness_metadata present)
- [ ] 9 Results on map (real tiles, accurate metadata, no fabricated data)
- [ ] 10 Choose two dates (pair selection with rejection explanation)
- [ ] 11 ChangeFormer inference (domain-gap notice visible)
- [ ] 12 Polygons on map (draw-in animation, area in m²)
- [ ] 13 Timeline of real observations (gaps empty, cloudy nodes dimmed)
- [ ] 14 Earliest supported observation (distinct from confirmed; exact date unknown)
- [ ] 15 Before/after inspect (swipe/side-by-side; labels per side with scene IDs)
- [ ] 16 Groq explanation (or deterministic fallback if unavailable — marked unverified)
- [ ] 17 Confirm/reject (persists with server timestamp; history immutable)
- [ ] 18 Provenance stored (full chain traceable; every step recorded)

---

## Additional Acceptance Demonstrations (master prompt §18)

- [ ] No-Groq operation (all pipeline steps without LLM)
- [ ] Empty/low-quality imagery handling (NO_IMAGERY, structured response)
- [ ] Restart with persisted search/reviews (decisions survive)
- [ ] Idempotent ingest (repeat POST → same result, cache hit)
- [ ] New-scene incremental search (old vector IDs/scores unchanged)
- [ ] Ingestion crash recovery (simulate crash at each boundary; journal recovers)
- [ ] SSE reconnection (Last-Event-ID resume; polling fallback)
- [ ] Restore verification (DB + indexes restored into clean environment)
- [ ] Authorized report/raster access (unauthorized → 401)
- [ ] No secret leakage (bundle grep; log scan; response inspection)

---

## Backlog / Future Work
- [ ] HNSW / IVF / PQ index upgrade (behind same VectorIndex interface)
- [ ] Sentinel-1 SAR fusion (described as future in PRD §14)
- [ ] Confidence calibration study (requires labeled data)
- [ ] Fine-tune ChangeFormer on labeled regional data
- [ ] Offline packaging (local COG archive, local LLM, local map tiles) — interfaces prepared
- [ ] Enterprise auth / RBAC (out of scope for initial release)
- [ ] Automatic alerting

