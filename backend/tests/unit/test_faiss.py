"""
backend/tests/unit/test_faiss.py
Unit tests for the Durable FAISS vector indexing protocol (Phase 4, ADR-003, ADR-004).

Verifies:
1. Empty index queries return empty results without errors.
2. Self-search roundtrip: querying with a normalized vector returns itself as top-1 with score ≈ 1.0.
3. Stable int64 vector IDs preserved through additions and search.
4. Eligible-ID subset search (ADR-004) restricts returned candidates to allowed IDs only.
5. Durable generation commit: versioned snapshots and SHA-256 checksums written to disk.
6. Generation reload: index successfully reloads from persisted snapshot.
7. Crash recovery: falls back to previous valid generation when newest snapshot is corrupted.
8. Idempotency: re-adding an existing vector_id does not duplicate vectors.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import pytest

from app.services.faiss_service import (
    DurableIndexManager,
    FaissVectorIndex,
    NumpyVectorIndex,
    FAISS_AVAILABLE,
)


@pytest.fixture
def temp_index_dir():
    temp_dir = Path(tempfile.mkdtemp(prefix="satquery_faiss_test_"))
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def _generate_normalized_vectors(n: int, dim: int = 768, seed: int = 42) -> np.ndarray:
    rng = np.random.RandomState(seed)
    raw = rng.randn(n, dim).astype(np.float32)
    norms = np.linalg.norm(raw, axis=-1, keepdims=True)
    return raw / np.maximum(norms, 1e-12)


def test_empty_index_search():
    index_cls = FaissVectorIndex if FAISS_AVAILABLE else NumpyVectorIndex
    idx = index_cls(dimension=768)

    q = _generate_normalized_vectors(1, dim=768)[0]
    scores, ids = idx.search(q, top_k=5)
    assert len(scores) == 0
    assert len(ids) == 0


def test_add_and_search_roundtrip():
    index_cls = FaissVectorIndex if FAISS_AVAILABLE else NumpyVectorIndex
    idx = index_cls(dimension=768)

    vecs = _generate_normalized_vectors(5, dim=768)
    vector_ids = [1001, 1002, 1003, 1004, 1005]
    idx.add(vector_ids, vecs)

    assert idx.total_vectors == 5

    # Self-search for vector 1003
    scores, ids = idx.search(vecs[2], top_k=3)
    assert len(ids) >= 1
    assert ids[0] == 1003
    assert np.isclose(scores[0], 1.0, atol=1e-4)


def test_eligible_subset_search():
    index_cls = FaissVectorIndex if FAISS_AVAILABLE else NumpyVectorIndex
    idx = index_cls(dimension=768)

    vecs = _generate_normalized_vectors(10, dim=768)
    vector_ids = list(range(100, 110))
    idx.add(vector_ids, vecs)

    # Restrict search only to subset [105, 107]
    eligible = [105, 107]
    q = vecs[5]  # exact vector of 105
    scores, ids = idx.search_with_ids(q, eligible_ids=eligible, top_k=5)

    assert len(ids) <= 2
    for found_id in ids:
        assert found_id in eligible
    assert ids[0] == 105
    assert np.isclose(scores[0], 1.0, atol=1e-4)


def test_durable_generation_commit_and_reload(temp_index_dir):
    manager = DurableIndexManager(index_dir=temp_index_dir, dimension=768)
    assert manager.current_generation == 0

    vecs1 = _generate_normalized_vectors(3, dim=768, seed=1)
    gen1, sha1 = manager.commit_new_generation([10, 20, 30], vecs1)
    assert gen1 == 1
    assert manager.index.total_vectors == 3

    # Add more vectors in generation 2
    vecs2 = _generate_normalized_vectors(2, dim=768, seed=2)
    gen2, sha2 = manager.commit_new_generation([40, 50], vecs2)
    assert gen2 == 2
    assert manager.index.total_vectors == 5

    # Reload fresh manager instance from disk
    fresh_manager = DurableIndexManager(index_dir=temp_index_dir, dimension=768)
    assert fresh_manager.current_generation == 2
    assert fresh_manager.index.total_vectors == 5

    # Query loaded index
    scores, ids = fresh_manager.index.search(vecs1[0], top_k=1)
    assert ids[0] == 10


def test_idempotent_vector_addition(temp_index_dir):
    manager = DurableIndexManager(index_dir=temp_index_dir, dimension=768)
    vecs = _generate_normalized_vectors(2, dim=768)

    # First add
    manager.commit_new_generation([1, 2], vecs)
    assert manager.index.total_vectors == 2

    # Re-adding existing IDs should not create duplicates
    manager.commit_new_generation([1, 2], vecs)
    assert manager.index.total_vectors == 2


def test_crash_recovery_from_corrupt_generation(temp_index_dir):
    manager = DurableIndexManager(index_dir=temp_index_dir, dimension=768)
    vecs1 = _generate_normalized_vectors(2, dim=768, seed=10)
    manager.commit_new_generation([100, 200], vecs1)
    assert manager.current_generation == 1

    vecs2 = _generate_normalized_vectors(2, dim=768, seed=20)
    gen2, _ = manager.commit_new_generation([300, 400], vecs2)
    assert gen2 == 2

    # Simulate corrupting generation 2 artifact on disk
    ext = "faiss" if FAISS_AVAILABLE else "json"
    gen2_file = temp_index_dir / f"satquery_index_v00002.{ext}"
    gen2_file.write_text("CORRUPTED_BYTES_GARBAGE_CRASH")

    # Fresh manager should detect corruption via checksum / read error and roll back to generation 1
    recovered_manager = DurableIndexManager(index_dir=temp_index_dir, dimension=768)
    assert recovered_manager.current_generation == 1
    assert recovered_manager.index.total_vectors == 2
    assert recovered_manager.index.contains_id(100)
    assert not recovered_manager.index.contains_id(300)
