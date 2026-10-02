"""
backend/app/ml/change_detection/deep_detector.py
Deep-learning based change detection method (Method B).
Supports ChangeFormerV6 and Siamese Multi-Scale Attention neural networks.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, List
import cv2
import numpy as np
import structlog

from app.core.settings import settings
from app.ml.change_detection.base_detector import (
    BaseChangeDetector,
    ChangeComponent,
    ChangeDetectionResult,
)
from app.ml.change_detection.classical_detector import ClassicalSpectralChangeDetector

log = structlog.get_logger("satquery.ml.deep_change")


class DeepLearningChangeDetector(BaseChangeDetector):
    """Method B: Deep learning based change detection using Siamese/ChangeFormer architecture."""

    def __init__(
        self,
        checkpoint_path: str | Path | None = None,
        device: str = "cpu",
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path or settings.changeformer_checkpoint_path)
        self.device = device or settings.device
        self._model: Any = None
        self._fallback = ClassicalSpectralChangeDetector()

    @property
    def algorithm_name(self) -> str:
        return "Deep Siamese ChangeFormer V6 (Multi-Scale Feature Attention)"

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        if not self.checkpoint_path.exists():
            log.warning("ChangeFormer checkpoint file not found, will use verified classical fallback", path=str(self.checkpoint_path))
            return

        try:
            import torch
            checkpoint = torch.load(str(self.checkpoint_path), map_location="cpu")
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint and checkpoint["state_dict"]:
                try:
                    from scripts.train_change_detection import SiameseChangeDetector
                    net = SiameseChangeDetector(in_channels=3, num_classes=2, base_dim=32)
                    net.load_state_dict(checkpoint["state_dict"], strict=False)
                    net.eval()
                    self._model = net
                    log.info("Deep ChangeFormer Siamese network loaded into memory", device=self.device)
                except Exception as exc:
                    log.warning("Could not construct Siamese network class, using state_dict fallback", error=str(exc))
                    self._model = checkpoint
            else:
                self._model = checkpoint
        except Exception as exc:
            log.warning("Deep model loading failed, falling back to classical method", error=str(exc))

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
        self._ensure_loaded()

        # If neural network model is loaded and callable
        if self._model is not None and hasattr(self._model, "forward") and callable(self._model):
            try:
                import torch

                h = min(t1_image.shape[0], t2_image.shape[0])
                w = min(t1_image.shape[1], t2_image.shape[1])
                t1_crop = t1_image[:h, :w].astype(np.float32) / 255.0
                t2_crop = t2_image[:h, :w].astype(np.float32) / 255.0

                t1_tensor = torch.from_numpy(t1_crop).permute(2, 0, 1).unsqueeze(0)
                t2_tensor = torch.from_numpy(t2_crop).permute(2, 0, 1).unsqueeze(0)

                with torch.no_grad():
                    logits = self._model(t1_tensor, t2_tensor)
                    probs = torch.softmax(logits, dim=1)[0, 1].cpu().numpy()

                raw_mask = (probs >= threshold).astype(np.uint8)

                # Morphology and components
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                cleaned_mask = cv2.morphologyEx(raw_mask, cv2.MORPH_OPEN, kernel)
                cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel)

                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned_mask, connectivity=8)
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

                    comp_prob = float(np.mean(probs[comp_mask]))
                    polygon = self._fallback._mask_to_geojson_polygon(comp_mask, geotransform, h, w)

                    components.append(
                        ChangeComponent(
                            polygon=polygon,
                            bbox_pixel=bbox,
                            pixel_count=pixel_count,
                            area_m2=round(area_m2, 2),
                            confidence=round(min(0.98, max(0.50, comp_prob)), 3),
                            change_type="construction" if comp_prob > 0.70 else "urban expansion",
                            spectral_delta={"deep_prob": round(comp_prob, 4)},
                        )
                    )

                # Overlay
                overlay_rgb = (t2_crop * 255.0).astype(np.uint8)
                overlay_rgba = cv2.cvtColor(overlay_rgb, cv2.COLOR_RGB2RGBA)
                overlay_rgba[final_mask, 0] = 255
                overlay_rgba[final_mask, 1] = 45
                overlay_rgba[final_mask, 2] = 85
                overlay_rgba[final_mask, 3] = 220

                total_aoi_m2 = float(h * w * pixel_area_m2)
                total_change_m2 = float(np.sum(final_mask) * pixel_area_m2)
                pct_change = round((total_change_m2 / max(1.0, total_aoi_m2)) * 100.0, 2)

                overall_conf = float(np.mean([c.confidence for c in components])) if components else 0.0

                return ChangeDetectionResult(
                    before_image=(t1_crop * 255.0).astype(np.uint8),
                    after_image=(t2_crop * 255.0).astype(np.uint8),
                    change_mask=final_mask,
                    change_overlay=overlay_rgba,
                    components=components,
                    total_change_area_m2=round(total_change_m2, 2),
                    total_aoi_area_m2=round(total_aoi_m2, 2),
                    percentage_change=pct_change,
                    primary_change_type="construction" if pct_change > 0 else "Unknown / Needs Review",
                    overall_confidence=round(overall_conf, 3),
                    methodology=self.algorithm_name,
                    parameters={
                        "threshold": threshold,
                        "min_area_m2": min_area_m2,
                        "checkpoint": str(self.checkpoint_path.name),
                    },
                )
            except Exception as exc:
                log.warning("Neural inference failed, executing verified classical detector", error=str(exc))

        # Fallback to classical detector with honest provenance
        result = self._fallback.detect_changes(
            t1_image=t1_image,
            t2_image=t2_image,
            pixel_resolution_m=pixel_resolution_m,
            threshold=threshold,
            min_area_m2=min_area_m2,
            geotransform=geotransform,
            crs_epsg=crs_epsg,
        )
        return result
