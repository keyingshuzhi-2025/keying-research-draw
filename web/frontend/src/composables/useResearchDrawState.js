import { computed, reactive, ref } from "vue";

export function useResearchDrawState() {
  const TOOL_NAME = "柯影智绘 Atlas";
  const TOOL_SUBTITLE = "科研绘图工作台";

  const GROUP_ORDER = ["stats_2d", "domain_2d", "plots_3d", "maps"];

  const PLOT_DISPLAY_NAMES = {
    box: "箱线图",
    violin: "小提琴图",
    scatter: "散点回归图",
    bar: "横向条形图",
    column: "纵向柱状图",
    line: "折线图",
    histogram: "直方图",
    area: "面积图",
    volcano: "火山图",
    forest: "森林图",
    ma: "MA 均值-差异图",
    enrich_dot: "富集气泡图",
    gsea: "GSEA 富集曲线",
    embedding: "降维散点图（PCA/UMAP）",
    upset: "UpSet 集合交集图",
    km: "Kaplan–Meier 生存曲线",
    roc: "ROC/PR 评估曲线",
    calibration: "概率校准曲线",
    bland_altman: "Bland–Altman 一致性图",
    dca: "决策曲线分析图",
    stress_strain: "应力-应变曲线",
    xrd: "X 射线衍射图（XRD）",
    raman: "拉曼/红外光谱图",
    phase: "材料相图",
    hysteresis: "磁滞/滞回曲线",
    spectral_signature: "遥感光谱特征曲线",
    index_ts: "遥感指数时序图",
    confusion: "分类混淆矩阵",
    class_dist: "地物类别分布图",
    candlestick: "金融 K 线图",
    cum_return: "累计收益与回撤图",
    rolling_stats: "滚动统计图",
    frontier: "投资组合有效前沿图",
    acf_pacf: "自相关/偏自相关图",
    likert: "Likert 量表分布图",
    raincloud: "雨云分布图",
    irt_icc: "IRT 项目特征曲线（ICC）",
    factor_loadings: "因子载荷图",
    interaction: "交互效应图",
    scatter3d: "三维散点图",
    surface3d: "三维曲面图",
    wireframe3d: "三维线框图",
    contour3d: "三维等高线图",
    line3d: "三维轨迹图",
    isosurface3d: "三维等值面图",
    slice3d: "三维正交切片图",
    quiver3d: "三维矢量场图",
    waterfall3d: "三维瀑布图",
    embedding3d: "三维降维图",
    mesh3d: "三维网格图",
    world: "世界底图",
    world_admin1: "世界一级行政区图",
    china: "中国行政区底图",
    choropleth_world: "世界分级设色地图",
    choropleth_china: "中国分级设色地图",
    raster: "栅格影像叠加图",
    points: "地图点位分布图"
  };

  const GROUP_META_FALLBACK = {
    stats_2d: {
      label: "统计二维",
      description: "通用统计分析图型，适用于实验比较与相关分析。",
      scene: "实验组比较、差异分析、相关性分析",
      order: 10
    },
    domain_2d: {
      label: "学科二维",
      description: "生物、临床、材料、遥感、金融、心理等领域科研图型。",
      scene: "生信分析、临床评估、材料表征、遥感与金融时序",
      order: 20
    },
    plots_3d: {
      label: "三维图型",
      description: "科研常用三维可视化图型，支持轨迹、曲面、向量场等。",
      scene: "三维结构展示、体数据分析、向量场分析",
      order: 30
    },
    maps: {
      label: "地理地图",
      description: "离线地图绘图，支持底图、分级着色、栅格与点位叠加。",
      scene: "全球/中国空间分布、区域分级、点位与栅格叠加",
      order: 40
    }
  };

  const ABOUT_FEATURES = [
    {
      title: "数据输入",
      content: "支持上传 CSV/TSV/TXT/Excel 文件，或直接在页面表格录入并保存为数据集。"
    },
    {
      title: "智能字段匹配",
      content: "自动识别列名并映射常用字段（x/y/z、group/value、经纬度等），减少手工配置。"
    },
    {
      title: "常用二维图型",
      content: "包含条形图、柱状图、折线图、直方图、面积图，以及箱线图、散点回归图等统计图。"
    },
    {
      title: "每种图型都有演示",
      content: "全部已登记图型都提供内置 Demo，点选即可快速查看效果。"
    },
    {
      title: "结果与文件管理",
      content: "支持渲染历史复用、上传文件管理、本地渲染文件管理与一键清理。"
    },
    {
      title: "项目资料与帮助",
      content: "在设置弹窗中查看项目介绍、用户手册与联系方式，集中查阅项目资料。"
    }
  ];

  const FILE_TYPE_META = {
    png: { short: "PNG", long: "PNG 图片" },
    jpg: { short: "JPG", long: "JPG 图片" },
    jpeg: { short: "JPEG", long: "JPEG 图片" },
    webp: { short: "WEBP", long: "WEBP 图片" },
    gif: { short: "GIF", long: "GIF 图片" },
    bmp: { short: "BMP", long: "BMP 图片" },
    svg: { short: "SVG", long: "SVG 矢量图" },
    pdf: { short: "PDF", long: "PDF 文档" }
  };

  const FIELD_LABELS = {
    group_col: "分组列 (group_col)",
    value_col: "数值列 (value_col)",
    x_col: "X 列 (x_col)",
    y_col: "Y 列 (y_col)",
    z_col: "Z 列 (z_col)",
    u_col: "U 列 (u_col)",
    v_col: "V 列 (v_col)",
    w_col: "W 列 (w_col)",
    scalar_col: "标量列 (scalar_col)",
    label_col: "标签列 (label_col)",
    log2fc_col: "log2FC 列 (log2fc_col)",
    p_col: "P 值列 (p_col)",
    forest_label_col: "标签列 (forest_label_col)",
    effect_col: "效应量列 (effect_col)",
    ci_low_col: "CI 下限列 (ci_low_col)",
    ci_high_col: "CI 上限列 (ci_high_col)",
    key_col: "键列 (key_col)",
    lon_col: "经度列 (lon_col)",
    lat_col: "纬度列 (lat_col)"
  };

  const BASE_FIELDS = ["x_col", "y_col", "z_col", "group_col", "value_col", "label_col"];

  const FIELD_SUGGEST = {
    x_col: ["x", "x_col", "time", "date"],
    y_col: ["y", "y_col", "value", "score"],
    z_col: ["z", "z_col", "depth", "height"],
    group_col: ["group", "class", "category", "type"],
    value_col: ["value", "val", "count", "amount", "intensity"],
    label_col: ["label", "name", "id"],
    log2fc_col: ["log2fc", "logfc", "fc"],
    p_col: ["p", "pvalue", "p_val", "p_value"],
    forest_label_col: ["study", "label", "name"],
    effect_col: ["effect", "estimate", "beta"],
    ci_low_col: ["ci_low", "lower", "lcl"],
    ci_high_col: ["ci_high", "upper", "ucl"],
    key_col: ["key", "region", "name", "code"],
    lon_col: ["lon", "lng", "longitude"],
    lat_col: ["lat", "latitude"],
    u_col: ["u"],
    v_col: ["v"],
    w_col: ["w"],
    scalar_col: ["scalar", "density", "value"]
  };

  const DYNAMIC_ARG_DEFS = {
    bar: [
      { key: "aggregation", label: "重复类别汇总 (aggregation)", type: "select", default: "mean", options: ["mean", "median", "sum"] },
      { key: "group_mode", label: "分组显示 (group_mode)", type: "select", default: "grouped", options: ["grouped", "stacked"] },
      { key: "show_values", label: "显示数值 (show_values)", type: "bool", default: false },
      { key: "tick_rotation", label: "分类标签旋转角度", type: "number", step: 15, default: 0 },
      { key: "palette", label: "配色方案 (palette)", type: "select", default: "tab10", options: ["tab10", "Set2", "Dark2", "Paired", "viridis"] },
      { key: "grid", label: "显示网格线 (grid)", type: "bool", default: true, sendFalse: true }
    ],
    column: [
      { key: "aggregation", label: "重复类别汇总 (aggregation)", type: "select", default: "mean", options: ["mean", "median", "sum"] },
      { key: "group_mode", label: "分组显示 (group_mode)", type: "select", default: "grouped", options: ["grouped", "stacked"] },
      { key: "show_values", label: "显示数值 (show_values)", type: "bool", default: false },
      { key: "tick_rotation", label: "分类标签旋转角度", type: "number", step: 15, default: 0 },
      { key: "palette", label: "配色方案 (palette)", type: "select", default: "tab10", options: ["tab10", "Set2", "Dark2", "Paired", "viridis"] },
      { key: "grid", label: "显示网格线 (grid)", type: "bool", default: true, sendFalse: true }
    ],
    line: [
      { key: "aggregation", label: "重复 X 值汇总 (aggregation)", type: "select", default: "mean", options: ["mean", "median", "sum"] },
      { key: "marker", label: "数据点标记 (marker)", type: "select", default: "o", options: ["o", "s", "^", "D", ""] },
      { key: "line_width", label: "线宽 (line_width)", type: "number", min: 0.1, step: 0.1, default: 2 },
      { key: "palette", label: "配色方案 (palette)", type: "select", default: "tab10", options: ["tab10", "Set2", "Dark2", "Paired", "viridis"] },
      { key: "grid", label: "显示网格线 (grid)", type: "bool", default: true, sendFalse: true }
    ],
    histogram: [
      { key: "bins", label: "分箱数 (bins)", type: "number", min: 1, step: 1, default: 20 },
      { key: "density", label: "显示概率密度 (density)", type: "bool", default: false },
      { key: "hist_alpha", label: "填充透明度", type: "number", min: 0.05, max: 1, step: 0.05, default: 0.68 },
      { key: "palette", label: "配色方案 (palette)", type: "select", default: "tab10", options: ["tab10", "Set2", "Dark2", "Paired", "viridis"] },
      { key: "grid", label: "显示网格线 (grid)", type: "bool", default: true, sendFalse: true }
    ],
    area: [
      { key: "aggregation", label: "重复 X 值汇总 (aggregation)", type: "select", default: "mean", options: ["mean", "median", "sum"] },
      { key: "stacked", label: "堆叠面积 (stacked)", type: "bool", default: false },
      { key: "area_alpha", label: "填充透明度", type: "number", min: 0.05, max: 1, step: 0.05, default: 0.28 },
      { key: "palette", label: "配色方案 (palette)", type: "select", default: "tab10", options: ["tab10", "Set2", "Dark2", "Paired", "viridis"] },
      { key: "grid", label: "显示网格线 (grid)", type: "bool", default: true, sendFalse: true }
    ],
    scatter: [
      { key: "ci", label: "置信区间 (ci)", type: "number", min: 0, max: 1, step: 0.01, default: 0.95 },
      { key: "equal", label: "等比例坐标 (equal)", type: "bool", default: false }
    ],
    volcano: [
      { key: "fc_thresh", label: "FC 阈值 (fc_thresh)", type: "number", min: 0, step: 0.1, default: 1.0 },
      { key: "p_thresh", label: "P 阈值 (p_thresh)", type: "number", min: 0, max: 1, step: 0.01, default: 0.05 },
      { key: "top_n", label: "标注前 N 个点 (top_n)", type: "number", min: 0, step: 1, default: 10 }
    ],
    forest: [{ key: "ref_line", label: "参考线位置 (ref_line)", type: "number", step: 0.1, default: 0.0 }],
    surface3d: [
      { key: "elev", label: "仰角 (elev)", type: "number", step: 1, default: "" },
      { key: "azim", label: "方位角 (azim)", type: "number", step: 1, default: "" }
    ],
    wireframe3d: [
      { key: "rstride", label: "行步长 (rstride)", type: "number", min: 1, step: 1, default: 2 },
      { key: "cstride", label: "列步长 (cstride)", type: "number", min: 1, step: 1, default: 2 },
      { key: "elev", label: "仰角 (elev)", type: "number", step: 1, default: "" },
      { key: "azim", label: "方位角 (azim)", type: "number", step: 1, default: "" }
    ],
    contour3d: [
      { key: "levels", label: "等高层数 (levels)", type: "number", min: 3, step: 1, default: 18 },
      { key: "elev", label: "仰角 (elev)", type: "number", step: 1, default: "" },
      { key: "azim", label: "方位角 (azim)", type: "number", step: 1, default: "" }
    ],
    line3d: [
      { key: "elev", label: "仰角 (elev)", type: "number", step: 1, default: "" },
      { key: "azim", label: "方位角 (azim)", type: "number", step: 1, default: "" }
    ],
    quiver3d: [
      { key: "max_arrows", label: "最大箭头数 (max_arrows)", type: "number", min: 1, step: 1, default: 600 },
      { key: "elev", label: "仰角 (elev)", type: "number", step: 1, default: "" },
      { key: "azim", label: "方位角 (azim)", type: "number", step: 1, default: "" }
    ],
    isosurface3d: [{ key: "iso_level", label: "等值面阈值 (iso_level)", type: "number", step: 0.1, default: "" }],
    slice3d: [
      { key: "slice_x", label: "切片 X 位置 (slice_x)", type: "number", step: 0.1, default: "" },
      { key: "slice_y", label: "切片 Y 位置 (slice_y)", type: "number", step: 0.1, default: "" },
      { key: "slice_z", label: "切片 Z 位置 (slice_z)", type: "number", step: 0.1, default: "" }
    ],
    choropleth_world: [
      {
        key: "scheme",
        label: "分级方案 (scheme)",
        type: "select",
        default: "quantiles",
        options: [
          { value: "quantiles", label: "quantiles" },
          { value: "equal", label: "equal" },
          { value: "natural", label: "natural" }
        ]
      },
      { key: "k", label: "分级数 (k)", type: "number", min: 2, max: 9, step: 1, default: 5 }
    ],
    choropleth_china: [
      {
        key: "scheme",
        label: "分级方案 (scheme)",
        type: "select",
        default: "quantiles",
        options: [
          { value: "quantiles", label: "quantiles" },
          { value: "equal", label: "equal" },
          { value: "natural", label: "natural" }
        ]
      },
      { key: "k", label: "分级数 (k)", type: "number", min: 2, max: 9, step: 1, default: 5 }
    ],
    raster: [{ key: "alpha", label: "栅格透明度 (alpha)", type: "number", min: 0, max: 1, step: 0.05, default: 0.65 }],
    calibration: [
      { key: "n_bins", label: "分箱数 (n_bins)", type: "number", min: 2, step: 1, default: 10 },
      {
        key: "calib_strategy",
        label: "分箱策略 (calib_strategy)",
        type: "select",
        default: "uniform",
        options: [
          { value: "uniform", label: "uniform" },
          { value: "quantile", label: "quantile" }
        ]
      }
    ],
    rolling_stats: [{ key: "window", label: "滚动窗口 (window)", type: "number", min: 2, step: 1, default: 20 }],
    acf_pacf: [{ key: "lags", label: "滞后阶数 (lags)", type: "number", min: 1, step: 1, default: 40 }]
  };

  const RENDER_HISTORY_KEY = "kydz_research_draw_history_v1";
  const RENDER_HISTORY_LIMIT = 20;

  const sectionDefs = [
    { id: "section-data", key: "data", title: "数据输入", icon: "D" },
    { id: "section-plot", key: "plot", title: "图型选择", icon: "P" },
    { id: "section-figure", key: "figure", title: "图形设置", icon: "F" },
    { id: "section-result", key: "result", title: "渲染结果", icon: "R" }
  ];

  const HISTORY_BATCH_SIZE = 8;
  const RENDER_FILES_BATCH_SIZE = 10;

  const apiBase = ref("http://127.0.0.1:8000");
  const healthStatus = ref("unknown");
  const healthText = computed(() => (healthStatus.value === "ok" ? "后端在线" : healthStatus.value === "down" ? "后端离线" : "状态未知"));

  const plotsByGroup = ref({});
  const plotRegistry = ref({});
  const groupMeta = ref({ ...GROUP_META_FALLBACK });
  const selectedGroup = ref("stats_2d");
  const selectedPlot = ref("box");
  const renderMode = ref("file");
  const fmt = ref("png");

  const dataSourceMode = ref("upload");
  const pickedFile = ref(null);
  const uploadedFileId = ref("");
  const uploadedFileName = ref("");
  const uploadColumns = ref([]);
  const previewRows = ref([]);
  const fileInputRef = ref(null);

  const tableHeaders = ref(["x", "y", "z"]);
  const tableRows = ref(Array.from({ length: 8 }, () => ["", "", ""]));

  const mappings = reactive({
    group_col: "",
    value_col: "",
    x_col: "",
    y_col: "",
    z_col: "",
    u_col: "",
    v_col: "",
    w_col: "",
    scalar_col: "",
    label_col: "",
    log2fc_col: "",
    p_col: "",
    forest_label_col: "",
    effect_col: "",
    ci_low_col: "",
    ci_high_col: "",
    key_col: "",
    lon_col: "",
    lat_col: ""
  });

  const figure = reactive({
    title: "",
    xlabel: "",
    ylabel: "",
    zlabel: ""
  });

  const extraArgsText = ref("{}");
  const imageUrl = ref("");
  const resultPreviewType = ref("image");
  const resultFileName = ref("");
  const currentResultFmt = ref("");
  const lastSaveName = ref("");
  const messageOk = ref("");
  const messageErr = ref("");
  const rendering = ref(false);
  const renderProgress = ref(0);
  const renderStatusText = ref("");
  const lastFailedPayload = ref(null);
  const currentTaskId = ref("");
  const renderHistory = ref([]);
  const uploadFiles = ref([]);
  const renderFiles = ref([]);
  const uploadFilesLoading = ref(false);
  const renderFilesLoading = ref(false);
  const historyVisibleCount = ref(HISTORY_BATCH_SIZE);
  const renderFilesVisibleCount = ref(RENDER_FILES_BATCH_SIZE);
  const historyScrollRef = ref(null);
  const renderFilesScrollRef = ref(null);

  const activeMenu = ref("");
  const menuWrapRef = ref(null);
  const activeSection = ref("data");
  const mainView = ref("home");
  const contactAssets = ref([]);
  const contactLoading = ref(false);
  const contactError = ref("");
  const contactLoaded = ref(false);
  const manualTitle = ref("用户手册页面");
  const manualText = ref("");
  const manualLoading = ref(false);
  const manualError = ref("");
  const manualLoaded = ref(false);

  function buildDynamicArgDefaults() {
    const defaults = {};
    for (const defs of Object.values(DYNAMIC_ARG_DEFS)) {
      for (const def of defs) {
        if (!(def.key in defaults)) {
          if (def.type === "bool") defaults[def.key] = Boolean(def.default);
          else defaults[def.key] = def.default ?? "";
        }
      }
    }
    return defaults;
  }

  const dynamicArgs = reactive(buildDynamicArgDefaults());

  function fallbackDefaultForDef(def) {
    if (def.type === "bool") return Boolean(def.default);
    return def.default ?? "";
  }

  function applyRegistryDefaultsToDynamicArgs() {
    for (const [plotName, defs] of Object.entries(DYNAMIC_ARG_DEFS)) {
      const specDefaults = plotRegistry.value?.[plotName]?.defaults;
      if (!specDefaults || typeof specDefaults !== "object") continue;
      for (const def of defs) {
        if (!(def.key in specDefaults)) continue;
        const fallback = fallbackDefaultForDef(def);
        const current = dynamicArgs[def.key];
        if (current === fallback || current === "" || current === null || typeof current === "undefined") {
          dynamicArgs[def.key] = specDefaults[def.key];
        }
      }
    }
  }

  const orderedGroups = computed(() => {
    const keys = Object.keys(plotsByGroup.value || {});
    const meta = groupMeta.value || {};
    const byMeta = keys.slice().sort((a, b) => {
      const ao = Number(meta[a]?.order ?? 999);
      const bo = Number(meta[b]?.order ?? 999);
      return ao - bo;
    });
    const preferred = GROUP_ORDER.filter((k) => keys.includes(k));
    const orderedByMeta = byMeta.filter((k) => !preferred.includes(k));
    const rest = keys.filter((k) => !preferred.includes(k));
    return [...preferred, ...orderedByMeta, ...rest.filter((k) => !orderedByMeta.includes(k))];
  });

  const plotsInSelectedGroup = computed(() => plotsByGroup.value[selectedGroup.value] || []);
  const requiredFields = computed(() => plotRegistry.value[selectedPlot.value]?.required_fields || []);
  const missingRequiredFields = computed(() => requiredFields.value.filter((k) => !(String(mappings[k] || "").trim())));
  const visibleMappingFields = computed(() => {
    const required = requiredFields.value;
    const merged = [...required, ...BASE_FIELDS];
    const unique = [];
    for (const key of merged) {
      if (!unique.includes(key)) unique.push(key);
    }
    return unique.map((k) => ({ key: k, label: FIELD_LABELS[k] || k }));
  });

  const activeDynamicArgDefs = computed(() => DYNAMIC_ARG_DEFS[selectedPlot.value] || []);
  function plotDisplayName(plotKey) {
    return plotRegistry.value?.[plotKey]?.display_name || PLOT_DISPLAY_NAMES[plotKey] || plotKey;
  }

  function plotDescription(plotKey) {
    return plotRegistry.value?.[plotKey]?.description || "可从内置 Demo 查看此图型的示例。";
  }

  const visibleRenderHistory = computed(() => renderHistory.value.slice(0, historyVisibleCount.value));
  const hasMoreHistory = computed(() => historyVisibleCount.value < renderHistory.value.length);
  const visibleRenderFiles = computed(() => renderFiles.value.slice(0, renderFilesVisibleCount.value));
  const hasMoreRenderFiles = computed(() => renderFilesVisibleCount.value < renderFiles.value.length);

  const aboutPlotCatalog = computed(() => {
    const source = plotsByGroup.value || {};
    const meta = groupMeta.value || {};
    const keys = Object.keys(source);
    const ordered = [...GROUP_ORDER.filter((k) => keys.includes(k)), ...keys.filter((k) => !GROUP_ORDER.includes(k))];
    return ordered.map((groupKey) => {
      const plots = Array.isArray(source[groupKey]) ? source[groupKey] : [];
      return {
        key: groupKey,
        title: meta[groupKey]?.label || GROUP_META_FALLBACK[groupKey]?.label || groupKey,
        description: meta[groupKey]?.description || GROUP_META_FALLBACK[groupKey]?.description || "科研图型分组",
        scene: meta[groupKey]?.scene || GROUP_META_FALLBACK[groupKey]?.scene || "科研可视化分析",
        plots: plots.map((key) => ({
          key,
          label: plotDisplayName(key),
          description: plotDescription(key)
        }))
      };
    });
  });

  const aboutOverview = computed(() => {
    const groups = aboutPlotCatalog.value.length;
    const totalPlots = aboutPlotCatalog.value.reduce((sum, group) => sum + group.plots.length, 0);
    return [
      { label: "图型分组", value: `${groups} 类` },
      { label: "可绘制图型", value: `${totalPlots} 种` },
      { label: "内置演示", value: `${totalPlots} 种` },
      { label: "数据输入", value: "文件上传 + 表格录入" },
      { label: "输出格式", value: "PNG / SVG / PDF" },
      { label: "开源许可", value: "MIT" }
    ];
  });

  const sectionStatus = computed(() => ({
    data: uploadedFileId.value ? "ready" : "pending",
    plot: selectedPlot.value ? "ready" : "pending",
    figure: "ready",
    result: imageUrl.value ? "ready" : "pending"
  }));

  return {
    TOOL_NAME,
    TOOL_SUBTITLE,
    GROUP_ORDER,
    GROUP_META_FALLBACK,
    PLOT_DISPLAY_NAMES,
    ABOUT_FEATURES,
    FILE_TYPE_META,
    FIELD_LABELS,
    BASE_FIELDS,
    FIELD_SUGGEST,
    DYNAMIC_ARG_DEFS,
    RENDER_HISTORY_KEY,
    RENDER_HISTORY_LIMIT,
    sectionDefs,
    HISTORY_BATCH_SIZE,
    RENDER_FILES_BATCH_SIZE,
    apiBase,
    healthStatus,
    healthText,
    plotsByGroup,
    plotRegistry,
    groupMeta,
    selectedGroup,
    selectedPlot,
    renderMode,
    fmt,
    dataSourceMode,
    pickedFile,
    uploadedFileId,
    uploadedFileName,
    uploadColumns,
    previewRows,
    fileInputRef,
    tableHeaders,
    tableRows,
    mappings,
    figure,
    extraArgsText,
    imageUrl,
    resultPreviewType,
    resultFileName,
    currentResultFmt,
    lastSaveName,
    messageOk,
    messageErr,
    rendering,
    renderProgress,
    renderStatusText,
    lastFailedPayload,
    currentTaskId,
    renderHistory,
    uploadFiles,
    renderFiles,
    uploadFilesLoading,
    renderFilesLoading,
    historyVisibleCount,
    renderFilesVisibleCount,
    historyScrollRef,
    renderFilesScrollRef,
    activeMenu,
    menuWrapRef,
    activeSection,
    mainView,
    contactAssets,
    contactLoading,
    contactError,
    contactLoaded,
    manualTitle,
    manualText,
    manualLoading,
    manualError,
    manualLoaded,
    dynamicArgs,
    orderedGroups,
    plotsInSelectedGroup,
    requiredFields,
    missingRequiredFields,
    visibleMappingFields,
    activeDynamicArgDefs,
    plotDisplayName,
    plotDescription,
    visibleRenderHistory,
    hasMoreHistory,
    visibleRenderFiles,
    hasMoreRenderFiles,
    aboutPlotCatalog,
    aboutOverview,
    sectionStatus,
    applyRegistryDefaultsToDynamicArgs
  };
}
