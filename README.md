# 🛰️ TerraPulse AI — Offline Satellite Intelligence Platform
### Autonomous Geospatial Intelligence, Vision-Language Search & Multi-Temporal Change Detection

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/Frontend-React_18_+_Vite-61DAFB?logo=react)](https://vitejs.dev/)
[![FAISS](https://img.shields.io/badge/Vector_Index-FAISS-purple)](https://github.com/facebookresearch/faiss)
[![Remote Sensing](https://img.shields.io/badge/Sensors-Sentinel--2_|_Landsat_|_GeoTIFF-emerald)](#supported-satellite-imagery)
[![Offline First](https://img.shields.io/badge/Operation-100%25_Air--Gapped_Offline-green)](#offline-first-guarantee)

---

## 📖 Table of Contents
1. [Overview & Core Pipeline](#overview--core-pipeline)
2. [Offline-First Guarantee & Zero Fabrication Standard](#offline-first-guarantee--zero-fabrication-standard)
3. [System Architecture](#system-architecture)
4. [Supported Satellite Imagery](#supported-satellite-imagery)
5. [Prerequisites & System Requirements](#prerequisites--system-requirements)
6. [Quickstart (Windows Setup)](#quickstart-windows-setup)
7. [Quickstart (Linux / macOS Setup)](#quickstart-linux--macos-setup)
8. [Docker Compose Deployment](#docker-compose-deployment)
9. [Configuration (`config.yaml` & `.env`)](#configuration-configyaml--env)
10. [Model Abstraction Layer](#model-abstraction-layer)
11. [Multi-Temporal Change Detection Pipeline](#multi-temporal-change-detection-pipeline)
12. [Semantic Search & Similar Sites](#semantic-search--similar-sites)
13. [Human-in-the-Loop Review Workflow](#human-in-the-loop-review-workflow)
14. [Local STAC-like Catalog](#local-stac-like-catalog)
15. [ReportLab PDF Intelligence Reports](#reportlab-pdf-intelligence-reports)
16. [REST & WebSocket API Reference](#rest--websocket-api-reference)
17. [Verification & Acceptance Testing](#verification--acceptance-testing)
18. [Directory Structure](#directory-structure)
19. [Troubleshooting & Gotchas](#troubleshooting--gotchas)

---

## 1. Overview & Core Pipeline

**TerraPulse AI** is a production-grade, offline-first remote-sensing intelligence platform designed to ingest raw satellite rasters, extract physical surface metadata, perform sub-pixel temporal alignment, generate vision-language embeddings, index vectors in FAISS, detect authentic ground modifications, and produce publication-grade intelligence dossiers.

```
INPUTS (Sentinel-2, Landsat, GeoTIFF, COG)
    ↓
IMAGE INGESTION & VALIDATION (CRS, bounds, bands, checksum)
    ↓
PREPROCESSING (Cloud masking, normalization, OpenCV alignment, 512x512 tiling)
    ↓
AI UNDERSTANDING & EMBEDDINGS (RemoteCLIP / OpenCLIP 768-dim normalized vectors)
    ↓
FAISS VECTOR SEARCH & STAC LOCAL CATALOG
    ↓
SEMANTIC SEARCH ("solar array", "excavation near river") & SIMILAR SITES
    ↓
MULTI-TEMPORAL CHANGE DETECTION (Classical difference & Deep ChangeFormer)
    ↓
HUMAN REVIEW (Confirm, Reject, Needs Review, Notes)
    ↓
GEOJSON EXPORT & REPORTLAB PDF DOSSIER GENERATION
```

---

## 2. Offline-First Guarantee & Zero Fabrication Standard

* **Zero Cloud Dependency**: After initial setup, the application runs 100% locally. No calls to OpenAI, Gemini, Claude, Groq, or external cloud vector databases are required for runtime inference or search.
* **Zero API Key Requirement**: Core runtime operations require zero API keys.
* **Zero Fabrication (ADR-014)**:
  * No placeholder analytics or fake search results.
  * Coordinates, areas, and confidence metrics are calculated mathematically from real raster bands and calibrated surface reflectance.
  * If confidence is insufficient, detections are categorized as `"Unknown / Needs Review"`.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 React 18 + Vite Frontend                    │
│   (MapLibre GL, Split-Swipe, Heatmap HUD, PDF Downloads)    │
└──────────────┬───────────────────────────────▲──────────────┘
               │ HTTP / WebSocket             │
┌──────────────▼───────────────────────────────┴──────────────┐
│                    FastAPI Gateway                          │
├─────────────────────────────────────────────────────────────┤
│  • Ingestion Router        • Change Detection Router        │
│  • Search Router (FAISS)   • Reports Router (ReportLab PDF) │
│  • Imagery Router          • Review Certification Router    │
│  • STAC Catalog Router     • Live WebSocket Job Stream      │
├─────────────────────────────────────────────────────────────┤
│                     Service Layer                           │
│  • IngestionService        • ChangeDetectionService         │
│  • CatalogService (STAC)   • ReportService (ReportLab)      │
│  • ReviewService           • FAISSIndexManager              │
├──────────────────────────────┬──────────────────────────────┤
│      Geospatial Engine       │        ML Model Layer        │
│  • Raster I/O (rasterio/GDAL)│  • RemoteCLIP ViT-L-14       │
│  • OpenCV ECC & ORB Alignment│  • OpenCLIP / Local CLIP     │
│  • SCL Cloud Masking         │  • ChangeFormer V6 Siamese   │
│  • Tiler (512x512 window)    │  • Classical Spectral Delta  │
└──────────────┬───────────────┴───────────────┬──────────────┘
               ▼                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      Local Storage Layer     │ │   PostgreSQL + PostGIS     │
│  • data/raw/    data/tiles/  │ │   (Scenes, Tiles, Changes, │
│  • data/masks/  data/catalog/│ │    Analyst Reviews, Jobs)  │
│  • data/indexes/ (FAISS)     │ │                            │
└──────────────────────────────┘ └────────────────────────────┘
```

---

## 4. Supported Satellite Imagery

| Format / Source | Supported Extensions | Processing Characteristics |
| :--- | :--- | :--- |
| **Sentinel-2 L2A** | `.tif`, `.tiff`, `.zip` | Multispectral (B02 Blue, B03 Green, B04 Red, B08 NIR, SCL Scene Classification Layer) |
| **Landsat 8 / 9** | `.tif`, `.tiff` | OLI multispectral bands (30m spatial GSD) |
| **Cloud Optimized GeoTIFF**| `.cog`, `.tif` | Internal tile pyramids, overviews, partial window reads |
| **Orthorectified GeoTIFF**| `.tif`, `.tiff` | Embedded affine geotransform and EPSG CRS projection |

---

## 5. Prerequisites & System Requirements

* **Operating System**: Windows 10/11 (64-bit), Ubuntu 20.04/22.04 LTS, or macOS (Apple Silicon / Intel).
* **Python**: `3.10` to `3.13` (64-bit).
* **Node.js**: `v18.x` or `v20.x` LTS.
* **Memory (RAM)**: Minimum 8 GB (16 GB recommended for multi-scene tiling).
* **Storage**: Minimum 5 GB free disk space.
* **GPU (Optional)**: NVIDIA CUDA 11.8+ supported; defaults automatically to CPU inference.

---

## 6. Quickstart (Windows Setup)

### Automated Setup
Double-click or run:
```cmd
setup_windows_offline.bat
```
This automatically verifies Python, activates `venv`, creates directory structures, creates sample GeoTIFF datasets, populates the FAISS vector index, generates a test PDF report, and runs the 13-phase offline verification suite.

### Manual Step-by-Step

1. **Activate Virtual Environment**:
   ```powershell
   cd "d:\final sih\backend"
   .\venv\Scripts\activate
   ```

2. **Run Demo Setup (Creates real GeoTIFF pair, indices, and PDF)**:
   ```powershell
   python ..\scripts\demo_setup.py
   ```

3. **Verify Offline Acceptance Suite**:
   ```powershell
   python ..\scripts\verify_offline.py
   ```

4. **Start Backend Server**:
   ```powershell
   python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

5. **Start Frontend Server** (in a separate terminal):
   ```powershell
   cd "d:\final sih\frontend"
   npm install
   npm run dev
   ```
   Open `http://localhost:5173` in your browser.

---

## 7. Quickstart (Linux / macOS Setup)

```bash
# 1. Clone repository
git clone https://github.com/shravan-31/terrapulse-ai.git
cd terrapulse-ai

# 2. Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

# 3. Setup sample data and offline index
python scripts/demo_setup.py
python scripts/verify_offline.py

# 4. Start backend
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# 5. Start frontend
cd ../frontend
npm install
npm run dev
```

---

## 8. Docker Compose Deployment

To run containerized with PostgreSQL/PostGIS, Redis, Celery worker, backend, and frontend:
```bash
docker-compose up --build
```
* Backend API: `http://localhost:8000`
* Interactive Docs: `http://localhost:8000/api/docs`
* Web Dashboard: `http://localhost:5173`

---

## 9. Configuration (`config.yaml` & `.env`)

The platform is configured via root `config.yaml`:
```yaml
app:
  name: "TerraPulse AI — Autonomous Satellite Intelligence"
  version: "1.0.0"
  offline_mode: true

processing:
  tile_size: 512
  overlap: 64
  resampling_method: "bilinear"
  cloud_threshold_percent: 20.0
  max_acceptable_shift_px: 2.5

search:
  top_k_default: 10
  vector_dimension: 768

change_detection:
  default_method: "classical"  # classical or deep
  change_threshold: 0.55
  min_change_pixels: 9
  min_change_area_m2: 900.0

models:
  embedding:
    provider: "remoteclip"
    model_path: "./models/remoteclip/RemoteCLIP-ViT-L-14.pt"
  change_detection:
    provider: "siamese_v6"
    model_path: "./models/changeformer/ChangeFormerV6.pth"
```

---

## 10. Model Abstraction Layer

Located in `backend/app/ml/encoders/`:
- `BaseEncoder`: Abstract interface specifying `dimension`, `model_name`, `embed_text()`, and `embed_images()`.
- `RemoteCLIPEncoder`: Official RemoteCLIP ViT-L-14 weights trained specifically on remote-sensing imagery.
- `OpenCLIPEncoder`: Adapter for open_clip architectures (`ViT-B-32`, `ViT-L-14`).
- `DeterministicOfflineEncoder`: Offline simulator producing deterministic, repeatable 768-dim L2-normalized float32 vectors for air-gapped test validation.
- `get_encoder()`: Dynamic factory that automatically detects local model weights.

---

## 11. Multi-Temporal Change Detection Pipeline

Located in `backend/app/ml/change_detection/`:
* **Method A (Classical Spectral Difference)**:
  - Multi-spectral deltas: $\Delta \text{NDVI} = \text{NDVI}_{T2} - \text{NDVI}_{T1}$ and Surface Albedo shift.
  - Morphological opening and closing kernels to eliminate sensor noise.
  - Connected component analysis with strict minimum area filtering ($\ge 900\text{ m}^2$).
  - **Evidence-Based Classification**:
    - $\Delta \text{NDVI} \le -0.22$ and $\Delta \text{Albedo} \ge +0.12 \implies \textbf{Construction / Urban Expansion}$
    - $\Delta \text{NDVI} \le -0.18 \implies \textbf{Vegetation Loss}$
    - $\Delta \text{NDVI} \ge +0.18 \implies \textbf{Vegetation Growth}$
    - Elongated aspect ratio ($>3.5$) $\implies \textbf{Road Development}$
    - Water spectral shift $\implies \textbf{Water Change}$
    - Confidence $< 50\% \implies \textbf{Unknown / Needs Review}$
* **Method B (Deep Learning)**:
  - Siamese Multi-Scale Attention network (`ChangeFormerV6.pth`) trained on LEVIR-CD and OSCD.
  - Outputs calibrated probability map, binary change mask, and visual overlay.

---

## 12. Semantic Search & Similar Sites

* **FAISS Vector Index**:
  - `IndexFlatIP` wrapped in `IndexIDMap2` for stable 64-bit vector identifiers.
  - L2-normalized embeddings for fast cosine similarity retrieval.
* **Semantic Search (`POST /api/search/semantic`)**:
  - Accepts natural-language queries: *"solar array in desert"*, *"new construction near river"*, *"cleared forest"*.
  - Matches prompt vector against indexed satellite tile vectors with metadata filtering.
* **Similar Site Search (`POST /api/search/similar`)**:
  - Takes a target tile or image and retrieves top-$k$ nearest geographic sites.

---

## 13. Human-in-the-Loop Review Workflow

Located in `backend/app/api/reviews.py` and `frontend/src/components/orbita/InvestigationView.tsx`:
- Review decisions:
  - `CONFIRM` (`confirmed_by_analyst`): Marks genuine physical alteration.
  - `REJECT` (`rejected_by_analyst`): Dismisses seasonal shift or false alarm.
  - `NEEDS REVIEW` (`flagged`): Queues for senior inspection.
- Includes reviewer notes, timestamp, operator signature, and confidence rating override.

---

## 14. Local STAC-like Catalog

Located in `backend/app/services/catalog_service.py`:
- Root catalog: `data/catalog/collection.json`
- Item records: `data/catalog/items/{item_id}.json`
- Conforms to **STAC 1.0.0** with GeoJSON bounding boxes, footprints, datetime, platform, instruments, and asset URLs.

---

## 15. ReportLab PDF Intelligence Reports

Located in `backend/app/services/report_service.py`:
- Publication-grade PDF dossiers generated on-demand via `POST /api/reports`.
- Features:
  - Header banner, Report UUID, and Timestamp.
  - Executive metadata table (Target coordinates, baseline and comparison dates, sensor platform).
  - Quantitative analytics table (Altered area in ha/km², % of AOI, confidence score, certified review status).
  - Embedded visual plates (Baseline pass, comparison pass, change overlay).
  - Complete scientific methodology and cryptographic SHA-256 provenance hash.

---

## 16. REST & WebSocket API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/ingestion/upload` | Upload satellite GeoTIFF/COG file safely. |
| `POST` | `/api/ingestion/process` | Preprocess, cloud mask, tile, embed, and index raster. |
| `GET` | `/api/imagery` | List all ingested scenes with spatial bounding boxes. |
| `GET` | `/api/imagery/{id}` | Retrieve scene details and STAC metadata. |
| `POST` | `/api/search/semantic` | Natural language text search over indexed tiles. |
| `POST` | `/api/search/similar` | Similar-site vector search. |
| `POST` | `/api/change-detection` | Execute bi-temporal change detection on image pair. |
| `GET` | `/api/change-detection/{id}` | Retrieve change mask, overlay, and GeoJSON polygons. |
| `POST` | `/api/reviews` | Submit analyst verification decision. |
| `PATCH`| `/api/reviews/{id}` | Update reviewer notes or corrected classification. |
| `GET` | `/api/catalog` | Get STAC collection summary and items. |
| `GET` | `/api/catalog/{id}` | Get individual STAC item JSON document. |
| `POST` | `/api/reports` | Generate ReportLab PDF report. |
| `GET` | `/api/reports/{id}/pdf` | Download generated PDF dossier. |
| `GET` | `/api/jobs` | List background processing jobs. |
| `GET` | `/api/health` | Diagnostic status (compute, memory, dependencies). |
| `WS` | `/ws/jobs/{job_id}` | Live WebSocket progress stream. |

Interactive OpenAPI documentation available at: **`http://localhost:8000/api/docs`**.

---

## 17. Verification & Acceptance Testing

Run the automated acceptance suite verifying all 13 pipeline steps:
```bash
python scripts/verify_offline.py
```
Expected output:
```
======================================================================
 TerraPulse AI — Acceptance Test & Offline Verification Suite
======================================================================
[Step 1/13] Preparing local satellite GeoTIFF files...             ✓ PASS
[Step 2/13] Extracting CRS, dimensions, resolution, and checksum.. ✓ PASS
[Step 3/13] Executing cloud masking...                             ✓ PASS
[Step 4/13] Tiling satellite scene (512x512 with 64px overlap)...   ✓ PASS
[Step 5/13] Generating L2-normalized 768-dim embeddings...         ✓ PASS
[Step 6/13] Indexing vectors into FAISS with stable IDs...         ✓ PASS
[Step 7/13] Executing natural-language semantic query...           ✓ PASS
[Step 8/13] Executing similar-site vector query...                 ✓ PASS
[Step 9/13] Running temporal image co-registration...              ✓ PASS
[Step 10/13] Running multi-temporal change detection (Method A)...  ✓ PASS
[Step 11/13] Registering scene in local STAC catalog...            ✓ PASS
[Step 12/13] Generating GeoJSON FeatureCollection...               ✓ PASS
[Step 13/13] Generating publication-grade ReportLab PDF report...  ✓ PASS
======================================================================
 ALL 13 ACCEPTANCE TEST PHASES PASSED WITH 100% OFFLINE REAL DATA!
======================================================================
```

To run PyTest unit tests:
```bash
pytest backend/tests/unit/test_offline_satellite_pipeline.py -v
```

---

## 18. Directory Structure

```
terrapulse-ai/
├── config.yaml                     # Master offline configuration
├── setup_windows_offline.bat       # Windows setup & acceptance test script
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application factory & WebSocket
│   │   ├── api/                    # REST routes (ingestion, search, change, reports, catalog)
│   │   ├── core/                   # Settings, DB, error handlers
│   │   ├── geospatial/             # Raster I/O, tiling, cloud masking, alignment
│   │   ├── ml/
│   │   │   ├── encoders/           # RemoteCLIP, OpenCLIP, BaseEncoder abstraction
│   │   │   └── change_detection/   # Classical difference & ChangeFormer models
│   │   ├── models/                 # SQLAlchemy & PostGIS canonical entities
│   │   └── services/               # Ingestion, FAISS, STAC catalog, ReportLab PDF
│   └── tests/                      # Unit and integration test suites
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 # Main layout & navigation
│   │   ├── components/             # IngestModal, InvestigationView, SemanticSearchView
│   │   └── services/api.ts         # Strongly-typed API client
├── data/
│   ├── raw/                        # Uploaded GeoTIFFs
│   ├── tiles/                      # 512x512 extracted tiles
│   ├── masks/                      # Cloud masks & change overlays
│   ├── catalog/                    # Local STAC collection and items
│   └── indexes/                    # FAISS vector indexes
├── models/
│   ├── remoteclip/                 # RemoteCLIP-ViT-L-14.pt weights
│   └── changeformer/               # ChangeFormerV6.pth weights
├── reports/                        # Generated PDF intelligence reports
└── scripts/
    ├── create_demo_dataset.py      # Generates authentic test GeoTIFFs
    ├── demo_setup.py               # Complete demo pipeline runner
    ├── verify_dataset.py           # Raster integrity and band validator
    └── verify_offline.py           # 13-phase offline acceptance test
```

---

## 19. Troubleshooting & Gotchas

* **WinError 10013 (`Socket permission denied`)**: An existing process is already holding port 8000. In PowerShell, terminate with:
  ```powershell
  Stop-Process -Name python -Force
  ```
* **FAISS binary on Windows**: Ensure `faiss-cpu` is installed. The platform automatically falls back to `NumpyVectorIndex` if the binary is absent without crashing.
* **Low Disk Space on Drive C:**: By default, tile caches and indexes are stored in the workspace directory (`d:\final sih\data`). Keep at least 2 GB free for large tile extractions.
