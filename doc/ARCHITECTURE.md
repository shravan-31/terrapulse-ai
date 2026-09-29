# ARCHITECTURE — SIH 26227 Satellite Intelligence Platform

## 1. Principles

1. **LLM is peripheral.** Groq parses queries, explains and summarizes. It never interprets pixels or detects change. Core pipeline runs without it.
2. **Every external dependency sits behind an interface** (imagery, LLM, map, vector store, models) so offline replacement is a swap, not a rewrite.
3. **Provenance by construction.** Each pipeline step writes a provenance record.
4. **Incremental by default.** New scenes are appended to FAISS/PostGIS; no full rebuilds.
5. **Honesty in output.** No fabricated data; confidence is uncalibrated; dates are "supported", not "exact".

## 2. System context

```
                        ┌────────────────────────────┐
                        │        Analyst (Browser)   │
                        │  React + TS + MapLibre     │
                        └─────────────┬──────────────┘
                                      │ HTTPS / SSE
                        ┌─────────────▼──────────────┐
                        │      FastAPI API Gateway    │
                        └─┬────┬────┬────┬────┬────┬─┘
     ┌────────────────────┘    │    │    │    │    └───────────────────┐
┌────▼─────┐ ┌────────────┐ ┌──▼───┐ │ ┌──▼────────┐ ┌───────────────┐ ┌▼──────────┐
│ Search   │ │ Ingestion  │ │Change│ │ │ Temporal  │ │ Analyst Review│ │ Report    │
│ Service  │ │ Service    │ │Detect│ │ │ Analysis  │ │ + Provenance  │ │ Service   │
└─┬──┬─────┘ └─┬──────────┘ └──┬───┘ │ └──┬────────┘ └───────┬───────┘ └───────────┘
  │  │         │               │     │    │                  │
  │  │   ┌─────▼──────┐   ┌────▼─────▼────▼────┐       ┌─────▼──────┐
  │  │   │ Celery +   │   │ Quality Control      │       │ PostgreSQL │
  │  │   │ Redis jobs │   │ (confidence, flags)  │       │ + PostGIS  │
  │  │   └─────┬──────┘   └──────────────────────┘       └────────────┘
  │  │         │
┌─▼──▼──┐  ┌───▼───────────┐   ┌───────────────┐   ┌──────────────┐
│ FAISS │  │ Geospatial    │   │ RemoteCLIP    │   │ ChangeFormer │
│ index │  │ preprocessing │   │ (local, GPU/  │   │ (local, GPU/ │
│(disk) │  │ (GDAL/Rasterio)│  │  CPU)         │   │  CPU)        │
└───────┘  └───┬───────────┘   └───────────────┘   └──────────────┘
               │
   ┌───────────▼──────────┐   ┌───────────────┐   ┌───────────────┐
   │ Copernicus Data Space│   │ Groq API      │   │ MapTiler      │
   │ (online)             │   │ (online)      │   │ (online tiles)│
   └──────────────────────┘   └───────────────┘   └───────────────┘
```

## 3. Component responsibilities

| Component | Responsibility | Key abstraction |
|-----------|----------------|-----------------|
| API Gateway | Routing, validation, CORS, rate limits, error mapping | FastAPI routers |
| Search Service | Orchestrates parse → embed → FAISS → PostGIS filter → rank | `SearchService` |
| Ingestion Service | Scene validate/extract/preprocess/tile/embed/index/persist | `IngestionService` |
| Embedding Service | RemoteCLIP text + image encoders, batching, device selection | `EmbeddingModel` |
| Vector Search Service | FAISS add/search/persist; embedding_id ↔ tile map | `VectorIndex` (Flat now; HNSW/IVF/PQ later) |
| Change Detection Service | Pair preprocess, registration check, ChangeFormer, postprocess, polygonize | `ChangeDetector` |
| Temporal Analysis Service | Pair selection, timeline walk, earliest-supported / confirmed logic | `TemporalAnalyzer` |
| Quality Control Service | Cloud/registration/valid-pixel/season/area/temporal → confidence + flags | `QualityScorer` |
| Classification helper | NDVI/NDWI/NDBI + geometry + temporal pattern → change type | `ChangeClassifier` |
| Provenance Service | Writes/reads step records | `ProvenanceRecorder` |
| Analyst Review Service | Queue, decisions, notes | `ReviewService` |
| Report Service | PDF/GeoJSON/CSV/JSON export | `ReportBuilder` |
| Groq Service | Query parsing (schema-validated), explanations, chat, report text | `QueryParser`, `Explainer` |
| Imagery Source | Copernicus now; local COG later | `ImagerySource` |
| Map Provider | MapTiler now; local tiles later | `MapProvider` |

## 4. Core data flows

### 4.1 Ingestion (online)
```
AOI + dates → Copernicus search → filter cloud/quality → download/stream → cache
→ validate → extract metadata → CRS normalize/reproject/resample/clip
→ mask (cloud/shadow) + nodata → normalize → quality score → tile (TILE_SIZE)
→ RemoteCLIP embed (batch) → faiss.add() → PostGIS insert (scene, tiles) → provenance
```

### 4.2 Semantic search
```
query → Groq parse (Pydantic-validated; fallback raw text) → structured filters
→ RemoteCLIP text embed (L2-normalized) → FAISS top-K (over-fetch)
→ PostGIS filter (AOI/date/sensor/cloud) → rank → results
```

### 4.3 Change analysis
```
AOI + date range → list scenes → pair selection (cloud, valid px, overlap, season, sensor)
→ co-registration validation (warn/reject) → ChangeFormer → probability map
→ threshold → morphology → connected components → min-area → polygonize → GeoJSON
→ index computation (NDVI/NDWI/NDBI) + geometry → classify
→ multi-temporal walk over all usable observations → earliest_supported / confirmed
→ QC → system confidence + flags → PostGIS → provenance → review queue
```

### 4.4 Multi-temporal logic
For each candidate polygon, evaluate observations in chronological order:
`baseline → baseline → candidate → confirmed → expansion → stable`.
- **earliest_supported**: first observation where change evidence passes threshold with acceptable QC.
- **confirmed**: first observation where the change persists in ≥1 subsequent good observation.
- **exact event date**: not asserted; bounded by [last baseline, earliest_supported].

### 4.5 Job progress (drives UI animation)
Celery worker publishes stage events to Redis pub/sub; API exposes `GET /api/jobs/{id}/events` (SSE):
`search_scenes → download_cache → preprocess → tile → embed → index → registration_check → change_infer → postprocess → temporal_analysis → qc_scoring → persist`.
Event: `{job_id, stage, stage_index, stage_total, progress, message, cached, ts}`.

## 5. Data model (PostGIS)

| Table | Key columns |
|-------|-------------|
| `aoi` | id, geometry (Polygon, 4326), name, created_at |
| `scenes` | id, scene_id (unique), sensor, acquisition_date, cloud_cover, resolution, crs, bbox, geometry, file_path, metadata (JSONB), created_at |
| `tiles` | id, scene_id, tile_id (unique), geometry, bbox, date, sensor, resolution, file_path, embedding_id, quality_score |
| `analyses` | id, aoi_id, start_date, end_date, created_at, model_version, status, params (JSONB) |
| `changes` | id, analysis_id, geometry, area, change_type, confidence, first_supported_date, confirmed_date, before_scene, after_scene, quality_flags (JSONB), change_kind (appear/disappear/expand/contract) |
| `analyst_decisions` | id, analysis_id, change_id, decision, analyst_id, timestamp, notes |
| `provenance` | id, analysis_id, source_scene, processing_step, model, model_version, timestamp, parameters (JSONB) |
| `jobs` | id, type, status, stage, progress, error, created_at, finished_at |

Indexes: GiST on all geometry columns; B-tree on `scenes.acquisition_date`, `tiles.embedding_id`, `changes.analysis_id`.
Duplicate scenes prevented by unique `scene_id`.

## 6. FAISS design

- `IndexFlatIP` over L2-normalized embeddings (cosine via inner product).
- Wrapped in `VectorIndex` interface: `add(ids, vecs)`, `search(vec, k)`, `save()`, `load()`, `count()`.
- Persist to `FAISS_INDEX_PATH` after each ingest batch (atomic write: temp file + rename).
- `embedding_id` = sequential int stored in `tiles`; FAISS position ↔ tile mapping kept in DB.
- Deletions/re-index handled by tombstone flag + periodic compaction (future).
- Upgrade path: HNSW (recall/latency), IVF+PQ (scale) behind same interface.

## 7. Geospatial handling

- Canonical storage CRS: EPSG:4326 for geometry columns; analysis CRS = UTM zone of AOI centroid for area/length.
- Never mix CRS/resolution silently: resample to a documented common grid; record parameters in provenance.
- Area computed in projected CRS (m²).
- Registration check: phase-correlation / feature-based shift estimate between pair; above threshold → warn (flag `poor_registration`) or exclude.
- Masks: SCL band (Sentinel-2 L2A) for cloud/shadow/snow; valid-pixel ratio per tile.

## 8. ML components

| Model | Use | Notes |
|-------|-----|-------|
| RemoteCLIP | Text/image embeddings | Local weights; GPU if available; batch inference; record model + checkpoint hash |
| ChangeFormer | Change probability | Pretrained; **domain gap** vs Sentinel-2 (resolution, bands, training data); configurable `CHANGE_THRESHOLD`, `MIN_CHANGE_AREA` |
| Groq LLM | Parsing/explanation/chat | Structured JSON only; validated; never executed |

Device selection: CUDA → CPU fallback; reported in `/api/health` and evaluation output.

## 9. Confidence model (system confidence)

Weighted combination of: model_change_score, registration_quality, cloud_quality, valid_pixel_ratio, season_similarity,
temporal_consistency, minimum_area. Output `{confidence ∈ [0,1], quality_flags[]}`.
Weights are configuration, versioned in provenance. **Not calibrated** unless a calibration study is run.

## 10. API surface

```
GET  /api/health
POST /api/query/parse              POST /api/search/semantic        POST /api/search/image
POST /api/ingest                   GET  /api/scenes   /api/scenes/{id}
POST /api/aoi                      GET  /api/aoi/{id}
POST /api/change/analyze           GET  /api/change/{id}            GET /api/changes
POST /api/changes/{id}/decision    GET  /api/timeline               GET /api/similar/{tile_id}
GET  /api/provenance/{analysis_id} POST /api/report
POST /api/assistant/chat           GET  /api/jobs/{id}   /api/jobs/{id}/events
```
Errors: `{error, code, suggestion}` with codes such as `NO_IMAGERY`, `INVALID_AOI`, `MODEL_MISSING`, `LLM_UNAVAILABLE`, `UPSTREAM_FAILURE`, `EMPTY_INDEX`.

## 11. Frontend architecture

```
src/
  components/  (SearchBar, FilterPanel, Timeline, BeforeAfter, ChangePanel, ResultsList, ReviewQueue, Assistant, PipelineStepper)
  map/         (MapView, layerManager, aoiDraw, animations)
  motion/      (tokens, variants, useReducedMotion)
  stores/      (Zustand: map, filters, selection, settings)
  services/    (typed API client, SSE client)
  hooks/       (TanStack Query hooks)
  pages/  types/
```
State: server state via TanStack Query; UI/selection via Zustand. Map animation is imperative (MapLibre), not per-frame React renders.

## 12. Deployment

- **Docker Compose:** frontend, backend, postgres+postgis, redis (+ celery worker).
- **ML inference:** optionally host-run for NVIDIA GPU; containerize only where practical.
- **Volumes:** `data/`, `models/`, `indexes/`, `reports/`.
- **Config:** `.env` (never committed), Pydantic Settings.

## 13. Security

Secrets in env only; all third-party calls from backend; CORS allow-list; Pydantic validation; upload type/size limits and safe filenames;
rate limiting on search/analyze/assistant; structured JSON logs without secrets; MapTiler key public + domain-restricted.

## 14. Offline-readiness (future)

| Online | Offline replacement | Interface |
|--------|--------------------|-----------|
| Copernicus API | Local GeoTIFF/COG archive | `ImagerySource` |
| Groq | Local query parser / local LLM | `QueryParser`, `Explainer` |
| MapTiler | Local vector/raster tiles | `MapProvider` |

## 15. Architecture decision records (short)

| # | Decision | Rationale |
|---|----------|-----------|
| ADR-1 | LLM excluded from pixel analysis | Reliability, auditability |
| ADR-2 | FAISS FlatIP first | Simple, exact, fine at prototype scale |
| ADR-3 | Pretrained ChangeFormer, no training | Time; disclose domain gap |
| ADR-4 | Celery + SSE for jobs | Long-running tasks with live progress |
| ADR-5 | Earliest *supported* observation, not event date | Sparse observations cannot prove exact dates |
| ADR-6 | Interfaces for all externals | Offline packaging later |
