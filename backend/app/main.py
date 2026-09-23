import random, math
from typing import Optional
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Medical Imaging Viewer")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class VolumeRequest(BaseModel):
    preset: str = "brain"  # brain / chest / abdomen
    width: int = 64
    height: int = 64
    depth: int = 64


class ROIRequest(BaseModel):
    center: list = [32, 32, 32]
    radius: int = 10
    label: str = "lesion"


class WindowLevelRequest(BaseModel):
    window: float = 400.0
    level: float = 40.0
    preset: str = "brain"


WINDOW_PRESETS = {
    "lung":     {"window": 1500, "level": -600, "desc": "肺窗 (W1500/L-600)"},
    "mediastinum": {"window": 350, "level": 50, "desc": "纵隔窗 (W350/L50)"},
    "bone":     {"window": 2000, "level": 300, "desc": "骨窗 (W2000/L300)"},
    "brain":    {"window": 80, "level": 40, "desc": "脑窗 (W80/L40)"},
    "abdomen":  {"window": 400, "level": 40, "desc": "腹窗 (W400/L40)"},
}


def generate_volume(preset: str, w: int, h: int, d: int):
    """Generate synthetic CT-like volume"""
    np.random.seed(42)
    vol = np.zeros((d, h, w), dtype=np.float32)

    center_x, center_y, center_z = w//2, h//2, d//2
    for z in range(d):
        for y in range(h):
            for x in range(w):
                # Head-like shape
                rx = (x - center_x - 5) / (w * 0.4)
                ry = (y - center_y) / (h * 0.45)
                rz = (z - center_z + 3) / (d * 0.4)
                dist = math.sqrt(rx**2 + ry**2 + rz**2)

                if preset == "brain":
                    if dist < 0.85:
                        # Brain tissue
                        base = 35
                        # Sulci pattern
                        noise = (np.sin(x * 0.4) * np.cos(y * 0.3) + np.sin(z * 0.35)) * 8
                        # Ventricles (CSF)
                        vent_dist = math.sqrt(((x-center_x+2)/(w*0.15))**2 + ((y-center_y)/(h*0.12))**2 + ((z-center_z)/(d*0.1))**2)
                        if vent_dist < 0.6:
                            base = 10 + noise * 0.3
                        # Skull
                        if dist > 0.7 and dist < 0.85:
                            base = 200 + random.uniform(-20, 20)
                        vol[z, y, x] = base + noise
                    elif dist < 0.9:
                        vol[z, y, x] = 100  # Scalp
                elif preset == "chest":
                    # Body oval
                    bx = (x - center_x) / (w * 0.35)
                    by = (y - center_y) / (h * 0.4)
                    body = math.sqrt(bx**2 + by**2)
                    if body < 1.0:
                        # Lungs (dark)
                        lung_dist1 = math.sqrt(((x-center_x+8)/(w*0.12))**2 + ((y-center_y)/(h*0.13))**2)
                        lung_dist2 = math.sqrt(((x-center_x-8)/(w*0.12))**2 + ((y-center_y)/(h*0.13))**2)
                        if lung_dist1 < 0.7 or lung_dist2 < 0.7:
                            vol[z, y, x] = -650 + np.sin(z*0.3)*30
                        else:
                            vol[z, y, x] = 30 + np.random.uniform(-5, 5)
                        # Spine
                        if abs(x - center_x) < 3 and abs(y - center_y + 8) < 4:
                            vol[z, y, x] = 250
                    vol[z, y, x] += np.random.uniform(-3, 3)
                elif preset == "abdomen":
                    bx = (x - center_x) / (w * 0.33)
                    by = (y - center_y) / (h * 0.4)
                    body = math.sqrt(bx**2 + by**2)
                    if body < 1.0:
                        base = 35
                        # Liver (right upper)
                        lv = math.sqrt(((x-center_x-6)/(w*0.08))**2 + ((y-center_y+4)/(h*0.07))**2)
                        if lv < 0.6:
                            base = 55 + np.random.uniform(-5, 5)
                        # Kidneys
                        kd1 = math.sqrt(((x-center_x-5)/(w*0.04))**2 + ((y-center_y-5)/(h*0.04))**2)
                        kd2 = math.sqrt(((x-center_x+5)/(w*0.04))**2 + ((y-center_y-5)/(h*0.04))**2)
                        if kd1 < 0.4 or kd2 < 0.4:
                            base = 45
                        # Spine
                        if abs(x - center_x) < 3 and abs(y - center_y + 7) < 4:
                            base = 250 + np.random.uniform(-10, 10)
                        vol[z, y, x] = base + np.random.uniform(-9, 9)

    return vol.tolist()


@app.post("/api/volume")
def get_volume(req: VolumeRequest):
    vol = generate_volume(req.preset, req.width, req.height, req.depth)

    # Extract mid slices for MPR
    mid_axial = int(req.depth // 2)
    mid_coronal = int(req.height // 2)
    mid_sagittal = int(req.width // 2)

    # Return: 3D volume + 3 MPR slices
    return {
        "volume": vol,
        "dimensions": [req.depth, req.height, req.width],
        "mpr": {
            "axial": vol[mid_axial],
            "coronal": [[vol[z][mid_coronal][x] for x in range(req.width)] for z in range(req.depth)],
            "sagittal": [[vol[z][y][mid_sagittal] for y in range(req.height)] for z in range(req.depth)]
        },
        "preset": req.preset,
        "windowPresets": WINDOW_PRESETS
    }


class ROIAnalyzeRequest(BaseModel):
    volume: list
    rois: list = []


@app.post("/api/roi")
def analyze_roi(req: ROIAnalyzeRequest):
    results = []
    for roi in req.rois:
        center = roi.get("center", [32, 32, 32])
        radius = roi.get("radius", 8)
        label = roi.get("label", "roi")

        # Extract voxels within sphere
        voxels = []
        try:
            vol = np.array(req.volume)
            d, h, w = vol.shape
            for z in range(max(0, center[2]-radius), min(d, center[2]+radius+1)):
                for y in range(max(0, center[1]-radius), min(h, center[1]+radius+1)):
                    for x in range(max(0, center[0]-radius), min(w, center[0]+radius+1)):
                        if math.sqrt((x-center[0])**2 + (y-center[1])**2 + (z-center[2])**2) <= radius:
                            voxels.append(float(vol[z, y, x]))
        except:
            voxels = []

        if voxels:
            arr = np.array(voxels)
            results.append({
                "label": label,
                "center": center,
                "radius": radius,
                "mean": round(float(np.mean(arr)), 2),
                "std": round(float(np.std(arr)), 2),
                "min": round(float(np.min(arr)), 2),
                "max": round(float(np.max(arr)), 2),
                "voxelCount": len(voxels),
                "histogram": np.histogram(arr, bins=10, range=(float(np.min(arr)), float(np.max(arr))))[0].tolist()
            })

    return {"rois": results}


@app.get("/api/windows")
def get_windows():
    return {"presets": WINDOW_PRESETS}


class QualityRequest(BaseModel):
    volume: Optional[list] = None
    preset: str = "brain"


def _smooth3(v: np.ndarray) -> np.ndarray:
    """3-point moving average along each axis (numpy only)."""
    s = v.astype(np.float32)
    for ax in range(3):
        s = (np.roll(s, 1, axis=ax) + s + np.roll(s, -1, axis=ax)) / 3.0
    return s


@app.post("/api/quality")
def assess_quality(req: QualityRequest):
    """影像质量综合评估：返回噪声水平、层厚不均、伪影比例三项归一化指标。

    评分阈值与权重由前端持有，因此用户调整后可即时重算结论。
    """
    if req.volume is None:
        return {"ok": False, "reason": "影像数据缺失：未接收到体数据，请重新载入影像后重试", "metrics": None}

    try:
        vol = np.array(req.volume, dtype=np.float32)
    except Exception:
        return {"ok": False, "reason": "影像数据格式错误：无法解析为数值体数据", "metrics": None}

    if vol.ndim != 3:
        return {"ok": False, "reason": f"影像数据维度异常：期望三维体数据，实际为 {vol.ndim} 维，无法评估", "metrics": None}
    if min(vol.shape) < 2:
        return {"ok": False, "reason": "影像数据不完整：体数据尺寸过小，无法计算层厚不均指标", "metrics": None}
    if not np.isfinite(vol).all():
        return {"ok": False, "reason": "影像数据包含无效值（NaN/Inf），无法得出质量结论", "metrics": None}

    sigma_all = float(vol.std())
    if sigma_all < 1e-6:
        return {"ok": False, "reason": "影像无有效信号（体数据为常量），无法评估噪声与伪影", "metrics": None}

    # 1) 噪声水平：中央 1/4 均匀区内，原始体素与三维平滑体素残差的中位绝对偏差(MAD)，
    #    对骨骼边缘与离群伪影稳健（临床噪声测量惯例取均匀区 ROI）
    residual = vol - _smooth3(vol)
    d, h, w = vol.shape
    z0, z1 = d * 3 // 8, d * 5 // 8
    y0, y1 = h * 3 // 8, h * 5 // 8
    x0, x1 = w * 3 // 8, w * 5 // 8
    center_res = np.abs(residual[z0:z1, y0:y1, x0:x1])
    center_tissue = np.abs(vol[z0:z1, y0:y1, x0:x1]) > 1e-3
    if int(center_tissue.sum()) < 8:
        return {"ok": False, "reason": "有效组织体素过少，无法得出质量结论", "metrics": None}
    noise_std = float(1.4826 * np.median(center_res[center_tissue]))
    noise_level = min(1.0, noise_std / 15.0)  # 残差15HU视为满档噪声

    # 2) 层厚不均：相邻层面平均密度的跳变程度（按整体信号尺度归一化）
    slice_means = vol.reshape(d, -1).mean(axis=1)
    slice_diff = float(np.abs(np.diff(slice_means)).mean())
    slice_unevenness = min(1.0, slice_diff / (abs(float(slice_means.mean())) + 1e-6) / 0.3)

    # 3) 伪影比例：超出均值 ±4σ 的离群体素占比
    mu = float(vol.mean())
    outlier_ratio = float((np.abs(vol - mu) > 4 * sigma_all).mean())
    artifact_ratio = min(1.0, outlier_ratio / 0.02)  # 2% 离群视为满档伪影

    return {
        "ok": True,
        "reason": None,
        "metrics": {
            "noiseLevel": round(noise_level, 4),
            "sliceUnevenness": round(slice_unevenness, 4),
            "artifactRatio": round(artifact_ratio, 4),
            "noiseStdHU": round(noise_std, 2),
            "sliceMeanDiffHU": round(slice_diff, 2),
            "outlierRatio": round(outlier_ratio, 5),
        },
    }