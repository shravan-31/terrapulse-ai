"""
backend/tests/unit/test_clustering.py
Unit tests for Unsupervised Site Discovery and Spherical K-Means Clustering (SIH 26227 § 2.2.4).
"""

import pytest
import numpy as np
from app.services.clustering_service import spherical_kmeans, ClusteringService


def test_spherical_kmeans_convergence():
    """Verify that spherical k-means partitions normalized vectors properly."""
    np.random.seed(42)
    # Generate 3 distinct clusters on unit sphere in 768 dimensions
    d = 768
    c1 = np.random.randn(d)
    c1 /= np.linalg.norm(c1)

    c2 = np.random.randn(d)
    c2 /= np.linalg.norm(c2)

    c3 = np.random.randn(d)
    c3 /= np.linalg.norm(c3)

    # 10 points around c1, 10 around c2, 10 around c3
    pts1 = c1 + 0.05 * np.random.randn(10, d)
    pts2 = c2 + 0.05 * np.random.randn(10, d)
    pts3 = c3 + 0.05 * np.random.randn(10, d)

    pts = np.vstack([pts1, pts2, pts3]).astype(np.float32)
    pts /= np.linalg.norm(pts, axis=1, keepdims=True)

    centroids, labels = spherical_kmeans(pts, k=3, max_iter=20, random_seed=42)

    assert len(centroids) == 3
    assert len(labels) == 30
    assert len(set(labels)) == 3

    # Check that points from same group predominantly get assigned the same label
    assert len(set(labels[0:10])) == 1
    assert len(set(labels[10:20])) == 1
    assert len(set(labels[20:30])) == 1


@pytest.mark.asyncio
async def test_clustering_service_fallback():
    """Verify ClusteringService provides deterministic clusters when DB has no vectors."""
    service = ClusteringService(db=None)
    res = await service.cluster_tiles(aoi_id=None, k_clusters=3, min_cluster_size=1)

    assert "clusters" in res
    assert res["clusters_formed"] > 0
    assert res["total_tiles_clustered"] > 0

    first_cluster = res["clusters"][0]
    assert "label" in first_cluster
    assert "tile_count" in first_cluster
    assert "representative_tile" in first_cluster
    assert "cohesion_score" in first_cluster
    assert len(first_cluster["members"]) > 0
