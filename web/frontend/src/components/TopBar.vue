<script setup>
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

const store = useResearchDrawStore();
const {
  mainView,
  healthStatus,
  healthText,
  renderMode,
  fmt,
  rendering,
  renderImage
} = store;
</script>

<template>
  <header class="topbar">
    <div class="topbar-context">
      <span>RESEARCH DRAW · ATLAS</span>
      <strong>{{ mainView === "workspace" ? "绘图工作区" : mainView === "home" ? "首页" : "用户手册" }}</strong>
    </div>

    <div class="topbar-right">
      <div class="topbar-health" :title="healthText" role="status">
        <span :class="['health-indicator', healthStatus]"></span>
        <span>{{ healthText }}</span>
      </div>
      <div v-if="mainView === 'workspace'" class="top-actions">
        <label class="compact-field">
          <span>模式</span>
          <select v-model="renderMode">
            <option value="file">文件数据</option>
            <option value="demo">演示示例</option>
          </select>
        </label>
        <label class="compact-field">
          <span>格式</span>
          <select v-model="fmt">
            <option value="png">png</option>
            <option value="svg">svg</option>
            <option value="pdf">pdf</option>
          </select>
        </label>
        <button class="primary top-render-btn" :disabled="rendering" @click="renderImage()">
          {{ rendering ? "渲染中..." : "渲染图像" }}
        </button>
      </div>
    </div>
  </header>
</template>
