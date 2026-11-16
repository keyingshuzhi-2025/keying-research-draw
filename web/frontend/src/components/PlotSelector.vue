<script setup>
import { computed, ref } from "vue";
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

const store = useResearchDrawStore();
const {
  orderedGroups,
  selectedGroup,
  selectedPlot,
  groupMeta,
  GROUP_META_FALLBACK,
  rendering,
  plotsInSelectedGroup,
  chooseGroup,
  plotDisplayName,
  plotDescription,
  renderDemoForPlot,
  activeDynamicArgDefs,
  dynamicArgs,
  figure
} = store;

const plotSearch = ref("");
const filteredPlots = computed(() => {
  const query = plotSearch.value.trim().toLocaleLowerCase();
  if (!query) return plotsInSelectedGroup.value;
  return plotsInSelectedGroup.value.filter((plot) => {
    const searchable = `${plotDisplayName(plot)} ${plotDescription(plot)} ${plot}`.toLocaleLowerCase();
    return searchable.includes(query);
  });
});

function selectGroup(group) {
  plotSearch.value = "";
  chooseGroup(group);
}

function optionValue(option) {
  return option && typeof option === "object" ? option.value : option;
}

function optionLabel(option) {
  return option && typeof option === "object" ? option.label : option;
}

function updateOption(def, event) {
  const value = event.target.value;
  if (def.type === "bool") {
    dynamicArgs[def.key] = event.target.checked;
  } else if (def.type === "number") {
    dynamicArgs[def.key] = value === "" ? "" : Number(value);
  } else {
    dynamicArgs[def.key] = value;
  }
}
</script>

<template>
  <section id="section-plot" class="panel section-card plot-section">
    <div class="section-head plot-section-head">
      <div>
        <span class="section-kicker">绘图设置 · 步骤 02—03</span>
        <h2>选择图型并完成设置</h2>
        <p class="section-subtitle">先选择图型，再填写标题与坐标轴信息；图型列表可独立滚动。</p>
      </div>
      <span class="plot-total-badge">{{ plotsInSelectedGroup.length }} 种</span>
    </div>

    <div class="plot-groups" role="tablist" aria-label="图型类别">
      <button
        v-for="group in orderedGroups"
        :key="group"
        role="tab"
        :aria-selected="selectedGroup === group"
        :class="['group-chip', { active: selectedGroup === group }]"
        @click="selectGroup(group)"
      >
        {{ groupMeta[group]?.label || GROUP_META_FALLBACK[group]?.label || group }}
      </button>
    </div>

    <div class="plot-browser">
      <div class="plot-browser-toolbar">
        <label class="plot-search-field">
          <span aria-hidden="true">⌕</span>
          <input v-model="plotSearch" type="search" aria-label="搜索图型" placeholder="搜索中文名称、用途或类型代码" />
        </label>
        <span class="plot-result-count">{{ filteredPlots.length }} / {{ plotsInSelectedGroup.length }}</span>
      </div>

      <div class="plot-option-list" role="listbox" aria-label="可选图型">
        <button
          v-for="plot in filteredPlots"
          :key="plot"
          type="button"
          role="option"
          :aria-selected="selectedPlot === plot"
          :class="['plot-option-button', { selected: selectedPlot === plot }]"
          @click="selectedPlot = plot"
        >
          <span class="plot-option-copy">
            <strong>{{ plotDisplayName(plot) }}</strong>
            <small>{{ plotDescription(plot) }}</small>
          </span>
          <span v-if="selectedPlot === plot" class="plot-option-selected">当前</span>
        </button>
        <p v-if="!filteredPlots.length" class="plot-empty-state">没有找到匹配的图型，请更换关键词。</p>
      </div>
    </div>

    <div class="selected-plot-card">
      <div class="selected-plot-copy">
        <span>当前选择</span>
        <h3>{{ plotDisplayName(selectedPlot) }}</h3>
        <p>{{ plotDescription(selectedPlot) }}</p>
      </div>
      <button class="primary selected-plot-demo" :disabled="rendering" @click="renderDemoForPlot(selectedPlot)">
        {{ rendering ? "正在生成…" : "生成示例图" }}
      </button>
    </div>

    <p class="plot-mode-hint">文件数据模式会自动匹配字段。选择“演示示例”可直接查看图型效果。</p>

    <div v-if="activeDynamicArgDefs.length" class="plot-options">
      <div class="plot-options-heading">
        <div>
          <span class="section-kicker">可选设置</span>
          <h3>图形样式</h3>
        </div>
      </div>
      <div class="plot-options-grid">
        <label
          v-for="def in activeDynamicArgDefs"
          :key="def.key"
          :class="['plot-option-field', { 'plot-option-toggle': def.type === 'bool' }]"
        >
          <template v-if="def.type === 'bool'">
            <input
              type="checkbox"
              :checked="Boolean(dynamicArgs[def.key])"
              @change="updateOption(def, $event)"
            />
            <span>{{ def.label }}</span>
          </template>
          <template v-else>
            <span>{{ def.label }}</span>
            <select
              v-if="def.type === 'select'"
              :value="dynamicArgs[def.key] ?? def.default ?? ''"
              @change="updateOption(def, $event)"
            >
              <option v-for="option in def.options || []" :key="optionValue(option)" :value="optionValue(option)">
                {{ optionLabel(option) }}
              </option>
            </select>
            <input
              v-else
              :type="def.type === 'number' ? 'number' : 'text'"
              :value="dynamicArgs[def.key] ?? def.default ?? ''"
              :min="def.min"
              :max="def.max"
              :step="def.step"
              @input="updateOption(def, $event)"
            />
          </template>
        </label>
      </div>
    </div>

    <div id="section-figure" class="figure-settings-block">
      <div class="figure-settings-heading">
        <div>
          <span class="section-kicker">标注与输出</span>
          <h3>标题与坐标轴</h3>
        </div>
        <p>根据所选图型填写需要显示的标注。</p>
      </div>
      <div class="mapping-grid">
        <label>
          图标题（title）
          <input v-model="figure.title" placeholder="例如：样本结构分析" />
        </label>
        <label>
          X 轴标题（xlabel）
          <input v-model="figure.xlabel" placeholder="例如：Temperature (°C)" />
        </label>
        <label>
          Y 轴标题（ylabel）
          <input v-model="figure.ylabel" placeholder="例如：Intensity" />
        </label>
        <label>
          Z 轴标题（zlabel）
          <input v-model="figure.zlabel" placeholder="例如：Depth" />
        </label>
      </div>
    </div>
  </section>
</template>
