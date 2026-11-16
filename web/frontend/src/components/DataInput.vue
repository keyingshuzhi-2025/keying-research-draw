<script setup>
import { useResearchDrawStore } from "../composables/useResearchDrawStore";

const store = useResearchDrawStore();
const {
  dataSourceMode,
  fileInputRef,
  pickedFile,
  uploadedFileId,
  uploadedFileName,
  uploadColumns,
  previewRows,
  tableHeaders,
  tableRows,
  uploadFiles,
  uploadFilesLoading,
  onFileChosen,
  triggerFilePick,
  uploadSelectedFile,
  addTableColumn,
  removeTableColumn,
  addTableRow,
  removeTableRow,
  uploadTableDataset,
  formatFileSize,
  formatHistoryTime,
  fetchUploadFiles,
  clearUploadedFiles,
  useUploadedFile,
  deleteUploadedFile
} = store;
</script>

<template>
  <section id="section-data" class="panel section-card">
    <div class="section-head">
      <div>
        <span class="section-kicker">步骤 01 · 数据</span>
        <h2>准备绘图数据</h2>
        <p class="section-subtitle">上传表格文件，或直接录入少量示例数据。</p>
      </div>
      <div class="segmented">
        <button :class="{ active: dataSourceMode === 'upload' }" @click="dataSourceMode = 'upload'">文件上传</button>
        <button :class="{ active: dataSourceMode === 'table' }" @click="dataSourceMode = 'table'">表格录入</button>
      </div>
    </div>

    <div v-if="dataSourceMode === 'upload'" class="upload-card">
      <input ref="fileInputRef" class="hidden-file-input" type="file" accept=".csv,.tsv,.txt,.xlsx,.xls" @change="onFileChosen" />
      <div class="upload-action-row">
        <button class="ghost upload-pick-btn" @click="triggerFilePick">
          {{ pickedFile ? `已选文件：${pickedFile.name}` : "上传数据文件" }}
        </button>
        <button class="primary upload-parse-btn" @click="uploadSelectedFile">文件解析</button>
      </div>
      <p v-if="pickedFile" class="muted">待解析文件：{{ pickedFile.name }}</p>
      <p v-if="uploadedFileId" class="muted">当前数据集：{{ uploadedFileName }}（ID: {{ uploadedFileId }}）</p>
    </div>

    <div v-else class="table-editor-card">
      <div class="btn-row">
        <button class="ghost" @click="addTableColumn">加一列</button>
        <button class="ghost" @click="removeTableColumn">减一列</button>
        <button class="ghost" @click="addTableRow">加一行</button>
        <button class="ghost" @click="removeTableRow">减一行</button>
        <button class="primary" @click="uploadTableDataset">保存为数据集</button>
      </div>
      <div class="table-wrap">
        <table class="editor-table">
          <thead>
            <tr>
              <th v-for="(h, hi) in tableHeaders" :key="`h-${hi}`">
                <input v-model="tableHeaders[hi]" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in tableRows" :key="`r-${ri}`">
              <td v-for="(cell, ci) in row" :key="`c-${ri}-${ci}`">
                <input v-model="tableRows[ri][ci]" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="preview-card">
      <h3>数据预览</h3>
      <div v-if="uploadColumns.length" class="table-wrap">
        <table class="preview-table">
          <thead>
            <tr>
              <th v-for="col in uploadColumns" :key="col">{{ col }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in previewRows" :key="idx">
              <td v-for="col in uploadColumns" :key="`${idx}-${col}`">
                {{ row[col] }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-else class="muted">上传或保存表格后，会显示列名与前 5 行数据。</p>
    </div>

    <div class="upload-files-card">
      <div class="upload-files-head">
        <h3>上传文件管理</h3>
        <div class="btn-row">
          <button class="ghost" :disabled="uploadFilesLoading" @click="fetchUploadFiles">刷新</button>
          <button class="ghost" :disabled="uploadFilesLoading || !uploadFiles.length" @click="clearUploadedFiles">清空上传文件</button>
        </div>
      </div>

      <p v-if="uploadFilesLoading" class="muted">正在读取上传文件列表...</p>
      <div v-else-if="uploadFiles.length" class="upload-files-list">
        <article v-for="item in uploadFiles" :key="item.file_id" class="upload-file-item">
          <div class="upload-file-meta">
            <strong>{{ item.file_id }}</strong>
            <span>{{ formatFileSize(item.size) }} · {{ formatHistoryTime(item.modified_at) }}</span>
            <span v-if="uploadedFileId === item.file_id" class="active-badge">当前使用中</span>
          </div>
          <div class="upload-file-actions">
            <button class="ghost" @click="useUploadedFile(item.file_id)">使用</button>
            <button class="ghost" @click="deleteUploadedFile(item.file_id)">删除</button>
          </div>
        </article>
      </div>
      <p v-else class="muted">暂无上传文件。</p>
    </div>
  </section>
</template>
