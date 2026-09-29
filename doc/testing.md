# TESTING — Strategy & Test Plan

Companion to `PRD.md`, `ARCHITECTURE.md`, `design.md`, `task.md`, `memory.md`.

## 1. Principles

1. **No fabricated data.** Tests use either real public Sentinel-2 scenes (small cached AOI) or synthetic fixtures explicitly labeled `TEST DATA`. Synthetic fixtures must never appear in product UI or reports.
2. **Core pipeline is tested without Groq.** LLM calls are mocked; a separate contract test validates schema handling.
3. **Failures are features.** Every error code (`NO_IMAGERY`, `INVALID_AOI`, `MODEL_MISSING`, `LLM_UNAVAILABLE`, `UPSTREAM_FAILURE`, `EMPTY_INDEX`) has a test.
4. **Measured, not invented.** Evaluation metrics are computed from data; if no labels exist, the metric is reported as "not available".
5. **Deterministic.** Fixed seeds, pinned model checkpoints (hash recorded), fixed thresholds in tests.

## 2. Tooling

| Layer | Tools |
|-------|-------|
| Backend | `pytest`, `pytest-asyncio`, `httpx` (AsyncClient), `pytest-cov`, `respx` (mock HTTP), `factory-boy` |
| DB | Dockerized PostGIS test database, Alembic migrations applied per session, transaction rollback per test |
| Geo | `rasterio` in-memory datasets, `shapely` assertions |
| ML | small CPU-only smoke inference, checkpoint hash check |
| Frontend | `vitest`, `@testing-library/react`, `msw` (API mocks), `jest-axe` (a11y) |
| E2E | `playwright` (real backend + real cached imagery) |
| Perf | `pytest-benchmark`, Lighthouse/Chrome tracing for animation |

Commands:
```bash
# backend
pytest -q --cov=app --cov-report=term-missing
pytest -m "not slow and not network"        # fast suite
pytest -m network                           # live Copernicus/Groq (opt-in, needs keys)
# frontend
npm run test           # vitest
npm run test:e2e       # playwright
```

Markers: `unit`, `integration`, `api`, `geo`, `ml`, `faiss`, `slow`, `network`, `gpu`.

## 3. Test pyramid & targets

| Level | Share | Notes |
|-------|-------|-------|
| Unit | ~60% | pure functions, services with mocks |
| Integration | ~25% | DB, FAISS, Celery/Redis, raster IO |
| API | ~10% | FastAPI endpoints, schemas, errors |
| E2E | ~5% | MVP acceptance path |

Coverage goals: backend ≥ 80% lines (services/quality/temporal ≥ 90%); frontend critical components ≥ 70%.

## 4. Fixtures

```
tests/fixtures/
  real/        # small cached real Sentinel-2 crops (license/attribution in README); scene IDs recorded
  synthetic/   # generated rasters — files prefixed TEST_DATA_
  aoi/         # valid + invalid GeoJSON
  images/      # valid jpg/png, corrupted, oversized, wrong mime
  llm/         # recorded Groq JSON responses (valid, malformed, off-schema)
```
Synthetic generators (in `tests/factories/`): identical pair, pair with inserted rectangle (known change), cloudy pair (masked band), shifted pair (known offset), seasonal-tint pair, all-nodata raster, mixed-CRS pair.

## 5. Backend tests

### 5.1 Config & infrastructure
- Settings load from env; missing required var raises clear error; `.env` never read in tests unless specified.
- `GET /api/health` reports DB, Redis, device (CUDA/CPU); degraded state when a dependency is down.
- Structured logs contain no secrets (assert API keys redacted).
- Error handler returns `{error, code, suggestion}` and never a stack trace.
- Rate limiting returns 429 with structured body.

### 5.2 Query parsing (Groq service)
| Case | Expected |
|------|----------|
| Valid response | Pydantic model populated |
| Malformed JSON | fallback to raw-text search + warning flag |
| Off-schema / extra fields | rejected/stripped, never executed |
| Injection-like text in query | treated as data; no tool/DB action |
| Groq timeout / 5xx / 429 | `LLM_UNAVAILABLE` handled; retry with backoff; fallback |
| Date normalization ("after 2022", "between 2021 and 2026") | correct ISO dates; invalid ranges rejected |
| No Groq key | fallback path works |

### 5.3 AOI
- Valid rectangle/polygon/circle → stored, retrievable, SRID 4326.
- Invalid: self-intersecting, <3 vertices, unclosed ring, lat/lon out of range, NaN, empty, huge area over limit → `INVALID_AOI`.
- Antimeridian and pole edge cases handled or rejected explicitly.

### 5.4 Copernicus service
- Token acquisition/refresh (mocked with `respx`).
- Search parsing: fields (scene ID, datetime, sensor, cloud, bbox, source ref) preserved.
- No results → `NO_IMAGERY`; HTTP 401/403/429/5xx/timeouts → `UPSTREAM_FAILURE` with retry/backoff.
- Cache: first call downloads, second call hits cache (assert no network); checksum mismatch triggers re-download; partial download resumed/cleaned.
- Duplicate scene ingest is idempotent (unique `scene_id`).
- `@network` live test on a tiny AOI (skipped without credentials).

### 5.5 Geospatial (`geo`)
- CRS normalization: EPSG:32643-type UTM → common grid; assert transform, resolution recorded.
- Mixed CRS/resolution pair is **resampled explicitly** and logged, never silently mixed; incompatible pair raises.
- Clip to AOI returns expected bounds; AOI outside scene → `NO_IMAGERY`/empty handled.
- Nodata handling: all-nodata tile has `valid_pixel_ratio = 0` and is excluded from indexing.
- Cloud/shadow mask (SCL classes) yields expected valid ratio on known raster.
- Tiling: tile count/size/overlap correct; tile geometry matches raster window; edge tiles handled.
- Area computed in projected CRS: 1 km² square ≈ 1,000,000 m² within tolerance at several latitudes.
- Registration check: known 0 px shift → good; known N px shift → `poor_registration` flag.
- Index computation: NDVI/NDWI/NDBI on hand-computed pixel values; divide-by-zero safe.

### 5.6 Embeddings & FAISS (`ml`, `faiss`)
- Model missing → `MODEL_MISSING` with instructions (run `download_models.py`).
- Checkpoint hash matches recorded value in provenance.
- Output embeddings: correct dim, L2-normalized (norm ≈ 1), deterministic across runs.
- Batching equals single inference (within tolerance).
- Corrupted/unsupported image → clear error, batch continues.
- FAISS: add/search roundtrip returns self as top-1 with score ≈ 1.
- Empty index search → `EMPTY_INDEX` (not crash).
- Persistence: save → reload → identical results; atomic write (simulate crash mid-write; old index intact).
- Incremental: adding scene B leaves scene A results unchanged; **assert no rebuild call** (spy).
- `embedding_id` ↔ `tile_id` mapping consistency check across DB and index count.
- Interface contract test runs same suite against Flat (and future HNSW/IVF).

### 5.7 Search service
- Over-fetch then PostGIS filtering returns ≤ `top_k` and respects AOI/date/sensor/cloud filters.
- Ranking order by similarity; ties stable.
- Filter yields nothing → empty list with helpful `suggestion`, not an error.
- Image search: type/size limits, safe filename, path-traversal filename rejected, decompression-bomb guard.
- Text-to-image sanity: on real fixture, a "water" query ranks water tiles above non-water (qualitative smoke test, not accuracy claim).

### 5.8 Change detection
- Identical pair → zero polygons.
- Synthetic inserted-rectangle pair → polygon overlaps known region (IoU above a loose smoke threshold; **not** an accuracy claim).
- Threshold/min-area respected (`CHANGE_THRESHOLD`, `MIN_CHANGE_AREA`); morphology removes speckle.
- Polygons valid (`ST_IsValid`), in correct CRS, area in m².
- Misregistered pair → flagged/rejected per config.
- Missing checkpoint → `MODEL_MISSING`.
- GPU vs CPU results within tolerance (`gpu` marker).
- Domain-gap notice present in analysis response metadata.

### 5.9 Temporal analysis
Timeline scenarios (tabular tests):

| Observations | Expected |
|--------------|----------|
| B,B,C,✓,E,S | earliest = C, confirmed = ✓, latest = S |
| Change only in last scene | earliest = last, confirmed = null (unconfirmed) |
| Single scene | no analysis possible → clear message |
| Cloudy scene in middle | skipped/dimmed, does not break sequence |
| Flicker (change appears then disappears) | flagged as inconsistent; lower confidence |
| Seasonal-only difference | not marked as change or heavily down-weighted |
| Sparse gaps (years missing) | no fabricated dates; event bound reported as interval |
| Unsorted input | sorted chronologically |

Assert output never contains an "exact event date" field claiming precision.

### 5.10 Quality control
- Each factor moves confidence in the expected direction (monotonicity tests).
- Weights from config; changes recorded in provenance.
- Flags emitted correctly: `good_registration`, `low_cloud`, `multi_temporal_confirmation`, `poor_registration`, `high_cloud`, `low_valid_pixels`, `seasonal_mismatch`, `below_min_area`.
- Confidence bounded [0,1]; response includes `calibrated: false`.

### 5.11 Classification
- Vegetation→bare soil (NDVI drop) → clearance.
- Land→water (NDWI rise) / water→land → water variation.
- NDBI rise + compact geometry → construction; elongated thin geometry → road development.
- Growth adjacent to existing built area → construction expansion.
- Ambiguous → `unknown`.

### 5.12 Ingestion
- Full ingest flow adds scene, tiles, embeddings, DB rows, provenance in one logical unit; failure mid-way rolls back DB and leaves index consistent (compensating delete/tombstone).
- Corrupted raster → rejected with reason, no partial rows.
- Duplicate scene → skipped/idempotent.
- Job events emitted in order with `stage_index`, `stage_total`, `cached` flag; SSE stream tested with async client.

### 5.13 Review & provenance
- Decision stored with analyst id, timestamp, notes; multiple decisions keep history.
- Invalid decision value rejected.
- Provenance contains scene, model, version, thresholds, preprocessing params, software version for every step; `GET /api/provenance/{id}` complete; unknown id → 404 structured.

### 5.14 Reports
- PDF, GeoJSON, CSV, JSON all generated; GeoJSON validates; CSV columns stable.
- Includes: AOI, date range, scene count, changes, areas, confidence, before/after scenes, earliest supported, pipeline, model versions, quality flags, uncalibrated disclaimer.
- Groq unavailable → report still generated (without AI narrative).

### 5.15 Security
- Upload: oversize, wrong MIME vs magic bytes, polyglot, traversal filename, zero-byte.
- CORS allows only configured origins.
- SQL injection strings in filters handled (parameterized).
- API keys absent from any response body/log/frontend bundle (bundle grep test in CI).
- Rate limit enforced per route.

## 6. API contract tests

For each endpoint in `ARCHITECTURE.md` §10: status codes, schema validation (OpenAPI), pagination, filters, error shape. Use schemathesis (optional) for fuzzing OpenAPI.

## 7. Frontend tests

| Area | Tests |
|------|-------|
| SearchBar | submit, mode buttons, parsed-filter chips editable, Groq-fallback warning shown |
| FilterPanel | AOI tools, date validation (end ≥ start), sliders update store |
| MapView | layer add/remove/toggle/opacity via mocked MapLibre; AOI draw emits geometry |
| Timeline | nodes at real dates; **gaps stay empty**; cloudy nodes dimmed; click shows date/sensor/scene/cloud/quality |
| Date semantics | legend shown; "exact date unknown" text present; supported ≠ confirmed markers |
| BeforeAfter | swipe (mouse + keyboard), side-by-side sync, opacity slider, labels |
| ChangePanel | all required fields rendered; confidence caption says uncalibrated |
| ReviewQueue | confirm/reject/flag; optimistic update; rollback on API failure |
| Assistant | send/stream/error/typing states |
| PipelineStepper | renders SSE events; failed stage shows error + suggestion; cached label |
| Error/empty states | one per API error code |
| Accessibility | `jest-axe` no violations; focus order; aria-live on progress |
| Reduced motion | with `prefers-reduced-motion` or settings toggle: no flyTo animation, no autoplay, no pulse/marching; transitions instant/opacity-only |
| Bundle | no secret keys in built assets |

## 8. E2E (Playwright) — MVP acceptance

Runs against real backend + cached real imagery; one spec per acceptance step group.

| # | Step | Assertion |
|---|------|-----------|
| 1–2 | Open map, draw AOI | AOI persisted via API |
| 3–4 | Enter NL query | parsed chips shown (Groq mocked or live) |
| 5–7 | Ingest imagery | stepper progresses through real stages; scenes/tiles exist |
| 8–9 | Retrieve | results rendered on map |
| 10–12 | Two dates → analyze | polygons rendered |
| 13–14 | Timeline | real observations; earliest supported reported |
| 15 | Before/after | swipe works |
| 16 | Explanation | Groq (mocked) text shown, or fallback |
| 17 | Review | confirm/reject persists |
| 18 | Provenance | API returns full chain |

Negative E2E: AOI with no imagery → `NO_IMAGERY` message with suggestion; Groq down → search still works.

## 9. Performance & animation testing

- Query latency, embedding throughput, ingest time, change-analysis latency (recorded by `scripts/evaluate.py`, with hardware info).
- Animation: Chrome performance trace during time-lapse, swipe drag, and polygon draw-in; long tasks <50 ms; target ~60 fps mid-range laptop.
- Verify rAF loops cancelled on unmount (no leaked listeners) via heap/listener assertions.
- Large result sets (e.g., 500 tiles) render without jank.

## 10. Evaluation (not pass/fail unit tests)

`scripts/evaluate.py` outputs a JSON + markdown report.

**Retrieval** (needs relevance judgments): Recall@K, Precision@K, MRR, latency p50/p95.
**Change** (needs labels): Precision, Recall, F1, IoU, false-positive rate. Report results **per condition** (cloud level, season gap) and state the ChangeFormer domain gap.
**System:** indexed scenes/tiles/area, index size on disk, ingest time, embedding time, avg query latency, analysis latency, hardware (CPU/GPU/RAM).

Rules: never invent values; missing labels → "N/A (no ground truth)"; record dataset, scene IDs, model checkpoint hashes, thresholds, seeds.

## 11. CI pipeline

1. Lint/type: `ruff`, `mypy`, `eslint`, `tsc --noEmit`.
2. Backend fast suite (`not slow and not network and not gpu`) with PostGIS + Redis services.
3. Frontend unit + a11y.
4. Bundle secret scan.
5. E2E on nightly (cached real fixtures).
6. Network/GPU suites manual or scheduled with secrets.

Fail build on: coverage drop >2%, any new a11y violation, any test touching live network without `@network`.

## 12. Requirement → test traceability

| Requirement | Tests |
|-------------|-------|
| FR-S1 parse | §5.2 |
| FR-S2/S3 search | §5.7, §8 |
| FR-S4 similar | §5.6, §5.7 |
| FR-I1–I6 imagery | §5.4, §5.5, §5.12 |
| FR-C1–C6 change | §5.8–5.11 |
| FR-A1–A4 analyst | §5.13, §5.14 |
| FR-U1–U5 UI | §7, §8, §9 |
| NFR security | §5.15 |
| NFR errors | §5.1, all negative tests |

## 13. Required negative-case checklist

- [ ] invalid AOI
- [ ] missing dates / inverted range
- [ ] missing satellite data (`NO_IMAGERY`)
- [ ] cloudy imagery
- [ ] duplicate scenes
- [ ] invalid coordinates
- [ ] failed Copernicus request
- [ ] failed Groq request
- [ ] missing model
- [ ] corrupted image
- [ ] empty FAISS index
- [ ] misregistered pair
- [ ] all-nodata tile
- [ ] oversized / malicious upload
- [ ] mid-ingest failure rollback

## 14. Definition of done (per phase)

- New code has unit + relevant integration tests; error paths covered.
- Phase gate in `task.md` passes from a clean checkout.
- No test relies on fabricated data presented as real.
- Coverage targets met; CI green.
- `memory.md` status log updated with test status and known gaps.
