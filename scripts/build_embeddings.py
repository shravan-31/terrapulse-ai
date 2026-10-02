"""
scripts/build_embeddings.py
Batch generates 768-dimensional vision-language embeddings for all preprocessed image tiles.
Saves vectors with stable int64 IDs ready for FAISS vector indexing.
"""

import sys
import json
from pathlib import Path
import numpy as np

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.ml.encoders import get_encoder

TILES_DIR = Path("./data/tiles")
EMB_DIR = Path("./data/embeddings")

def main():
    print("=" * 65)
    print("TerraPulse AI — Batch Tile Embedding Generator")
    print("=" * 65)

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    EMB_DIR.mkdir(parents=True, exist_ok=True)

    encoder = get_encoder()
    print(f"Loaded Encoder: {encoder.__class__.__name__} (dim={encoder.dimension})")

    tile_files = list(TILES_DIR.glob("*.png")) + list(TILES_DIR.glob("*.jpg")) + list(TILES_DIR.glob("*.tif"))
    print(f"Found {len(tile_files)} tile images in {TILES_DIR}")

    if not tile_files:
        print("No tile images found. Ingest imagery or run scripts/demo_setup.py first.")
        return

    embeddings = []
    id_map = {}

    batch_size = 8
    for i in range(0, len(tile_files), batch_size):
        batch_paths = [str(p) for p in tile_files[i:i + batch_size]]
        vecs = encoder.embed_images(batch_paths)

        for j, (p, vec) in enumerate(zip(batch_paths, vecs)):
            vector_id = i + j + 1
            embeddings.append(vec)
            id_map[str(vector_id)] = {
                "vector_id": vector_id,
                "file_path": p,
                "tile_id": Path(p).stem,
            }
        print(f"  Processed {min(i + batch_size, len(tile_files))}/{len(tile_files)} tiles...")

    emb_matrix = np.array(embeddings, dtype=np.float32)
    np.save(EMB_DIR / "tile_embeddings.npy", emb_matrix)

    with open(EMB_DIR / "id_map.json", "w", encoding="utf-8") as f:
        json.dump(id_map, f, indent=2)

    print("=" * 65)
    print(f"Saved {len(embeddings)} embeddings to {EMB_DIR / 'tile_embeddings.npy'}")
    print(f"Saved ID map to {EMB_DIR / 'id_map.json'}")
    print("STATUS: BATCH EMBEDDING COMPLETE")
    print("=" * 65)

if __name__ == "__main__":
    main()
