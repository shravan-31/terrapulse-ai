# Procedure: Index Build & Incremental Ingestion
### TerraPulse.AI Operational Manual (SIH 26227 § 2.2.6 & 2.3)

---

## 1. Overview & Invariants

This operational document details the procedure for building the baseline semantic vector index and incrementally ingesting newly acquired satellite scenes into TerraPulse.AI without requiring a full index rebuild.

### Key Operational Guarantees (ADR-003, ADR-004):
1. **Incremental by Construction**: Newly acquired imagery tiles are assigned monotonically increasing, stable `int64` vector IDs. Existing IDs, embeddings, and distances remain strictly immutable.
2. **Crash Resilience & Atomic Commits**: Index modifications follow a write-ahead outbox protocol (`index_outbox` table). Checkpointed snapshots (`.faiss` + `.sha256`) are saved atomically via temporary file rename.
3. **Sovereign Air-Gapped Ingestion**: Ingests standard GeoTIFF or Cloud Optimized GeoTIFF (COG) packages directly from local disk or staged directories without external network dependencies.

---

## 2. Prerequisites & Environment Setup

### 2.1 File System Hierarchy
Ensure the following directories exist in the operational workspace:
```
data/
  ├── scenes/       # Raw or staged Copernicus GeoTIFF/COG products
  ├── rasters/      # Normalized reflectance and display PNG assets
indexes/
  ├── faiss/        # Active FAISS IndexIDMap2 snapshot and checksum
  └── current_generation.json
models/
  ├── remoteclip/   # RemoteCLIP-ViT-L-14.pt weights
  └── changeformer/ # ChangeFormerV6.pth weights
```

### 2.2 Model Weights Verification
Before indexing, verify that pretrained model weights are staged locally and their SHA-256 signatures match:
```bash
python scripts/download_models.py --verify-only
```

---

## 3. Baseline Index Build Procedure

### Step 1: Stage Baseline Imagery
Place target GeoTIFF or COG archives into the local ingestion drop zone:
```bash
cp /staged_data/S2A_MSIL2A_2026*.SAFE data/scenes/
```

### Step 2: Initialize Database Migrations
Apply the canonical schema and PostGIS geometry extensions:
```bash
python scripts/migrate.py
```

### Step 3: Execute Baseline Ingestion & Vector Index Generation
Run the ingestion worker or invoke the ingest API for the baseline AOI:
```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "aoi_id": "00000000-0000-0000-0000-000000000001",
    "start_date": "2025-01-01T00:00:00Z",
    "end_date": "2025-06-30T23:59:59Z",
    "max_cloud_cover": 20.0,
    "max_scenes": 20
  }'
```

#### Under the Hood:
1. **CRS Normalization**: Rasters are reprojected to the target UTM zone (WGS84).
2. **Quality Masking**: SCL mask separates valid pixels from cloud/shadow/snow.
3. **Deterministic Tiling**: 256x256 pixel non-overlapping tiles are generated.
4. **Feature Extraction**: RemoteCLIP encodes each tile into a 768-d L2-normalized vector.
5. **Atomic Index Creation**:
   - Outbox records created with status `pending`.
   - `IndexWriter` adds vectors into `IndexIDMap2` with stable IDs.
   - Atomically writes `indexes/faiss/generation_0001.faiss` and its `.sha256`.
   - Records generation in PostgreSQL and points `current_generation.json`.

---

## 4. Incremental Ingestion Procedure (Zero-Downtime)

When a newly acquired satellite pass arrives (e.g., Sentinel-2 pass acquired today):

### Step 1: Stage New Acquisition
Drop the new GeoTIFF / COG product into `data/scenes/`.

### Step 2: Trigger Incremental Ingestion
Call `POST /api/ingest` targeting the specific acquisition window:
```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "aoi_id": "00000000-0000-0000-0000-000000000001",
    "start_date": "2026-10-01T00:00:00Z",
    "end_date": "2026-10-01T23:59:59Z",
    "max_cloud_cover": 15.0
  }'
```

### Step 3: Fenced Append & Generation Roll
1. The server extracts and normalizes the new scene tiles.
2. Embeddings are generated and appended strictly to the pending outbox queue.
3. The `IndexWriter` locks the index journal:
   - Fetches the current total count $N$.
   - Appends $M$ new vectors with IDs $[N+1, \dots, N+M]$.
   - Writes new snapshot `generation_{GEN+1}.faiss.tmp`.
   - Verifies SHA-256 checksum and atomically moves to `generation_{GEN+1}.faiss`.
   - Updates `indexes/current_generation.json`.
4. Live queries continue running on `generation_{GEN}` without interruption or locks. Active readers detect the generation bump via file watch and hot-swap to `generation_{GEN+1}` in $<5$ ms.

---

## 5. Verification & Health Audit

Verify index integrity and retrieval latency:
```bash
python scripts/evaluate.py
```
Expected output:
- **Vector Dimension**: Exactly 768 float32.
- **Index Type**: `IndexFlatIP` wrapped in `IndexIDMap2`.
- **Search Latency**: $p50 < 2\text{ ms}$, $p95 < 5\text{ ms}$ over 10,000 indexed tiles.
- **Checksum Verification**: Valid cryptographic match between index file and stored hash.
