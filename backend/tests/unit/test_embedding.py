"""
backend/tests/unit/test_embedding.py
Unit tests for the RemoteCLIP and EmbeddingModel interfaces (Phase 4, ADR-003).

Verifies:
1. Dimensionality: strict 768-d float32 vectors.
2. L2-normalization: unit Euclidean length (norm ≈ 1.0).
3. Finiteness: no NaN or Inf values.
4. Determinism: identical inputs in eval mode produce identical embeddings.
5. Error handling: missing model weights raise ModelMissingError.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.core.errors import ModelMissingError
from app.services.embedding_service import (
    DeterministicMockEmbeddingModel,
    RemoteCLIPAdapter,
    _normalize_l2,
)


def test_l2_normalization_helper():
    raw = np.array([[3.0, 4.0], [1.0, 1.0]], dtype=np.float32)
    normed = _normalize_l2(raw)
    norms = np.linalg.norm(normed, axis=-1)
    np.testing.assert_allclose(norms, [1.0, 1.0], rtol=1e-5)


def test_mock_embedding_dimension_and_dtype():
    model = DeterministicMockEmbeddingModel(dimension=768)
    texts = ["dense forest in rural area", "industrial warehouse construction"]
    vectors = model.embed_text(texts)

    assert vectors.shape == (2, 768)
    assert vectors.dtype == np.float32
    assert np.all(np.isfinite(vectors))


def test_mock_embedding_l2_normalized():
    model = DeterministicMockEmbeddingModel(dimension=768)
    vectors = model.embed_text(["solar panel farm near lake", "river flood plain"])
    norms = np.linalg.norm(vectors, axis=-1)
    np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-5)


def test_mock_embedding_eval_determinism():
    model = DeterministicMockEmbeddingModel(dimension=768)
    prompt = "urban expansion and new roads"
    v1 = model.embed_text([prompt])
    v2 = model.embed_text([prompt])
    np.testing.assert_array_equal(v1, v2)


def test_mock_embedding_empty_input():
    model = DeterministicMockEmbeddingModel(dimension=768)
    vectors = model.embed_text([])
    assert vectors.shape == (0, 768)


def test_mock_embedding_images_dimension():
    model = DeterministicMockEmbeddingModel(dimension=768)
    fake_img1 = np.zeros((256, 256, 3), dtype=np.uint8)
    fake_img2 = np.ones((256, 256, 3), dtype=np.uint8) * 128
    vectors = model.embed_images([fake_img1, fake_img2])

    assert vectors.shape == (2, 768)
    assert vectors.dtype == np.float32
    norms = np.linalg.norm(vectors, axis=-1)
    np.testing.assert_allclose(norms, [1.0, 1.0], atol=1e-5)


def test_remoteclip_missing_file_raises_model_missing():
    adapter = RemoteCLIPAdapter(model_path="nonexistent_checkpoint_file.pt")
    with pytest.raises(ModelMissingError) as exc_info:
        adapter.embed_text(["test prompt"])
    assert "missing" in str(exc_info.value.error).lower() or "not found" in str(exc_info.value.error).lower()
