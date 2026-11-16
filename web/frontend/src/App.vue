<script setup>
import { computed, nextTick, onMounted, onUnmounted, provide, ref, watch } from "vue";
import AssetManagementPage from "./components/AssetManagementPage.vue";
import AboutPage from "./components/AboutPage.vue";
import HomePage from "./components/HomePage.vue";
import DataInput from "./components/DataInput.vue";
import ManualPage from "./components/ManualPage.vue";
import PlotSelector from "./components/PlotSelector.vue";
import RenderPanel from "./components/RenderPanel.vue";
import TopBar from "./components/TopBar.vue";
import { useResearchDrawState } from "./composables/useResearchDrawState";
import { RESEARCH_DRAW_STORE_KEY } from "./composables/useResearchDrawStore";
import brandMark from "../../assets/Keying-Atlas-Brand-Kit-v1/05-web-favicon/favicon.svg";
import { APP_VERSION } from "./version.js";

const state = useResearchDrawState();
const sidebarCollapsed = ref(false);
const sidebarWidth = ref(288);
const settingsOpen = ref(false);
const settingsPage = ref("basic");
const modalKind = ref("settings");
const assetPage = ref("history");
const SIDEBAR_MIN_WIDTH = 232;
const SIDEBAR_MAX_WIDTH = 368;
const SIDEBAR_DEFAULT_WIDTH = 288;
let sidebarResizeStartX = 0;
let sidebarResizeStartWidth = SIDEBAR_DEFAULT_WIDTH;

const workflowSections = computed(() => sectionDefs.filter((section) => section.key !== "result"));

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value;
  window.localStorage.setItem("research-draw-sidebar-collapsed", String(sidebarCollapsed.value));
}

function setSidebarWidth(width) {
  sidebarWidth.value = Math.max(SIDEBAR_MIN_WIDTH, Math.min(SIDEBAR_MAX_WIDTH, width));
}

function startSidebarResize(event) {
  if (event.button !== 0 || sidebarCollapsed.value) return;
  event.preventDefault();
  sidebarResizeStartX = event.clientX;
  sidebarResizeStartWidth = sidebarWidth.value;
  document.body.classList.add("sidebar-resizing");
  window.addEventListener("pointermove", moveSidebarResize);
  window.addEventListener("pointerup", stopSidebarResize, { once: true });
  window.addEventListener("pointercancel", stopSidebarResize, { once: true });
}

function moveSidebarResize(event) {
  setSidebarWidth(sidebarResizeStartWidth + event.clientX - sidebarResizeStartX);
}

function stopSidebarResize() {
  window.removeEventListener("pointermove", moveSidebarResize);
  window.removeEventListener("pointerup", stopSidebarResize);
  window.removeEventListener("pointercancel", stopSidebarResize);
  document.body.classList.remove("sidebar-resizing");
  window.localStorage.setItem("research-draw-sidebar-width", String(sidebarWidth.value));
}

function handleSidebarResizeKeydown(event) {
  if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault();
    setSidebarWidth(sidebarWidth.value + (event.key === "ArrowRight" ? 12 : -12));
  } else if (event.key === "Home") {
    event.preventDefault();
    setSidebarWidth(SIDEBAR_MIN_WIDTH);
  } else if (event.key === "End") {
    event.preventDefault();
    setSidebarWidth(SIDEBAR_MAX_WIDTH);
  }
  window.localStorage.setItem("research-draw-sidebar-width", String(sidebarWidth.value));
}

function resetSidebarWidth() {
  setSidebarWidth(SIDEBAR_DEFAULT_WIDTH);
  window.localStorage.setItem("research-draw-sidebar-width", String(sidebarWidth.value));
}

const {
  TOOL_NAME,
  TOOL_SUBTITLE,
  GROUP_META_FALLBACK,
  ABOUT_FEATURES,
  FILE_TYPE_META,
  FIELD_LABELS,
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
  plotDisplayName,
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
  activeDynamicArgDefs,
  visibleRenderHistory,
  hasMoreHistory,
  visibleRenderFiles,
  hasMoreRenderFiles,
  aboutPlotCatalog,
  aboutOverview,
  sectionStatus,
  applyRegistryDefaultsToDynamicArgs
} = state;

let renderProgressTimer = null;
const settingsActionLoading = ref("");
const settingsActionMessage = ref("");
const settingsActionTone = ref("info");

function escapeHtml(raw) {
  return String(raw ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttr(raw) {
  return escapeHtml(raw);
}

function parseInlineMarkdown(text) {
  let out = escapeHtml(text);

  const codeTokens = [];
  out = out.replace(/`([^`]+)`/g, (_m, code) => {
    const token = `@@CODETOKEN${codeTokens.length}@@`;
    codeTokens.push(`<code>${code}</code>`);
    return token;
  });

  out = out.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)/g, (_m, label, href, title) => {
    const hrefText = String(href || "").replace(/&amp;/g, "&");
    const safeHref = /^(https?:\/\/|\/|#)/i.test(hrefText) ? href : "#";
    const safeTitle = title ? ` title="${escapeAttr(title)}"` : "";
    const extAttrs = /^https?:\/\//i.test(hrefText) ? ' target="_blank" rel="noopener noreferrer"' : "";
    return `<a href="${safeHref}"${safeTitle}${extAttrs}>${label}</a>`;
  });

  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/__([^_]+)__/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^\*])\*([^*]+)\*(?!\*)/g, "$1<em>$2</em>");
  out = out.replace(/(^|[^_])_([^_]+)_(?!_)/g, "$1<em>$2</em>");

  for (let i = 0; i < codeTokens.length; i += 1) {
    out = out.replace(`@@CODETOKEN${i}@@`, codeTokens[i]);
  }
  return out;
}

function markdownToHtml(markdownText) {
  const lines = String(markdownText ?? "").replace(/\r\n?/g, "\n").split("\n");
  const html = [];
  let paragraph = [];
  let listType = "";
  let inCode = false;
  let codeLang = "";
  let codeLines = [];
  let inQuote = false;
  let manualHeadingIndex = 0;

  const flushParagraph = () => {
    if (!paragraph.length) return;
    html.push(`<p>${parseInlineMarkdown(paragraph.join(" "))}</p>`);
    paragraph = [];
  };

  const closeList = () => {
    if (!listType) return;
    html.push(`</${listType}>`);
    listType = "";
  };

  const closeQuote = () => {
    if (!inQuote) return;
    flushParagraph();
    closeList();
    html.push("</blockquote>");
    inQuote = false;
  };

  const flushCode = () => {
    const safeLang = String(codeLang || "").toLowerCase().replace(/[^a-z0-9_-]/g, "");
    const classAttr = safeLang ? ` class="language-${escapeAttr(safeLang)}"` : "";
    html.push(`<pre><code${classAttr}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    inCode = false;
    codeLang = "";
    codeLines = [];
  };

  for (const line of lines) {
    if (inCode) {
      if (/^```/.test(line.trim())) {
        flushCode();
      } else {
        codeLines.push(line);
      }
      continue;
    }

    const trimmed = line.trim();
    const quoteMatch = line.match(/^>\s?(.*)$/);

    if (/^```/.test(trimmed)) {
      flushParagraph();
      closeList();
      closeQuote();
      inCode = true;
      codeLang = trimmed.slice(3).trim();
      codeLines = [];
      continue;
    }

    if (!trimmed) {
      flushParagraph();
      closeList();
      closeQuote();
      continue;
    }

    if (quoteMatch) {
      if (!inQuote) {
        flushParagraph();
        closeList();
        html.push("<blockquote>");
        inQuote = true;
      }
      const quoteBody = String(quoteMatch[1] || "").trim();
      if (!quoteBody) {
        flushParagraph();
        closeList();
      } else {
        paragraph.push(quoteBody);
      }
      continue;
    }

    if (inQuote) {
      closeQuote();
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      flushParagraph();
      closeList();
      const level = headingMatch[1].length;
      const id = `manual-heading-${manualHeadingIndex}`;
      manualHeadingIndex += 1;
      html.push(`<h${level} id="${id}">${parseInlineMarkdown(headingMatch[2].trim())}</h${level}>`);
      continue;
    }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      flushParagraph();
      closeList();
      html.push("<hr />");
      continue;
    }

    const ulMatch = trimmed.match(/^[-*+]\s+(.+)$/);
    const olMatch = trimmed.match(/^\d+\.\s+(.+)$/);
    if (ulMatch || olMatch) {
      flushParagraph();
      const nextType = ulMatch ? "ul" : "ol";
      if (listType && listType !== nextType) {
        closeList();
      }
      if (!listType) {
        listType = nextType;
        html.push(`<${listType}>`);
      }
      html.push(`<li>${parseInlineMarkdown((ulMatch || olMatch)[1].trim())}</li>`);
      continue;
    }

    closeList();
    paragraph.push(trimmed);
  }

  if (inCode) {
    flushCode();
  }
  flushParagraph();
  closeList();
  closeQuote();
  return html.join("\n");
}

const manualHtml = computed(() => markdownToHtml(manualText.value));
const manualHeadings = computed(() => {
  const headings = [];
  let inCode = false;
  let headingIndex = 0;
  for (const line of String(manualText.value || "").replace(/\r\n?/g, "\n").split("\n")) {
    const trimmed = line.trim();
    if (/^```/.test(trimmed)) {
      inCode = !inCode;
      continue;
    }
    if (inCode) continue;
    const match = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (!match) continue;
    const index = headingIndex;
    headingIndex += 1;
    if (match[1].length <= 3) {
      headings.push({
        id: `manual-heading-${index}`,
        level: match[1].length,
        title: match[2].trim().replace(/[\`*_]/g, "")
      });
    }
  }
  return headings;
});

function normalizeApiBase() {
  return apiBase.value.replace(/\/+$/, "");
}

function apiUrl(path) {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  return `${normalizeApiBase()}${path}`;
}

function toggleMenu(name) {
  activeMenu.value = activeMenu.value === name ? "" : name;
}

function closeMenu() {
  activeMenu.value = "";
}

function openMainView(view) {
  if (view === "workspace" || view === "home") {
    mainView.value = view;
    settingsOpen.value = false;
    closeMenu();
    return;
  }
  openSettingsPage(view);
}

function openSettingsPage(page) {
  modalKind.value = "settings";
  settingsPage.value = ["basic", "about", "manual"].includes(page) ? page : "basic";
  settingsOpen.value = true;
  if (settingsPage.value === "about") void fetchContactAssets();
  if (settingsPage.value === "manual") void fetchUserManual();
}

function openAssetPage(page = "history") {
  modalKind.value = "assets";
  assetPage.value = ["history", "files"].includes(page) ? page : "history";
  settingsOpen.value = true;
  if (assetPage.value === "files") void fetchRenderFiles();
}

function closeSettings() {
  settingsOpen.value = false;
}

function onSettingsKeydown(event) {
  if (event.key === "Escape") closeSettings();
}

function onDocClick(event) {
  if (!menuWrapRef.value) return;
  if (!menuWrapRef.value.contains(event.target)) {
    closeMenu();
  }
}

async function scrollToSection(sectionId, sectionKey) {
  if (mainView.value !== "workspace") {
    mainView.value = "workspace";
    await nextTick();
  }
  const node = document.getElementById(sectionId);
  if (node) {
    node.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  activeSection.value = sectionKey;
}

function prettifyContactName(name) {
  const key = String(name || "").replace(/\.[^.]+$/, "");
  const known = {
    小红书: "小红书",
    微信公众号: "微信公众号",
    粉丝群: "粉丝群"
  };
  return known[key] || key.replace(/[_-]+/g, " ");
}

async function fetchContactAssets(force = false) {
  if (contactLoaded.value && !force) return;
  contactLoading.value = true;
  contactError.value = "";
  try {
    const res = await fetch(apiUrl("/api/contact-assets"));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "读取联系方式失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const items = Array.isArray(data?.items) ? data.items : [];
    contactAssets.value = items.map((item) => ({
      ...item,
      displayName: prettifyContactName(item.name)
    }));
    contactLoaded.value = true;
  } catch (e) {
    contactError.value = String(e);
  } finally {
    contactLoading.value = false;
  }
}

async function fetchUserManual(force = false) {
  if (manualLoaded.value && !force) return;
  manualLoading.value = true;
  manualError.value = "";
  try {
    const res = await fetch(apiUrl("/api/user-manual"));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "读取用户手册失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    manualTitle.value = data?.title || "用户手册页面";
    manualText.value = String(data?.content || "");
    manualLoaded.value = true;
  } catch (e) {
    manualError.value = String(e);
  } finally {
    manualLoading.value = false;
  }
}

async function fetchHealth() {
  try {
    const res = await fetch(apiUrl("/api/health"));
    healthStatus.value = res.ok ? "ok" : "down";
  } catch {
    healthStatus.value = "down";
  }
  return healthStatus.value === "ok";
}

async function fetchPlotRegistry() {
  try {
    const res = await fetch(apiUrl("/api/plot-registry"));
    if (!res.ok) throw new Error("加载图型注册中心失败");
    const data = await res.json();
    if (data?.plots_by_group && typeof data.plots_by_group === "object") {
      plotsByGroup.value = data.plots_by_group;
    }
    plotRegistry.value = data?.plots && typeof data.plots === "object" ? data.plots : {};
    const groups = Array.isArray(data?.groups) ? data.groups : [];
    if (groups.length) {
      const nextMeta = { ...GROUP_META_FALLBACK };
      for (const group of groups) {
        if (!group?.key) continue;
        nextMeta[group.key] = {
          label: group.label || GROUP_META_FALLBACK[group.key]?.label || group.key,
          description: group.description || GROUP_META_FALLBACK[group.key]?.description || "科研图型分组",
          scene: group.scene || GROUP_META_FALLBACK[group.key]?.scene || "科研可视化分析",
          order: Number(group.order ?? GROUP_META_FALLBACK[group.key]?.order ?? 999)
        };
      }
      groupMeta.value = nextMeta;
    }
    applyRegistryDefaultsToDynamicArgs();
    return true;
  } catch (e) {
    // graceful fallback: keep local fallback metadata
    plotRegistry.value = {};
    groupMeta.value = { ...GROUP_META_FALLBACK };
    console.warn(e);
    return false;
  }
}

async function fetchPlots() {
  try {
    const res = await fetch(apiUrl("/api/plots"));
    if (!res.ok) throw new Error("加载图型列表失败");
    const data = await res.json();
    plotsByGroup.value = data || {};
    const groups = orderedGroups.value;
    if (groups.length) {
      selectedGroup.value = groups[0];
      selectedPlot.value = (plotsByGroup.value[selectedGroup.value] || [])[0] || "box";
    }
    return true;
  } catch (e) {
    messageErr.value = String(e);
    return false;
  }
}

async function checkSettingsConnection() {
  settingsActionLoading.value = "health";
  settingsActionTone.value = "loading";
  settingsActionMessage.value = "正在检查后端连接…";
  try {
    const connected = await fetchHealth();
    settingsActionTone.value = connected ? "success" : "error";
    settingsActionMessage.value = connected
      ? `连接成功：${apiBase.value}`
      : `连接失败：无法访问 ${apiBase.value}，请检查服务地址和后端状态。`;
  } finally {
    settingsActionLoading.value = "";
  }
}

async function refreshSettingsPlotCatalog() {
  settingsActionLoading.value = "plots";
  settingsActionTone.value = "loading";
  settingsActionMessage.value = "正在同步图型目录…";
  try {
    const [registryOk, plotsOk] = await Promise.all([fetchPlotRegistry(), fetchPlots()]);
    const groups = Object.values(plotsByGroup.value || {});
    const plotCount = groups.reduce((total, group) => total + (Array.isArray(group) ? group.length : 0), 0);
    const groupCount = groups.filter((group) => Array.isArray(group) && group.length).length;
    const refreshed = registryOk && plotsOk;
    settingsActionTone.value = refreshed ? "success" : "error";
    settingsActionMessage.value = refreshed
      ? `图型目录已更新：${groupCount} 个分类，${plotCount} 种图型。`
      : "图型目录刷新失败，请检查后端连接后重试。";
  } finally {
    settingsActionLoading.value = "";
  }
}

function pickBestColumn(candidates) {
  const cols = uploadColumns.value || [];
  if (!cols.length) return "";
  const lowerMap = cols.map((c) => ({ raw: c, lower: c.toLowerCase() }));
  for (const key of candidates) {
    const hit = lowerMap.find((it) => it.lower === key.toLowerCase());
    if (hit) return hit.raw;
  }
  for (const key of candidates) {
    const hit = lowerMap.find((it) => it.lower.includes(key.toLowerCase()));
    if (hit) return hit.raw;
  }
  return "";
}

function autoMapColumns() {
  const keys = Object.keys(mappings);
  for (const key of keys) {
    if (String(mappings[key] || "").trim()) continue;
    const suggest = FIELD_SUGGEST[key] || [];
    const hit = pickBestColumn(suggest);
    if (hit) mappings[key] = hit;
  }
}

function onFileChosen(event) {
  const file = event.target.files?.[0];
  pickedFile.value = file || null;
}

function triggerFilePick() {
  if (fileInputRef.value) {
    fileInputRef.value.click();
  }
}

function onDynamicArgChange(def, rawValue) {
  if (def.type === "bool") {
    dynamicArgs[def.key] = Boolean(rawValue);
    return;
  }
  if (def.type === "number") {
    if (rawValue === "" || rawValue === null || typeof rawValue === "undefined") {
      dynamicArgs[def.key] = "";
      return;
    }
    const n = Number(rawValue);
    dynamicArgs[def.key] = Number.isFinite(n) ? n : "";
    return;
  }
  dynamicArgs[def.key] = String(rawValue ?? "");
}

function collectDynamicArgs() {
  const out = {};
  for (const def of activeDynamicArgDefs.value) {
    const val = dynamicArgs[def.key];
    if (def.type === "bool") {
      if (def.sendFalse || Boolean(val)) out[def.key] = Boolean(val);
      continue;
    }
    if (val === "" || val === null || typeof val === "undefined") continue;
    out[def.key] = val;
  }
  return out;
}

function startRenderProgress(text = "准备渲染...") {
  if (renderProgressTimer) {
    clearInterval(renderProgressTimer);
    renderProgressTimer = null;
  }
  renderProgress.value = 6;
  renderStatusText.value = text;
  renderProgressTimer = setInterval(() => {
    if (renderProgress.value >= 90) return;
    const delta = Math.max(1.2, (92 - renderProgress.value) / 9);
    renderProgress.value = Math.min(90, renderProgress.value + delta);
  }, 180);
}

function setRenderProgressText(text) {
  renderStatusText.value = text;
}

function finishRenderProgress(ok) {
  if (renderProgressTimer) {
    clearInterval(renderProgressTimer);
    renderProgressTimer = null;
  }
  if (ok) {
    renderProgress.value = 100;
    renderStatusText.value = "渲染完成";
    setTimeout(() => {
      renderProgress.value = 0;
      renderStatusText.value = "";
    }, 900);
  } else {
    renderProgress.value = 100;
    renderStatusText.value = "渲染失败";
    setTimeout(() => {
      renderProgress.value = 0;
    }, 1200);
  }
}

function persistRenderHistory() {
  try {
    localStorage.setItem(RENDER_HISTORY_KEY, JSON.stringify(renderHistory.value));
  } catch {
    // ignore storage errors
  }
}

function loadRenderHistory() {
  try {
    const raw = localStorage.getItem(RENDER_HISTORY_KEY);
    if (!raw) {
      renderHistory.value = [];
      return;
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      renderHistory.value = [];
      return;
    }
    renderHistory.value = parsed.slice(0, RENDER_HISTORY_LIMIT);
    historyVisibleCount.value = Math.min(HISTORY_BATCH_SIZE, renderHistory.value.length);
  } catch {
    renderHistory.value = [];
  }
}

function snapshotCurrentConfig() {
  return {
    selectedGroup: selectedGroup.value,
    selectedPlot: selectedPlot.value,
    renderMode: renderMode.value,
    fmt: fmt.value,
    dataSourceMode: dataSourceMode.value,
    mappings: { ...mappings },
    dynamicArgs: { ...dynamicArgs },
    figure: { ...figure },
    extraArgsText: extraArgsText.value
  };
}

function applyConfigSnapshot(config) {
  if (!config || typeof config !== "object") return;
  if (config.selectedGroup) selectedGroup.value = config.selectedGroup;
  if (config.selectedPlot) selectedPlot.value = config.selectedPlot;
  if (config.renderMode) renderMode.value = config.renderMode;
  if (config.fmt) fmt.value = config.fmt;
  if (config.dataSourceMode) dataSourceMode.value = config.dataSourceMode;
  if (config.mappings && typeof config.mappings === "object") {
    for (const key of Object.keys(mappings)) {
      if (key in config.mappings) mappings[key] = config.mappings[key];
    }
  }
  if (config.dynamicArgs && typeof config.dynamicArgs === "object") {
    for (const [key, value] of Object.entries(config.dynamicArgs)) {
      dynamicArgs[key] = value;
    }
  }
  if (config.figure && typeof config.figure === "object") {
    figure.title = config.figure.title || "";
    figure.xlabel = config.figure.xlabel || "";
    figure.ylabel = config.figure.ylabel || "";
    figure.zlabel = config.figure.zlabel || "";
  }
  if (typeof config.extraArgsText === "string") {
    extraArgsText.value = config.extraArgsText;
  }
}

function pushRenderHistory(payload, data) {
  const item = {
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    timestamp: new Date().toISOString(),
    plot: payload.plot,
    title: payload.title || "",
    fmt: payload.fmt,
    saveName: data.save_name || "",
    imagePath: data.image_url || "",
    argv: (data.argv || []).join(" "),
    config: snapshotCurrentConfig(),
    uploadedFile: payload.uploaded_file || ""
  };
  renderHistory.value = [item, ...renderHistory.value].slice(0, RENDER_HISTORY_LIMIT);
  persistRenderHistory();
}

function formatHistoryTime(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return String(ts || "");
  return d.toLocaleString();
}

function formatFileSize(bytes) {
  const n = Number(bytes || 0);
  if (!Number.isFinite(n) || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let value = n;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  const fixed = value >= 100 || i === 0 ? value.toFixed(0) : value.toFixed(1);
  return `${fixed} ${units[i]}`;
}

function extractRenderFilename(imagePath) {
  if (!imagePath) return "";
  const raw = String(imagePath);
  const marker = "/api/files/";
  const idx = raw.lastIndexOf(marker);
  if (idx < 0) return "";
  const tail = raw.slice(idx + marker.length).split("?")[0];
  try {
    return decodeURIComponent(tail);
  } catch {
    return tail;
  }
}

function extFromFilename(filename) {
  const raw = String(filename || "");
  const part = raw.split("?")[0].trim();
  const dot = part.lastIndexOf(".");
  if (dot < 0) return "";
  return part.slice(dot + 1).toLowerCase();
}

function extFromUrl(url) {
  return extFromFilename(extractRenderFilename(url));
}

function normalizeExt(ext) {
  return String(ext || "").trim().toLowerCase();
}

function fileTypeShort(ext) {
  const normalized = normalizeExt(ext);
  if (!normalized) return "文件";
  return FILE_TYPE_META[normalized]?.short || normalized.toUpperCase();
}

function fileTypeLong(ext) {
  const normalized = normalizeExt(ext);
  if (!normalized) return "未知格式";
  return FILE_TYPE_META[normalized]?.long || `${normalized.toUpperCase()} 文件`;
}

function inferPreviewType({ filename = "", url = "", fmt = "" } = {}) {
  const ext = String(fmt || "").toLowerCase() || extFromFilename(filename) || extFromUrl(url);
  if (ext === "pdf") return "pdf";
  if (["png", "jpg", "jpeg", "webp", "gif", "svg", "bmp"].includes(ext)) return "image";
  return "unsupported";
}

function setResultPreview({ url = "", filename = "", fmt = "" } = {}) {
  imageUrl.value = String(url || "");
  resultFileName.value = String(filename || extractRenderFilename(url) || "");
  const ext = String(fmt || "").toLowerCase() || extFromFilename(resultFileName.value) || extFromUrl(url);
  currentResultFmt.value = ext;
  resultPreviewType.value = imageUrl.value ? inferPreviewType({ filename: resultFileName.value, url, fmt: ext }) : "image";
}

function historyImageUrl(item) {
  if (!item?.imagePath) return "";
  return `${apiUrl(item.imagePath)}?h=${encodeURIComponent(item.id || "")}`;
}

function historyHasImagePreview(item) {
  return inferPreviewType({ filename: item?.saveName ? `${item.saveName}.${item.fmt || ""}` : "", url: item?.imagePath || "", fmt: item?.fmt || "" }) === "image";
}

function historyPreviewLabel(item) {
  const ext = String(item?.fmt || "").toLowerCase() || extFromUrl(item?.imagePath || "");
  return fileTypeShort(ext);
}

function renderFileExt(item) {
  return extFromFilename(item?.filename || "");
}

function renderFilePreviewType(item) {
  return inferPreviewType({ filename: item?.filename || "", url: item?.image_url || "", fmt: renderFileExt(item) });
}

function renderFileTypeLabel(item) {
  return fileTypeLong(renderFileExt(item));
}

function renderFileTypeBadge(item) {
  return fileTypeShort(renderFileExt(item));
}

function openRenderFileInNewWindow(item) {
  if (!item?.image_url) return;
  window.open(apiUrl(item.image_url), "_blank", "noopener,noreferrer");
}

function openHistoryResult(item) {
  if (!item) return;
  if (item.imagePath) {
    setResultPreview({
      url: `${historyImageUrl(item)}&t=${Date.now()}`,
      filename: item.saveName ? `${item.saveName}.${item.fmt || ""}` : "",
      fmt: item.fmt || ""
    });
  }
  lastSaveName.value = item.saveName || "";
  messageErr.value = "";
  messageOk.value = "已打开历史结果";
  scrollToSection("section-result", "result");
}

function applyHistoryItem(item) {
  if (!item) return;
  applyConfigSnapshot(item.config);
  if (item.uploadedFile) {
    uploadedFileId.value = item.uploadedFile;
    if (!uploadedFileName.value) uploadedFileName.value = item.uploadedFile;
  }
  openHistoryResult(item);
  messageOk.value = "已复用历史配置";
}

function clearRenderHistory() {
  renderHistory.value = [];
  persistRenderHistory();
  historyVisibleCount.value = HISTORY_BATCH_SIZE;
}

async function retryLastRender() {
  if (!lastFailedPayload.value) {
    messageErr.value = "当前没有可重试的失败任务";
    return;
  }
  await renderImage(lastFailedPayload.value);
}

const FILE_LIST_PAGE_SIZE = 200;
const FILE_LIST_PAGE_CAP = 200;

async function fetchPagedItems(endpoint, fallbackErrorMessage) {
  const merged = [];
  let page = 1;
  while (page <= FILE_LIST_PAGE_CAP) {
    const url = apiUrl(`${endpoint}?page=${page}&page_size=${FILE_LIST_PAGE_SIZE}`);
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || fallbackErrorMessage;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const items = Array.isArray(data?.items) ? data.items : [];
    merged.push(...items);
    if (!data?.has_next) break;
    page += 1;
  }
  return merged;
}

async function fetchUploadFiles() {
  uploadFilesLoading.value = true;
  try {
    uploadFiles.value = await fetchPagedItems("/api/uploads", "读取上传文件列表失败");
  } catch (e) {
    messageErr.value = String(e);
  } finally {
    uploadFilesLoading.value = false;
  }
}

async function fetchRenderFiles() {
  renderFilesLoading.value = true;
  try {
    renderFiles.value = await fetchPagedItems("/api/renders", "读取渲染文件列表失败");
    renderFilesVisibleCount.value = Math.min(RENDER_FILES_BATCH_SIZE, renderFiles.value.length);
  } catch (e) {
    messageErr.value = String(e);
  } finally {
    renderFilesLoading.value = false;
  }
}

async function useUploadedFile(fileId) {
  if (!fileId) return;
  messageErr.value = "";
  try {
    const res = await fetch(apiUrl(`/api/uploads/${encodeURIComponent(fileId)}/inspect`));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "读取上传文件详情失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    uploadedFileId.value = data.file_id || fileId;
    uploadedFileName.value = data.filename || fileId;
    uploadColumns.value = data.columns || [];
    previewRows.value = data.preview_rows || [];
    autoMapColumns();
    messageOk.value = `已切换数据集：${uploadedFileName.value}`;
    scrollToSection("section-data", "data");
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function deleteUploadedFile(fileId) {
  if (!fileId) return;
  messageErr.value = "";
  try {
    const res = await fetch(apiUrl(`/api/uploads/${encodeURIComponent(fileId)}`), { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "删除上传文件失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    if (uploadedFileId.value === fileId) {
      uploadedFileId.value = "";
      uploadedFileName.value = "";
      uploadColumns.value = [];
      previewRows.value = [];
    }
    messageOk.value = `已删除上传文件：${fileId}`;
    await fetchUploadFiles();
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function clearUploadedFiles() {
  messageErr.value = "";
  try {
    const res = await fetch(apiUrl("/api/uploads"), { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "清空上传文件失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    uploadFiles.value = [];
    uploadedFileId.value = "";
    uploadedFileName.value = "";
    uploadColumns.value = [];
    previewRows.value = [];
    messageOk.value = `已清空上传文件（${Number(data?.deleted || 0)} 个）`;
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function deleteRenderFileByName(filename, { silent = false } = {}) {
  if (!filename) return;
  const res = await fetch(apiUrl(`/api/renders/${encodeURIComponent(filename)}`), { method: "DELETE" });
  if (!res.ok && res.status !== 404 && !silent) {
    const data = await res.json().catch(() => ({}));
    const detail = data?.detail || "删除渲染文件失败";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
}

async function deleteHistoryItem(item, { removeFile = true } = {}) {
  if (!item) return;
  messageErr.value = "";
  try {
    if (removeFile) {
      const filename = extractRenderFilename(item.imagePath);
      if (filename) {
        await deleteRenderFileByName(filename);
      }
    }
    renderHistory.value = renderHistory.value.filter((it) => it.id !== item.id);
    persistRenderHistory();
    if (lastSaveName.value && item.saveName === lastSaveName.value) {
      setResultPreview({});
      lastSaveName.value = "";
    }
    if (removeFile) {
      await fetchRenderFiles();
      messageOk.value = "已删除历史记录并清理本地图像";
    } else {
      messageOk.value = "已删除历史记录";
    }
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function clearRenderHistoryAndLocalFiles() {
  messageErr.value = "";
  try {
    const res = await fetch(apiUrl("/api/renders"), { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "清空本地渲染文件失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    renderHistory.value = [];
    persistRenderHistory();
    historyVisibleCount.value = HISTORY_BATCH_SIZE;
    setResultPreview({});
    lastSaveName.value = "";
    await fetchRenderFiles();
    messageOk.value = `已清空历史并删除本地图像（${Number(data?.deleted || 0)} 个文件）`;
  } catch (e) {
    messageErr.value = String(e);
  }
}

function openRenderFileItem(item) {
  if (!item?.image_url) return;
  setResultPreview({
    url: `${apiUrl(item.image_url)}?rf=${Date.now()}`,
    filename: item.filename || "",
    fmt: extFromFilename(item.filename || "")
  });
  lastSaveName.value = String(item.filename || "").replace(/\.[^.]+$/, "");
  messageOk.value = "已打开本地渲染文件";
  scrollToSection("section-result", "result");
}

async function deleteRenderFileItem(item) {
  if (!item?.filename) return;
  messageErr.value = "";
  try {
    await deleteRenderFileByName(item.filename);
    renderHistory.value = renderHistory.value.filter((it) => extractRenderFilename(it.imagePath) !== item.filename);
    persistRenderHistory();
    if (extractRenderFilename(imageUrl.value) === item.filename) {
      setResultPreview({});
      lastSaveName.value = "";
    }
    await fetchRenderFiles();
    messageOk.value = `已删除本地渲染文件：${item.filename}`;
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function uploadFileObject(fileObj) {
  const formData = new FormData();
  formData.append("file", fileObj);
  const res = await fetch(apiUrl("/api/upload"), {
    method: "POST",
    body: formData
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "上传失败");
  }
  return res.json();
}

async function uploadSelectedFile() {
  messageErr.value = "";
  messageOk.value = "";
  if (!pickedFile.value) {
    messageErr.value = "请先选择数据文件";
    return;
  }
  try {
    const data = await uploadFileObject(pickedFile.value);
    uploadedFileId.value = data.file_id;
    uploadedFileName.value = data.filename;
    uploadColumns.value = data.columns || [];
    previewRows.value = data.preview_rows || [];
    autoMapColumns();
    messageOk.value = `上传成功：${data.filename}`;
    await fetchUploadFiles();
  } catch (e) {
    messageErr.value = String(e);
  }
}

function ensureRowWidth() {
  const width = tableHeaders.value.length;
  tableRows.value = tableRows.value.map((r) => {
    const next = [...r];
    while (next.length < width) next.push("");
    return next.slice(0, width);
  });
}

function addTableRow() {
  tableRows.value.push(Array.from({ length: tableHeaders.value.length }, () => ""));
}

function removeTableRow() {
  if (tableRows.value.length > 1) {
    tableRows.value.pop();
  }
}

function addTableColumn() {
  tableHeaders.value.push(`col_${tableHeaders.value.length + 1}`);
  ensureRowWidth();
}

function removeTableColumn() {
  if (tableHeaders.value.length <= 1) return;
  tableHeaders.value.pop();
  ensureRowWidth();
}

function tableToCsv() {
  const escape = (val) => {
    const text = String(val ?? "");
    if (text.includes(",") || text.includes("\"") || text.includes("\n")) {
      return `"${text.replace(/"/g, "\"\"")}"`;
    }
    return text;
  };
  const head = tableHeaders.value.map((h) => escape(h || "")).join(",");
  const body = tableRows.value
    .filter((row) => row.some((v) => String(v || "").trim() !== ""))
    .map((row) => row.map((cell) => escape(cell || "")).join(","))
    .join("\n");
  return body ? `${head}\n${body}\n` : `${head}\n`;
}

async function uploadTableDataset() {
  const csv = tableToCsv();
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const file = new File([blob], "inline_table.csv", { type: "text/csv" });
  const data = await uploadFileObject(file);
  uploadedFileId.value = data.file_id;
  uploadedFileName.value = "inline_table.csv";
  uploadColumns.value = data.columns || [];
  previewRows.value = data.preview_rows || [];
  autoMapColumns();
  await fetchUploadFiles();
  return data.file_id;
}

function chooseGroup(group) {
  selectedGroup.value = group;
  const list = plotsByGroup.value[group] || [];
  if (!list.includes(selectedPlot.value)) {
    selectedPlot.value = list[0] || "";
  }
}

function resetResult() {
  setResultPreview({});
  lastSaveName.value = "";
  messageOk.value = "";
  messageErr.value = "";
}

function loadMoreHistory() {
  historyVisibleCount.value = Math.min(renderHistory.value.length, historyVisibleCount.value + HISTORY_BATCH_SIZE);
}

function loadMoreRenderFiles() {
  renderFilesVisibleCount.value = Math.min(renderFiles.value.length, renderFilesVisibleCount.value + RENDER_FILES_BATCH_SIZE);
}

function onHistoryScroll(event) {
  const el = event?.target;
  if (!el || !hasMoreHistory.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) {
    loadMoreHistory();
  }
}

function onRenderFilesScroll(event) {
  const el = event?.target;
  if (!el || !hasMoreRenderFiles.value) return;
  if (el.scrollTop + el.clientHeight >= el.scrollHeight - 24) {
    loadMoreRenderFiles();
  }
}

function parseExtraArgs() {
  const text = extraArgsText.value.trim();
  if (!text) return {};
  const data = JSON.parse(text);
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new Error("高级参数必须是 JSON 对象");
  }
  return data;
}

function buildRenderArgs() {
  const args = {};
  if (renderMode.value !== "demo") {
    for (const [k, v] of Object.entries(mappings)) {
      const val = String(v || "").trim();
      if (val) args[k] = val;
    }
  }
  Object.assign(args, collectDynamicArgs());
  if (figure.xlabel.trim()) args.xlabel = figure.xlabel.trim();
  if (figure.ylabel.trim()) args.ylabel = figure.ylabel.trim();
  if (figure.zlabel.trim()) args.zlabel = figure.zlabel.trim();
  if (renderMode.value !== "demo") Object.assign(args, parseExtraArgs());
  return args;
}

async function renderDemoForPlot(plotKey) {
  const matchingGroup = Object.entries(plotsByGroup.value || {}).find(([, plots]) => plots.includes(plotKey));
  if (!matchingGroup) {
    messageErr.value = `未找到图型“${plotKey}”所属分组，请刷新图型目录后重试。`;
    return;
  }
  selectedGroup.value = matchingGroup[0];
  selectedPlot.value = plotKey;
  renderMode.value = "demo";
  figure.title = `${plotDisplayName(plotKey)}示例`;
  mainView.value = "workspace";
  activeSection.value = "plot";
  await nextTick();
  await renderImage();
}

function sanitizeRetryPayload(retryPayload) {
  if (!retryPayload || typeof retryPayload !== "object") return null;
  if (retryPayload instanceof Event) return null;
  const required = ["mode", "plot", "fmt", "args"];
  const hasAllKeys = required.every((k) => Object.prototype.hasOwnProperty.call(retryPayload, k));
  if (!hasAllKeys) return null;
  return retryPayload;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollRenderTask(taskId) {
  let retries = 0;
  while (true) {
    const res = await fetch(apiUrl(`/api/tasks/${encodeURIComponent(taskId)}`));
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "读取任务状态失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    const status = String(data?.status || "");
    const detail = String(data?.detail || "");
    if (status === "queued") {
      setRenderProgressText(detail || "任务排队中...");
    } else if (status === "running") {
      setRenderProgressText(detail || "任务执行中...");
    }

    if (status === "success") {
      return data;
    }
    if (status === "failed") {
      throw new Error(String(data?.error || data?.detail || "渲染任务失败"));
    }
    if (status === "cancelled") {
      throw new Error(String(data?.detail || "任务已取消"));
    }

    retries += 1;
    await sleep(Math.min(1600, 700 + retries * 40));
  }
}

async function cancelCurrentRenderTask() {
  if (!currentTaskId.value) return;
  try {
    const taskId = currentTaskId.value;
    const res = await fetch(apiUrl(`/api/tasks/${encodeURIComponent(taskId)}/cancel`), { method: "POST" });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = data?.detail || "取消任务失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    messageOk.value = "已发送取消请求，任务将在可中断点停止。";
  } catch (e) {
    messageErr.value = String(e);
  }
}

async function renderImage(retryPayload = null) {
  messageErr.value = "";
  messageOk.value = "";
  rendering.value = true;
  currentTaskId.value = "";
  const safeRetryPayload = sanitizeRetryPayload(retryPayload);
  let payload = safeRetryPayload ? JSON.parse(JSON.stringify(safeRetryPayload)) : null;
  startRenderProgress(safeRetryPayload ? "重试任务准备中..." : "准备渲染任务...");
  try {
    if (!payload) {
      let mode = renderMode.value;
      let uploadId = "";

      if (mode !== "demo") {
        setRenderProgressText("正在准备数据...");
        if (dataSourceMode.value === "table") {
          uploadId = await uploadTableDataset();
        } else {
          uploadId = uploadedFileId.value;
        }
        if (!uploadId) {
          throw new Error("file 模式下需要先上传文件或保存表格数据");
        }
        autoMapColumns();
        const missing = requiredFields.value.filter((k) => !(String(mappings[k] || "").trim()));
        if (missing.length) {
          const missingText = missing.map((f) => FIELD_LABELS[f] || f).join("、");
          throw new Error(`当前数据缺少可识别字段：${missingText}。请检查列名后重试。`);
        }
        mode = "file";
      }

      payload = {
        mode,
        plot: selectedPlot.value,
        title: figure.title.trim() || null,
        fmt: fmt.value,
        uploaded_file: uploadId || null,
        args: buildRenderArgs()
      };
    }

    setRenderProgressText("任务提交中...");
    const submitRes = await fetch(apiUrl("/api/tasks/render/submit"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const submitData = await submitRes.json().catch(() => ({}));
    if (!submitRes.ok) {
      const detail = submitData?.detail || "任务提交失败";
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    currentTaskId.value = String(submitData?.task_id || "");
    if (!currentTaskId.value) {
      throw new Error("任务提交成功但未返回 task_id");
    }

    setRenderProgressText("任务已提交，正在等待执行...");
    const taskData = await pollRenderTask(currentTaskId.value);

    setResultPreview({
      url: `${apiUrl(taskData.image_url)}?t=${Date.now()}`,
      filename: taskData.save_name ? `${taskData.save_name}.${taskData.fmt || payload.fmt || fmt.value}` : "",
      fmt: taskData.fmt || payload.fmt || fmt.value
    });
    lastSaveName.value = taskData.save_name || "";
    messageOk.value = safeRetryPayload ? "重试成功，渲染完成" : "渲染完成";
    lastFailedPayload.value = null;
    pushRenderHistory(payload, taskData);
    await fetchRenderFiles();
    finishRenderProgress(true);
    scrollToSection("section-result", "result");
  } catch (e) {
    messageErr.value = String(e);
    if (payload) {
      lastFailedPayload.value = payload;
    }
    finishRenderProgress(false);
  } finally {
    rendering.value = false;
    currentTaskId.value = "";
  }
}

const appStore = {
  ...state,
  manualHtml,
  manualHeadings,
  escapeHtml,
  escapeAttr,
  parseInlineMarkdown,
  markdownToHtml,
  normalizeApiBase,
  apiUrl,
  toggleMenu,
  closeMenu,
  openMainView,
  onDocClick,
  scrollToSection,
  prettifyContactName,
  fetchContactAssets,
  fetchUserManual,
  fetchHealth,
  fetchPlotRegistry,
  fetchPlots,
  pickBestColumn,
  autoMapColumns,
  onFileChosen,
  triggerFilePick,
  onDynamicArgChange,
  collectDynamicArgs,
  startRenderProgress,
  setRenderProgressText,
  finishRenderProgress,
  persistRenderHistory,
  loadRenderHistory,
  snapshotCurrentConfig,
  applyConfigSnapshot,
  pushRenderHistory,
  formatHistoryTime,
  formatFileSize,
  extractRenderFilename,
  extFromFilename,
  extFromUrl,
  normalizeExt,
  fileTypeShort,
  fileTypeLong,
  inferPreviewType,
  setResultPreview,
  historyImageUrl,
  historyHasImagePreview,
  historyPreviewLabel,
  renderFileExt,
  renderFilePreviewType,
  renderFileTypeLabel,
  renderFileTypeBadge,
  openRenderFileInNewWindow,
  openHistoryResult,
  applyHistoryItem,
  clearRenderHistory,
  retryLastRender,
  fetchUploadFiles,
  fetchRenderFiles,
  useUploadedFile,
  deleteUploadedFile,
  clearUploadedFiles,
  deleteRenderFileByName,
  deleteHistoryItem,
  clearRenderHistoryAndLocalFiles,
  openRenderFileItem,
  deleteRenderFileItem,
  uploadFileObject,
  uploadSelectedFile,
  ensureRowWidth,
  addTableRow,
  removeTableRow,
  addTableColumn,
  removeTableColumn,
  tableToCsv,
  uploadTableDataset,
  chooseGroup,
  renderDemoForPlot,
  resetResult,
  loadMoreHistory,
  loadMoreRenderFiles,
  onHistoryScroll,
  onRenderFilesScroll,
  parseExtraArgs,
  buildRenderArgs,
  sanitizeRetryPayload,
  cancelCurrentRenderTask,
  renderImage
};

provide(RESEARCH_DRAW_STORE_KEY, appStore);

watch(
  () => selectedGroup.value,
  () => {
    const list = plotsByGroup.value[selectedGroup.value] || [];
    if (list.length && !list.includes(selectedPlot.value)) {
      selectedPlot.value = list[0];
    }
  }
);

watch(
  () => selectedPlot.value,
  () => {
    activeSection.value = "plot";
    autoMapColumns();
  }
);

watch(
  () => mainView.value,
  async (view) => {
    if (view === "about") {
      await fetchContactAssets();
    } else if (view === "manual") {
      await fetchUserManual();
    }
  }
);

watch(
  () => renderHistory.value.length,
  (len) => {
    historyVisibleCount.value = Math.min(Math.max(historyVisibleCount.value, HISTORY_BATCH_SIZE), len);
  }
);

watch(
  () => renderFiles.value.length,
  (len) => {
    renderFilesVisibleCount.value = Math.min(Math.max(renderFilesVisibleCount.value, RENDER_FILES_BATCH_SIZE), len);
  }
);

watch(settingsOpen, (isOpen) => {
  document.body.classList.toggle("modal-open", isOpen);
  if (isOpen) {
    document.addEventListener("keydown", onSettingsKeydown);
  } else {
    document.removeEventListener("keydown", onSettingsKeydown);
  }
});

onMounted(async () => {
  const savedSidebarState = window.localStorage.getItem("research-draw-sidebar-collapsed");
  const savedSidebarWidth = Number(window.localStorage.getItem("research-draw-sidebar-width"));
  if (Number.isFinite(savedSidebarWidth) && savedSidebarWidth > 0) setSidebarWidth(savedSidebarWidth);
  sidebarCollapsed.value = savedSidebarState === null
    ? window.matchMedia("(max-width: 900px)").matches
    : savedSidebarState === "true";
  document.addEventListener("click", onDocClick);
  loadRenderHistory();
  await fetchHealth();
  await fetchPlotRegistry();
  await fetchPlots();
  await fetchUploadFiles();
  await fetchRenderFiles();
});

onUnmounted(() => {
  stopSidebarResize();
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onSettingsKeydown);
  document.body.classList.remove("modal-open");
  if (renderProgressTimer) {
    clearInterval(renderProgressTimer);
    renderProgressTimer = null;
  }
});
</script>

<template>
  <div
    :class="['app-shell', { 'nav-collapsed': sidebarCollapsed }]"
    :style="{ '--sidebar-width': `${sidebarWidth}px` }"
  >
    <aside :class="['sidebar panel', { collapsed: sidebarCollapsed }]">
      <div class="sidebar-brand">
        <button
          v-if="sidebarCollapsed"
          class="brand-logo-wrap brand-expand-trigger"
          type="button"
          aria-label="展开侧边导航"
          aria-expanded="false"
          @click="toggleSidebar"
        >
          <img class="brand-mark" :src="brandMark" alt="" />
          <span class="brand-expand-indicator" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <rect x="3.5" y="4" width="17" height="16" rx="2.5" />
              <path d="M9 4v16m4-7 3-3-3-3" />
            </svg>
          </span>
        </button>
        <div v-else class="brand-logo-wrap">
          <img class="brand-mark" :src="brandMark" alt="柯影智绘 Atlas" />
        </div>
        <div v-if="!sidebarCollapsed" class="brand-copy">
          <div class="brand-heading">
            <div class="brand-title">{{ TOOL_NAME }}</div>
            <span class="brand-version">{{ APP_VERSION }}</span>
          </div>
          <div class="brand-sub">{{ TOOL_SUBTITLE || "科研绘图工作台" }}</div>
        </div>
        <button
          v-if="!sidebarCollapsed"
          class="nav-collapse-btn"
          aria-label="折叠侧边导航"
          aria-expanded="true"
          @click="toggleSidebar"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <rect x="3.5" y="4" width="17" height="16" rx="2.5" />
            <path d="M9 4v16" />
            <path d="m16 9-3 3 3 3" />
          </svg>
        </button>
      </div>

      <nav class="side-nav-list primary-side-nav" aria-label="主导航">
        <button
          class="side-nav-btn"
          :class="{ active: mainView === 'home' }"
          :data-tooltip="sidebarCollapsed ? '首页' : null"
          aria-label="首页"
          @click="openMainView('home')"
        >
          <span class="side-nav-main">
            <span class="side-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="m3 10 9-7 9 7"/><path d="M5.5 9v11h13V9M9 20v-6h6v6"/></svg>
            </span>
            <span v-if="!sidebarCollapsed">首页</span>
          </span>
        </button>
      </nav>

      <div v-if="mainView === 'workspace'" class="workflow-nav">
        <span v-if="!sidebarCollapsed" class="nav-group-label">绘图流程</span>
        <nav class="side-nav-list" aria-label="绘图流程导航">
          <button
            v-for="section in workflowSections"
            :key="section.id"
            class="side-nav-btn"
            :class="{ active: activeSection === section.key }"
            :data-tooltip="sidebarCollapsed ? section.title : null"
            :aria-label="section.title"
            @click="scrollToSection(section.id, section.key)"
          >
            <span class="side-nav-main">
              <span class="side-icon" aria-hidden="true">
                <svg v-if="section.key === 'data'" viewBox="0 0 24 24"><path d="M6 3.5h8l4 4V20H6z"/><path d="M14 3.5V8h4M9 12h6M9 15h6"/></svg>
                <svg v-else-if="section.key === 'plot'" viewBox="0 0 24 24"><path d="M4 20V4M4 20h17"/><path d="M8 16v-4M12 16V8M16 16V5M20 16v-7"/></svg>
                <svg v-else-if="section.key === 'figure'" viewBox="0 0 24 24"><path d="M5 5v14M12 5v14M19 5v14"/><path d="M3 9h4M10 15h4M17 8h4"/></svg>
              </span>
              <span v-if="!sidebarCollapsed">{{ section.title }}</span>
            </span>
            <span :class="['status-dot', sectionStatus[section.key] === 'ready' ? 'ready' : 'pending']"></span>
          </button>
        </nav>
      </div>

      <div class="sidebar-footer">
        <button
          class="side-nav-btn"
          :data-tooltip="sidebarCollapsed ? '资产管理' : null"
          aria-label="资产管理"
          @click="openAssetPage('history')"
        >
          <span class="side-nav-main">
            <span class="side-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M4 7.5h6l2 2h8v9.5H4z"/><path d="M4 7.5V5h6l2 2"/></svg>
            </span>
            <span v-if="!sidebarCollapsed">资产管理</span>
          </span>
        </button>
        <button
          class="side-nav-btn settings-entry"
          :data-tooltip="sidebarCollapsed ? '设置' : null"
          aria-label="设置"
          @click="openSettingsPage('basic')"
        >
          <span class="side-nav-main">
            <span class="side-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="M19 12a7 7 0 0 0-.1-1.2l1.2-.9-1.4-2.3-1.4.6a7 7 0 0 0-2-.9L15 5.8h-2.8l-.3 1.5a7 7 0 0 0-2 .9l-1.4-.6-1.4 2.3 1.2.9a7 7 0 0 0 0 2.4l-1.2.9 1.4 2.3 1.4-.6a7 7 0 0 0 2 .9l.3 1.5H15l.3-1.5a7 7 0 0 0 2-.9l1.4.6 1.4-2.3-1.2-.9A7 7 0 0 0 19 12Z"/></svg>
            </span>
            <span v-if="!sidebarCollapsed">设置</span>
          </span>
        </button>
      </div>
      <button
        v-if="!sidebarCollapsed"
        class="sidebar-resize-handle"
        type="button"
        role="separator"
        aria-label="调整导航栏宽度"
        aria-orientation="vertical"
        :aria-valuemin="SIDEBAR_MIN_WIDTH"
        :aria-valuemax="SIDEBAR_MAX_WIDTH"
        :aria-valuenow="sidebarWidth"
        @pointerdown="startSidebarResize"
        @keydown="handleSidebarResizeKeydown"
        @dblclick="resetSidebarWidth"
      ></button>
    </aside>

    <div class="app-main">
      <TopBar />
      <div class="main-layout">
        <main v-if="mainView === 'workspace'" class="workspace">
          <div class="workspace-columns">
            <div class="workflow-column" aria-label="绘图步骤一至三">
              <section class="workspace-intro">
                <div class="workspace-intro-copy">
                  <span class="page-eyebrow">RESEARCH DRAW · SCIENTIFIC FIGURE STUDIO</span>
                  <h1>让科研数据，清晰地表达</h1>
                  <p>导入数据或从示例开始，选择合适图型、调整样式并导出结果。</p>
                </div>
              </section>
              <DataInput />
              <PlotSelector />
            </div>
            <section class="render-column" aria-label="渲染与预览">
              <RenderPanel />
            </section>
          </div>
        </main>
        <main v-else class="home-main">
          <HomePage
            @open-workspace="openMainView('workspace')"
            @open-manual="openSettingsPage('manual')"
          />
        </main>
      </div>
      </div>

    <div
      v-if="settingsOpen"
      class="settings-overlay"
      @click.self="closeSettings"
    >
      <section
        :class="['settings-modal', { 'assets-modal': modalKind === 'assets', 'manual-settings-modal': modalKind === 'settings' && settingsPage === 'manual' }]"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="modalKind === 'settings' ? 'settings-title' : 'assets-title'"
      >
        <header class="settings-modal-header">
          <div class="settings-modal-heading">
            <span class="settings-modal-mark" aria-hidden="true">
              <svg v-if="modalKind === 'settings'" viewBox="0 0 24 24"><path d="M12 8.5a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7Z"/><path d="M19 12a7 7 0 0 0-.1-1.2l1.2-.9-1.4-2.3-1.4.6a7 7 0 0 0-2-.9L15 5.8h-2.8l-.3 1.5a7 7 0 0 0-2 .9l-1.4-.6-1.4 2.3 1.2.9a7 7 0 0 0 0 2.4l-1.2.9 1.4 2.3 1.4-.6a7 7 0 0 0 2 .9l.3 1.5H15l.3-1.5a7 7 0 0 0 2-.9l1.4.6 1.4-2.3-1.2-.9A7 7 0 0 0 19 12Z"/></svg>
              <svg v-else viewBox="0 0 24 24"><path d="M4 7.5h6l2 2h8v9.5H4z"/><path d="M4 7.5V5h6l2 2"/></svg>
            </span>
            <div>
              <span>{{ modalKind === "settings" ? "偏好与项目信息" : "渲染产物与记录" }}</span>
              <h2 v-if="modalKind === 'settings'" id="settings-title">设置</h2>
              <h2 v-else id="assets-title">资产管理</h2>
            </div>
          </div>
          <button class="settings-close" aria-label="关闭弹窗" @click="closeSettings">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 6 12 12M18 6 6 18"/></svg>
          </button>
        </header>

        <div class="settings-modal-layout">
          <nav v-if="modalKind === 'settings'" class="settings-subnav" aria-label="设置页面">
            <span class="settings-nav-label">设置页面</span>
            <button :class="{ active: settingsPage === 'basic' }" @click="openSettingsPage('basic')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2"/><circle cx="15" cy="12" r="2"/><circle cx="8" cy="18" r="2"/></svg>
              <span>基础设置</span>
            </button>
            <button :class="{ active: settingsPage === 'about' }" @click="openSettingsPage('about')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/></svg>
              <span>关于</span>
            </button>
            <button :class="{ active: settingsPage === 'manual' }" @click="openSettingsPage('manual')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21z"/><path d="M4 5.5v13A2.5 2.5 0 0 1 6.5 16H20M8 7h8M8 10h8"/></svg>
              <span>用户手册</span>
            </button>
          </nav>
          <nav v-else class="settings-subnav" aria-label="资产管理页面">
            <span class="settings-nav-label">资产类别</span>
            <button :class="{ active: assetPage === 'history' }" @click="openAssetPage('history')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="8.5"/><path d="M12 7v5l3.5 2"/></svg>
              <span>渲染历史</span>
            </button>
            <button :class="{ active: assetPage === 'files' }" @click="openAssetPage('files')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="4" width="17" height="16" rx="2"/><circle cx="9" cy="10" r="1.5"/><path d="m5 18 5-5 3 3 2-2 4 4"/></svg>
              <span>渲染文件</span>
            </button>
          </nav>

          <div class="settings-page-scroll">
            <section v-if="modalKind === 'settings' && settingsPage === 'basic'" class="settings-basic-page">
              <div class="settings-page-heading">
                <span class="section-kicker">基础设置</span>
                <h3>后端连接</h3>
                <p>默认使用本机服务地址；仅在部署环境变化时需要调整。</p>
              </div>
              <label class="settings-api-field">
                服务地址
                <input v-model="apiBase" placeholder="http://127.0.0.1:8000" />
              </label>
              <div class="settings-api-actions">
                <button class="ghost" :disabled="settingsActionLoading !== ''" @click="checkSettingsConnection">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12a7 7 0 0 1 12-4.9L19 9"/><path d="M19 5v4h-4M19 12a7 7 0 0 1-12 4.9L5 15"/><path d="M5 19v-4h4"/></svg>
                  {{ settingsActionLoading === "health" ? "检查中…" : "检查连接" }}
                </button>
                <button class="ghost" :disabled="settingsActionLoading !== ''" @click="refreshSettingsPlotCatalog">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19.5h16M6 16V9M10 16V5M14 16v-4M18 16V7"/></svg>
                  {{ settingsActionLoading === "plots" ? "同步中…" : "刷新图型目录" }}
                </button>
              </div>
              <p
                v-if="settingsActionMessage"
                :class="['settings-action-feedback', settingsActionTone]"
                role="status"
                aria-live="polite"
              >
                <span class="settings-feedback-icon" aria-hidden="true">
                  <svg v-if="settingsActionTone === 'success'" viewBox="0 0 24 24"><path d="m5 12 4.5 4.5L19 7"/></svg>
                  <svg v-else-if="settingsActionTone === 'loading'" viewBox="0 0 24 24"><path d="M20 12a8 8 0 1 1-2.3-5.6"/><path d="M20 4v5h-5"/></svg>
                  <svg v-else viewBox="0 0 24 24"><path d="M12 8v5M12 17h.01"/><circle cx="12" cy="12" r="9"/></svg>
                </span>
                {{ settingsActionMessage }}
              </p>
            </section>
            <AboutPage v-else-if="modalKind === 'settings' && settingsPage === 'about'" />
            <ManualPage v-else-if="modalKind === 'settings' && settingsPage === 'manual'" />
            <AssetManagementPage v-else :page="assetPage" />
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
