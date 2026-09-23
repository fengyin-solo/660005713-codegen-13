<template>
  <div class="panel quality-card" :class="statusClass">
    <div class="q-head">
      <h4>🧪 影像质量综合评分</h4>
      <el-popover placement="bottom-end" :width="300" trigger="click">
        <template #reference>
          <el-button size="small" text class="gear">⚙️ 阈值与权重</el-button>
        </template>
        <div class="settings">
          <div class="set-row">
            <span>噪声阈值 (HU)</span>
            <el-input-number v-model="s.noiseLimit" :min="1" :max="100" :step="1" size="small"/>
          </div>
          <div class="set-row">
            <span>层厚不均阈值 (CV%)</span>
            <el-input-number v-model="s.thicknessCvLimit" :min="1" :max="100" :step="1" size="small"/>
          </div>
          <div class="set-row">
            <span>伪影比例阈值 (%)</span>
            <el-input-number v-model="s.artifactLimit" :min="1" :max="100" :step="1" size="small"/>
          </div>
          <div class="set-row">
            <span>综合合格线</span>
            <el-input-number v-model="s.scoreLimit" :min="0" :max="100" :step="5" size="small"/>
          </div>
          <el-divider style="margin:8px 0"/>
          <div class="set-row"><span>权重 · 噪声</span>
            <el-input-number v-model="s.weights.noise" :min="0" :max="1" :step="0.1" :precision="2" size="small"/>
          </div>
          <div class="set-row"><span>权重 · 层厚</span>
            <el-input-number v-model="s.weights.thickness" :min="0" :max="1" :step="0.1" :precision="2" size="small"/>
          </div>
          <div class="set-row"><span>权重 · 伪影</span>
            <el-input-number v-model="s.weights.artifacts" :min="0" :max="1" :step="0.1" :precision="2" size="small"/>
          </div>
          <div class="set-hint">权重按启用项自动归一化；无层厚数据时该项不参与评分。</div>
          <el-button size="small" text type="primary" @click="store.resetQualitySettings()">恢复默认</el-button>
        </div>
      </el-popover>
    </div>

    <!-- 计算中 -->
    <div v-if="store.qualityStatus === 'loading'" class="q-state">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>正在评估噪声、层厚不均与伪影…</span>
    </div>

    <!-- 数据缺失 / 算不出结论 -->
    <div v-else-if="store.qualityStatus === 'error'" class="q-state q-error">
      <div class="err-title">⚠️ 无法给出质量结论</div>
      <div class="err-reason">{{ store.qualityError }}</div>
      <el-button size="small" type="warning" plain @click="store.fetchQuality()">🔄 重试</el-button>
    </div>

    <!-- 未载入影像 -->
    <div v-else-if="store.qualityStatus === 'idle'" class="q-state">
      <span>载入影像后将自动给出噪声、层厚不均与伪影的质量结论。</span>
    </div>

    <!-- 结论 -->
    <template v-else-if="ev">
      <div class="verdict">
        <div class="score-ring" :class="ringClass">
          <span class="score-num">{{ ev.score }}</span>
          <span class="score-total">/100</span>
        </div>
        <div class="verdict-text">
          <el-tag :type="ev.pass ? 'success' : 'danger'" effect="dark" size="small">
            {{ ev.pass ? '✔ 质量合格' : '✘ 低于合格线' }}
          </el-tag>
          <div class="verdict-line">
            合格线 {{ s.scoreLimit }} 分，
            <template v-if="ev.pass">各项指标均满足当前阈值。</template>
            <template v-else>
              {{ failedItems.length }} 项越限<span v-if="ev.unavailable.length">，{{ ev.unavailable.length }} 项数据不足</span>。
            </template>
          </div>
        </div>
      </div>

      <div class="items">
        <div v-for="it in ev.items" :key="it.key" class="item" :class="{ fail: it.enabled && !it.pass, dim: !it.enabled }">
          <div class="item-top">
            <span class="item-label">{{ it.label }}</span>
            <span v-if="it.enabled" class="item-val">
              {{ it.value }}<i>{{ it.unit }}</i>
              <em :class="it.pass ? 'ok' : 'bad'">{{ it.pass ? '≤' : '>' }} {{ it.limit }}{{ it.unit }}</em>
            </span>
            <span v-else class="item-na">数据不足</span>
          </div>
          <div v-if="it.enabled" class="bar">
            <div class="bar-fill" :style="barStyle(it.ratio)"
                 :class="it.pass ? 'ok-fill' : 'bad-fill'"></div>
            <span class="bar-mark" :style="{ left: thresholdMark }"></span>
          </div>
          <div v-if="it.enabled" class="item-sub">
            单项得分 {{ it.score }} · 权重 {{ Math.round(it.weight * 100) }}%
          </div>
          <div v-else class="item-sub">缺少层厚元信息，不参与评分与扣分</div>
        </div>
      </div>

      <div v-if="ev.suggestions.length" class="suggestions">
        <div class="sug-title">改进建议</div>
        <ul>
          <li v-for="(sg, i) in ev.suggestions" :key="i">{{ sg }}</li>
        </ul>
      </div>

      <div v-if="motionHint" class="raw-hint">检测到运动伪影层：第 {{ motionHint }} 层；异常体素占比 {{ spikeRatio }}%</div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { useImagingStore } from '../store/imaging'
import type { QualityEvaluation } from '../types'

const store = useImagingStore()
const s = computed(() => store.qualitySettings)

const ev = computed<QualityEvaluation | null>(() => store.qualityEvaluation)
const failedItems = computed(() => (ev.value?.items || []).filter(i => i.enabled && !i.pass))
const ringClass = computed(() => ev.value ? (ev.value.pass ? 'ring-ok' : 'ring-bad') : '')
const statusClass = computed(() => ev.value ? (ev.value.pass ? 'card-ok' : 'card-bad') : '')

const motionHint = computed(() => {
  const zs = store.qualityMetrics?.details.motionBoundarySlices || []
  return zs.length ? zs.join('、') : ''
})
const spikeRatio = computed(() => store.qualityMetrics?.details.spikeRatio ?? 0)

const thresholdMark = '50%'

function barStyle(ratio: number) {
  // 阈值位于进度条 50% 处（ratio=1），允许越限显示到 100%
  return { width: `${Math.min(100, ratio * 50)}%` }
}
</script>

<style scoped>
.panel { background:#161b22; border-radius:6px; padding:10px; border:1px solid #30363d }
.quality-card.card-ok { border-color:#2ea04366 }
.quality-card.card-bad { border-color:#f8514999; box-shadow:0 0 0 1px #f8514933 inset }
.q-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:8px }
.q-head h4 { color:#58a6ff; font-size:12px }
.gear { color:#8b949e !important; font-size:11px }
.q-state { display:flex; align-items:center; gap:8px; font-size:11px; color:#8b949e; padding:8px 2px }
.q-error { flex-direction:column; align-items:flex-start; gap:6px }
.err-title { color:#e3b341; font-size:12px; font-weight:600 }
.err-reason { color:#c9d1d9; font-size:11px }
.verdict { display:flex; gap:12px; align-items:center; margin-bottom:10px }
.score-ring { width:56px; height:56px; border-radius:50%; display:flex; flex-direction:column;
  align-items:center; justify-content:center; border:3px solid #30363d; flex-shrink:0 }
.ring-ok { border-color:#2ea043 }
.ring-bad { border-color:#f85149 }
.score-num { font-size:18px; font-weight:700; color:#e6edf3; line-height:1 }
.score-total { font-size:9px; color:#8b949e }
.verdict-text { display:flex; flex-direction:column; gap:4px }
.verdict-line { font-size:11px; color:#8b949e }
.items { display:flex; flex-direction:column; gap:8px }
.item.fail .item-label { color:#ff7b72 }
.item.dim { opacity:.75 }
.item-top { display:flex; justify-content:space-between; align-items:baseline; font-size:11px }
.item-label { color:#c9d1d9 }
.item-val { color:#e6edf3; font-weight:600 }
.item-val i { font-style:normal; font-size:9px; color:#8b949e; margin-left:2px }
.item-val em { font-style:normal; margin-left:6px; font-size:10px }
.item-val em.ok { color:#3fb950 }
.item-val em.bad { color:#f85149 }
.item-na { color:#8b949e; font-size:10px }
.bar { position:relative; height:5px; background:#0d1117; border-radius:3px; margin-top:3px; overflow:visible }
.bar-fill { height:100%; border-radius:3px }
.ok-fill { background:linear-gradient(90deg,#2ea043,#3fb950) }
.bad-fill { background:linear-gradient(90deg,#d29922,#f85149) }
.bar-mark { position:absolute; top:-2px; bottom:-2px; width:2px; background:#8b949e; opacity:.7 }
.item-sub { font-size:9px; color:#8b949e; margin-top:2px }
.suggestions { margin-top:10px; padding:6px 8px; background:#3d2f1333; border:1px solid #d2992244; border-radius:4px }
.sug-title { color:#e3b341; font-size:11px; font-weight:600; margin-bottom:4px }
.suggestions ul { margin-left:14px; color:#c9d1d9; font-size:10px; line-height:1.6 }
.raw-hint { margin-top:6px; font-size:9px; color:#8b949e }
.settings { display:flex; flex-direction:column; gap:8px }
.set-row { display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#30363d }
.set-row > span { color:#30363d }
.set-hint { font-size:10px; color:#909399; line-height:1.4 }
</style>
