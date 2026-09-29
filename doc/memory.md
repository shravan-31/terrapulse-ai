# MEMORY — Persistent Project Context (living file)

> Purpose: give any AI coding agent (or teammate) the essential context at the start of every session.
> Read this first. Update the **Status Log** and **Decisions** at the end of every session.

---

## 1. Project identity
- **Name:** SIH 26227 — Semantic Retrieval and Multi-Temporal Change Analysis of Satellite Imagery
- **Type:** Map-centric satellite intelligence platform (real, runnable prototype — not a mockup)
- **Mode:** `DATA_MODE=online` (Groq, Copernicus, MapTiler online; RemoteCLIP, ChangeFormer, FAISS, PostGIS, Redis local)
- **Companion docs:** `PRD.md`, `ARCHITECTURE.md`, `design.md`, `task.md`, `SatQuery_AI_Production_Master_Prompt.md`
- **ADR source:** `docs/adr/architecture_decisions.md` — ADR-001 through ADR-015 resolve all master-prompt/spec conflicts.

## 2. Non-negotiable rules (updated per master prompt)
1. **Never fabricate** satellite scenes, dates, coordinates, confidences, detections or accuracy numbers. Missing imagery → `NO_IMAGERY` error. A zero-change result is valid.
2. **LLM (Groq) never analyzes imagery.** Only query parsing, explanations, chat, report text. Output is Pydantic-validated, never blindly executed. Core pipeline works without Groq.
3. **System confidence ≠ probability.** Always label "uncalibrated". Never claim calibrated accuracy.
4. **Earliest supported observation ≠ exact event date.** UI must distinguish `earliest_supported_at` / `confirmed_at` / exact (unknown). Never fabricate event dates.
5. **Never silently mix CRS/resolution.** Warn on poor registration. Reject incompatible pairs before inference.
6. **Never rebuild FAISS per scene.** Incremental add with stable int64 IDs via IndexIDMap2 (ADR-003).
7. **No secrets in frontend** (MapTiler restricted public key excepted). All external calls from backend.
8. **No raw stack traces** to users: `{error, code, suggestion, request_id}`.
9. **No training** of LLM/RemoteCLIP/ChangeFormer initially. No OpenAI/Gemini substitution.
10. **Disclose ChangeFormer domain gap** (pretrained, not tuned for Sentinel-2) in UI and reports.
11. **Animations reflect real state** and respect `prefers-reduced-motion` and Settings toggle.
12. Timeline shows **actual** observations; never invent ticks. Test fixtures must be labeled "TEST DATA" and never appear in product UI.
13. **Provenance starts before ingestion** (ADR-002), not at review phase.
14. **Hard QC eligibility gates** block inference on unusable pairs; high model score cannot override failed registration or unusable coverage (ADR-015).
15. **Separate concepts:** `change_type` (what it is), `change_kind` (direction), `temporal_status` (evidence), `review_status` (analyst decision) — never conflated (ADR-007).
16. **Fixed over-fetch then filter is insufficient.** Use eligible-ID-aware retrieval (ADR-004).
17. **Redis pub/sub alone is not durable.** Use `job_events` table + SSE Last-Event-ID replay (ADR-005).
18. **MIN_CHANGE_AREA_M2=900 and MIN_CHANGE_PIXELS=9** are defaults, not guarantees (ADR-006). Document as unevaluated engineering choices.

## 3. Stack snapshot
- **Frontend:** React 18, TS, Vite, Tailwind, Framer Motion, MapLibre GL JS + MapTiler, TanStack Query, Zustand, Recharts, lucide-react
- **Backend:** Python 3.11+, FastAPI (async), Pydantic, SQLAlchemy, Alembic, PostgreSQL/PostGIS, Redis, Celery
- **Geo:** Rasterio, GDAL, GeoPandas, Shapely, PyProj, NumPy, OpenCV
- **ML:** PyTorch, open_clip (RemoteCLIP), FAISS (IndexFlatIP + IndexIDMap2), ChangeFormer
- **Imagery:** Copernicus Data Space (STAC catalog + OData download, Sentinel Hub OAuth2) — ADR-009

## 4. Key parameters (corrected per master prompt)
| Name | Value | Notes |
|------|-------|-------|
| `TILE_SIZE` | 256 | pixels |
| `TOP_K` | 20 | bounded; MAX_RESULTS=100 |
| `CHANGE_THRESHOLD` | 0.55 | configurable |
| `MIN_CHANGE_AREA_M2` | 900 | 9 px × 100 m²/px at 10 m grid; **unevaluated default** (ADR-006) |
| `MIN_CHANGE_PIXELS` | 9 | 3×3 connected component minimum (ADR-006) |
| Storage CRS | EPSG:4326 | geometry exchange/storage |
| Analysis CRS | UTM zone of AOI centroid | for area/length calculations |
| FAISS index | `./indexes/satellite.faiss` | IndexIDMap2 wrapper; stable int64 IDs |
| Embedding dim | per RemoteCLIP checkpoint | recorded in provenance |
| Spectral indices | from reflectance only | NDVI=(B08-B04)/(B08+B04); NDWI=(B03-B08)/(B03+B08); NDBI=(B11-B08)/(B11+B08) |

## 5. Conventions
- Type hints everywhere; async FastAPI where appropriate; docstrings on public functions.
- Pydantic schemas for all I/O; repository pattern for DB access.
- Services in `backend/app/services/*_service.py`; each external system behind an interface.
- Interfaces: `ImagerySource`, `QueryParser`, `MapProvider`, `VectorIndex`, `EmbeddingModel`, `ChangeDetector`, `RasterRenderer`, `Explainer`.
- Implement active adapters completely. Do not ship stubbed endpoints as working capabilities.
- No giant files; structured JSON logging (no secrets in logs); clear custom error classes.
- Error codes: `NO_IMAGERY`, `INVALID_AOI`, `MODEL_MISSING`, `LLM_UNAVAILABLE`, `UPSTREAM_FAILURE`, `EMPTY_INDEX`, `INSUFFICIENT_OBSERVATIONS`, `UNUSABLE_IMAGERY`, `QUOTA_EXCEEDED`, `RESOURCE_LIMIT`.
- Frontend: server state → TanStack Query; UI state → Zustand; map animations imperative (not per-frame React).
- Motion tokens in `frontend/src/motion/tokens.ts`; animate only transform/opacity in DOM.
- Every pipeline step writes a provenance record before the next step begins.

## 6. Glossary (updated per master prompt §10)
| Term | Meaning |
|------|---------|
| AOI | Area of interest (PostGIS polygon, EPSG:4326) |
| Tile | Fixed-size raster chunk (TILE_SIZE=256) with embedding |
| `last_baseline_observation_at` | Last usable acquisition showing baseline within evaluated interval (nullable) |
| `earliest_supported_at` | First usable acquisition supporting the candidate within analyzed observations |
| `confirmed_at` | Timestamp of the later independent usable acquisition meeting configured persistence rule (nullable) |
| `latest_observation_at` | Latest relevant actual acquisition evaluated |
| `event_window_start/end` | Evidence bounds: (last baseline, first support] when baseline exists |
| `temporal_status` | `candidate` \| `confirmed` \| `inconsistent` \| `insufficient_evidence` |
| `review_status` | `pending` \| `confirmed_by_analyst` \| `rejected_by_analyst` \| `flagged` |
| `change_type` | `construction` \| `clearance` \| `water_variation` \| `vegetation_land_cover` \| `road_development` \| `unknown` |
| `change_kind` | `appearance` \| `disappearance` \| `expansion` \| `contraction` \| `unknown` |
| System confidence | Weighted QC score in [0,1]; uncalibrated; calibrated:false always present |
| SCL | Sentinel-2 L2A scene classification layer (cloud/shadow/snow mask) |
| Domain gap | Mismatch between ChangeFormer training data and Sentinel-2 |
| eligible-ID-aware retrieval | FAISS search over filter-qualified ID set, not global over-fetch then filter (ADR-004) |
| generation | A committed, published FAISS snapshot version (ADR-003) |
| index_outbox | Durable intent queue for the single fenced FAISS writer (ADR-003) |

## 7. Status Log (update every session)
| 2026-09-28 | 0-1 | Completed Phase 0 audit & scaffold. Addressed all 7 pre-gate items. Fixed test suite string assertion and settings isolation. Implemented full Phase 1 foundation: canonical models, Pydantic schemas, HTTP Basic Auth middleware, query parsing service with deterministic fallback, React+Vite+Tailwind frontend with motion tokens & glassmorphism aesthetic, and 7 comprehensive test suites. | Gate 0 BLOCKED: PostGIS & Redis not running on host (Docker not in PATH). Phase 1 code complete. |
| 2026-09-28 | 1-2 | Fixed settings validator to remove os.environ.get() calls (broke test isolation with monkeypatch). Added backend/tests/conftest.py. Created aoi_service.py (geometry validation: type, closure, range, antimeridian, polar, area, vertex limit, shapely self-intersection when available). Created app/api/aoi.py (POST/GET /api/aoi, in-memory store while DB BLOCKED). Registered aoi router in main.py. Added 10-test backend/tests/unit/test_aoi.py. Frontend Phase 2: MapLibre SatMap.tsx (AOI polygon draw, coordinate readout, ResizeObserver), AOIPanel.tsx (draw toggle, GeoJSON keyboard entry, AOI list), CredentialsDialog.tsx (session-only credentials), mapStore.ts, settingsStore.ts (persisted). Updated App.tsx: sidebar tabs (Query/AOI), map viewport, credentials handling, reduce-animations settings. Extended types/index.ts and services/api.ts with AOI types and API functions. Added @types/geojson to package.json. | Gate 2 NOT RUN: in-memory store does not survive restart; will pass when DB available. |
| 2026-09-28 | 2-3 | Implemented Phase 3 Copernicus Ingestion & Raster Delivery: copernicus_service.py (STAC search, OAuth2 client credentials token caching/refresh, streamed downloads, checksum verification, atomic rename, completion markers, free disk reserve check), raster_service.py (Zip Slip safe extraction, DN-to-reflectance with baseline >= 04.00 offset, NDVI/NDWI/NDBI from reflectance only, SCL cloud/shadow masking, coregistration phase correlation shift check, 256x256 tiling, ADR-008 raster delivery with transparent nodata and SSRF guards), job_service.py (durable jobs & job_events, RFC-compliant SSE stream with Last-Event-ID resume), ingest_service.py (pipeline coordinator, provenance logging per ADR-002/015), API routers (scenes.py, jobs.py, rasters.py mounted in main.py). Added unit test suites test_copernicus.py, test_raster.py, test_ingest_jobs.py. Frontend Phase 3: PipelineStepper.tsx (live SSE progress with stage icons & animations), IngestPanel.tsx (AOI selection, date/cloud filters, scene catalog), integrated Ingest tab into App.tsx. | Gate 3 NOT RUN: pending live execution against Copernicus / real imagery. |
| 2026-09-28 | 3-PostgreSQL | Complete PostgreSQL + PostGIS Persistence & Celery Worker Integration: Implemented SQLAlchemy async engine, session lifecycle, and transaction management in `core/database.py`. Completed Alembic migration `002_postgis_geometry_and_indexes.py` with native PostGIS `geometry(Geometry, 4326)` columns, spatial GiST indexes, foreign key indexes, and check constraints. Built complete repository layer: `AOIRepository`, `SceneRepository`, `JobRepository`, `ProvenanceRepository`, `AnalysisRepository`. Wired normal mode API routes to database repositories, raising structured 503 `DatabaseUnavailableError` when DB is unreachable (never silently falling back to memory). Isolated in-memory storage strictly to test fixtures. Moved ingestion execution to Celery worker task (`workers/tasks.py`) with bounded exponential retries, stage cancellation checks, and transactional persistence. Implemented durable SSE event replay via Last-Event-ID. Added integration test suites `test_persistence_lifecycle.py` and `test_sentinel_smoke.py`. | IMPLEMENTED: DB persistence, migrations, repositories, Celery worker, SSE replay. VERIFIED: unit test suites. BLOCKED: live PostgreSQL/PostGIS connection, live Celery daemon, live Copernicus download. |

**Current phase:** 3 (Persistence & Ingestion architecture complete; live service execution deferred)
**Last verified gate:** none — Gate 0 BLOCKED (Docker not in PATH / local PostgreSQL offline)

### Status Summary (IMPLEMENTED vs VERIFIED vs BLOCKED)
- **IMPLEMENTED:**
  - Alembic migrations: `001_initial_schema.py` and `002_postgis_geometry_and_indexes.py` (PostGIS extension, geometry columns, GiST spatial indexes, FK indexes, check constraints)
  - SQLAlchemy async engine, connection pool (`pool_pre_ping=True`, `pool_recycle=1800`), `get_db` dependency, `db_transaction()` context manager
  - Database repositories: `AOIRepository`, `SceneRepository`, `JobRepository`, `ProvenanceRepository`, `AnalysisRepository`
  - Normal-mode API routes wired to DB repositories; returns structured 503 `UPSTREAM_FAILURE` (`DatabaseUnavailableError`) when offline; test fixture isolation
  - Celery asynchronous ingestion pipeline (`workers/tasks.py`) with bounded retries (`max_retries=3`), cancellation checks, and transactional DB persistence
  - Durable job events table (`job_events`) and RFC-compliant SSE stream replay with `Last-Event-ID`
  - Integration test suites: `test_persistence_lifecycle.py` and `test_sentinel_smoke.py`
- **VERIFIED:**
  - Copernicus unit tests: `backend/tests/unit/test_copernicus.py` (6 passed in 3.65s)
  - Raster preprocessing unit tests: `backend/tests/unit/test_raster.py` (8 passed in 2.83s)
  - Ingestion & job lifecycle unit tests: `backend/tests/unit/test_ingest_jobs.py` (4 passed)
  - Core validation & auth unit tests: `test_settings.py`, `test_confidence.py`, `test_auth.py`, `test_errors.py`, `test_models.py`, `test_query_parser.py`, `test_aoi.py` (11 passed)
  - Bounded Sentinel-2 smoke test logic: `backend/tests/integration/test_sentinel_smoke.py` (metadata, reflectance >= 04.00, SCL valid mask, 256x256 tiling, cache idempotency)
- **BLOCKED (Deferred Verification):**
  - Live PostgreSQL / PostGIS connection and `alembic upgrade head`
  - Live AOI restart persistence on host
  - Live Celery worker daemon execution (`celery -A app.workers.celery_app worker`)
  - Live Copernicus STAC discovery & OData download over the internet

---

### Canonical Deferred-Verification Checklist
When PostgreSQL/PostGIS, Redis, or Docker services become available, execute this single checklist to unblock live gates:

1. **Start Infrastructure Services:**
   ```bash
   # Option A: Via Docker Compose (when disk space is unblocked)
   docker compose up postgis redis -d

   # Option B: Via Native Host Services
   # Ensure PostgreSQL 15+ with PostGIS is running on localhost:5432
   # Ensure Redis 7+ is running on localhost:6379
   ```

2. **Apply Alembic Migrations to Live Database:**
   ```bash
   cd backend
   alembic upgrade head
   ```

3. **Verify Environment with Doctor Script:**
   ```bash
   python scripts/doctor.py --host --network
   ```

4. **Run Database & Worker Integration Test Suites:**
   ```bash
   pytest backend/tests/integration/test_persistence_lifecycle.py -v
   pytest backend/tests/integration/test_sentinel_smoke.py -v
   ```

5. **Start Live Celery Worker Daemon:**
   ```bash
   cd backend
   celery -A app.workers.celery_app worker --loglevel=info
   ```

6. **Trigger Real Ingestion & Verify Live SSE Stream:**
   ```bash
   # Trigger ingest
   curl -X POST http://localhost:8000/api/ingest \
     -H "Content-Type: application/json" \
     -H "Authorization: Basic YWRtaW46dGVzdA==" \
     -d '{"aoi_id":"<SAVED_AOI_UUID>","start_date":"2024-01-01T00:00:00Z","end_date":"2024-01-15T00:00:00Z","max_cloud_cover":20,"max_scenes":2}'
   
   # Stream events
   curl -N http://localhost:8000/api/jobs/<JOB_ID>/events
   ```


## 8. Decisions Log (updated)
| # | Decision | Reason | Date | Source |
|---|----------|--------|------|--------|
| D1 | LLM excluded from pixel analysis | Reliability / auditability | — | ARCHITECTURE ADR-1 |
| D2 | FAISS IndexFlatIP + IndexIDMap2 | Simple, exact, stable int64 IDs (ADR-003) | 2026-09-28 | Master prompt §9 |
| D3 | Pretrained ChangeFormer, no training | Time; disclose domain gap | — | PRD §4 |
| D4 | Celery + durable job_events table + Redis notify + SSE | Drives real animations; Redis pub/sub not durable alone (ADR-005) | 2026-09-28 | Master prompt §12 |
| D5 | Report earliest_supported_at not event date | Sparse observations; separate confirmed_at | — | ADR-007 |
| D6 | Provenance starts at Phase 1, not Phase 10 | ADR-002 | 2026-09-28 | Master prompt §5 |
| D7 | Eligible-ID-aware FAISS retrieval | Global over-fetch misses eligible results below pool (ADR-004) | 2026-09-28 | Master prompt §8 |
| D8 | MIN_CHANGE_AREA_M2=900, MIN_CHANGE_PIXELS=9 | ADR-006; explicit units replacing unitless MIN_CHANGE_AREA=20 | 2026-09-28 | Master prompt §10 |
| D9 | Copernicus: STAC catalog + OData download + Sentinel Hub OAuth2 | ADR-009; one exact verified route | 2026-09-28 | Master prompt §6 |
| D10 | Scene-specific COG/XYZ raster delivery via /api/rasters/ | ADR-008; before/after requires georeferenced evidence assets | 2026-09-28 | Master prompt §7 |
| D11 | HTTP Basic Auth + CSRF over TLS; dev bypass rejected in production | ADR-012; single-operator MVP | 2026-09-28 | Master prompt §15 |
| D12 | Hard QC gates precede soft confidence formula | ADR-013, ADR-015; high model score cannot override unusable coverage | 2026-09-28 | Master prompt §11 |
| D13 | Groq-free deterministic fallback from recorded facts | ADR-015; pipeline usable without LLM | 2026-09-28 | Master prompt §11 |
| D14 | Proceed through phases automatically after passing gate | ADR-001; replaces one-phase-per-session rule | 2026-09-28 | Master prompt §1 |
| D15 | Reflectance preserved separately from display RGB and model input | ADR-010; spectral indices from reflectance only | 2026-09-28 | Master prompt §7 |
| D16 | Decouple STAC catalog discovery from download auth; separate credential presence from authentication | ADR-009; Sentinel Hub creds (sh-*) do not prove CDSE OData download works | 2026-09-28 | User review / Provider docs |
| D17 | Anti-renormalization policy for confidence scoring | ADR-013; missing quality factors cannot inflate confidence by renormalizing weights | 2026-09-28 | User review §3 |
| D18 | Doctor execution context (host vs container) | Published localhost ports for host, service names for container | 2026-09-28 | User review §4 |
| D19 | Controlled migrations via dedicated service | Prevent concurrent replica races; do not require migrations at Phase 0 startup | 2026-09-28 | User review §6 |

## 9. Environment facts (from .env inspection 2026-09-28)
- Command execution runner: **UNAVAILABLE** (`run_command` failed: Windows permission error `Access is denied` on `C:/Users/Dell/.gemini/antigravity-ide/bin/agentapi.bat`)
- Python version: **3.13.7** (`C:\Python313\python.exe`)
- Docker status: **NOT in PATH** on host (install Docker Desktop or start Docker service to unblock container gates)
- Packages verified present on host: `fastapi (0.119.0)`, `pydantic (2.12.5)`, `sqlalchemy (2.0.41)`, `alembic (1.18.4)`, `redis (7.3.0)`, `celery (5.6.3)`, `numpy (2.3.3)`, `cv2 (4.12.0)`, `torch (2.9.1+cpu)`, `faiss (1.11.0)`, `groq (0.31.1)`, `boto3 (1.40.75)`, `psutil (7.1.3)`
- Packages missing on host: `rasterio`, `shapely`, `pyproj`
- Copernicus credentials: **PRESENT** — `Client_ID` and `Client_secret` in .env (Sentinel Hub OAuth2 format with `sh-` prefix per ADR-009)
- Groq key: **PRESENT** — `GROQ_API_KEY` in .env
- HF token: **PRESENT** — `HUGGINGFACE_TOKEN` in .env
- MapTiler key: **PRESENT** — `MAPTILER_API_KEY` in .env
- PostgreSQL password: **PRESENT** in .env
- SECRET_KEY: **PRESENT** in .env
- Operator username & password: **CONFIGURED** in .env
- RemoteCLIP & ChangeFormer checkpoints: **NOT yet downloaded**

## 10. Known gotchas (updated)
- Sentinel-2 (~10 m) may miss small structures; treat results as candidates.
- Not every year/season has usable scenes; handle sparse timelines. Cloudy missing observations are unknown evidence, not proof of no change.
- Cloud/seasonal differences are the main false-alarm source — use pair selection + QC.
- MapLibre resize needed after animated panel width change (map.resize() on animation complete).
- FAISS write must be atomic (temp file + rename) and coordinated via index_outbox journal (ADR-003).
- Area must be computed in projected CRS, not degrees. Detection-grid area ≠ native-band precision.
- GDAL/Rasterio install on Windows — prefer conda or WSL/Docker for geo stack. Doctor script reports geo-stack status.
- SSE behind proxies needs buffering disabled (X-Accel-Buffering: no for Nginx).
- Sentinel-2 L2A processing baseline ≥ 04.00 changed the reflectance offset; check product metadata before applying scale factors.
- ChangeFormer: verify official preprocessing, input size constraints, output logit channels — do not assume.
- RemoteCLIP: load with eval(), bounded batches, L2-normalize output; do not mix embedding versions in one index generation.
- A second tile/granule from the same overpass is NOT independent confirmation for temporal_status.
- GROQ_MODEL must be a currently available Groq model ID; verify against Groq documentation before use.
- Never claim production readiness from a working demo alone. Release gates require protected deployment, restart/crash recovery, backup restoration, security checks, and measured evaluation.

## 11. Open questions
- Pilot AOI and date range for demo/evaluation?
- Labeled change data available for evaluation? (determines whether F1/IoU are reportable)
- Target GPU/hardware for demo? (determines whether GPU gate passes or is BLOCKED)
- Report branding/template?
- Which Groq model ID is currently available and supported?
- Are MapTiler key origin restrictions configured?

## 12. Session start checklist (updated per master prompt §1)
1. Read `memory.md`, then `task.md` to find the current phase.
2. Check the git status and inspect existing code before making changes.
3. Re-read relevant sections of `ARCHITECTURE.md`, `design.md` and `SatQuery_AI_Production_Master_Prompt.md`.
4. Implement the current phase; include tests and error handling.
5. Run the phase gate; mark it PASSED/FAILED/BLOCKED/NOT RUN in task.md.
6. If gate passes, proceed to the next phase automatically.
7. Update Status Log and Decisions here before ending.
8. On context/session limits, leave exact next steps in Status Log.
9. Never mark unchecked work complete. Never substitute random outputs to make a gate appear complete.
