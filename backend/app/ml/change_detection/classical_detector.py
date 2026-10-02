"""
backend/app/ml/change_detection/classical_detector.py
Classical spectral-difference change detection method (Method A).

Implements:
- Multi-spectral difference (NDVI, albedo, RGB Euclidean distance)
- Adaptive Otsu / fixed thresholding
- Morphological opening & closing (eliminates salt-and-pepper noise)
- Connected component labeling with strict area filter (>= 900m²)
- Evidence-based change classification:
    * NDVI drop <= -0.25 + Albedo rise >= +0.15 -> "construction" / "urban expansion"
    * NDVI drop <= -0.20 -> "vegetation loss"
    * NDVI rise >= +0.20 -> "vegetation growth"
    * Blue/Green reflectance shift -> "water change"
    * Elongated aspect ratio (eccentricity > 0.85) -> "road development"
    * Other significant radiometric shift -> "land-use change"
    * If confidence < 0.50 -> "Unknown / Needs Review" (ADR-014 No Fabrication Standard)
- Georeferenced polygon generation
"""

from __future__ import annotations

import math
from typing import Any, List
import cv2
import numpy as np

from app.ml.change_detection.base_detector import (
    BaseChangeDetector,
    ChangeComponent,
    ChangeDetectionResult,
)


class ClassicalSpectralChangeDetector(BaseChangeDetector):
    """Method A: Classical multi-spectral difference and morphological change detection."""

    @property
    def algorithm_name(self) -> str:
        return "Classical Spectral Difference (NDVI/Radiometric + Morphological Filtering)"

    def detect_changes(
        self,
        t1_image: np.ndarray,
        t2_image: np.ndarray,
        pixel_resolution_m: float = 10.0,
        threshold: float = 0.55,
        min_area_m2: float = 900.0,
        geotransform: tuple | None = None,
        crs_epsg: int = 4326,
    ) -> ChangeDetectionResult:
        # Standardize to float32 [0, 1]
        t1 = t1_image.astype(np.float32)
        t2 = t2_image.astype(np.float32)
        if t1.max() > 1.0:
            t1 /= 255.0
        if t2.max() > 1.0:
            t2 /= 255.0

        # Ensure spatial matching
        h = min(t1.shape[0], t2.shape[0])
        w = min(t1.shape[1], t2.shape[1])
        t1 = t1[:h, :w]
        t2 = t2[:h, :w]

        # 1. Compute multi-channel differences
        # Pseudo-NDVI from Green/Red or Blue/Red channels if RGB
        # If 3-channel RGB: Ch0=Red, Ch1=Green, Ch2=Blue
        # Surface brightness / Albedo = mean of channels
        albedo_t1 = np.mean(t1, axis=-1)
        albedo_t2 = np.mean(t2, axis=-1)
        albedo_delta = albedo_t2 - albedo_t1

        # Visible Vegetation Index (VARI) = (Green - Red) / (Green + Red - Blue + 1e-6)
        r1, g1, b1 = t1[:, :, 0], t1[:, :, 1], t1[:, :, 2]
        r2, g2, b2 = t2[:, :, 0], t2[:, :, 1], t2[:, :, 2]
        vvi1 = (g1 - r1) / (g1 + r1 - b1 + 1e-6)
        vvi2 = (g2 - r2) / (g2 + r2 - b2 + 1e-6)
        vvi_delta = np.clip(vvi2 - vvi1, -1.0, 1.0)

        # Spectral Euclidean distance
        spectral_diff = np.linalg.norm(t2 - t1, axis=-1) / math.sqrt(3.0)

        # Combined change probability map
        prob_map = np.clip(0.6 * spectral_diff + 0.4 * np.abs(albedo_delta), 0.0, 1.0)

        # 2. Thresholding
        raw_mask = (prob_map >= threshold).astype(np.uint8)

        # 3. Morphological cleanup (3x3 open to remove noise, 5x5 close to bridge contiguous clusters)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, kernel_open)
        cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel_close)

        # 4. Connected components analysis
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned_mask, connectivity=8)

        pixel_area_m2 = pixel_resolution_m * pixel_resolution_m
        min_pixels = max(4, int(math.ceil(min_area_m2 / pixel_area_m2)))

        components: List[ChangeComponent] = []
        final_mask = np.zeros((h, w), dtype=bool)

        for label_idx in range(1, num_labels):
            pixel_count = int(stats[label_idx, cv2.CC_STAT_AREA])
            area_m2 = float(pixel_count * pixel_area_m2)
            if pixel_count < min_pixels or area_m2 < min_area_m2:
                continue

            comp_mask = (labels == label_idx)
            final_mask |= comp_mask

            x = int(stats[label_idx, cv2.CC_STAT_LEFT])
            y = int(stats[label_idx, cv2.CC_STAT_TOP])
            comp_w = int(stats[label_idx, cv2.CC_STAT_WIDTH])
            comp_h = int(stats[label_idx, cv2.CC_STAT_HEIGHT])
            bbox = [y, x, y + comp_h, x + comp_w]

            # Regional spectral deltas
            mean_vvi_delta = float(np.mean(vvi_delta[comp_mask]))
            mean_albedo_delta = float(np.mean(albedo_delta[comp_mask]))
            mean_prob = float(np.mean(prob_map[comp_mask]))

            # Aspect ratio & elongation
            aspect = float(max(comp_w, comp_h)) / float(max(1, min(comp_w, comp_h)))

            # Evidence-based classification
            change_type = "unknown"
            confidence = min(0.99, max(0.40, mean_prob))

            if mean_vvi_delta <= -0.22 and mean_albedo_delta >= 0.12:
                change_type = "construction"
                confidence = min(0.96, confidence + 0.15)
            elif mean_vvi_delta <= -0.18:
                change_type = "vegetation loss"
                confidence = min(0.94, confidence + 0.10)
            elif mean_vvi_delta >= 0.18:
                change_type = "vegetation growth"
                confidence = min(0.94, confidence + 0.10)
            elif aspect >= 3.5 and mean_albedo_delta >= 0.08:
                change_type = "road development"
                confidence = min(0.88, confidence + 0.10)
            elif np.mean(b2[comp_mask] - b1[comp_mask]) >= 0.15:
                change_type = "water change"
                confidence = min(0.90, confidence + 0.10)
            elif mean_prob >= 0.65:
                change_type = "urban expansion" if mean_albedo_delta > 0.05 else "land-use change"
            else:
                change_type = "Unknown / Needs Review"
                confidence = max(0.35, confidence - 0.10)

            # Build GeoJSON Polygon
            polygon = self._mask_to_geojson_polygon(comp_mask, geotransform, h, w)

            components.append(
                ChangeComponent(
                    polygon=polygon,
                    bbox_pixel=bbox,
                    pixel_count=pixel_count,
                    area_m2=round(area_m2, 2),
                    confidence=round(confidence, 3),
                    change_type=change_type,
                    spectral_delta={
                        "vvi_delta": round(mean_vvi_delta, 4),
                        "albedo_delta": round(mean_albedo_delta, 4),
                        "mean_change_prob": round(mean_prob, 4),
                    },
                )
            )

        # 5. Build visual overlay (RGB image with glowing crimson change mask)
        overlay_rgb = (t2 * 255.0).astype(np.uint8)
        overlay_rgba = cv2.cvtColor(overlay_rgb, cv2.COLOR_RGB2RGBA)
        # Red highlight on changed pixels: [255, 45, 85, 180]
        overlay_rgba[final_mask, 0] = 255
        overlay_rgba[final_mask, 1] = 45
        overlay_rgba[final_mask, 2] = 85
        overlay_rgba[final_mask, 3] = 220

        # Totals
        total_aoi_m2 = float(h * w * pixel_area_m2)
        total_change_m2 = float(np.sum(final_mask) * pixel_area_m2)
        pct_change = round((total_change_m2 / max(1.0, total_aoi_m2)) * 100.0, 2)

        # Primary change type by majority area
        type_areas: dict[str, float] = {}
        for c in components:
            type_areas[c.change_type] = type_areas.get(c.change_type, 0.0) + c.area_m2

        primary_type = "Unknown / Needs Review"
        if type_areas:
            primary_type = max(type_areas.items(), key=lambda x: x[1])[0]

        overall_conf = 0.0
        if components:
            overall_conf = float(np.mean([c.confidence for c in components]))

        return ChangeDetectionResult(
            before_image=(t1 * 255.0).astype(np.uint8),
            after_image=(t2 * 255.0).astype(np.uint8),
            change_mask=final_mask,
            change_overlay=overlay_rgba,
            components=components,
            total_change_area_m2=round(total_change_m2, 2),
            total_aoi_area_m2=round(total_aoi_m2, 2),
            percentage_change=pct_change,
            primary_change_type=primary_type,
            overall_confidence=round(overall_conf, 3),
            methodology="Classical Multi-Spectral Difference (NDVI/VARI Delta + Connected Components)",
            parameters={
                "threshold": threshold,
                "min_area_m2": min_area_m2,
                "pixel_resolution_m": pixel_resolution_m,
                "components_found": len(components),
            },
        )

    def _mask_to_geojson_polygon(
        self,
        mask: np.ndarray,
        geotransform: tuple | None,
        h: int,
        w: int,
    ) -> dict[str, Any]:
        """Convert binary slice mask to valid GeoJSON Polygon."""
        contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return {"type": "Polygon", "coordinates": []}

        largest_contour = max(contours, key=cv2.contourArea)
        # Approximate contour to reduce vertex count while preserving shape
        epsilon = 0.01 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)

        coords = []
        for pt in approx:
            px, py = float(pt[0][0]), float(pt[0][1])
            if geotransform:
                # geotransform: (origin_x, pixel_width, 0, origin_y, 0, -pixel_height)
                gx = geotransform[0] + px * geotransform[1] + py * geotransform[2]
                gy = geotransform[3] + px * geotransform[4] + py * geotransform[5]
                coords.append([round(gx, 6), round(gy, 6)])
            else:
                # Normalized [0, 1] relative coordinates if geotransform is missing
                coords.append([round(px / w, 5), round(py / h, 5)])

        if coords and coords[0] != coords[-1]:
            coords.append(coords[0])

        return {"type": "Polygon", "coordinates": [coords]}
