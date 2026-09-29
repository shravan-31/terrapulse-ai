"""
backend/app/services/copernicus_service.py
Copernicus Data Space Ecosystem (CDSE) client.

Implements ADR-009:
- Decouples catalog discovery (STAC) from download authorization.
- Separates credential presence from authentication success.
- Sentinel Hub OAuth2 token management with automatic refresh and caching.
- STAC search for Sentinel-2 L2A collections by AOI geometry, date range, and cloud cover.
- Streamed asset downloads with checksum validation, atomic write, and completion markers.
- Disk reserve budget enforcement before downloading.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import structlog

from app.core.errors import (
    NoImageryError,
    QuotaExceededError,
    ResourceLimitError,
    UnauthorizedError,
    UpstreamFailureError,
)
from app.core.settings import settings

log = structlog.get_logger("satquery.copernicus")


class CopernicusAuth:
    """Manages Sentinel Hub OAuth2 client credentials token caching and refresh."""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0

    @property
    def is_configured(self) -> bool:
        """Returns True if client credentials are present in configuration."""
        return bool(settings.copernicus_client_id and settings.copernicus_client_secret)

    async def get_token(self, client: httpx.AsyncClient | None = None) -> str:
        """
        Retrieve a valid access token. Reuses cached token if still valid.
        Raises UnauthorizedError if credentials are not configured or invalid.
        """
        now = time.time()
        # Return cached token if valid for at least another 60 seconds
        if self._token and now < (self._expires_at - 60):
            return self._token

        if not self.is_configured:
            raise UnauthorizedError()

        client_id = settings.copernicus_client_id
        client_secret = settings.copernicus_client_secret

        log.info("Requesting Copernicus OAuth2 token", url=settings.copernicus_token_url)
        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=settings.request_timeout_s)
            close_client = True

        try:
            resp = await client.post(
                settings.copernicus_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if resp.status_code == 401 or resp.status_code == 403:
                log.error("Copernicus authentication failed", status=resp.status_code)
                raise UnauthorizedError()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 60))
                raise QuotaExceededError(resource="Copernicus Auth", retry_after=retry_after)

            if resp.is_error:
                raise UpstreamFailureError(
                    service="Copernicus Auth",
                    detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )

            data = resp.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)

            if not access_token:
                raise UpstreamFailureError(
                    service="Copernicus Auth",
                    detail="No access_token found in token response",
                )

            self._token = access_token
            self._expires_at = now + float(expires_in)
            log.info("Copernicus OAuth2 token obtained", expires_in_sec=expires_in)
            return self._token

        except httpx.RequestError as exc:
            log.error("Network error during Copernicus token request", error=str(exc))
            raise UpstreamFailureError(service="Copernicus Auth", detail=str(exc)) from exc
        finally:
            if close_client:
                await client.aclose()


# Singleton auth instance
copernicus_auth = CopernicusAuth()


class CopernicusSTACClient:
    """Client for discovering Sentinel-2 L2A scenes via Copernicus STAC API."""

    def __init__(self, auth: CopernicusAuth = copernicus_auth) -> None:
        self.auth = auth
        self.stac_url = settings.copernicus_stac_url.rstrip("/")

    async def search(
        self,
        geometry: dict[str, Any],
        start_date: datetime,
        end_date: datetime,
        max_cloud_cover: float = 30.0,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search for Sentinel-2 L2A products intersecting the given GeoJSON geometry
        between start_date and end_date.

        Raises:
            NoImageryError: If no scenes match the search parameters.
            UpstreamFailureError: If Copernicus STAC returns an error or times out.
            QuotaExceededError: If rate limits are exceeded.
        """
        start_iso = start_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = end_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "collections": ["sentinel-2-l2a"],
            "intersects": geometry,
            "datetime": f"{start_iso}/{end_iso}",
            "query": {
                "eo:cloud_cover": {"lte": max_cloud_cover}
            },
            "limit": limit,
        }

        search_url = f"{self.stac_url}/search"
        log.info(
            "Searching Copernicus STAC catalog",
            url=search_url,
            start=start_iso,
            end=end_iso,
            max_cloud=max_cloud_cover,
            limit=limit,
        )

        async with httpx.AsyncClient(timeout=settings.request_timeout_s) as client:
            try:
                resp = await client.post(
                    search_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 60))
                    raise QuotaExceededError(resource="Copernicus STAC", retry_after=retry_after)

                if resp.is_error:
                    log.error(
                        "Copernicus STAC search error",
                        status=resp.status_code,
                        response=resp.text[:300],
                    )
                    raise UpstreamFailureError(
                        service="Copernicus STAC",
                        detail=f"HTTP {resp.status_code}: {resp.text[:200]}",
                    )

                result = resp.json()
                features = result.get("features", [])

                if not features:
                    raise NoImageryError(
                        message=f"No Sentinel-2 L2A scenes found between {start_iso[:10]} and {end_iso[:10]} with cloud cover <= {max_cloud_cover}%.",
                        suggestion="Try expanding the date range or increasing the cloud cover limit.",
                    )

                scenes: list[dict[str, Any]] = []
                for feat in features:
                    props = feat.get("properties", {})
                    feat_id = feat.get("id") or props.get("title") or "unknown_product"
                    dt_str = props.get("datetime") or props.get("start_datetime")
                    
                    # Parse acquisition timestamp
                    if dt_str:
                        acq_time = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    else:
                        acq_time = datetime.now(timezone.utc)

                    cloud_cover = float(props.get("eo:cloud_cover", 0.0))
                    crs_code = props.get("proj:epsg", 4326)

                    scene_info = {
                        "product_id": feat_id,
                        "provider": "copernicus",
                        "acquisition_at": acq_time.isoformat(),
                        "cloud_coverage_percent": cloud_cover,
                        "footprint": feat.get("geometry", {}),
                        "crs": f"EPSG:{crs_code}",
                        "assets": feat.get("assets", {}),
                        "metadata_json": {
                            "platform": props.get("platform", "Sentinel-2"),
                            "constellation": props.get("constellation", "Sentinel-2"),
                            "processing_baseline": props.get("s2:processing_baseline", "unknown"),
                            "orbit_number": props.get("sat:relative_orbit"),
                        },
                    }
                    scenes.append(scene_info)

                log.info("Copernicus STAC search succeeded", scenes_found=len(scenes))
                return scenes

            except httpx.RequestError as exc:
                log.error("Network error connecting to Copernicus STAC", error=str(exc))
                raise UpstreamFailureError(service="Copernicus STAC", detail=str(exc)) from exc


class CopernicusDownloadClient:
    """
    Handles streaming download of scene assets with checksums, completion markers,
    and storage reserve enforcement.
    """

    def __init__(self, auth: CopernicusAuth = copernicus_auth) -> None:
        self.auth = auth

    def _check_disk_budget(self, target_dir: Path) -> None:
        """
        Enforce disk reserve limit before starting download.
        Raises ResourceLimitError if available space is below reserve threshold.
        """
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            total, used, free = shutil.disk_usage(str(target_dir))
            free_gb = free / (1024 ** 3)
            reserve_gb = settings.free_disk_reserve_gb
            if free_gb < reserve_gb:
                log.error("Disk budget reserve breach", free_gb=round(free_gb, 2), reserve_gb=reserve_gb)
                raise ResourceLimitError(
                    resource="Free disk space",
                    limit=f"{reserve_gb} GB required, {free_gb:.2f} GB available",
                )
        except OSError as exc:
            log.warning("Could not query disk usage", error=str(exc))

    async def download_asset(
        self,
        asset_url: str,
        target_path: Path,
        expected_sha256: str | None = None,
        auth_required: bool = True,
    ) -> tuple[Path, str]:
        """
        Stream an asset to disk with atomic write, SHA-256 calculation,
        and completion marker verification.

        Returns:
            (target_path, computed_sha256)
        """
        target_path = Path(target_path).resolve()
        
        # Security: Prevent path traversal (Zip Slip / directory traversal)
        base_cache = Path(settings.cache_path).resolve()
        base_data = Path(settings.data_path).resolve()
        if not (base_cache in target_path.parents or base_data in target_path.parents):
            raise ValueError(f"Target path {target_path} is outside allowed data directories.")

        completion_marker = target_path.with_suffix(target_path.suffix + ".complete")
        
        # Idempotency / Cache Hit check
        if target_path.exists() and completion_marker.exists():
            with open(completion_marker, "r", encoding="utf-8") as f:
                saved_hash = f.read().strip()
            log.info("Asset download cache hit", path=str(target_path), sha256=saved_hash)
            return target_path, saved_hash

        self._check_disk_budget(target_path.parent)

        headers: dict[str, str] = {}
        if auth_required and self.auth.is_configured:
            token = await self.auth.get_token()
            headers["Authorization"] = f"Bearer {token}"

        temp_path = target_path.with_suffix(target_path.suffix + ".part")
        hasher = hashlib.sha256()

        log.info("Starting streamed asset download", url=asset_url, target=str(target_path))
        async with httpx.AsyncClient(timeout=settings.job_time_limit_s) as client:
            try:
                async with client.stream("GET", asset_url, headers=headers) as resp:
                    if resp.status_code == 401 or resp.status_code == 403:
                        raise UnauthorizedError()
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", 60))
                        raise QuotaExceededError(resource="Copernicus Download", retry_after=retry_after)
                    if resp.is_error:
                        raise UpstreamFailureError(
                            service="Copernicus Download",
                            detail=f"HTTP {resp.status_code} while downloading {asset_url}",
                        )

                    with open(temp_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
                            hasher.update(chunk)

                computed_hash = hasher.hexdigest()

                if expected_sha256 and computed_hash.lower() != expected_sha256.lower():
                    if temp_path.exists():
                        temp_path.unlink()
                    raise ValueError(
                        f"Checksum mismatch: expected {expected_sha256}, got {computed_hash}"
                    )

                # Atomic rename
                if target_path.exists():
                    target_path.unlink()
                temp_path.rename(target_path)

                # Write completion marker
                with open(completion_marker, "w", encoding="utf-8") as f:
                    f.write(computed_hash)

                log.info("Asset download completed", target=str(target_path), sha256=computed_hash)
                return target_path, computed_hash

            except Exception as exc:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                if isinstance(exc, (UnauthorizedError, QuotaExceededError, UpstreamFailureError, ResourceLimitError)):
                    raise
                raise UpstreamFailureError(service="Copernicus Download", detail=str(exc)) from exc
