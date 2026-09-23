export interface WindowPreset { window: number; level: number; desc: string }
export interface VolumeData {
  volume: number[][][]
  dimensions: [number, number, number]
  mpr: { axial: number[][]; coronal: number[][]; sagittal: number[][] }
  preset: string
  seriesName: string
  sliceThicknesses: number[]
  windowPresets: Record<string, WindowPreset>
}

export interface ROIResult {
  label: string; center: number[]; radius: number
  mean: number; std: number; min: number; max: number; voxelCount: number
  histogram: number[]
}

export type QualityItemKey = 'noise' | 'thickness' | 'artifacts'

export interface QualitySettings {
  /** 噪声阈值（HU），超过判为不合格 */
  noiseLimit: number
  /** 层厚不均阈值（变异系数 CV%） */
  thicknessCvLimit: number
  /** 伪影比例阈值（%） */
  artifactLimit: number
  /** 综合得分合格线（0-100） */
  scoreLimit: number
  /** 各项权重，内部按启用项归一化 */
  weights: Record<QualityItemKey, number>
}

export interface QualityMetrics {
  noiseLevelHu: number
  thicknessCvPercent: number | null
  artifactRatioPercent: number
  details: {
    voxelCount: number
    spikeRatio: number
    motionBoundarySlices: number[]
  }
}

export type QualityStatus = 'idle' | 'loading' | 'done' | 'error'

export interface QualityItemResult {
  key: QualityItemKey
  label: string
  value: number | null
  unit: string
  limit: number
  weight: number
  /** 层厚元信息缺失时该项不参与评分 */
  enabled: boolean
  pass: boolean
  /** 0-100，越小越差 */
  score: number
  /** value / limit，用于进度条展示 */
  ratio: number
}

export interface QualityEvaluation {
  score: number
  pass: boolean
  items: QualityItemResult[]
  suggestions: string[]
  /** 未参与评分的项（数据缺失），用于说明 */
  unavailable: QualityItemKey[]
}
