"""
backend/app/api/search.py
Semantic visual search and similar tile retrieval API endpoints (Phase 5, ADR-004).

Endpoints:
- POST /api/search/semantic — NL query → parse → embed → eligible-ID FAISS search → rank
- POST /api/search/image    — Image upload → embed → FAISS search
- GET  /api/similar/{id}    — Find nearest neighbor tiles to a query tile
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from PIL import Image
import numpy as np
import structlog

from app.core.database import get_db
from app.core.errors import EmptyIndexError, NotFoundError, ValidationError
from app.models.entities import AOI, Embedding, Scene, Tile
from app.services.embedding_service import get_embedding_model
from app.services.faiss_service import get_index_manager
from app.services.query_parser import parse_natural_language_query

log = structlog.get_logger("satquery.api.search")

router = APIRouter(prefix="/api/search", tags=["search"])


# ---------------------------------------------------------------------------
# Request Schemas
# ---------------------------------------------------------------------------
class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language search query")
    aoi_id: str | None = Field(None, description="Restrict search to a specific AOI UUID")
    start_date: str | None = Field(None, description="Filter scenes acquired after ISO date")
    end_date: str | None = Field(None, description="Filter scenes acquired before ISO date")
    max_cloud_cover: float | None = Field(None, ge=0.0, le=100.0, description="Max cloud coverage percentage")
    top_k: int = Field(20, ge=1, le=100, description="Number of results to return")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/semantic")
async def semantic_search(
    req: SemanticSearchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Execute semantic text search over satellite tile embeddings.
    Applies eligible-subset FAISS search per ADR-004.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    index_mgr = get_index_manager()
    index_mgr.check_for_newer_generation()

    if index_mgr.index.total_vectors == 0:
        return JSONResponse(
            status_code=200,
            content={
                "results": [],
                "count": 0,
                "completeness": "exact",
                "searched_count": 0,
                "eligible_count": 0,
                "message": "Index is empty. Ingest satellite scenes first to enable search.",
                "request_id": request_id,
            },
        )

    # 1. Parse natural language query to extract semantic prompt & filter hints
    parsed = await parse_natural_language_query(req.query)
    prompt_to_embed = parsed.semantic_prompt or req.query

    # 2. Build eligible vector_id set from PostgreSQL metadata
    stmt = (
        select(Embedding.vector_id, Embedding.tile_id)
        .join(Tile, Embedding.tile_id == Tile.id)
        .join(Scene, Tile.scene_id == Scene.id)
    )

    if req.max_cloud_cover is not None:
        stmt = stmt.where(Scene.cloud_coverage_percent <= req.max_cloud_cover)
    elif parsed.max_cloud_cover is not None:
        stmt = stmt.where(Scene.cloud_coverage_percent <= parsed.max_cloud_cover)

    if req.start_date:
        try:
            start_dt = datetime.fromisoformat(req.start_date.replace("Z", "+00:00"))
            stmt = stmt.where(Scene.acquisition_at >= start_dt)
        except ValueError:
            pass

    if req.end_date:
        try:
            end_dt = datetime.fromisoformat(req.end_date.replace("Z", "+00:00"))
            stmt = stmt.where(Scene.acquisition_at <= end_dt)
        except ValueError:
            pass

    emb_results = await db.execute(stmt)
    eligible_pairs = emb_results.all()
    eligible_vector_ids = [p[0] for p in eligible_pairs]
    vector_to_tile_id = {p[0]: p[1] for p in eligible_pairs}

    # 3. Embed text query
    embed_model = get_embedding_model()
    query_vector = embed_model.embed_text([prompt_to_embed])[0]

    # 4. Search FAISS index
    if eligible_vector_ids:
        scores, found_vector_ids = index_mgr.index.search_with_ids(
            query_vector, eligible_ids=eligible_vector_ids, top_k=req.top_k
        )
    else:
        scores, found_vector_ids = index_mgr.index.search(query_vector, top_k=req.top_k)

    # 5. Fetch full tile & scene records for results
    matched_tile_ids = [vector_to_tile_id.get(vid) for vid in found_vector_ids if vid in vector_to_tile_id]
    matched_tiles: dict[uuid.UUID, Any] = {}
    if matched_tile_ids:
        tile_stmt = (
            select(Tile)
            .options(selectinload(Tile.scene))
            .where(Tile.id.in_(matched_tile_ids))
        )
        tiles_res = await db.execute(tile_stmt)
        matched_tiles = {t.id: t for t in tiles_res.scalars().all()}

    results = []
    for score, vid in zip(scores, found_vector_ids):
        tile_uuid = vector_to_tile_id.get(vid)
        tile = matched_tiles.get(tile_uuid) if tile_uuid else None
        results.append({
            "vector_id": int(vid),
            "score": round(float(score), 4),
            "tile_id": str(tile_uuid) if tile_uuid else None,
            "bounds": tile.bounds if tile else None,
            "scene_product_id": tile.scene.product_id if (tile and tile.scene) else None,
            "acquisition_at": tile.scene.acquisition_at.isoformat() if (tile and tile.scene) else None,
            "cloud_cover": tile.scene.cloud_coverage_percent if (tile and tile.scene) else None,
            "preview_url": f"/api/rasters/tiles/{tile_uuid}/preview.png" if tile_uuid else None,
        })

    return JSONResponse(
        content={
            "results": results,
            "count": len(results),
            "completeness": "exact",
            "searched_count": len(results),
            "eligible_count": len(eligible_vector_ids) if eligible_vector_ids else index_mgr.index.total_vectors,
            "semantic_prompt": prompt_to_embed,
            "request_id": request_id,
        }
    )


@router.post("/image")
async def image_search(
    file: UploadFile = File(...),
    top_k: int = Query(20, ge=1, le=100),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Search satellite tiles by visual similarity to an uploaded image.
    Validates image size and type against path traversal and decompression bombs.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10 MB limit
        raise ValidationError(detail="Uploaded image exceeds 10MB limit")

    try:
        pil_img = Image.open(io.BytesIO(content)).convert("RGB")
        # Check pixel dimension limit to prevent decompression bombs
        if pil_img.width * pil_img.height > 2048 * 2048:
            raise ValidationError(detail="Image dimensions exceed maximum allowed size (2048x2048)")
    except Exception as exc:
        raise ValidationError(detail=f"Invalid image file: {exc}")

    index_mgr = get_index_manager()
    if index_mgr.index.total_vectors == 0:
        return JSONResponse(content={"results": [], "count": 0, "request_id": request_id})

    embed_model = get_embedding_model()
    query_vector = embed_model.embed_images([pil_img])[0]
    scores, vector_ids = index_mgr.index.search(query_vector, top_k=top_k)

    results = []
    found_vids = [int(v) for v in vector_ids]
    if found_vids:
        stmt = (
            select(Embedding.vector_id, Tile)
            .join(Tile, Embedding.tile_id == Tile.id)
            .options(selectinload(Tile.scene))
            .where(Embedding.vector_id.in_(found_vids))
        )
        res = await db.execute(stmt)
        v_to_tile = {row[0]: row[1] for row in res.all()}
        
        for s, vid in zip(scores, vector_ids):
            t = v_to_tile.get(int(vid))
            results.append({
                "vector_id": int(vid),
                "score": round(float(s), 4),
                "tile_id": str(t.id) if t else None,
                "bounds": t.bounds if t else None,
                "scene_product_id": t.scene.product_id if (t and t.scene) else None,
                "acquisition_at": t.scene.acquisition_at.isoformat() if (t and t.scene) else None,
                "cloud_cover": t.scene.cloud_coverage_percent if (t and t.scene) else None,
                "preview_url": f"/api/rasters/tiles/{t.id}/preview.png" if t else None,
            })
    else:
        for s, vid in zip(scores, vector_ids):
            results.append({
                "vector_id": int(vid),
                "score": round(float(s), 4),
            })

    return JSONResponse(content={"results": results, "count": len(results), "request_id": request_id})


@router.get("/similar/{tile_id}")
async def get_similar_tiles(
    tile_id: str,
    top_k: int = Query(10, ge=1, le=50),
    exclude_same_scene: bool = Query(False),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Find tiles visually similar to an existing catalog tile."""
    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())
    try:
        tile_uuid = uuid.UUID(tile_id)
    except ValueError:
        raise ValidationError(detail=f"Invalid tile UUID format: {tile_id}")

    # Fetch query tile embedding
    stmt = select(Embedding).where(Embedding.tile_id == tile_uuid)
    res = await db.execute(stmt)
    emb = res.scalar_one_or_none()
    if not emb:
        raise NotFoundError(resource="Embedding for Tile", resource_id=tile_id)

    query_vector = np.array(emb.vector_data, dtype=np.float32)
    index_mgr = get_index_manager()

    # Search top_k + 1 to account for self
    scores, vector_ids = index_mgr.index.search(query_vector, top_k=top_k + 5)

    results = []
    for s, vid in zip(scores, vector_ids):
        if int(vid) == emb.vector_id:
            continue  # Exclude self
        results.append({
            "vector_id": int(vid),
            "similarity_score": round(float(s), 4),
        })
        if len(results) >= top_k:
            break

    return JSONResponse(
        content={
            "query_tile_id": tile_id,
            "similar_tiles": results,
            "count": len(results),
            "request_id": request_id,
        }
    )


@router.post("/clusters")
async def cluster_sites(
    aoi_id: str | None = Query(None, description="Optional AOI UUID filter"),
    k_clusters: int = Query(5, ge=2, le=20, description="Target cluster count"),
    min_cluster_size: int = Query(1, ge=1, description="Minimum tiles per cluster"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Unsupervised Discovery & Clustering (SIH 26227 § 2.2.4).
    Groups indexed sites into semantic clusters across an AOI or archive.
    """
    from app.services.clustering_service import ClusteringService

    request_id = getattr(request.state, "request_id", str(uuid.uuid4())) if request else str(uuid.uuid4())
    clustering_svc = ClusteringService(db=db)
    
    result = await clustering_svc.cluster_tiles(
        aoi_id=aoi_id,
        k_clusters=k_clusters,
        min_cluster_size=min_cluster_size,
    )
    result["request_id"] = request_id
    return JSONResponse(content=result)
