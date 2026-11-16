<script setup>
import brandLockup from "../../../assets/Keying-Atlas-Brand-Kit-v1/02-vector-svg/atlas-lockup-horizontal-for-light.svg";
import { APP_VERSION } from "../version.js";

const emit = defineEmits(["open-workspace", "open-manual"]);

const capabilities = [
  {
    number: "01",
    title: "整理与导入数据",
    description: "从本地文件或内置示例开始，快速完成字段识别与数据准备。",
    icon: "M5 4.5h9l5 5V20H5z M14 4.5V10h5 M8 14h8 M8 17h5"
  },
  {
    number: "02",
    title: "选择合适图型",
    description: "涵盖统计图、学科图、三维图与地理地图，按用途浏览图型。",
    icon: "M4 20V4 M4 20h17 M8 16v-4 M12 16V8 M16 16V5 M20 16v-7"
  },
  {
    number: "03",
    title: "调整图形样式",
    description: "设置标题、坐标轴、配色和图例，让图表重点清楚易读。",
    icon: "M4 6h16 M7 12h10 M10 18h4 M7 3v6 M17 9v6 M12 15v6"
  },
  {
    number: "04",
    title: "预览并导出",
    description: "在独立预览区检查绘制结果，并导出 PNG、SVG 或 PDF。",
    icon: "M12 3v12 M7 10l5 5 5-5 M5 14v5h14v-5"
  }
];

const chartFamilies = [
  { name: "统计二维", detail: "比较、分布与趋势", symbol: "▥" },
  { name: "学科二维", detail: "临床、材料与分析", symbol: "⌁" },
  { name: "三维图型", detail: "结构、曲面与空间", symbol: "◇" },
  { name: "地理地图", detail: "区域、底图与空间数据", symbol: "◎" }
];
</script>

<template>
  <div class="home-page">
    <section class="home-hero">
      <div class="home-hero-copy">
        <div class="home-brand-row">
          <img :src="brandLockup" alt="柯影智绘 Atlas · Research Draw" />
          <span class="home-version">{{ APP_VERSION }}</span>
        </div>
        <span class="home-eyebrow">RESEARCH DRAW · SCIENTIFIC FIGURE STUDIO</span>
        <h1>让科研数据，<br /><span>清晰地表达。</span></h1>
        <p class="home-lede">
          柯影智绘 Atlas 是面向科研工作的绘图工具。从数据准备、图型选择到样式设置与文件导出，
          在一个连贯的工作区里完成图表表达。
        </p>
        <div class="home-actions">
          <button class="primary home-primary-action" @click="emit('open-workspace')">
            开始绘图 <span aria-hidden="true">→</span>
          </button>
          <button class="home-secondary-action" @click="emit('open-manual')">
            查看用户手册 <span aria-hidden="true">↗</span>
          </button>
        </div>
        <div class="home-trust-note">
          <span class="home-status-dot" aria-hidden="true"></span>
          为科研数据分析与图形表达而设计
        </div>
      </div>
      <div class="home-hero-art" aria-hidden="true">
        <div class="home-art-orbit home-art-orbit-one"></div>
        <div class="home-art-orbit home-art-orbit-two"></div>
        <div class="home-art-glow"></div>
        <div class="home-art-card home-art-card-main">
          <div class="home-art-card-head"><span></span><span></span><span></span></div>
          <div class="home-chart-labels"><i></i><i></i><i></i><i></i><i></i></div>
          <svg viewBox="0 0 420 240" role="presentation">
            <defs>
              <linearGradient id="homeChartFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stop-color="#4ec8ba" stop-opacity=".3" />
                <stop offset="1" stop-color="#4ec8ba" stop-opacity="0" />
              </linearGradient>
            </defs>
            <path class="home-chart-grid" d="M42 36h346M42 82h346M42 128h346M42 174h346M42 220h346M42 36v184" />
            <path class="home-chart-area" d="M43 175 C88 166 91 113 137 130 S190 170 229 113 292 120 324 76 365 82 388 44 V220 H43Z" />
            <path class="home-chart-line" d="M43 175 C88 166 91 113 137 130 S190 170 229 113 292 120 324 76 365 82 388 44" />
            <g class="home-chart-points"><circle cx="43" cy="175" r="5"/><circle cx="137" cy="130" r="5"/><circle cx="229" cy="113" r="5"/><circle cx="324" cy="76" r="5"/><circle cx="388" cy="44" r="5"/></g>
          </svg>
          <div class="home-art-axis"><span>数据趋势</span><span>图形预览</span></div>
        </div>
        <div class="home-art-card home-art-card-float">
          <span class="home-float-icon">↗</span>
          <span class="home-float-title">清晰呈现</span>
          <span class="home-float-bars"><i></i><i></i><i></i><i></i><i></i></span>
        </div>
        <span class="home-art-spark home-art-spark-one">✦</span>
        <span class="home-art-spark home-art-spark-two">✧</span>
      </div>
    </section>

    <section class="home-section home-capabilities">
      <div class="home-section-heading">
        <div>
          <span class="home-section-kicker">A CLEARER WORKFLOW</span>
          <h2>从数据到图表，步骤清晰</h2>
        </div>
        <p>把绘图过程拆成易上手的步骤，专注于数据本身和表达效果。</p>
      </div>
      <div class="home-capability-grid">
        <article v-for="item in capabilities" :key="item.number" class="home-capability-card">
          <div class="home-capability-top">
            <span class="home-capability-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path :d="item.icon" /></svg>
            </span>
            <span class="home-capability-number">{{ item.number }}</span>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
        </article>
      </div>
    </section>

    <section class="home-section home-chart-families">
      <div class="home-section-heading">
        <div>
          <span class="home-section-kicker">PLOT LIBRARY</span>
          <h2>覆盖多种科研表达</h2>
        </div>
        <button class="home-text-link" @click="emit('open-workspace')">浏览全部图型 <span aria-hidden="true">→</span></button>
      </div>
      <div class="home-family-grid">
        <article v-for="family in chartFamilies" :key="family.name" class="home-family-card">
          <span class="home-family-symbol" aria-hidden="true">{{ family.symbol }}</span>
          <span class="home-family-copy"><strong>{{ family.name }}</strong><small>{{ family.detail }}</small></span>
          <span class="home-family-arrow" aria-hidden="true">↗</span>
        </article>
      </div>
    </section>

    <footer class="home-footer">
      <span>柯影智绘 Atlas <span aria-hidden="true">·</span> Research Draw</span>
      <span>科研绘图工作台 <i></i> {{ APP_VERSION }}</span>
    </footer>
  </div>
</template>
