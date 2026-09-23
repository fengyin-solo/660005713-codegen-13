<template>
  <div class="app-root">
    <header class="top-bar">
      <h1>🩻 三维医学影像体渲染与ROI标注平台</h1>
      <div class="tools">
        <el-select v-model="store.preset" size="small" style="width:120px">
          <el-option value="brain" label="头部CT"/><el-option value="chest" label="胸部CT"/><el-option value="abdomen" label="腹部CT"/>
        </el-select>
        <el-button size="small" @click="store.loadVolume()" :loading="store.loading">载入影像</el-button>
        <span v-if="store.volumeData" class="dim-info">{{ store.volumeData.dimensions.join('×') }}</span>
      </div>
    </header>
    <div class="main-grid" v-if="store.volumeData">
      <div class="render-area"><VolumeRenderer /></div>
      <div class="mpr-area">
        <div class="mpr-row">
          <div class="mpr-panel"><div class="mpr-title">横断面 (轴位)</div><MPRView plane="axial" /></div>
          <div class="mpr-panel"><div class="mpr-title">冠状面</div><MPRView plane="coronal" /></div>
          <div class="mpr-panel"><div class="mpr-title">矢状面</div><MPRView plane="sagittal" /></div>
        </div>
        <WindowControl />
        <QualityPanel />
        <ROIPanel />
      </div>
    </div>
    <div class="loading-state" v-else-if="!store.loading">
      <div class="placeholder">选择预设并点击"载入影像"开始分析</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import VolumeRenderer from './components/VolumeRenderer.vue'
import MPRView from './components/MPRView.vue'
import WindowControl from './components/WindowControl.vue'
import QualityPanel from './components/QualityPanel.vue'
import ROIPanel from './components/ROIPanel.vue'
import { useImagingStore } from './store/imaging'
const store = useImagingStore()
</script>

<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0d1117;color:#c9d1d9}
.app-root{min-height:100vh}
.top-bar{display:flex;justify-content:space-between;align-items:center;padding:10px 20px;background:#161b22;border-bottom:1px solid #30363d}
.top-bar h1{font-size:1rem;color:#58a6ff}
.tools{display:flex;gap:8px;align-items:center}
.dim-info{font-size:11px;color:#8b949e;font-family:monospace}
.loading-state{display:flex;align-items:center;justify-content:center;height:50vh}
.placeholder{color:#484f58;font-size:14px}
.main-grid{display:grid;grid-template-columns:1fr 480px;gap:12px;padding:12px 20px;min-height:85vh}
.render-area{background:#0d1117;border-radius:8px;border:1px solid #30363d;overflow:hidden}
.mpr-area{display:flex;flex-direction:column;gap:12px;overflow-y:auto}
.mpr-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}
.mpr-panel{background:#161b22;border-radius:6px;border:1px solid #30363d;overflow:hidden}
.mpr-title{font-size:10px;color:#8b949e;padding:4px 6px;background:#0d1117;text-align:center}
</style>