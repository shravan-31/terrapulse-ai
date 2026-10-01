# Model & Dataset Provenance Register
### TerraPulse.AI Compliance & Lineage Declaration (SIH 26227 § 2.2.7 & 2.3)

---

## 1. Declarative Statement of Compliance

In accordance with SIH 26227 § 2.2.7:
1. **Public & Verified Models Only**: All pretrained models used in TerraPulse.AI originate from publicly accessible academic repositories. Licences, checkpoint identifiers, and cryptographic hashes are formally declared below.
2. **Public Imagery Only**: All evaluation and demonstration imagery consists solely of publicly available open-access datasets (Copernicus Sentinel-2 L2A) and organiser-supplied test rasters. No classified, operational, or proprietary commercial imagery is included.
3. **Air-Gapped Execution**: All weights and datasets are packaged for 100% on-premises execution with network connectivity disabled.

---

## 2. Pretrained Models Register

| Model Identifier | Primary Task | Source Repository / Author | Licence | Checkpoint File | Embedding Dim / Output | Checkpoint SHA-256 Hash |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **RemoteCLIP-ViT-L-14** | Multimodal Vision-Language Tile & Text Embeddings | `chendelong/RemoteCLIP` (Delong Chen et al., IEEE TGRS) | CC-BY-NC-SA 4.0 / Academic Open | `RemoteCLIP-ViT-L-14.pt` | 768-d unit-normalized float32 vector | `fcc2a7e21e171f4ffcb7a9c0206b8b74ac0c9eb83c67b576958b7a4ed6c8cecb` |
| **ChangeFormer V6** | Siamese Transformer-based Change Detection | `wgcban/ChangeFormer` (Bandara & Patel, IEEE CVPR/GRSL) | MIT Licence | `ChangeFormerV6.pth` | Binary change logit map ($256\times256$) | `d979335bc19ea38232d820493fb85b9cb9e0fed8bc7734d3a2a299d4b454e415` |
| **Deterministic Mock Adapter** | Unit Testing & Minimal-Resource Fallback | Internal / TerraPulse (`backend/app/services/`) | MIT Licence | Embedded in codebase | 768-d unit vector / deterministic mask | N/A (Source Verified) |

---

## 3. Remote Sensing Datasets Register

| Dataset Name | Providing Agency | Product Type | Spatial Resolution | Bands Utilized | Licence & Access Terms |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Copernicus Sentinel-2 L2A** | European Space Agency (ESA) / European Commission | Bottom-Of-Atmosphere (BOA) Surface Reflectance | 10m (B02, B03, B04, B08), 20m (B05-B07, B11, B12, SCL) | RGB (B04, B03, B02), NIR (B08), SWIR (B11), SCL (Scene Classification) | Open Access (Creative Commons / Legal Notice on the use of Copernicus Sentinel Data) |
| **Organiser-Supplied GeoTIFF/COG** | Competition Evaluation Benchmarks | Analysis-Ready COG | 10m – 30m GSD | Calibrated Reflectance / Display RGB | Organiser Competition Open Dataset |

---

## 4. Offline Packaging & Air-Gapped Staging Instructions

To stage all models and datasets locally prior to severing network connectivity:

### 1. Download Model Weights
```bash
python scripts/download_models.py
```
This utility:
- Connects to Hugging Face Hub over secure TLS.
- Downloads `RemoteCLIP-ViT-L-14.pt` (approx. 1.2 GB) and `ChangeFormerV6.pth` (approx. 165 MB).
- Computes SHA-256 signatures and verifies bit-for-bit authenticity against the registry.
- Stores weights in `models/remoteclip/` and `models/changeformer/`.

### 2. Verify Air-Gapped Readiness
Ensure `.env` or system environment has:
```env
APP_ENV=production
DATA_MODE=offline
DEVICE=cpu              # or 'cuda' if local NVIDIA GPU present
REMOTECLIP_MODEL_PATH=models/remoteclip/RemoteCLIP-ViT-L-14.pt
CHANGEFORMER_CHECKPOINT_PATH=models/changeformer/ChangeFormerV6.pth
```
Sever network connectivity and execute the doctor script to verify 100% offline capability:
```bash
python scripts/doctor.py
```
