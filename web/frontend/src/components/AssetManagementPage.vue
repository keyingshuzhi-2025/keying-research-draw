<script setup>
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

defineProps({
  page: { type: String, default: "history" }
});

const store = useResearchDrawStore();
const {
  renderHistory,
  clearRenderHistory,
  clearRenderHistoryAndLocalFiles,
  historyScrollRef,
  visibleRenderHistory,
  hasMoreHistory,
  onHistoryScroll,
  historyHasImagePreview,
  historyImageUrl,
  historyPreviewLabel,
  formatHistoryTime,
  applyHistoryItem,
  openHistoryResult,
  deleteHistoryItem,
  loadMoreHistory,
  renderFilesLoading,
  renderFiles,
  renderFilesScrollRef,
  visibleRenderFiles,
  hasMoreRenderFiles,
  fetchRenderFiles,
  renderFileTypeBadge,
  renderFileTypeLabel,
  formatFileSize,
  openRenderFileItem,
  renderFilePreviewType,
  openRenderFileInNewWindow,
  deleteRenderFileItem,
  loadMoreRenderFiles,
  onRenderFilesScroll
} = store;
</script>

<template>
  <section class="asset-page-content">
    <div v-if="page === 'history'" class="asset-page-card">
      <div class="section-head asset-page-head">
        <div>
          <span class="section-kicker">资产管理 · 01</span>
          <h2>渲染历史</h2>
          <p class="section-subtitle">查看过往图形、复用配置或打开已生成结果。</p>
        </div>
        <div class="btn-row">
          <button class="ghost" :disabled="!renderHistory.length" @click="clearRenderHistory">清空历史</button>
          <button class="ghost" :disabled="!renderHistory.length" @click="clearRenderHistoryAndLocalFiles">清空历史与文件</button>
        </div>
      </div>

      <div v-if="renderHistory.length" ref="historyScrollRef" class="history-scroll" @scroll="onHistoryScroll">
        <div class="history-list">
          <article v-for="item in visibleRenderHistory" :key="item.id" class="history-item">
            <div class="history-thumb">
              <img v-if="item.imagePath && historyHasImagePreview(item)" :src="historyImageUrl(item)" alt="历史图形预览" />
              <span v-else class="history-thumb-empty">{{ historyPreviewLabel(item) }}</span>
            </div>
            <div class="history-meta">
              <strong>{{ item.plot }}</strong>
              <span>{{ item.title || "未命名标题" }}</span>
              <span>{{ formatHistoryTime(item.timestamp) }} · {{ String(item.fmt || "").toUpperCase() }}</span>
            </div>
            <div class="history-actions">
              <button class="ghost" @click="applyHistoryItem(item)">复用配置</button>
              <button class="ghost" @click="openHistoryResult(item)">打开结果</button>
              <button class="ghost" @click="deleteHistoryItem(item, { removeFile: true })">删除记录与文件</button>
            </div>
          </article>
        </div>
        <div v-if="hasMoreHistory" class="load-more-row">
          <button class="ghost" @click="loadMoreHistory">加载更多</button>
        </div>
      </div>
      <div v-else class="asset-empty-state">
        <span class="asset-empty-icon" aria-hidden="true">◷</span>
        <strong>还没有渲染历史</strong>
        <p>完成一次绘图后，记录会出现在这里。</p>
      </div>
    </div>

    <div v-else class="asset-page-card">
      <div class="section-head asset-page-head">
        <div>
          <span class="section-kicker">资产管理 · 02</span>
          <h2>渲染文件</h2>
          <p class="section-subtitle">管理本机保存的图像文件，可预览、打开或删除。</p>
        </div>
        <div class="btn-row">
          <button class="ghost" :disabled="renderFilesLoading" @click="fetchRenderFiles">刷新文件</button>
          <button class="ghost" :disabled="renderFilesLoading || !renderFiles.length" @click="clearRenderHistoryAndLocalFiles">清空本地文件</button>
        </div>
      </div>

      <p v-if="renderFilesLoading" class="muted">正在读取本地渲染文件...</p>
      <div v-else-if="renderFiles.length" ref="renderFilesScrollRef" class="render-files-scroll" @scroll="onRenderFilesScroll">
        <div class="render-files-list">
          <article v-for="file in visibleRenderFiles" :key="file.filename" class="render-file-item">
            <div class="render-file-meta">
              <div class="render-file-name-row">
                <strong>{{ file.filename }}</strong>
                <span class="file-type-badge">{{ renderFileTypeBadge(file) }}</span>
              </div>
              <span>{{ renderFileTypeLabel(file) }} · {{ formatFileSize(file.size) }} · {{ formatHistoryTime(file.modified_at) }}</span>
            </div>
            <div class="render-file-actions">
              <button class="ghost" @click="openRenderFileItem(file)">打开</button>
              <button v-if="renderFilePreviewType(file) === 'pdf'" class="ghost" @click="openRenderFileInNewWindow(file)">新窗口</button>
              <button class="ghost" @click="deleteRenderFileItem(file)">删除</button>
            </div>
          </article>
        </div>
        <div v-if="hasMoreRenderFiles" class="load-more-row">
          <button class="ghost" @click="loadMoreRenderFiles">加载更多</button>
        </div>
      </div>
      <div v-else class="asset-empty-state">
        <span class="asset-empty-icon" aria-hidden="true">▧</span>
        <strong>还没有渲染文件</strong>
        <p>绘图导出后，文件会集中保存在这里。</p>
      </div>
    </div>
  </section>
</template>
