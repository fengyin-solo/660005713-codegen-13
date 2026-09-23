import type {
  QualityEvaluation, QualityItemKey, QualityItemResult, QualityMetrics, QualitySettings
} from '@/types'

export const DEFAULT_QUALITY_SETTINGS: QualitySettings = {
  noiseLimit: 8,
  thicknessCvLimit: 10,
  artifactLimit: 5,
  scoreLimit: 70,
  weights: { noise: 0.4, thickness: 0.3, artifacts: 0.3 },
}

const ITEM_META: Record<QualityItemKey, { label: string; unit: string }> = {
  noise: { label: '噪声水平', unit: 'HU' },
  thickness: { label: '层厚不均', unit: '%' },
  artifacts: { label: '伪影比例', unit: '%' },
}

const SUGGESTIONS: Record<QualityItemKey, string> = {
  noise: '噪声偏高：建议提高扫描 mAs/管电流、增大层厚或在重建时启用迭代降噪后重新采集。',
  thickness: '层厚不均：建议在重建端统一重建层间隔/层厚后重新导出序列，并核对扫描定位像与进床精度。',
  artifacts: '伪影明显：建议检查金属物、患者制动与屏气配合，去除金属源或开启金属伪影校正(MAR)后重新扫描。',
}

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v))
}

/** 单项得分：阈值处为 60 分，值为 0 时满分，约 2 倍阈值处接近 0。 */
function itemScore(value: number, limit: number) {
  if (limit <= 0) return value <= 0 ? 100 : 0
  return round1(clamp(100 * (1 - value / (2 * limit)), 0, 100))
}

function round1(v: number) {
  return Math.round(v * 10) / 10
}

/**
 * 纯函数：由原始指标 + 用户阈值/权重计算综合结论。
 * 设置变化时对已打开影像重新调用即可得到新结论，无需重新请求后端。
 */
export function evaluateQuality(metrics: QualityMetrics, settings: QualitySettings): QualityEvaluation {
  const unavailable: QualityItemKey[] = []

  const raw: Array<{ key: QualityItemKey; value: number | null; limit: number; weight: number }> = [
    { key: 'noise', value: metrics.noiseLevelHu, limit: settings.noiseLimit, weight: settings.weights.noise },
    {
      key: 'thickness', value: metrics.thicknessCvPercent,
      limit: settings.thicknessCvLimit, weight: settings.weights.thickness,
    },
    {
      key: 'artifacts', value: metrics.artifactRatioPercent,
      limit: settings.artifactLimit, weight: settings.weights.artifacts,
    },
  ]

  const available = raw.filter(r => r.value !== null && isFinite(r.value as number))
  const weightSum = available.reduce((s, r) => s + Math.max(0, r.weight), 0)

  const items: QualityItemResult[] = raw.map(r => {
    const meta = ITEM_META[r.key]
    const enabled = r.value !== null && isFinite(r.value as number)
    if (!enabled) unavailable.push(r.key)
    const value = enabled ? (r.value as number) : null
    const pass = enabled ? (value as number) <= r.limit : false
    return {
      key: r.key,
      label: meta.label,
      value: enabled ? round1(value as number) : null,
      unit: meta.unit,
      limit: r.limit,
      weight: enabled && weightSum > 0 ? Math.max(0, r.weight) / weightSum : 0,
      enabled,
      pass,
      score: enabled ? itemScore(value as number, r.limit) : 0,
      ratio: enabled && r.limit > 0 ? (value as number) / r.limit : 0,
    }
  })

  const score = weightSum > 0
    ? round1(items.filter(i => i.enabled).reduce((s, i) => s + i.score * i.weight, 0))
    : 0
  const itemPass = items.filter(i => i.enabled).every(i => i.pass)
  const pass = itemPass && score >= settings.scoreLimit
  const suggestions = items.filter(i => i.enabled && !i.pass).map(i => SUGGESTIONS[i.key])

  return { score, pass, items, suggestions, unavailable }
}
