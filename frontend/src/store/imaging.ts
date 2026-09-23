import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import axios from 'axios'
import type {
  VolumeData, ROIResult, QualityMetrics, QualitySettings, QualityStatus, QualityEvaluation
} from '@/types'
import { DEFAULT_QUALITY_SETTINGS, evaluateQuality } from '@/quality/evaluate'

const SETTINGS_KEY = 'quality-settings-v1'

function loadSettings(): QualitySettings {
  try {
    const saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || 'null')
    if (saved && typeof saved === 'object') {
      return {
        ...DEFAULT_QUALITY_SETTINGS,
        ...saved,
        weights: { ...DEFAULT_QUALITY_SETTINGS.weights, ...(saved.weights || {}) },
      }
    }
  } catch { /* ignore corrupted settings */ }
  return { ...DEFAULT_QUALITY_SETTINGS, weights: { ...DEFAULT_QUALITY_SETTINGS.weights } }
}

export const useImagingStore = defineStore('imaging', () => {
  const loading = ref(false)
  const volumeData = ref<VolumeData | null>(null)
  const preset = ref('brain')
  const windowVal = ref(80)
  const levelVal = ref(40)
  const roiResults = ref<ROIResult[]>([])
  const mprSlice = ref({ axial: 32, coronal: 32, sagittal: 32 })

  // ---- 影像质量综合评分 ----
  const qualitySettings = ref<QualitySettings>(loadSettings())
  const qualityStatus = ref<QualityStatus>('idle')
  const qualityMetrics = ref<QualityMetrics | null>(null)
  const qualityError = ref('')
  /** 用于"重试"：记录最近一次质量计算使用的体数据快照 */
  let lastQualityPayload: { volume: unknown; sliceThicknesses?: number[] } | null = null

  // 阈值/权重变化时，已打开卡片的结论即时重算（纯前端计算，无需请求）；
  // 同时深监听，弹窗内直接 v-model 修改也会自动持久化
  const qualityEvaluation = computed<QualityEvaluation | null>(() =>
    qualityMetrics.value ? evaluateQuality(qualityMetrics.value, qualitySettings.value) : null)

  watch(qualitySettings, (val) => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(val))
  }, { deep: true })

  function resetQualitySettings() {
    qualitySettings.value = { ...DEFAULT_QUALITY_SETTINGS, weights: { ...DEFAULT_QUALITY_SETTINGS.weights } }
  }

  async function fetchQuality() {
    if (!lastQualityPayload) return
    qualityStatus.value = 'loading'
    qualityError.value = ''
    try {
      const { data } = await axios.post('/api/quality', lastQualityPayload)
      qualityMetrics.value = data.metrics
      qualityStatus.value = 'done'
    } catch (e: any) {
      qualityStatus.value = 'error'
      qualityMetrics.value = null
      qualityError.value = e?.response?.data?.detail?.message
        || e?.message || '质量计算服务不可用，请稍后重试'
    }
  }

  async function loadVolume() {
    loading.value = true
    try {
      const { data } = await axios.post('/api/volume', {
        preset: preset.value, width: 64, height: 64, depth: 64
      })
      volumeData.value = data
      mprSlice.value = { axial: 32, coronal: 32, sagittal: 32 }
      // 质量评分为独立旁路：不 await，失败只影响质量卡片，不阻断阅片/测量流程
      lastQualityPayload = { volume: data.volume, sliceThicknesses: data.sliceThicknesses }
      qualityMetrics.value = null
      qualityError.value = ''
      fetchQuality()
    } finally { loading.value = false }
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
    loadVolume, analyzeROI, applyWindow,
    qualitySettings, qualityStatus, qualityMetrics, qualityError, qualityEvaluation,
    resetQualitySettings, fetchQuality,
  }
})
