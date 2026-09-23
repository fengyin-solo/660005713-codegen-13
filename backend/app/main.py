import random, math
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from app.services.quality import compute_quality_metrics, QualityComputeError

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

    vol = inject_synthetic_degradation(vol, preset)
    return vol


# 各预设的层厚元信息（模拟实际扫描中不均匀的重建层间隔）
SLICE_THICKNESSES = {
    "brain":   [5.0] * 64,
    "chest":   [round(5.0 + 0.5 * math.sin(i / 64 * 2 * math.pi * 2), 3) for i in range(64)],
    "abdomen": [round(5.0 + 0.9 * math.sin(i / 64 * 2 * math.pi * 3) + 0.3 * math.sin(i * 3.7), 3)
                for i in range(64)],
}

PRESET_NAMES = {"brain": "头部CT", "chest": "胸部CT", "abdomen": "腹部CT"}


def inject_synthetic_degradation(vol: np.ndarray, preset: str) -> np.ndarray:
    """向合成体数据注入确定性的真实感退化，用于质量评分演示。

    brain  ：轻度高斯噪声；
    chest  ：高斯噪声 + 金属植入体放射条带/拉链伪影；
    abdomen：较强高斯噪声 + 扫描中患者运动（连续层段整体移位）。
    """
    rng = np.random.RandomState(7)
    d, h, w = vol.shape
    cy, cx = h // 2, w // 2

    if preset == "brain":
        vol = vol + rng.normal(0, 6, vol.shape).astype(np.float32)
    elif preset == "chest":
        vol = vol + rng.normal(0, 10, vol.shape).astype(np.float32)
        # 金属植入体核心 + 穿过核心的拉链/条纹线
        vol[20:45, cy - 7, cx] = 900
        for z in (22, 26, 30, 34, 38):
            vol[z, :, cx] = np.where(np.abs(np.arange(h) - cy) < 2, 900, vol[z, :, cx])
            vol[z, cy - 7, :] = np.where(np.arange(w) % 2 == 0, 800, -300)
    elif preset == "abdomen":
        vol = vol + rng.normal(0, 14, vol.shape).astype(np.float32)
        # 扫描过程中的患者运动：两段连续层在 x 方向整体移位
        for z0, z1, shift in ((16, 30, 4), (40, 48, -3)):
            vol[z0:z1] = np.roll(vol[z0:z1], shift, axis=2)
    return vol


@app.post("/api/volume")
def get_volume(req: VolumeRequest):
    vol = generate_volume(req.preset, req.width, req.height, req.depth)
    vol_list = vol.tolist()
    thicknesses = _match_thicknesses(req.depth, SLICE_THICKNESSES.get(req.preset, []))

    # Extract mid slices for MPR
    mid_axial = int(req.depth // 2)
    mid_coronal = int(req.height // 2)
    mid_sagittal = int(req.width // 2)

    # Return: 3D volume + 3 MPR slices
    return {
        "volume": vol_list,
        "dimensions": [req.depth, req.height, req.width],
        "sliceThicknesses": thicknesses,
        "seriesName": PRESET_NAMES.get(req.preset, req.preset),
        "mpr": {
            "axial": vol_list[mid_axial],
            "coronal": [[vol_list[z][mid_coronal][x] for x in range(req.width)] for z in range(req.depth)],
            "sagittal": [[vol_list[z][y][mid_sagittal] for y in range(req.height)] for z in range(req.depth)]
        },
        "preset": req.preset,
        "windowPresets": WINDOW_PRESETS
    }


def _match_thicknesses(depth: int, template: List[float]) -> List[float]:
    """按当前层数对预设层厚序列做最近邻重采样。"""
    if not template:
        return []
    if len(template) == depth:
        return list(template)
    idx = np.rint(np.linspace(0, len(template) - 1, depth)).astype(int)
    return [float(template[i]) for i in idx]


class QualityRequest(BaseModel):
    volume: Optional[list] = None
    sliceThicknesses: Optional[List[float]] = None


@app.post("/api/quality")
def quality(req: QualityRequest):
    try:
        metrics = compute_quality_metrics(req.volume, req.sliceThicknesses)
    except QualityComputeError as exc:
        # 数据缺失或算不出结论：返回明确原因，前端展示失败状态与重试入口
        raise HTTPException(status_code=422, detail={"message": str(exc)})
    return {"status": "ok", "metrics": metrics}


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