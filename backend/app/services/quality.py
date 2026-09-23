"""影像质量综合评分：噪声水平、层厚不均、伪影比例。

所有指标只基于体素数据与可选的层厚元信息计算，与 DICOM/NIfTI 解析、
ROI 分析、窗宽窗位等既有流程完全解耦。
"""
import math
from typing import List, Optional

import numpy as np
from scipy.ndimage import binary_erosion, gaussian_filter, median_filter, sobel


class QualityComputeError(Exception):
    """影像数据缺失或无法算出质量结论时抛出。"""


def _to_volume(volume) -> np.ndarray:
    if volume is None:
        raise QualityComputeError("影像体素数据缺失，无法计算质量指标")
    try:
        vol = np.asarray(volume, dtype=np.float32)
    except (TypeError, ValueError) as exc:
        raise QualityComputeError(f"体素数据格式无法解析：{exc}")
    if vol.ndim != 3:
        raise QualityComputeError(
            f"体素数据不是三维数组（当前维度为 {vol.ndim}），无法计算质量指标"
        )
    if vol.size == 0 or np.prod(vol.shape) < 27:
        raise QualityComputeError("影像体素数量过少，无法估计质量指标")
    if not np.isfinite(vol).all():
        raise QualityComputeError("影像中存在缺失值(NaN/Inf)，无法计算质量指标")
    return vol


def estimate_noise_hu(vol: np.ndarray, body: np.ndarray) -> float:
    """组织区内"体素-局部3x3x3中值"残差的稳健尺度(MAD)，近似加性噪声标准差(HU)。"""
    tissue = binary_erosion(body & (vol < 200), iterations=1)
    if int(tissue.sum()) < 30:
        raise QualityComputeError("有效组织体素过少，无法估计噪声水平")
    residual = vol - median_filter(vol, size=3)
    rt = residual[tissue]
    mad = float(np.median(np.abs(rt - np.median(rt))))
    noise = 1.4826 * mad
    if noise <= 0:
        raise QualityComputeError("噪声尺度估计为 0，数据可能经过平滑或为常量")
    return float(noise)


def _edge_map(sl2d: np.ndarray, body2d: np.ndarray) -> np.ndarray:
    edges = np.hypot(sobel(sl2d, 0), sobel(sl2d, 1))
    edges[~binary_erosion(body2d, iterations=1)] = 0
    return edges


def _phase_correlation_shift(a: np.ndarray, b: np.ndarray, max_shift: int = 6):
    """返回两幅边缘图的最佳整数位移 (dy, dx) 与相位相关峰值。"""
    fa, fb = np.fft.fft2(a), np.fft.fft2(b)
    cps = fa * np.conj(fb)
    mag = np.abs(cps)
    mag[mag == 0] = 1.0
    corr = np.fft.ifft2(cps / mag).real
    h, w = corr.shape
    cy, cx = h // 2, w // 2
    window = np.roll(np.roll(corr, cy, axis=0), cx, axis=1)[
        cy - max_shift:cy + max_shift + 1, cx - max_shift:cx + max_shift + 1
    ]
    iy, ix = np.unravel_index(int(np.argmax(window)), window.shape)
    return iy - max_shift, ix - max_shift, float(window[iy, ix])


def estimate_artifacts(vol: np.ndarray, body: np.ndarray, noise_hu: float):
    """返回 (伪影比例%, 明细)。

    伪影比例由两部分合成：
    - spikeRatio：明显偏离局部中值的体素（金属/拉链等硬伪影），放大到百分比量纲；
    - motionRatio：相邻轴位层间出现孤立突变位移的层数占比（运动伪影边界）。
    """
    residual = np.abs(vol - median_filter(vol, size=3))
    spikes = body & (residual > max(6.0 * noise_hu, 120.0))
    spike_ratio = int(spikes.sum()) / max(int(body.sum()), 1)

    smoothed = gaussian_filter(vol, (0, 2, 2))
    d = vol.shape[0]
    magnitudes = np.zeros(d)
    peaks = np.zeros(d)
    boundaries: List[int] = []

    for z in range(1, d):
        overlap = body[z] & body[z - 1]
        if int(overlap.sum()) < 80:
            continue
        a = _edge_map(smoothed[z], body[z])
        b = _edge_map(smoothed[z - 1], body[z - 1])
        if a.sum() < 1 or b.sum() < 1:
            continue
        dy, dx, pk = _phase_correlation_shift(a, b)
        magnitudes[z] = math.hypot(dy, dx)
        peaks[z] = pk

    strong = (magnitudes >= 2.0) & (peaks > 0.5)
    motion_count = 0
    for z in range(1, d):
        # 真实运动表现为孤立的单帧位移跳变（两侧层位移归零），
        # 头颅两端形态收窄等连续变化不会被计为运动。
        if strong[z] and magnitudes[z - 1] < 2.0 and (z == d - 1 or magnitudes[z + 1] < 2.0):
            motion_count += 1
            boundaries.append(int(z))

    motion_ratio = motion_count / max(d - 1, 1)
    artifact_ratio = min(1.0, 10.0 * spike_ratio + motion_ratio)
    return artifact_ratio * 100.0, {
        "spikeRatio": round(spike_ratio * 100.0, 3),
        "motionBoundarySlices": boundaries,
    }


def estimate_thickness_cv(slice_thicknesses: Optional[List[float]]) -> Optional[float]:
    """层厚变异系数 CV%。无层厚元信息时返回 None（该项判为数据不足，不参与扣分）。"""
    if not slice_thicknesses:
        return None
    try:
        t = np.asarray(slice_thicknesses, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    t = t[np.isfinite(t)]
    if t.size < 2 or float(np.mean(t)) <= 0:
        return None
    return float(np.std(t) / np.mean(t) * 100.0)


def compute_quality_metrics(volume, slice_thicknesses: Optional[List[float]] = None) -> dict:
    """计算三项原始质量指标，不做阈值判定。"""
    vol = _to_volume(volume)
    body = vol > -500
    if int(body.sum()) < 100:
        raise QualityComputeError("影像中未检出有效扫描区域，可能为全空数据")

    noise_hu = estimate_noise_hu(vol, body)
    artifact_ratio, artifact_detail = estimate_artifacts(vol, body, noise_hu)
    thickness_cv = estimate_thickness_cv(slice_thicknesses)

    return {
        "noiseLevelHu": round(noise_hu, 2),
        "thicknessCvPercent": round(thickness_cv, 2) if thickness_cv is not None else None,
        "artifactRatioPercent": round(artifact_ratio, 2),
        "details": {
            "voxelCount": int(vol.size),
            **artifact_detail,
        },
    }
