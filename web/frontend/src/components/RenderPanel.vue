<script setup>
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

const store = useResearchDrawStore();
const {
  rendering,
  renderProgress,
  renderStatusText,
  currentTaskId,
  messageErr,
  messageOk,
  lastFailedPayload,
  retryLastRender,
  cancelCurrentRenderTask,
  lastSaveName,
  currentResultFmt,
  fmt,
  imageUrl,
  resultPreviewType,
  resultFileName,
  resetResult
} = store;
</script>

<template>
  <section id="section-result" class="panel section-card result-section">
    <div class="section-head">
      <div>
        <span class="section-kicker">步骤 04 · 结果</span>
        <h2>预览与导出</h2>
        <p class="section-subtitle">查看当前图像和任务状态；过往记录与文件请到资产管理中查看。</p>
      </div>
      <button class="ghost" @click="resetResult">清空当前结果</button>
    </div>

    <div v-if="rendering || renderProgress > 0" class="progress-card">
      <div class="progress-head">
        <span>{{ renderStatusText || (rendering ? "渲染中..." : "任务完成") }}</span>
        <span>{{ Math.round(renderProgress) }}%</span>
      </div>
      <div class="progress-track">
        <div class="progress-bar" :style="{ width: `${renderProgress}%` }"></div>
      </div>
      <div v-if="rendering && currentTaskId" class="btn-row">
        <button class="ghost" @click="cancelCurrentRenderTask">取消任务</button>
      </div>
    </div>

    <div v-if="messageErr" class="error-row">
      <p class="msg error">{{ messageErr }}</p>
      <button class="ghost" :disabled="rendering || !lastFailedPayload" @click="retryLastRender">失败重试</button>
    </div>
    <p v-if="messageOk" class="msg ok">{{ messageOk }}</p>
    <p v-if="lastSaveName" class="muted">输出文件名：{{ lastSaveName }}.{{ (currentResultFmt || fmt).toUpperCase() }}</p>

    <div class="image-wrap" :class="`preview-${resultPreviewType}`">
      <img v-if="imageUrl && resultPreviewType === 'image'" :key="imageUrl" :src="imageUrl" alt="当前渲染结果" />
      <div v-else-if="imageUrl && resultPreviewType === 'pdf'" class="pdf-preview-wrap">
        <iframe class="result-pdf-frame" :src="imageUrl" title="PDF 渲染结果"></iframe>
        <a class="open-link pdf-open-link" :href="imageUrl" target="_blank" rel="noopener noreferrer">若页面未显示 PDF，请在新窗口打开</a>
      </div>
      <div v-else-if="imageUrl && resultPreviewType === 'unsupported'" class="empty">
        <p>当前文件类型暂不支持内嵌预览</p>
        <p class="muted">文件：{{ resultFileName || "unknown" }}</p>
        <a class="open-link" :href="imageUrl" target="_blank" rel="noopener noreferrer">在新窗口打开文件</a>
      </div>
      <div v-else class="empty">
        <p>尚未渲染图像</p>
        <p class="muted">在顶部操作栏点击“渲染图像”开始绘图。</p>
      </div>
    </div>
  </section>
</template>
