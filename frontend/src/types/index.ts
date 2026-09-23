export interface WindowPreset { window: number; level: number; desc: string }
export interface VolumeData {
  volume: number[][][]
  dimensions: [number, number, number]
  mpr: { axial: number[][]; coronal: number[][]; sagittal: number[][] }
  preset: string
  windowPresets: Record<string, WindowPreset>
}

export interface ROIResult {
  label: string; center: number[]; radius: number
  mean: number; std: number; min: number; max: number; voxelCount: number
  histogram: number[]
}

export interface QualityMetrics {
  noiseLevel: number        // 噪声水平 0-1
  sliceUnevenness: number   // 层厚不均 0-1
  artifactRatio: number     // 伪影比例 0-1
  noiseStdHU: number
  sliceMeanDiffHU: number
  outlierRatio: number
}

export interface QualityWeights { noise: number; thickness: number; artifact: number }

export type QualityVerdictLevel = 'excellent' | 'pass' | 'fail'
export interface QualityVerdict { level: QualityVerdictLevel; label: string; pass: boolean }