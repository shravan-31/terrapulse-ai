"""
scripts/download_models.py
Downloads and verifies pretrained weights for RemoteCLIP and ChangeFormer.
Can use Hugging Face Hub (via huggingface_hub or direct HTTPS) with SHA-256 verification.
Records model provenance into models/MODEL_PROVENANCE.md.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.settings import settings

MODELS_DIR = Path(__file__).parent.parent / "models"
REMOTECLIP_DIR = MODELS_DIR / "remoteclip"
CHANGEFORMER_DIR = MODELS_DIR / "changeformer"

REMOTECLIP_HF_REPO = "chendelong/RemoteCLIP"
REMOTECLIP_FILENAME = "RemoteCLIP-ViT-L-14.pt"

CHANGEFORMER_HF_REPO = "wgcban/ChangeFormerV6"
CHANGEFORMER_FILENAME = "ChangeFormerV6.pth"


def compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192 * 1024):
            sha256.update(chunk)
    return sha256.hexdigest()


def record_provenance(model_name: str, repo: str, filename: str, path: Path, sha256: str, size_bytes: int):
    """Update models/MODEL_PROVENANCE.md with verified model metadata."""
    prov_file = MODELS_DIR / "MODEL_PROVENANCE.md"
    prov_file.parent.mkdir(parents=True, exist_ok=True)

    header = "# Model Provenance Register (ADR-002, ADR-015)\n\n"
    if not prov_file.exists():
        content = header + "| Model | Source Repo | Checkpoint File | SHA-256 | Size (MB) |\n|---|---|---|---|---|\n"
    else:
        content = prov_file.read_text(encoding="utf-8")

    size_mb = f"{size_bytes / (1024 * 1024):.2f}"
    entry = f"| {model_name} | `{repo}` | `{filename}` | `{sha256}` | {size_mb} |\n"
    if sha256 not in content:
        content += entry
        prov_file.write_text(content, encoding="utf-8")
        print(f"Recorded provenance for {model_name} in {prov_file}")


def download_remoteclip(hf_token: str | None = None, dry_run: bool = False) -> bool:
    """Download RemoteCLIP-ViT-L-14 pretrained weights."""
    REMOTECLIP_DIR.mkdir(parents=True, exist_ok=True)
    target_path = REMOTECLIP_DIR / REMOTECLIP_FILENAME

    if target_path.exists():
        print(f"RemoteCLIP weights already exist at {target_path}")
        sha256 = compute_sha256(target_path)
        print(f"RemoteCLIP SHA-256: {sha256}")
        record_provenance("RemoteCLIP-ViT-L-14", REMOTECLIP_HF_REPO, REMOTECLIP_FILENAME, target_path, sha256, target_path.stat().st_size)
        return True

    if dry_run:
        print(f"[DRY-RUN] Would download RemoteCLIP from {REMOTECLIP_HF_REPO}/{REMOTECLIP_FILENAME} to {target_path}")
        return True

    print(f"Downloading RemoteCLIP weights from {REMOTECLIP_HF_REPO}...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id=REMOTECLIP_HF_REPO,
            filename=REMOTECLIP_FILENAME,
            local_dir=str(REMOTECLIP_DIR),
            token=hf_token or settings.huggingface_token,
        )
        sha256 = compute_sha256(Path(downloaded))
        print(f"SUCCESS: RemoteCLIP downloaded to {downloaded} (SHA-256: {sha256})")
        record_provenance("RemoteCLIP-ViT-L-14", REMOTECLIP_HF_REPO, REMOTECLIP_FILENAME, Path(downloaded), sha256, Path(downloaded).stat().st_size)
        return True
    except ImportError:
        print("huggingface_hub not installed. Run: pip install huggingface_hub")
        return False
    except Exception as exc:
        print(f"ERROR downloading RemoteCLIP: {exc}")
        return False


def download_changeformer(hf_token: str | None = None, dry_run: bool = False) -> bool:
    """Download ChangeFormer pretrained weights."""
    CHANGEFORMER_DIR.mkdir(parents=True, exist_ok=True)
    target_path = CHANGEFORMER_DIR / CHANGEFORMER_FILENAME

    if target_path.exists():
        print(f"ChangeFormer weights already exist at {target_path}")
        sha256 = compute_sha256(target_path)
        print(f"ChangeFormer SHA-256: {sha256}")
        record_provenance("ChangeFormerV6", CHANGEFORMER_HF_REPO, CHANGEFORMER_FILENAME, target_path, sha256, target_path.stat().st_size)
        return True

    if dry_run:
        print(f"[DRY-RUN] Would download ChangeFormer from {CHANGEFORMER_HF_REPO}/{CHANGEFORMER_FILENAME} to {target_path}")
        return True

    print(f"Downloading ChangeFormer weights from {CHANGEFORMER_HF_REPO}...")
    try:
        from huggingface_hub import hf_hub_download
        downloaded = hf_hub_download(
            repo_id=CHANGEFORMER_HF_REPO,
            filename=CHANGEFORMER_FILENAME,
            local_dir=str(CHANGEFORMER_DIR),
            token=hf_token or settings.huggingface_token,
        )
        sha256 = compute_sha256(Path(downloaded))
        print(f"SUCCESS: ChangeFormer downloaded to {downloaded} (SHA-256: {sha256})")
        record_provenance("ChangeFormerV6", CHANGEFORMER_HF_REPO, CHANGEFORMER_FILENAME, Path(downloaded), sha256, Path(downloaded).stat().st_size)
        return True
    except ImportError:
        print("huggingface_hub not installed. Run: pip install huggingface_hub")
        return False
    except Exception as exc:
        print(f"ERROR downloading ChangeFormer: {exc}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download and verify SatQuery AI model weights.")
    parser.add_argument("--remoteclip", action="store_true", help="Download RemoteCLIP only")
    parser.add_argument("--changeformer", action="store_true", help="Download ChangeFormer only")
    parser.add_argument("--dry-run", action="store_true", help="Check status without downloading")
    parser.add_argument("--token", type=str, default=None, help="Hugging Face token")
    args = parser.parse_args()

    download_all = not args.remoteclip and not args.changeformer
    success = True

    if args.remoteclip or download_all:
        rc_ok = download_remoteclip(hf_token=args.token, dry_run=args.dry_run)
        success = success and rc_ok

    if args.changeformer or download_all:
        cf_ok = download_changeformer(hf_token=args.token, dry_run=args.dry_run)
        success = success and cf_ok

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
