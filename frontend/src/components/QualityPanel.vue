<template>
  <div class="panel quality-card" :class="{ 'is-fail': verdict && !verdict.pass }">
    <div class="qc-header">
      <h4>🧪 影像质量综合评分</h4>
      <el-button size="small" text class="rule-btn" @click="showSettings = !showSettings">
        ⚙️ 评分规则
      </el-button>
    </div>

    <!-- 规则设置：阈值与各项权重 -->
    <div v-if="showSettings" class="qc-settings">
      <div class="set-row">
        <span>合格阈值 <b>{{ store.qualityThreshold }}</b> 分</span>
        <input type="range" min="0" max="100" v-model.number="store.qualityThreshold"/>
      </div>
      <div class="set-row" v-for="item in weightItems" :key="item.key">
        <span>{{ item.name }}权重 <b>{{ pct(item.value) }}%</b></span>
        <input type="range" min="0" max="1" step="0.05" v-model.number="store.qualityWeights[item.key]"/>
      </div>
      <div class="set-hint" :class="{ invalid: store.weightTotal <= 0 }">
        权重合计 {{ pct(store.weightTotal) }}%，评分时自动归一化
      </div>
    </div>

    <!-- 评估中 -->
    <div v-if="store.qualityLoading" class="qc-state">⏳ 正在评估影像质量（噪声 / 层厚 / 伪影）…</div>

    <!-- 数据缺失或算不出结论：说明原因并给出重试入口 -->
    <div v-else-if="store.qualityError" class="qc-state qc-error">
      <div class="err-reason">⚠️ {{ store.qualityError }}</div>
      <el-button size="small" type="warning" @click="store.loadQuality()">🔄 重试</el-button>
    </div>

    <!-- 无影像 -->
    <div v-else-if="!store.qualityMetrics" class="qc-state">载入影像后将自动给出质量结论</div>

    <!-- 权重非法 -->
    <div v-else-if="score === null" class="qc-state qc-error">
      <div class="err-reason">权重之和不能为 0，请在“评分规则”中调整</div>
    </div>

    <!-- 质量结论 -->
    <template v-else>
      <div v-if="verdict && !verdict.pass" class="fail-banner">
        ⚠️ 综合评分低于合格阈值（{{ store.qualityThreshold }} 分），已在阅片卡片中标出，请按建议改进
      </div>
      <div class="score-row">
        <div class="score-num" :class="scoreClass">{{ score }}<small>分</small></div>
        <div class="score-side">
          <el-tag :type="tagType" size="small" effect="dark">{{ verdict?.label }}</el-tag>
          <div class="threshold-hint">合格阈值 {{ store.qualityThreshold }} 分</div>
        </div>
      </div>

      <div class="metric" v-for="m in metricList" :key="m.key">
        <div class="m-head">
          <span>{{ m.name }}</span>
          <span :class="{ bad: m.value >= 0.5 }">{{ (m.value * 100).toFixed(0) }}%</span>
        </div>
        <div class="m-bar"><div class="m-fill" :class="{ bad: m.value >= 0.5 }" :style="{ width: (m.value * 100) + '%' }"></div></div>
        <div class="m-raw">{{ m.raw }}</div>
      </div>

      <div class="suggestions">
        <div class="sug-title">📋 质量结论与改进建议</div>
        <div v-for="(s, i) in store.qualitySuggestions" :key="i" class="sug-item">• {{ s }}</div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useImagingStore } from '../store/imaging'
import type { QualityWeights } from '@/types'

const store = useImagingStore()
const showSettings = ref(false)

const score = computed(() => store.qualityScore)
const verdict = computed(() => store.qualityVerdict)
const scoreClass = computed(() => verdict.value?.level || 'fail')
const tagType = computed(() => {
  if (verdict.value?.level === 'excellent') return 'success'
  if (verdict.value?.level === 'pass') return 'primary'
  return 'danger'
})

const weightItems = computed(() => [
  { key: 'noise' as keyof QualityWeights, name: '噪声', value: store.qualityWeights.noise },
  { key: 'thickness' as keyof QualityWeights, name: '层厚不均', value: store.qualityWeights.thickness },
  { key: 'artifact' as keyof QualityWeights, name: '伪影', value: store.qualityWeights.artifact },
])

const metricList = computed(() => {
  const m = store.qualityMetrics
  if (!m) return []
  return [
    { key: 'noise', name: '噪声水平', value: m.noiseLevel, raw: `噪声标准差 ${m.noiseStdHU} HU` },
    { key: 'thickness', name: '层厚不均', value: m.sliceUnevenness, raw: `相邻层均值差 ${m.sliceMeanDiffHU} HU` },
    { key: 'artifact', name: '伪影比例', value: m.artifactRatio, raw: `离群体素占比 ${(m.outlierRatio * 100).toFixed(2)}%` },
  ]
})

function pct(v: number) { return (v * 100).toFixed(0) }
</script>

<style scoped>
.quality-card { background:#161b22; border-radius:6px; padding:10px; border:1px solid #30363d }
.quality-card.is-fail { border-color:#f85149; box-shadow:0 0 0 1px rgba(248,81,73,.35) }
.qc-header { display:flex; justify-content:space-between; align-items:center }
.quality-card h4 { color:#58a6ff; font-size:12px; margin-bottom:8px }
.rule-btn { color:#8b949e; font-size:11px }
.qc-settings { background:#0d1117; border:1px solid #30363d; border-radius:4px; padding:8px; margin-bottom:8px }
.set-row { display:flex; flex-direction:column; gap:2px; font-size:11px; color:#8b949e; margin-bottom:6px }
.set-row b { color:#e6edf3 }
.set-row input { accent-color:#58a6ff }
.set-hint { font-size:10px; color:#8b949e }
.set-hint.invalid { color:#f85149 }
.qc-state { font-size:11px; color:#8b949e; padding:10px 4px; text-align:center }
.qc-error { display:flex; flex-direction:column; gap:8px; align-items:center; color:#e6edf3 }
.err-reason { font-size:11px; color:#f0b97b; line-height:1.5 }
.fail-banner { background:rgba(248,81,73,.12); border:1px solid rgba(248,81,73,.4); color:#ffa198;
  font-size:11px; padding:6px 8px; border-radius:4px; margin-bottom:8px; line-height:1.5 }
.score-row { display:flex; align-items:center; gap:12px; margin-bottom:10px }
.score-num { font-size:34px; font-weight:700; line-height:1; font-family:monospace }
.score-num small { font-size:12px; font-weight:400; margin-left:2px }
.score-num.excellent { color:#3fb950 }
.score-num.pass { color:#58a6ff }
.score-num.fail { color:#f85149 }
.score-side { display:flex; flex-direction:column; gap:4px }
.threshold-hint { font-size:10px; color:#8b949e }
.metric { margin-bottom:6px }
.m-head { display:flex; justify-content:space-between; font-size:11px; color:#c9d1d9 }
.m-head .bad, .m-fill.bad { color:#f85149 }
.m-bar { height:5px; background:#0d1117; border-radius:3px; overflow:hidden; margin:3px 0 1px }
.m-fill { height:100%; background:#58a6ff; transition:width .2s }
.m-fill.bad { background:#f85149 }
.m-raw { font-size:9px; color:#8b949e }
.suggestions { margin-top:8px; border-top:1px solid #30363d; padding-top:6px }
.sug-title { font-size:11px; color:#e6edf3; margin-bottom:4px }
.sug-item { font-size:10px; color:#c9d1d9; line-height:1.6 }
</style>
