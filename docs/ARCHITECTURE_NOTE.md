# Architecture Note: TerraPulse.AI (SatQuery AI)
### Autonomous Earth Observation Intelligence & Semantic Retrieval Platform
**Problem Statement Reference: SIH 26227 / EO Archive Semantic Search & Change Detection**

---

## 1. Executive Overview & Problem Context (Background 2.1)

Modern Earth Observation (EO) archives are inundated with petabytes of multi-temporal, multi-spectral, and multi-sensor imagery (e.g., Copernicus Sentinel-2 L2A). While spatial coordinates, timestamps, and sensor filters suffice for known-target lookups, analysts routinely face discovery-oriented missions where the *exact coordinates and acquisition times are unknown*.

**TerraPulse.AI** bridges this operational gap by operationalizing recent advances in vision-language foundation models (RemoteCLIP) and transformer-based change detection (ChangeFormer V6) into an **on-premises, sovereign, network-isolated operational system**.

TerraPulse natively resolves the key challenges outlined in the specification:
1. **Semantic & Multimodal Retrieval (2.2.1)**: Natural-language free-text and image-to-image queries over satellite archives.
2. **Multi-Temporal Change Analysis (2.2.2)**: Change classification (`construction`, `clearance`, `water_variation`, `road_development`) and earliest observation estimation.
3. **False-Alarm Suppression & Quality Handling (2.2.3)**: Anti-renormalization confidence scoring, SCL masks, and registration phase correlation to reject seasonal, atmospheric, shadow, and viewing geometry artifacts.
4. **Unsupervised Discovery & Clustering (2.2.4)**: Embedding-based grouping of sites across regional AOIs to discover comparable facilities without manual query formulation.
5. **Analyst Workflow & Provenance (2.2.5)**: Review queue, confirmation/rejection audit trail, feedback loop, and immutable lineage tracking.
6. **Scale, Incremental Ingestion & Sovereignty (2.2.6 & 2.2.7)**: FAISS IndexIDMap2 vector indexing with atomic journaling, incremental addition without rebuilds, and 100% offline, on-premises operation.

---

## 2. High-Level Architecture Topology

```
                              ┌─────────────────────────────────────────┐
                              │            Analyst Browser UI           │
                              │  React 18 + TypeScript + MapLibre GL    │
                              │  (Split-Swipe, Cluster Discovery, QC)   │
                              └────────────────────┬────────────────────┘
                                                   │ HTTPS / SSE
                              ┌────────────────────▼────────────────────┐
                              │        FastAPI Gateway & Auth           │
                              │   - Structured Request Tracing (UUID)   │
                              │   - Operator Session & RBAC Middleware  │
                              └─┬──────────────┬──────────────┬─────────┘
                                │              │              │
        ┌───────────────────────┘              │              └────────────────────────┐
        ▼                                      ▼                                       ▼
┌──────────────┐                     ┌────────────────────┐                  ┌───────────────────┐
│ Search &     │                     │ Ingest & Preproc   │                  │ Change Detection  │
│ Clustering   │                     │ Engine (GDAL/SCL)  │                  │ & Temporal Engine │
└───────┬──────┘                     └─────────┬──────────┘                  └─────────┬─────────┘
        │                                      │                                       │
        ├──────────────────────┬───────────────┴──────────────┬────────────────────────┤
        ▼                      ▼                              ▼                        ▼
┌───────────────┐      ┌───────────────┐              ┌───────────────┐        ┌───────────────┐
│ RemoteCLIP    │      │ Durable FAISS │              │ ChangeFormer  │        │ PostGIS DB    │
│ ViT-L-14      │      │ IndexIDMap2   │              │ V6 Siamese    │        │ (13 Canonical │
│ (768-d Unit)  │      │ (Atomic Sync) │              │ (Hard QC)     │        │ Tables)       │
└───────────────┘      └───────────────┘              └───────────────┘        └───────────────┘
```

---

## 3. Core Capability Architectural Mapping

### 3.1 Semantic and Multimodal Retrieval (§ 2.2.1)
- **Natural Language Parsing & Embedding**: Queries such as *"newly built structures near a river"* or *"large vehicle concentrations on open ground"* are parsed via `POST /api/query/parse` and mapped to a 768-dimensional L2-normalized hypersphere vector using `RemoteCLIP-ViT-L-14`.
- **Image-to-Image Search**: `POST /api/search/image` accepts imagery tiles, applies decompression-bomb validation (max 2048x2048 px, 10MB), computes the image embedding, and searches nearest visual neighbors.
- **Eligible-ID PostGIS Pre-Filtering (ADR-004)**: Avoids disconnected search results by generating an eligible candidate set based on spatial intersection (`ST_Intersects(tiles.geom, aoi.geom)`), acquisition dates, and cloud thresholds, then executing restricted retrieval via FAISS `IDSelectorArray`.

### 3.2 Multi-Temporal Change Analysis (§ 2.2.2)
- **Siamese ChangeFormer V6 Pipeline**: Pairs of co-registered rasters ($T_1, T_2$) are fed to the dual-backbone transformer. 
- **Morphology & Connected Components**: Generates binary change masks via thresholding (default $\tau = 0.55$), opening/closing morphology, connected components extraction, and seam boundary merging.
- **Canonical Change Taxonomy**: Categorizes change into:
  - `change_type`: `construction`, `clearance`, `water_variation`, `vegetation_land_cover`, `road_development`, `unknown`.
  - `change_kind`: `appearance`, `disappearance`, `expansion`, `contraction`.
- **Earliest Supported Observation Estimation**: Walks chronological observation stacks to compute `earliest_supported_at` (first acquisition with verified change) and `confirmed_at` (subsequent verifying pass). Surfaces left-censoring flags when change preceded the search window.

### 3.3 False-Alarm Suppression & Quality Handling (§ 2.2.3)
False change driven by seasonal sun angles, cloud shadows, haze, phenology, and coregistration drift is suppressed via multi-stage gates:
1. **Scene Classification Layer (SCL) Masking**: Identifies cloud, cloud shadow, snow, and defective pixels from Sentinel-2 L2A auxiliary bands.
2. **Sub-Pixel Co-Registration Check**: Computes phase-correlation FFT translation shifts between scene pairs. Pairs with drift $>0.5$ pixels are flagged or rejected.
3. **Hard QC Eligibility Filters**: Enforces `MIN_CHANGE_PIXELS = 9` (900 m² at 10m/px GSD). Sub-threshold anomalies are strictly eliminated.
4. **Anti-Renormalization Confidence Model (ADR-013)**: Confidence combines radiometric consistency, registration accuracy, valid pixel ratio, and seasonal proximity. Missing quality variables *never* inflate confidence; they contribute zero weight and cap the final score.

### 3.4 Discovery and Clustering (§ 2.2.4)
- **Spherical K-Means Engine**: Employs spherical clustering ($k \in [2, 10]$) on 768-d unit-norm tile embeddings via `POST /api/search/clusters`.
- **Zero-Shot Semantic Anchor Classification**: Cluster centroids are automatically matched against pre-embedded domain anchors (`Built-up Infrastructure`, `Excavation & Bare Ground`, `Dense Canopy`, `Agricultural Fields`, `Water Networks`, `Transportation`) to provide descriptive natural language labels.
- **Representative Medoid Identification**: The tile closest to the cluster centroid is surfaced with full metadata, enabling analysts to discover all related sites across an entire regional AOI in one click.

### 3.5 Analyst Workflow and Provenance (§ 2.2.5)
- **Interactive Review Queue**: Analysts inspect detections via split-swipe and side-by-side comparison, reviewing spectral deltas (NDVI, NDWI, NDBI).
- **Certified Human-in-the-Loop Audit Trail**: Review actions (`confirmed_by_analyst`, `rejected_by_analyst`, `flagged`) are stamped with server-derived operator ID and immutable timestamps in `analyst_decisions`.
- **Comprehensive Lineage Tracking**: Every tile, embedding, change polygon, and report references a `provenance` record tracking parent artifacts, raw product IDs, model checkpoint hashes, and runtime parameters.

### 3.6 Scale, Incremental Ingestion and Sovereignty (§ 2.2.6 & 2.2.7)
- **Zero-Downtime Incremental Indexing**: New acquisitions are preprocessed and appended to `IndexIDMap2` with stable sequential int64 IDs. Changes are staged in `index_outbox` and committed via atomic file swaps (`.faiss` + `.sha256`).
- **Complete Air-Gapped Sovereignty**: All models (RemoteCLIP, ChangeFormer) run on local CPU/GPU hardware. No external cloud inference or commercial APIs are required during evaluation.
