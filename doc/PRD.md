# PRD — SIH 26227 Satellite Intelligence Platform

**Problem statement:** Semantic Retrieval and Multi-Temporal Change Analysis of Satellite Imagery
**Version:** 0.1 (online-first prototype) · **Status:** Draft

---

## 1. Summary

A map-centric web platform that lets analysts (a) find satellite imagery using natural language or an example image,
and (b) detect, verify and date land-surface changes across multiple observations, with full provenance and analyst review.

## 2. Problem

Analysts reviewing satellite archives face three issues:
1. Finding relevant imagery by manual browsing or coordinates is slow; semantic ("newly built structures near a river") search is missing.
2. Automated change detection produces many false alarms (clouds, shadows, seasons, misregistration).
3. Results are hard to trust and audit: unclear when a change first appeared, which scenes were used, and which model produced it.

## 3. Goals

| ID | Goal |
|----|------|
| G1 | Semantic text-to-image and image-to-image retrieval over tiled satellite imagery |
| G2 | Multi-temporal change detection over an AOI using all usable observations, not just first vs last |
| G3 | Report the **earliest supported observation** of each change, honestly distinguished from confirmed date and exact event date |
| G4 | Suppress false changes and expose a transparent (uncalibrated) system confidence with quality flags |
| G5 | Interactive before/after evidence on a map |
| G6 | Analyst review loop (confirm / reject / flag / notes) |
| G7 | End-to-end provenance for every result |
| G8 | Incremental ingestion without rebuilding the vector index |
| G9 | Modular design so an offline build can be packaged later |

## 4. Non-goals (initial release)

- Training or fine-tuning RemoteCLIP, ChangeFormer or any LLM.
- Full offline packaging (interfaces prepared only).
- Real-time / near-real-time streaming ingestion.
- Claiming calibrated probabilities or benchmark accuracy on Sentinel-2 without measured evaluation.
- Fabricated/demo satellite data.
- Multi-tenant auth and enterprise RBAC (single analyst identity acceptable for MVP).

## 5. Users

| Persona | Needs |
|---------|-------|
| **Imagery analyst** (primary) | Fast retrieval, trustworthy change evidence, ability to accept/reject |
| **Team lead / reviewer** | Reports, audit trail, summary counts |
| **Developer / evaluator** | Reproducible pipeline, metrics, clear docs |

## 6. User stories

1. As an analyst, I draw an AOI and type "new construction near rivers after 2022" and see ranked tiles on the map.
2. I upload a reference image and find visually similar sites.
3. I pick or auto-select two dates and see change polygons with before/after evidence.
4. I see when the change was first supported by data and when it was confirmed, and that the exact date is unknown.
5. I understand why a change was flagged (quality flags, indices, AI explanation).
6. I confirm, reject or flag each change and add notes.
7. I export a report (PDF/GeoJSON/CSV/JSON).
8. I trace any result to source scenes, model versions and parameters.
9. I add new imagery and it becomes searchable without a full re-index.

## 7. Functional requirements

### Search
- **FR-S1** NL query parsed by Groq into a Pydantic-validated schema; failures fall back to raw-text search with a warning.
- **FR-S2** Text embedding via RemoteCLIP → FAISS top-K → PostGIS spatial/temporal/sensor/cloud filters → ranking.
- **FR-S3** Image upload search (validated type, size, safe filename).
- **FR-S4** Similar-site discovery from a selected tile; optional DBSCAN/KMeans clustering.

### Imagery
- **FR-I1** Copernicus Data Space scene search by AOI/date/cloud; metadata preserved (scene ID, datetime, sensor, bands, CRS, resolution, bbox, cloud, source ref).
- **FR-I2** Local cache prevents repeated downloads.
- **FR-I3** Preprocessing: CRS normalization, reprojection, resampling, clipping, nodata, cloud/shadow masking where available, normalization, quality scoring, co-registration checks.
- **FR-I4** Fixed-size tiling (`TILE_SIZE`), tile metadata in PostGIS.
- **FR-I5** Incremental ingest (`POST /api/ingest`): validate → preprocess → tile → embed → `faiss.add()` → PostGIS insert.
- **FR-I6** If imagery is unavailable, return structured `NO_IMAGERY` error. Never fabricate.

### Change analysis
- **FR-C1** Pretrained ChangeFormer inference on before/after pairs; probability map → threshold → morphology → connected components → min-area → polygons → GeoJSON → PostGIS.
- **FR-C2** Automatic image-pair selection using cloud %, valid pixels, temporal distance, overlap, registration, season similarity, sensor compatibility, quality.
- **FR-C3** Multi-temporal walk producing `earliest_supported_date`, `confirmed_date`, latest observation, before/after scenes.
- **FR-C4** Categories: construction, construction expansion, clearance, road development, water variation, vegetation/land-cover change, unknown — assigned via NDVI/NDWI/NDBI + geometry + temporal pattern + retrieval (+ optional Groq explanation).
- **FR-C5** Appearance / disappearance / expansion / contraction reported per change.
- **FR-C6** System confidence + quality flags; labeled uncalibrated.

### Analyst workflow
- **FR-A1** Review queue (Pending → Review → Confirm/Reject/Flag) with notes; every decision persisted with analyst id and timestamp.
- **FR-A2** Groq assistant answers questions using only structured results (never raw rasters).
- **FR-A3** Reports: PDF, GeoJSON, CSV, JSON.
- **FR-A4** Provenance API per analysis.

### UI
- **FR-U1** Map-centric layout; AOI drawing (rectangle/polygon/circle).
- **FR-U2** Timeline of real observations only; details on click; time-lapse playback.
- **FR-U3** Before/after: side-by-side, swipe, opacity.
- **FR-U4** Change detail panel; layer toggles (search, before/after, change, AOI, similar, heatmap, NDVI/NDWI/NDBI).
- **FR-U5** Animated pipeline progress driven by real job events; reduced-motion support (see `design.md`).

## 8. Non-functional requirements

| Area | Requirement |
|------|-------------|
| Correctness | No fabricated data, dates, coordinates, scores |
| Reliability | Core pipeline works if Groq is down; graceful Copernicus failures |
| Performance | Semantic query latency measured and reported; UI target 60 fps for animations |
| Security | Secrets backend-only (MapTiler restricted key excepted), CORS, validation, upload limits, rate limiting, structured logs |
| Errors | Structured error `{error, code, suggestion}`, no stack traces to users |
| Portability | Runs via Docker Compose (DB/Redis) + local GPU/CPU ML; CUDA auto-detect |
| Modularity | Interfaces for imagery source, LLM, map provider |
| Accessibility | Reduced-motion, keyboard nav, focus rings, aria-live for progress |
| Reproducibility | Versions, parameters and model provenance stored |

## 9. Success metrics

Measured, never invented:
- Retrieval: Recall@K, Precision@K, MRR (if judgments), query latency.
- Change: Precision, Recall, F1, IoU, FPR where labeled data exists.
- System: indexed scenes/tiles/area, index size, ingest time, embedding time, change-analysis latency, hardware.
- Product: all 18 MVP acceptance steps pass with real data.

## 10. MVP acceptance (real data only)

1 open map · 2 select AOI · 3 NL query · 4 Groq → filters · 5 Copernicus imagery · 6 preprocess · 7 RemoteCLIP embeddings ·
8 FAISS retrieval · 9 results on map · 10 choose two dates · 11 ChangeFormer · 12 polygons on map · 13 timeline ·
14 earliest supported observation · 15 before/after · 16 Groq explanation · 17 confirm/reject · 18 provenance stored.

## 11. Constraints & assumptions

- Sentinel-2 (~10 m) limits detectable change size; small structures may be missed.
- Not every year/season has a usable scene; timeline reflects actual availability.
- Pretrained ChangeFormer has a **domain gap** (trained on other data/resolutions); results must be treated as candidates.
- Online services: Groq, Copernicus, MapTiler. Local: RemoteCLIP, ChangeFormer, FAISS, PostGIS, Redis.

## 12. Risks

| Risk | Mitigation |
|------|-----------|
| ChangeFormer domain gap on Sentinel-2 | Multi-temporal confirmation, QC scoring, analyst review, measured evaluation, disclosure |
| Cloud/seasonal false alarms | Pair selection, masks, season similarity, temporal consistency |
| Copernicus quota/latency | Cache, background jobs, retry with backoff |
| Registration errors | Registration validation; warn or reject pairs |
| LLM hallucination | Groq only for parsing/explaining structured data; schema validation |
| GPU unavailable | CPU fallback; document expected latency |
| Large downloads | Area-limited requests, tile cache, disk budget checks |

## 13. Release plan

Phases 0–12 as listed in `task.md`. MVP = Phases 0–7 + 10 (minimum path), full = all phases.

## 14. Out of scope / future

Offline packaging (local COG archive, local LLM, local map tiles), SAR (Sentinel-1) change fusion beyond basics, fine-tuning on labeled Indian imagery, user auth/RBAC, alerting.

## 15. Open questions

- Which pilot AOIs and date ranges will be used for demo and evaluation?
- Is labeled change data available for evaluation?
- GPU spec available for demo hardware?
- Preferred report template/branding?
