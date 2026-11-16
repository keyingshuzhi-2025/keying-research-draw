<script setup>
import { computed, ref } from "vue";
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

const {
  manualTitle,
  manualLoading,
  fetchUserManual,
  openMainView,
  manualError,
  manualHtml,
  manualHeadings
} = useResearchDrawStore();

const searchQuery = ref("");
const activeHeadingId = ref("");
const manualVersion = computed(() => manualHeadings.value[0]?.title.match(/v\d+\.\d+\.\d+/)?.[0] || "");
const visibleHeadings = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase();
  if (!query) return manualHeadings.value;
  return manualHeadings.value.filter((heading) => heading.title.toLocaleLowerCase().includes(query));
});

function jumpToHeading(heading) {
  activeHeadingId.value = heading.id;
  document.getElementById(heading.id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}
</script>

<template>
  <section class="panel page-card manual-page">
    <header class="manual-header">
      <div class="manual-header-copy">
        <span class="page-eyebrow">GUIDE · 操作指南</span>
        <div class="manual-title-line">
          <h2>{{ manualTitle.replace(/页面$/, "") || "用户手册" }}</h2>
          <span v-if="manualVersion" class="manual-version">{{ manualVersion }}</span>
        </div>
        <p>搜索章节，按步骤查看数据准备、图型选择和结果导出说明。</p>
      </div>
      <div class="manual-header-actions">
        <button class="ghost manual-refresh" :disabled="manualLoading" @click="fetchUserManual(true)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 0 0-14.8-3L4 10"/><path d="M4 5v5h5M4 13a8 8 0 0 0 14.8 3L20 14"/><path d="M20 19v-5h-5"/></svg>
          {{ manualLoading ? "刷新中…" : "刷新手册" }}
        </button>
        <button class="primary manual-start" @click="openMainView('workspace')">开始绘图 <span aria-hidden="true">→</span></button>
      </div>
    </header>

    <div v-if="manualLoading" class="manual-state-panel" role="status">
      <span class="manual-loading-mark" aria-hidden="true"></span>
      <strong>正在准备手册</strong>
      <p>正在读取最新的操作说明…</p>
    </div>
    <div v-else-if="manualError" class="manual-error-panel">
      <span class="manual-error-mark" aria-hidden="true">!</span>
      <div><strong>手册暂时无法加载</strong><p>{{ manualError }}</p></div>
      <button class="ghost" @click="fetchUserManual(true)">重新加载</button>
    </div>
    <div v-else class="manual-reader">
      <aside class="manual-toc" aria-label="用户手册目录">
        <div class="manual-toc-header">
          <div class="manual-toc-title-row">
            <div>
              <span class="section-kicker">CONTENTS</span>
              <h3>章节目录</h3>
            </div>
            <span class="manual-count">{{ visibleHeadings.length }} <small>章</small></span>
          </div>
          <label class="manual-search">
            <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>
            <input v-model="searchQuery" type="search" aria-label="搜索手册章节" placeholder="搜索章节标题" />
            <button v-if="searchQuery" type="button" aria-label="清除搜索" @click="searchQuery = ''">×</button>
          </label>
        </div>
        <nav class="manual-toc-list">
          <button
            v-for="(heading, index) in visibleHeadings"
            :key="heading.id"
            type="button"
            :class="['manual-toc-link', `level-${heading.level}`, { active: activeHeadingId === heading.id }]"
            @click="jumpToHeading(heading)"
          >
            <span class="manual-toc-index">{{ String(index + 1).padStart(2, "0") }}</span>
            <span class="manual-toc-text">{{ heading.title }}</span>
            <span class="manual-toc-arrow" aria-hidden="true">›</span>
          </button>
          <p v-if="!visibleHeadings.length" class="manual-toc-empty">没有匹配的章节，试试更短的关键词。</p>
        </nav>
        <div class="manual-toc-foot"><span class="manual-status-dot"></span>版本与项目文档同步</div>
      </aside>

      <article class="manual-card" aria-label="用户手册正文">
        <div class="manual-reading-bar">
          <span><span class="manual-reading-dot"></span>阅读模式</span>
          <span>{{ manualHeadings.length }} 个章节</span>
        </div>
        <div class="manual-markdown" v-html="manualHtml || '<p>暂无手册内容</p>'"></div>
      </article>
    </div>
  </section>
</template>
