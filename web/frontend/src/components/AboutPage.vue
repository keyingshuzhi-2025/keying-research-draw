<script setup>
import { computed, ref } from "vue";
import { useResearchDrawStore } from "../composables/useResearchDrawStore";
import { APP_VERSION } from "../version.js";

const store = useResearchDrawStore();
const {
  TOOL_NAME,
  ABOUT_FEATURES,
  contactLoading,
  fetchContactAssets,
  openMainView,
  aboutOverview,
  aboutPlotCatalog,
  renderDemoForPlot,
  rendering,
  contactError,
  contactAssets,
  apiUrl
} = store;

const catalogSearch = ref("");
const visiblePlotCatalog = computed(() => {
  const query = catalogSearch.value.trim().toLocaleLowerCase();
  if (!query) return aboutPlotCatalog.value;
  return aboutPlotCatalog.value
    .map((group) => ({
      ...group,
      plots: group.plots.filter((plot) =>
        `${plot.label} ${plot.key} ${plot.description} ${group.title}`.toLocaleLowerCase().includes(query)
      )
    }))
    .filter((group) => group.plots.length);
});
</script>

<template>
  <section class="panel page-card about-page">
    <div class="page-hero about-hero">
      <div class="page-hero-copy">
        <span class="page-eyebrow">ABOUT · 科研绘图工作台</span>
        <div class="about-title-line">
          <h2>{{ TOOL_NAME }}</h2>
          <span class="about-version-badge">{{ APP_VERSION }}</span>
        </div>
        <p>面向科研数据分析的绘图工具，支持从数据整理、图型选择、样式配置到结果导出的完整流程。</p>
      </div>
      <button class="primary page-hero-action" @click="openMainView('workspace')">
        开始绘图 <span aria-hidden="true">→</span>
      </button>
    </div>

    <div class="about-overview-grid">
      <article v-for="item in aboutOverview" :key="item.label" class="overview-item">
        <span class="overview-label">{{ item.label }}</span>
        <strong class="overview-value">{{ item.value }}</strong>
      </article>
    </div>

    <div class="about-feature-block">
      <div class="content-heading">
        <div>
          <span class="section-kicker">工作流能力</span>
          <h3>从数据到结果，一处完成</h3>
        </div>
      </div>
      <div class="about-feature-grid">
        <article v-for="(item, index) in ABOUT_FEATURES" :key="item.title" class="feature-item">
          <span class="feature-index">{{ String(index + 1).padStart(2, "0") }}</span>
          <h4>{{ item.title }}</h4>
          <p>{{ item.content }}</p>
        </article>
      </div>
    </div>

    <div class="about-plot-catalog">
      <div class="content-heading catalog-heading">
        <div>
          <span class="section-kicker">图型库</span>
          <h3>找到适合你的表达方式</h3>
          <p class="muted">图型名称和工作区保持同步。打开示例即可查看默认样式。</p>
        </div>
        <label class="catalog-search-field">
          <span aria-hidden="true">⌕</span>
          <input v-model="catalogSearch" type="search" aria-label="搜索图型目录" placeholder="搜索图型或用途" />
        </label>
      </div>

      <div v-if="visiblePlotCatalog.length" class="plot-catalog-grid">
        <article v-for="group in visiblePlotCatalog" :key="group.key" class="plot-group-card">
          <div class="plot-group-head">
            <div>
              <h4>{{ group.title }}</h4>
              <p>{{ group.description }}</p>
            </div>
            <span class="plot-count">{{ group.plots.length }} 种</span>
          </div>
          <p class="plot-group-scene">适用场景：{{ group.scene }}</p>
          <div class="plot-demo-list">
            <article v-for="plot in group.plots" :key="`${group.key}-${plot.key}`" class="plot-demo-item">
              <div class="plot-demo-title">
                <strong>{{ plot.label }}</strong>
                <code>{{ plot.key }}</code>
              </div>
              <p>{{ plot.description }}</p>
              <button
                class="plot-demo-button"
                :disabled="rendering"
                :aria-label="`运行${plot.label}示例`"
                @click="renderDemoForPlot(plot.key)"
              >
                运行示例 <span aria-hidden="true">→</span>
              </button>
            </article>
          </div>
        </article>
      </div>
      <p v-else class="catalog-empty">没有找到匹配的图型，试试“折线”“地图”或类型代码。</p>
    </div>

    <div class="contact-block">
      <div class="content-heading">
        <div>
          <span class="section-kicker">联系与交流</span>
          <h3>联系方式</h3>
          <p class="muted">关注项目动态或加入用户交流。</p>
        </div>
        <button class="ghost" :disabled="contactLoading" @click="fetchContactAssets(true)">
          {{ contactLoading ? "刷新中…" : "刷新联系方式" }}
        </button>
      </div>
      <p v-if="contactLoading" class="muted contact-state">正在加载联系方式…</p>
      <p v-else-if="contactError" class="msg error contact-state">{{ contactError }}</p>
      <div v-else-if="contactAssets.length" class="contact-grid">
        <article v-for="item in contactAssets" :key="item.url" class="contact-item">
          <img :src="apiUrl(item.url)" :alt="item.displayName || item.name || '联系方式二维码'" />
          <span>{{ item.displayName || item.name || "联系方式" }}</span>
        </article>
      </div>
      <p v-else class="muted contact-state">暂未配置联系方式。</p>
    </div>
  </section>
</template>
