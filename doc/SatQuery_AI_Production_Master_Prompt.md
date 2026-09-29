# SatQuery AI — Production Engineering Master Prompt

Prepared from PRD.md, ARCHITECTURE.md, design.md, task.md and testing.md, with memory.md as the current status record. Review date: 28 September 2026.

## How to use

Place the six source documents in your coding agent's project workspace. Copy everything between **BEGIN MASTER PROMPT** and **END MASTER PROMPT** into the agent. This asks the agent to implement the application; it is not a training-notebook prompt. Existing project files must be inspected and preserved. No application code or deployed system has been verified by this document review.

## Review of the six documents

The documents form a strong specification for an online-first satellite analysis prototype. They are not evidence of a production implementation: memory.md records Phase 0, no verified gate, and unconfigured external services and model weights. The most valuable existing requirements are honest temporal evidence, full provenance, analyst review, real imagery, and an optional LLM.

| Finding | Required correction in the implementation prompt |
|---|---|
| PRD explicitly excludes training and full offline packaging | Keep pretrained inference as release scope. Do not insert a VRSBench/LEVIR/OSCD training pipeline or claim full on-prem compliance. |
| task.md says one phase per session | Work through phases in order, proceeding after each passing gate. Maintain resumable records instead of stopping automatically after scaffolding. |
| MVP excludes Phase 8 quality controls and Phase 11 explanations, although goals/acceptance need them | Make core quality checks, provenance and grounded explanation fallback part of the first usable release. |
| Provenance is scheduled late in Phase 10 | Create provenance infrastructure before the first ingestion. |
| Naive FAISS add followed by a DB insert has no shared transaction | Use stable vector IDs, a durable ingestion journal/outbox, a single index writer, versioned snapshots and recovery. |
| Fixed over-fetch followed by metadata filtering can miss eligible results | Use a tested constrained-search strategy with completeness metadata and adversarial filter tests. |
| Plain Redis pub/sub does not replay missed progress events | Persist job state and use durable event IDs with SSE replay/polling fallback. |
| Raster delivery for historical comparison is unspecified | Add scene-specific COG/XYZ rendering, valid-pixel transparency, attribution and versioned caching. |
| Copernicus OAuth details are generic | Choose and verify one exact catalog/download integration; credentials must match that API family. |
| MIN_CHANGE_AREA=20 has no units | Replace with explicit square metres and pixel-count constraints tied to the analysis grid. At a 10 m grid, a pixel represents 100 m². |
| Band and reflectance handling are underspecified | Preserve scientific reflectance separately from RGB display/model inputs; explicitly align bands and masks. |
| Binary change output is followed by strong semantic labels | Keep categories as evidence-based hypotheses; allow unknown. Spectral indices alone do not prove roads/buildings. |
| Confirmed-date wording differs across files | Record the later confirming acquisition date separately from first supported observation and analyst decision time. |
| Single-analyst MVP identity is acceptable, but public access controls are unspecified | Provide protected single-operator deployment with server-derived identity; defer enterprise multi-tenancy. |
| Some tests assume model guarantees | Use synthetic fixtures for deterministic pipeline tests; measure real-model behavior separately. New indexed items may legitimately alter nearest-neighbor rankings. |

“Production-level” here means implementation with security, durability, observability, reproducibility and demonstrable release gates. It does not mean guaranteed detection accuracy, completed validation, unlimited free APIs, or high availability from a single Docker Compose host.

---

## BEGIN MASTER PROMPT

You are a senior full-stack engineer, geospatial engineer, ML inference engineer and production reliability engineer. Implement **SatQuery AI — SIH 26227 Semantic Retrieval and Multi-Temporal Change Analysis of Satellite Imagery** as a real, runnable application in this workspace.

Deliver working code, migrations, tests, operational scripts and documentation. Begin by inspecting the actual repository. Do not stop after an architecture proposal, a folder scaffold or a polished UI. Never claim a gate passed unless you ran it and retained its evidence.

### 1. Source documents, scope and working method

Read, in this order: memory.md, PRD.md, ARCHITECTURE.md, task.md, testing.md and design.md. Follow applicable repository instructions. Inspect existing code and git status before making changes. Preserve unrelated work and existing useful functionality.

Use the source documents for product intent. Apply the explicit engineering corrections in this prompt where the documents are contradictory or incomplete. Record those decisions and reasons in architecture decision records, and update the affected source documents to match implemented behavior.

The requested release is **online-first, single-operator, pretrained inference**:

- RemoteCLIP for semantic embeddings; ChangeFormer for binary change candidates.
- Groq for validated query interpretation and grounded explanations only.
- Copernicus Data Space for actual historical Sentinel-2 L2A acquisitions.
- MapLibre and MapTiler for map display; acquisition-specific imagery comes from the scientific imagery pipeline.
- PostgreSQL/PostGIS, FAISS and local workers for application processing.
- No model training, OpenAI/Gemini substitution, fabricated imagery or mandatory paid service added without a documented requirement.
- Sentinel-1 fusion, full offline deployment, enterprise RBAC and automatic alerting remain future work. Describe online dependencies honestly; an offline-ready interface does not establish offline capability.

Implement phases sequentially and continue automatically when a gate passes. This explicitly replaces the source checklist's “one phase per session” stopping rule. Keep phases reviewable. Ask only for information that genuinely blocks safe implementation. If credentials, weights, hardware or network access are unavailable, finish independent code and tests, mark the affected live gate BLOCKED, and state exactly what is needed. Never substitute random outputs to make a gate appear complete.

For each phase: inspect, implement, run targeted checks, fix failures, then update task.md and memory.md with files changed, commands, results and blockers. On context/session limits, leave exact next steps. Do not mark unchecked work complete.

### 2. Product behavior and scientific boundaries

Support the full workflow: AOI selection → imagery discovery/ingestion → text or image retrieval → candidate change analysis → chronological evidence → before/after inspection → explanation → analyst review → export/provenance.

Never fabricate scene IDs, footprints, observation dates, areas, confidence values, detections, metrics or job progress. A zero-change result is valid. Distinguish no scenes, no usable observations, no indexed imagery, insufficient temporal evidence, and a successful analysis with no detected change.

The basemap is navigation context. It must not be used as dated scientific evidence. “Latest available observation” means the newest acquired scene actually present in the archive, not live satellite video. Before/after and time-lapse use specific source acquisitions, not arbitrary mosaics across dates.

RemoteCLIP similarity is a ranking signal, not proof of an object or event. A query such as “new construction near rivers after 2022” has semantic, spatial and temporal parts. Text search alone cannot verify “new,” river distance or construction. Route change questions to the change workflow, and enforce proximity only against traceable geometry with a defined distance. Otherwise label that constraint unsupported/semantic-only and keep it visible; do not silently claim it was applied.

ChangeFormer supplies binary change evidence. It is not automatically a building/road classifier, and a checkpoint trained on a different spatial resolution has a domain gap. Categories such as construction, clearance, road development and water variation are candidate interpretations supported by available evidence. Ambiguous changes remain `unknown`.

Show system confidence as an **uncalibrated quality score**. Do not present it as probability or percent accuracy. Separate model score, retrieval similarity, QC score, temporal status and analyst decision. Never claim an exact construction/event date.

### 3. Stack and repository structure

Keep the source stack: React, TypeScript, Vite, Tailwind, MapLibre GL JS, MapTiler, TanStack Query, Zustand, Framer Motion and lucide-react; FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/PostGIS, Redis and Celery; Rasterio/GDAL, Shapely, PyProj, NumPy, OpenCV, PyTorch, open_clip and FAISS.

Verify supported compatible releases and official model interfaces when implementing. Pin the tested environment with lockfiles and checkpoint hashes. Do not guess package versions, retired Groq model IDs, checkpoint URLs, API routes or CUDA compatibility. Prefer a modular monolith with isolated job workers over unnecessary microservices. Retain compatible existing project versions unless a demonstrated problem requires change.

Use a structure equivalent to:

```text
frontend/src/{components,map,motion,stores,services,hooks,pages,types}
backend/app/{api,core,schemas,models,repositories,services,workers}
backend/alembic/
backend/tests/{unit,integration,geo,ml,api}
ml/{remoteclip,changeformer}
tests/{fixtures,e2e}
scripts/
docs/{adr,runbooks}
data/ models/ indexes/ reports/
```

Keep source-controlled fixture manifests small and include license/provenance. Exclude secrets, downloaded imagery, weights, index snapshots and generated reports from git. Define interfaces for ImagerySource, QueryParser, Explainer, EmbeddingModel, ChangeDetector, VectorIndex, RasterRenderer and MapProvider. Implement the active adapters completely; do not ship stubbed endpoints as working capabilities.

### 4. Configuration, preflight and operating limits

Create `.env.example` with safe placeholders and comments, validated backend settings, and a clear split between secret backend configuration and public frontend configuration. Include:

- APP_ENV, DATA_MODE, DATABASE_URL, REDIS_URL, allowed origins and operator authentication configuration.
- GROQ_API_KEY and a verified configurable GROQ_MODEL.
- Selected Copernicus adapter, endpoints and adapter-specific credential fields. Do not assume all CDSE services share a client-credentials flow.
- Public MapTiler key with origin restrictions; no private key under a VITE_ variable.
- Model paths, SHA-256 hashes, device, batch size, worker concurrency and CPU thread limits.
- Data/cache/index/report paths, free-disk reserve, total storage budget and retention policy.
- Tile/grid settings, TOP_K, bounded query/result limits, detection threshold, MIN_CHANGE_AREA_M2, MIN_CHANGE_PIXELS, QC thresholds and versioned confidence weights.
- Max AOI area, vertices, date span, scenes/job, raster pixels/job, upload bytes and decoded image pixels.
- Request timeouts, retry limits, backoff, job time limits and event retention.

Implement a doctor/preflight script: versions, DB/Redis connectivity, writable paths, available disk/RAM, CUDA/device availability, model compatibility/hash checks and per-provider readiness. Redact secrets. Report environment facts; do not assume a GPU or sufficient memory exists.

Provide a low-resource profile with one inference job at a time, conservative scene/AOI limits, small batches, disk-backed assets and sequential model use if needed. CPU fallback is functional but may be slow; measure it. Handle GPU OOM with a bounded smaller-batch retry or an explicit failure, never an endless retry loop. Do not load a model independently into every API process.

### 5. Database and provenance foundation

Create real Alembic migrations, PostGIS extension setup, constraints and indexes. Start with aoi, scenes, scene_assets, tiles, embeddings, index_generations, ingestion_batches/outbox, analyses, analysis_observations, changes, change_observation_evidence, analyst_decisions, provenance, jobs and job_events. Combine tables only when semantics remain explicit.

Use UTC timestamps and typed enums. Geometry uses EPSG:4326 for exchange/storage; processing uses an explicitly chosen metric grid. Store source and processing CRS, affine transform, resolution, band descriptions, acquisition timestamp, checksums, source product IDs and footprint. Use GiST and appropriate temporal/status indexes.

Separate scene identity from AOI-specific processed artifacts. Ingesting an additional AOI from the same source scene must not be skipped merely because the scene already exists. Version tiles/derivatives by source, grid/window and preprocessing configuration; version embeddings by tile artifact and model configuration.

Provenance starts before ingestion, not at the review phase. It must represent ingestion/search artifacts even without an analysis ID. Record parent artifact links, inputs/outputs, source references, model hashes, code version, configuration digest, parameters, timestamps, masks, resampling, grid and quality results. Do not log credentials or temporary signed URLs. Keep scientific analysis records immutable; re-analysis creates a linked version.

### 6. Copernicus imagery ingestion

Select one exact documented catalog and data-access route. Verify its authentication, pagination, cloud metadata, rate limits, download semantics and required account setup against current official documentation. Do not mix generic STAC, OData, Sentinel Hub or S3 credentials/endpoints. Document optional alternatives separately. Avoid promises of unlimited free usage; expose quotas and bounded requests.

Discover actual Sentinel-2 L2A products by AOI, time and sensor/cloud constraints. Retain real acquisition timestamps and product/granule identities. Scene-level cloud coverage is a preliminary filter; compute valid/cloud coverage inside the AOI and candidate polygons later.

Retrieve the bands needed by enabled features, including RGB and appropriate NIR/SWIR/mask assets. Prefer practical area-limited reads where supported; if full products are required, disclose size estimates and enforce disk budgets. Process API results, if used, must retain the contributing scene identities; do not treat a multi-date composite as one observation.

Use streamed downloads, bounded concurrency, safe archive extraction, checksums, temporary files, completion markers and atomic finalization. Handle expired tokens, 429 Retry-After, timeouts and transient 5xx with bounded retry/backoff. Return structured errors for nonrecoverable failures. Cache by source identity and processing version, with partial-download recovery and disk eviction rules that protect referenced evidence.

`POST /api/ingest` returns a durable job reference. Make repeated requests idempotent with a request key and processing-version-aware artifact keys. A user may retry safely after a lost connection.

### 7. Scientific preprocessing and map raster delivery

Validate AOIs: geometry type, ring closure, finite coordinates, lon/lat order, area, vertex count and self-intersections. Persist circles as a documented geodesic polygon approximation. Handle antimeridian, polar and multi-zone cases explicitly; reject unsupported extents with actionable errors instead of applying a wrong UTM zone silently.

Create one common analysis grid for compared observations: CRS, bounds, pixel size, origin and transform. Use appropriate continuous-band resampling and nearest-neighbor resampling for categorical SCL/quality masks. Record every transformation. Upsampling a coarser band does not add native spatial detail.

Preserve physical/scientific reflectance separately from RGB previews and model inputs. Apply provider/product scale factors and offsets according to metadata; avoid double scaling or hardcoded assumptions across product processing baselines. Keep nodata distinct from valid zero values. Use common valid-pixel masks for pairwise differences and mask clouds, shadows, snow and invalid pixels as supported by the source. Document configurable SCL rules and unavailable quality evidence.

Use consistent, versioned radiometric/display normalization. Avoid independent per-image auto-stretch that manufactures apparent temporal changes. Honor each checkpoint's exact input preprocessing separately from UI visualization. All-nodata tiles are excluded with a recorded reason.

Compute spectral indices from actual reflectance bands, never from RGB JPEGs:

- NDVI = (B08 − B04) / (B08 + B04).
- Green–NIR NDWI = (B03 − B08) / (B03 + B08); document this specific NDWI definition.
- NDBI = (B11 − B08) / (B11 + B08).

Align bands explicitly, guard near-zero denominators, preserve masks and expose unavailable indices as unavailable. Coarser native bands retain that limitation in provenance and UI metadata.

Check co-registration using suitable valid stable regions. Report shift and residual error in pixels/metres plus estimator confidence. Apply controlled registration only when reliable; otherwise reject/flag the pair. Do not let the registration routine align away genuine changes. Track overlap, valid area, season gap, atmospheric/illumination differences and available acquisition geometry; missing QC evidence cannot be counted as good quality.

Tile with deterministic windows, documented edge padding and optional overlap. Preserve tile-to-world transforms. Blend/crop overlap consistently during inference and merge connected change components across tile seams before area filtering.

Add scene-specific COG/XYZ tile rendering or an equivalent tested RasterRenderer. Provide RGB, index and change-mask previews with bounds, attribution, nodata transparency, zoom constraints and versioned cache keys. The browser requests controlled asset IDs, not arbitrary filesystem paths or remote URLs. Document the renderer dependency and deployment. Validate overlays against AOI geometry. The raster service must not trigger ML inference on each map tile request.

### 8. RemoteCLIP and filtered semantic retrieval

Load official compatible RemoteCLIP weights and their matching tokenizer, architecture and transforms. Pin source revision, checkpoint hash, embedding dimension and preprocessing version. Use eval/inference mode, bounded batches and finite float32 L2-normalized embeddings. Do not mix embedding versions in one index generation.

Support text-to-image, image-to-image and similar-site retrieval. Validate uploads using decoded content, size/pixel limits and safe server-generated names. Clear temporary files according to retention policy. Similar-site search can exclude the query tile, overlapping tiles and nearby duplicates under visible options; do not hide result suppression.

Use cosine ranking via normalized inner product with stable tie handling. Similarity is not confidence. Deduplicate visually overlapping source tiles when appropriate and expose the applied policy.

Enforce AOI, time, sensor, cloud, quality and active-state filters. A fixed global top-K/over-fetch then filter is insufficient for selective constraints. For the initial exact index, implement an eligible-ID-aware path supported by the pinned FAISS API, or exact scoring over stored eligible vectors in bounded chunks. An adaptive over-fetch path must expand until completeness is established or return an explicit bounded/truncated status. Never declare no eligible results merely because a small global candidate pool was filtered out. Test eligible results ranked below the initial pool.

Return tile ID, scene ID, footprint, acquisition time, score, preview URL, source/model references, applied filters, exclusions and warnings. Distinguish search of the existing archive from a separate user-visible ingestion job. Do not silently launch expensive unbounded imagery downloads for every query.

### 9. FAISS durability and consistency

Use IndexFlatIP with explicit stable int64 vector IDs, for example a verified IndexIDMap2 wrapper. The adapter's logical `add(ids, vectors)` may call FAISS `add_with_ids`. Do not confuse mutable row positions with permanent database IDs.

Make PostgreSQL plus durable embedding artifacts the authoritative state. Implement a concrete publish/recovery protocol:

1. Persist a batch, uniquely keyed vector records/artifacts and an index-outbox intent. These are pending, not searchable.
2. A single fenced writer consumes intents in sequence, checks existing IDs, and appends only missing vectors. Protect search/mutation on any shared index instance with locks or use immutable reader snapshots.
3. Write a checksummed versioned snapshot and manifest to temporary paths, flush as appropriate, and atomically publish them on the documented filesystem.
4. Commit the corresponding generation/membership state and batch completion in PostgreSQL. Search readers pin one published generation and only expose committed eligible memberships.
5. On restart, reconcile journal, database, vector IDs and snapshot checksums. Recover a published-but-uncommitted batch without duplicate vectors. Fall back to the last valid generation if a new artifact is corrupt/incomplete.

Test crashes before and after every boundary, duplicate delivery, two ingest requests and reader reload. DB rollback alone does not undo a FAISS mutation; atomic rename alone does not make DB and index one transaction. Snapshot serialization is allowed; full re-embedding/rebuilding on each new scene is not. Provide explicit maintenance/recovery tools for compaction or a model-version rebuild, with measured RAM/disk costs. Readers must detect new generations across multiple processes.

### 10. Change detection and temporal evidence

Wrap a verified ChangeFormer architecture/checkpoint pair. Inspect official preprocessing, input size constraints, output logits and class-channel semantics. Reject incompatible/missing weights. Never quietly replace missing ChangeFormer inference with image differencing or random weights. An optional baseline may be exposed only as a separately named, traceable algorithm.

Select pairs based on overlapping valid area, registration, sensor/grid compatibility, cloud/shadow, season similarity and useful temporal separation. Explain selection/rejection. Reject insufficient-quality pairs before candidate generation. Include both an analyst-selected pair mode and a multi-observation mode.

Run masked inference, convert logits correctly, apply a configured threshold, morphology, connected components, seam merging and polygonization. Keep pixel-to-world transforms correct. Calculate areas in a suitable metric/equal-area frame or a validated geodesic method, never in degrees. Preserve holes and valid MultiPolygon geometry where required.

Replace the ambiguous `MIN_CHANGE_AREA=20` with units. Enforce both MIN_CHANGE_PIXELS and MIN_CHANGE_AREA_M2. Compute the effective minimum using the analysis pixel area. A provisional engineering choice may use 9 connected valid pixels, but document it as unevaluated configuration, not a detection guarantee. A 10 m square pixel is 100 m²; resampling cannot justify subpixel building claims. Do not present detection-grid area as native-band precision.

For temporal analysis, evaluate all usable actual observations in chronological order. Store excluded observations and exclusion reasons. Use stable-baseline-to-later evidence together with appropriate adjacent comparisons; adjacent-only comparisons can miss a change that persists after its first appearance.

Track a candidate footprint across observations using reproducible overlap/association rules. Handle split/merge/expansion ambiguity explicitly, retain per-observation support and avoid double-counting area.

Use canonical fields consistently across DB, API, UI and reports:

- `last_baseline_observation_at`: last usable acquisition showing the relevant baseline within the evaluated interval, nullable.
- `earliest_supported_at`: first usable acquisition supporting the candidate within the analyzed observations.
- `confirmed_at`: timestamp of the later independent usable acquisition meeting the configured persistence rule, nullable.
- `latest_observation_at`: latest relevant actual acquisition evaluated.
- `event_window_start` and `event_window_end`: evidence bounds, interpreted as `(last baseline, first support]` when the baseline exists; otherwise left-censored.
- `temporal_status`: candidate, confirmed, inconsistent or insufficient_evidence.

Never substitute processing time or analyst approval time for acquisition time. A second tile/granule from the same overpass is not independent confirmation. Cloudy missing observations are unknown evidence, not proof of no change. Last-scene-only support stays unconfirmed. Flicker, disappearance or seasonal reversion lowers temporal support and may require analyst review. “Earliest” means earliest supported within the searched evidence, not proof there was no earlier event outside coverage.

Appearance/disappearance/expansion/contraction require an appropriate tracked feature or evidence definition. A binary change mask alone does not establish direction; return unknown where direction is unsupported.

### 11. Quality score, categories and grounded language

Make hard QC eligibility gates separate from the soft confidence formula: a high model score must not override unusable coverage or failed registration. Implement a documented versioned formula using available factors such as valid ratio, registration quality, cloud/season conditions, temporal consistency, model score and support area. Store factor values, missing factors, weights, rejection reasons and `calibrated: false`. Missing factors must not inflate confidence by silently assuming perfect quality.

Classifications use available spectral, geometric and temporal evidence as hypotheses. Expose the supporting observations and rules. NDVI decrease may support vegetation loss; NDBI rise is not sufficient proof of a building. Keep unknown when competing explanations exist or an object is below meaningful sensor resolution. Explain the pretrained model's domain gap in the UI and reports.

Groq receives bounded structured facts only, with allowed result/scene IDs. It never receives raw rasters, produces SQL, executes commands or drives unrestricted tools. Validate parser output with Pydantic, allowed fields and bounded values. Treat queries/notes as data, enforce deterministic explicit filters and visible conflict handling. Preserve the user's UI filters when the parser fails.

On invalid JSON, timeout, missing key or provider failure, run raw-text retrieval with structured filters and a visible fallback notice. Produce deterministic explanations from recorded facts when Groq is absent. Validate generated references; discard unsupported factual claims. Keep the entire retrieval/change/review/report pipeline usable without the LLM.

### 12. API, jobs and recoverable progress

Implement the existing API contracts and document additions in OpenAPI:

```text
GET  /api/health
GET  /api/health/live
GET  /api/health/ready
POST /api/query/parse
POST /api/aoi
GET  /api/aoi/{id}
GET  /api/scenes
GET  /api/scenes/{id}
POST /api/ingest
POST /api/search/semantic
POST /api/search/image
GET  /api/similar/{tile_id}
POST /api/change/analyze
GET  /api/change/{analysis_id}
GET  /api/changes
GET  /api/timeline
POST /api/changes/{id}/decision
GET  /api/provenance/{analysis_id}
GET  /api/tiles/{tile_id}/provenance
POST /api/assistant/chat
POST /api/report
GET  /api/reports/{report_id}
GET  /api/jobs/{id}
GET  /api/jobs/{id}/events
POST /api/jobs/{id}/cancel
GET  /api/rasters/{asset_id}/tiles/{z}/{x}/{y}.png
```

Long jobs return HTTP 202 with job/resource references. Use pagination, typed payloads and consistent errors containing `error`, `code`, `suggestion` and `request_id`; add retry metadata when relevant. Keep NO_IMAGERY, INVALID_AOI, MODEL_MISSING, LLM_UNAVAILABLE, UPSTREAM_FAILURE and EMPTY_INDEX; add explicit insufficient-observation, unusable-imagery, quota and resource-limit errors where needed. Never leak tracebacks to users.

Celery runs bounded idempotent stages; Postgres stores authoritative job state. Use a durable event table or replayable Redis Stream with defined retention/reconciliation. Redis pub/sub can notify clients but cannot be the only progress record.

Events include monotonically ordered event ID, job ID, stage, stage ordinal/total, measured completed/total units where known, status, cache state and UTC timestamp. Support Last-Event-ID resume, heartbeat, reconnection/backoff, stale-cursor handling and polling fallback. Progress may be indeterminate when work size is unknown; do not invent linear percent/time estimates.

Implement queued/running/succeeded/failed/cancel_requested/cancelled states, stage checkpoints, worker heartbeats, bounded retries and cooperative cancellation at safe boundaries. A worker crash must leave a recoverable/stale job, not “running” forever. Checkpoint committed stages before acknowledging completion. On reconnect, reconcile with durable final state.

### 13. Frontend and map experience

Implement the professional dark map-centric design from design.md. Retain its color tokens, readable typography, collapsible filters, resizable lower dock and responsive drawer/sheet behavior. Prioritize completed analyst workflows over decorative animation.

Build SearchBar with text/image modes and editable parsed chips; FilterPanel with AOI/date/sensor/cloud/quality controls; MapView with layer/opacity controls, coordinates and scale; ResultsList; Timeline; BeforeAfter; ChangePanel; ReviewQueue; Assistant; PipelineStepper; settings and report export.

Timeline markers are actual acquisition timestamps only. Calendar axis labels are allowed but must not masquerade as observations. Show missing intervals, excluded/cloudy scenes and the supported/confirmed/unknown-exact-date legend. Time-lapse advances only through actual loaded scenes and prefetches within limits.

Before/after supports synchronized side-by-side, swipe and opacity views using georeferenced evidence assets. Always label dates, sensor, scene IDs, units and any resampling. Change details show area, candidate category, temporal evidence, uncalibrated quality factors, limitations, provenance and review controls. Separate temporal confirmation from analyst confirmation.

All controls must work against real APIs. Define loading, empty, error, degraded and partial states. Never seed invented production results. A test-only fixture mode is isolated and visibly labeled TEST DATA; it cannot be used to claim live validation.

Use TanStack Query for server state and Zustand for UI state. Map animation stays imperative; DOM motion favors transform/opacity. Animate actual events, honor reduced motion, cancel rAF/listeners on cleanup, call map.resize() after layout changes and avoid per-frame React state updates. Virtualize large result lists and bound raster/layer prefetch.

Provide keyboard AOI alternatives such as coordinate/GeoJSON entry, labeled controls, visible focus, accessible swipe/timeline actions, a table alternative to map-only results and aria-live progress. Color never carries meaning alone. Review shortcuts must not fire while typing notes.

### 14. Analyst review and reports

Persist confirm/reject/flag decisions with server-derived operator identity, server timestamp, notes and immutable history. Keep current review status separate from evidence/temporal status. Use version checks for concurrent edits and safe optimistic UI rollback. Do not let the browser choose arbitrary analyst identities.

Export PDF, GeoJSON, CSV and JSON from the same canonical result snapshot. Include AOI, actual acquisition range, usable/excluded scene counts, change geometry/area, candidate class, quality factors, uncalibrated label, supported/confirmed dates, event bounds, review status, before/after references, provenance, model/code versions and limitations. PDF evidence images must correspond to the cited scenes. Include attribution and export schema versions.

Reports remain available without Groq. Escape HTML/Markdown where rendered, prevent CSV formula injection and disallow arbitrary external resource retrieval during PDF generation. Serve authorized report IDs with correct MIME types; do not expose host file paths. Document retention, regeneration and deletion behavior.

### 15. Deployment security and operations

Create a reproducible Docker Compose deployment with frontend/reverse proxy, API, worker, PostGIS, Redis and raster serving as needed. Provide CPU profile first and a documented tested GPU option where available. Use health checks, named volumes, non-root application containers, restricted internal ports and explicit migration/startup ordering. Do not run development servers as production entrypoints.

Provide protected single-operator access using a real supported authentication/session approach or a documented authenticated reverse proxy. Private localhost development can use an explicit development identity; production must reject that bypass. Enterprise user management is out of scope. Enforce authenticated access to data, exports, SSE and mutations; use appropriate secure cookies/CSRF protection for the selected session scheme. CORS is not authentication. Strip untrusted identity headers before proxy injection.

Use TLS at the ingress, narrow origins, route-specific quotas, safe secret management and redacted logs. Enforce upload decoding limits and archive extraction limits; block path traversal and SSRF through scene, tile, report and external fetch parameters. Never send backend credentials to the browser. The restricted public MapTiler key is an intentional exception; map tile requests may originate in the browser with proper attribution.

Add structured request/job/stage logs, latency histograms, queue depth, failure counts, provider errors, GPU/CPU/memory/disk measurements and index-generation consistency checks. Liveness tests process health; readiness shows core dependency health and feature-specific degradation. Optional Groq failure should not make the entire service unusable.

Write runbooks for installation, credentials, model download/licensing, migrations, quota exhaustion, full disk, corrupt index, failed jobs, rollback and disaster recovery. Back up DB, artifact manifests, authoritative embeddings/evidence and generation metadata consistently. Test restoration into a clean environment. A single-host Compose setup is not high availability; document supported scale and failure boundaries.

### 16. Meaningful tests and evaluation

Follow testing.md with corrections for actual model behavior. Use unit tests for deterministic geometry/temporal/QC logic, integration tests with real PostGIS/Redis and durable index files, frontend tests with Vitest/testing-library, and Playwright for complete workflows. Keep synthetic fixtures explicitly TEST DATA and isolated from product evidence.

Required cases include:

- Invalid/self-intersecting/oversized AOI; bad coordinate order/range; unsupported antimeridian/polar extent.
- Reflectance scaling/offsets, band order, mixed CRS/resolution, mask resampling, all-nodata, metric area, tile-to-map alignment and seam merging.
- Registration shifts and failed/uncertain registration; clouds, sparse coverage and missing bands.
- Provider pagination, 401/429/5xx/timeouts, caching/checksums and partial downloads.
- Duplicate ingestion, different AOIs from one scene, stage retries and crashes around every index-publication boundary.
- Stable vector IDs, checksums, index reload, new-generation readers and no per-scene full rebuild/re-embedding.
- New-scene ingestion preserves old IDs/vectors and their similarity scores; do not require old nearest-neighbor rankings to remain unchanged when valid new candidates are added.
- Filtered retrieval where all eligible results lie below the initial global over-fetch pool; tie handling and bounded/truncated response semantics.
- Missing/mismatched checkpoints, finite normalized embeddings, eval-mode reproducibility within declared tolerances, bounded CPU/GPU behavior.
- Synthetic probability-mask postprocessing with known expected polygons. A pretrained model need not detect an arbitrary inserted rectangle; keep that separate as a measured smoke experiment.
- Identical-pair handling at the service level and separately measured raw-model output. If a documented identity guard suppresses change, test that guard explicitly; do not call it model accuracy.
- Temporal sequences including baseline/baseline/candidate/confirmation, last-scene-only change, cloudy gaps, left-censoring, unsorted input, flicker, multiple same-day granules and candidate split/merge.
- LLM malformed/off-schema output, invented references, timeout and complete no-Groq operation.
- Review history, authorization, version conflict and report schema consistency.
- SSE disconnect/replay, stale cursor, terminal reconciliation, cancellation and worker death.
- Secret leakage, malicious uploads, SSRF, CSV formula injection, session/CSRF behavior, rate limits and authorized raster/report access.
- Reduced motion, keyboard use, usable error states and actual-date timeline rendering.

Use tolerance-based numerical assertions across devices. Do not hide failures by disabling tests or lowering thresholds without an explained correction. Measure the coverage targets specified in testing.md; report actual values and exclusions. Network/GPU tests are opt-in, and missing external resources produce explicit skips/blocked gates, not passes.

Implement scripts/evaluate.py with machine-readable JSON and a human-readable report. Retrieval: Recall@K, Precision@K, MRR only with defined relevance judgments; otherwise N/A. Change: precision, recall, F1, IoU and FPR with declared valid-pixel masks and ground truth; otherwise N/A. Report class/condition, scene, geography and model-domain limitations. Keep tuning data separate from held-out evaluation; overlapping geography/acquisitions must not leak across splits.

Record model hashes, scene/dataset manifests, thresholds, code/environment versions, hardware, seeds and sample counts. Measure warm/cold p50/p95 search, ingestion, inference, end-to-end latency, RAM/VRAM and disk/index size under stated load. Never invent benchmark numbers or claim Sentinel-2 accuracy from LEVIR results.

### 17. Implementation phases and gates

Respect original phase numbering where useful but move foundational safety/provenance earlier. Use this dependency order:

| Phase | Deliverable and exit gate |
|---|---|
| 0 | Repository audit, contradiction decisions, lockfiles, settings, Compose, doctor script; DB/Redis healthy and limitations recorded. |
| 1 | API/error/auth foundation, migrations, jobs/provenance scaffolding; real health/config/database tests pass. |
| 2 | Map/AOI/raster contracts; draw or enter AOI, persist and reload with validation/accessibility checks. |
| 3 | Verified Copernicus route, ingestion/cache/scientific preprocessing and raster delivery; ingest one small actual AOI, render its source scene and repeat with cache/idempotency evidence. |
| 4 | RemoteCLIP and durable incremental FAISS; checkpoint smoke, stable-ID search/reload and crash recovery pass. |
| 5 | Text/image/similar retrieval with correct filters; real indexed tiles visible with accurate metadata. |
| 6 | ChangeFormer plus hard QC/registration/area rules; valid real pair produces an honest zero-or-more-candidate result and before/after evidence. |
| 7 | Multi-temporal analysis; actual observation evidence, correct event interval and independent confirmation semantics pass. |
| 8 | QC scoring and cautious category hypotheses; factor provenance, unknown cases and condition tests pass. |
| 9 | Similar-site workflow and optional clustering, deduplication and tested spatial exclusions. |
| 10 | Review queue/history and complete provenance navigation; server-derived identity and decisions survive restart. |
| 11 | Grounded assistant/fallback plus PDF/GeoJSON/CSV/JSON reports; exports agree with source evidence. |
| 12 | CI, measured evaluation, clean startup, persistence/recovery, protected deployment and runbooks; final gate matrix complete. |

At each gate, explicitly classify PASSED, FAILED, BLOCKED or NOT RUN. Gate failures affecting correctness must not be hidden by moving to polish. Independent work can continue while a live external gate is blocked.

### 18. Final acceptance and handoff

Demonstrate all 18 PRD acceptance steps on a real small AOI with source scene IDs. If Groq is unavailable, show the functional fallback and mark the live Groq branch unverified. Never require a nonzero change polygon count just to make the demonstration look successful.

Additionally demonstrate: no-Groq operation; empty/low-quality imagery handling; restart with persisted search/reviews; idempotent ingest; new-scene incremental search; ingestion crash recovery; SSE reconnection; restore verification; authorized report/raster access; and no secret leakage.

Deliver:

1. Complete frontend/backend/ML adapter code, migrations, lockfiles and real service configurations.
2. CPU deployment and documented GPU profile; startup, shutdown, migration and preflight commands tested where possible.
3. .env.example, model download/verification script, source/checkpoint/license manifest and MODEL_PROVENANCE.md.
4. Real-fixture acquisition/verification script and manifests; test suites, CI and evaluation commands.
5. README, architecture decision records, API/export schemas, operations/backup/restore runbooks, demo guide and known limitations.
6. Updated PRD.md, ARCHITECTURE.md, design.md, task.md, testing.md and memory.md reflecting actual implementation, not aspirational completion.
7. A final status table listing implemented features, exact verification commands/results, measured metrics or N/A, blockers and release status.

Finish with concrete local run instructions and the smallest remaining external setup list. Do not claim production readiness until release gates are demonstrated on the target environment. Begin by reading the six files and auditing the repository, then implement.

## END MASTER PROMPT

---

## Technical references checked for this review

Use current primary documentation again when implementing; these references do not prove the eventual application is correct.

- [Copernicus Sentinel-2 mission data and native resolutions](https://documentation.dataspace.copernicus.eu/Data/Sentinel2.html)
- [Sentinel-2 L2A bands, units and masks](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html)
- [Copernicus STAC catalogue](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
- [Copernicus OData catalogue and download documentation](https://documentation.dataspace.copernicus.eu/APIs/OData.html)
- [Sentinel Hub OAuth authentication](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html)
- [RemoteCLIP official repository](https://github.com/ChenDelong1999/RemoteCLIP)
- [ChangeFormer official repository and checkpoints](https://github.com/wgcban/ChangeFormer)
- [FAISS concurrency and filtering FAQ](https://github.com/facebookresearch/faiss/wiki/FAQ)
- [FAISS ID mapping](https://github.com/facebookresearch/faiss/wiki/Pre--and-post-processing)

The recovery protocol, deployment controls and acceptance gates above are engineering recommendations derived from the supplied specification. They require implementation and validation; they are not claims of guarantees offered by those libraries.
