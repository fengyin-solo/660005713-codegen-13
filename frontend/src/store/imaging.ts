import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'
import type { VolumeData, ROIResult, QualityMetrics, QualityWeights, QualityVerdict } from '@/types'

export const useImagingStore = defineStore('imaging', () => {
  const loading = ref(false)
  const volumeData = ref<VolumeData | null>(null)
  const preset = ref('brain')
  const windowVal = ref(80)
  const levelVal = ref(40)
  const roiResults = ref<ROIResult[]>([])
  const mprSlice = ref({ axial: 32, coronal: 32, sagittal: 32 })

  // ---- 影像质量综合评分 ----
  const qualityMetrics = ref<QualityMetrics | null>(null)
  const qualityError = ref<string | null>(null)
  const qualityLoading = ref(false)
  const qualityThreshold = ref(70)
  const qualityWeights = ref<QualityWeights>({ noise: 0.4, thickness: 0.3, artifact: 0.3 })

  const weightTotal = computed(() =>
    qualityWeights.value.noise + qualityWeights.value.thickness + qualityWeights.value.artifact
  )

  // 加权综合分：基于后端给出的三项原始指标在前端实时重算
  const qualityScore = computed<number | null>(() => {
    const m = qualityMetrics.value
    if (!m || weightTotal.value <= 0) return null
    const w = qualityWeights.value
    const penalty = (
      w.noise * m.noiseLevel +
      w.thickness * m.sliceUnevenness +
      w.artifact * m.artifactRatio
    ) / weightTotal.value
    return Math.round((1 - penalty) * 100)
  })

  const qualityVerdict = computed<QualityVerdict | null>(() => {
    const score = qualityScore.value
    if (score === null) return null
    if (score >= 85) return { level: 'excellent', label: '优秀', pass: true }
    if (score >= qualityThreshold.value) return { level: 'pass', label: '合格', pass: true }
    return { level: 'fail', label: '不合格', pass: false }
  })

  // 改进建议随指标与权重设置实时更新
  const qualitySuggestions = computed<string[]>(() => {
    const m = qualityMetrics.value
    if (!m) return []
    const tips: string[] = []
    if (m.noiseLevel >= 0.5) tips.push('噪声水平偏高：建议提高扫描剂量(mAs)或启用迭代重建/降噪算法后重评')
    if (m.sliceUnevenness >= 0.5) tips.push('层厚不均明显：请核对扫描协议的层厚与层间距设置，建议薄层重建后复查')
    if (m.artifactRatio >= 0.5) tips.push('伪影比例偏高：排查患者运动或金属异物干扰，必要时重新扫描')
    if (!tips.length) tips.push('噪声、层厚与伪影均在可接受范围内，影像质量满足诊断要求')
    return tips
  })

  async function loadVolume() {
    loading.value = true
    try {
      const { data } = await axios.post('/api/volume', {
        preset: preset.value, width: 64, height: 64, depth: 64
      })
      volumeData.value = data
      mprSlice.value = { axial: 32, coronal: 32, sagittal: 32 }
      await loadQuality()
    } catch (e: any) {
      volumeData.value = null
      qualityMetrics.value = null
      qualityError.value = '影像载入失败：' + (e?.message || '网络请求异常') + '，无法计算质量结论'
    } finally { loading.value = false }
  }

  async function loadQuality() {
    if (!volumeData.value) {
      qualityMetrics.value = null
      qualityError.value = '影像数据缺失：尚未载入体数据，请先载入影像后重试'
      return
    }
    qualityLoading.value = true
    try {
      const { data } = await axios.post('/api/quality', {
        volume: volumeData.value.volume, preset: preset.value
      })
      if (data.ok) {
        qualityMetrics.value = data.metrics
        qualityError.value = null
      } else {
        qualityMetrics.value = null
        qualityError.value = data.reason || '无法计算质量结论，请重试'
      }
    } catch (e: any) {
      qualityMetrics.value = null
      qualityError.value = '质量评估服务异常：' + (e?.message || '网络请求失败') + '，请重试'
    } finally {
      qualityLoading.value = false
    }
  }

  async function analyzeROI(rois: any[]) {
    loading.value = true
    try {
      const { data } = await axios.post('/api/roi', { volume: volumeData.value?.volume, rois })
      roiResults.value = data.rois
    } finally { loading.value = false }
  }

  function applyWindow(w: number, l: number) { windowVal.value = w; levelVal.value = l }

  return {
    loading, volumeData, preset, windowVal, levelVal, roiResults, mprSlice,
    qualityMetrics, qualityError, qualityLoading, qualityThreshold, qualityWeights,
    weightTotal, qualityScore, qualityVerdict, qualitySuggestions,
    loadVolume, loadQuality, analyzeROI, applyWindow
  }
})
