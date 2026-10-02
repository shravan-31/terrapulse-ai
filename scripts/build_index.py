"""
scripts/build_index.py
Builds and persists the local FAISS IndexIDMap2 vector index (Section 17).
Maintains persistent stable mapping: FAISS vector ID <-> database tile ID.
"""

import sys
import json
from pathlib import Path
import numpy as np

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.faiss_service import get_index_manager

EMB_DIR = Path("./data/embeddings")
INDEX_DIR = Path("./data/indexes")

def main():
    print("=" * 65)
    print("TerraPulse AI — Persistent FAISS Index Builder")
    print("=" * 65)

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    index_mgr = get_index_manager()

    emb_file = EMB_DIR / "tile_embeddings.npy"
    id_map_file = EMB_DIR / "id_map.json"

    if not emb_file.exists() or not id_map_file.exists():
        print(f"Embedding file not found at {emb_file}.")
        print("Run scripts/build_embeddings.py or scripts/demo_setup.py first.")
        return

    vectors = np.load(emb_file)
    with open(id_map_file, "r", encoding="utf-8") as f:
        id_map = json.load(f)

    vector_ids = [int(k) for k in id_map.keys()]
    print(f"Loaded {len(vectors)} vectors with shape {vectors.shape}")

    # L2-normalize vectors
    norms = np.linalg.norm(vectors, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized_vectors = (vectors / norms).astype(np.float32)

    # Add to FAISS index
    index_mgr.index.add(vector_ids=vector_ids, vectors=normalized_vectors)
    print(f"Added {len(vector_ids)} vectors to {index_mgr.index.__class__.__name__}")

    # Save to disk
    snapshot_path = str(INDEX_DIR / "image.index")
    index_mgr.index.save(snapshot_path)
    print(f"Saved FAISS index to {snapshot_path}")

    # Save metadata
    meta = {
        "total_vectors": index_mgr.index.total_vectors,
        "dimension": index_mgr.index.dimension,
        "index_type": "IndexFlatIP",
        "snapshot_path": snapshot_path,
    }
    with open(INDEX_DIR / "faiss_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    with open(INDEX_DIR / "id_map.json", "w", encoding="utf-8") as f:
        json.dump(id_map, f, indent=2)

    print("=" * 65)
    print(f"STATUS: FAISS VECTOR INDEX BUILT & PERSISTED (Vectors: {index_mgr.index.total_vectors})")
    print("=" * 65)

if __name__ == "__main__":
    main()
