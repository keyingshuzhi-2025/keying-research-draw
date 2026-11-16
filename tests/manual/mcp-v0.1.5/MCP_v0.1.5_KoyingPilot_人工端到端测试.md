# MCP v0.1.5 柯影智航人工端到端测试

本文件同时保留已完成实测结果与可复用的补充回归步骤。项目负责人已确认 v0.1.5 项目测试完成；没有单独结果记录的回归步骤不代表当前发布阻塞项。

## 测试目标

从柯影智航 DSH 聊天会话工作区读取普通数据文件，通过 Research Draw MCP 分块上传到 MCP 逻辑工作区，再检查数据并完成绘图。测试重点是高熵文件的分块传输是否完整。

DSH 工作区与 MCP 逻辑工作区是两个独立的存储边界，即使它们在配置中都使用“工作区”一词。已验证入口是 DSH 会话工作区中的普通文件；柯影智航侧读取文件字节，再通过 MCP 上传工具发送。`import_data_file` 不能直接读取 DSH 工作区的绝对路径。本测试不要求把源文件复制到 MCP 逻辑工作区根目录；上传完成的数据应进入当前 MCP 会话的私有输入目录，成图再由客户端取回 DSH 工作区。数据方向是：

```text
DSH 工作区文件 → 柯影智航侧读取字节 → MCP 上传工具 → MCP 会话私有目录 → 检查与绘图 → 成图取回到 DSH 工作区
```

| 边界 | 本次实测配置 | 作用 |
| --- | --- | --- |
| DSH 工作区 | `research-draw-mcp-test` → `/Volumes/柯影数智/研发部/实验/research-draw-mcp-test` | 会话 cwd、文件沙箱和成图交付位置 |
| MCP 逻辑工作区 | `research` → `/Volumes/柯影数智/研发部/实验/demo-test` | 服务端允许使用的存储根 |
| MCP 会话目录 | `demo-test/.mcp-sessions/<MCP会话标识>/` | 该 MCP 会话的 `inputs/mcp`、`outputs/mcp` 和临时数据 |

`import_data_file` 只适用于 MCP 服务可见的当前会话目录或所选逻辑工作区根目录。DSH 工作区路径不会自动成为 MCP 源路径。本测试使用 `upload_data_file` 或分块上传工具跨越两个存储边界。

## 已完成的用户实测

用户提供的本轮实测已验证“DSH 会话工作区文件 → MCP 分块上传 → MCP 绘图 → 成图交付回会话工作区”：

- MCP 连接：Research Draw v0.1.5，本地 stdio；DSH 源文件来自 `/Volumes/柯影数智/研发部/实验/research-draw-mcp-test`，逻辑名 `research` 映射到 MCP 服务端 `/Volumes/柯影数智/研发部/实验/demo-test`。
- 输入：`xrd_two_samples_small.csv`。先将两列宽表无损重塑成长表，`TwoTheta`、`Intensity`、`Sample`，共 4,002 行。
- 上传：分块上传，原表块大小 8 KiB、重塑后表块大小 32 KiB；每块独立 gzip + Base64，服务端累计校验 `received_bytes`。
- 绘图：`start_plot_job` 返回 queued，约 3.41 秒后 succeeded；成图为 XRD 双样本曲线。
- 成果：输入位于 MCP 会话 `inputs/mcp/`，`file_id=061445edeb82_xrd_two_samples_small.csv`；成图位于同一 MCP 会话 `outputs/mcp/`，`render_id=xrd_two_samples_small_bab39a48cc95`；PNG 为 2100×1500、168,802 字节，且 `revisable=true`。
- 交付：客户端将 MCP 会话输出取回到 DSH 工作区 `research-draw-mcp-test/xrd_two_samples_small.png`。

### 高熵文件上传与批量绘图：通过

用户提供的本轮附件测试结果：

- 源文件：附件 `mcp_direct_import_e2e.csv`，20,277 字节；由于应用附件原始对象只读，实际从 DSH 工作区同名副本读取。副本 SHA-256 与附件一致：`09f6e340eee0851d78e5df027912a91c11659f16f976fbc848cc5999adf345aa`。
- 数据画像：512 行；`sample` 为 0–511 且无缺失，`signal` 为 float64，`noise` 是 512 个互不相同的随机字符串。`noise` 应按标识符处理，不作为分组变量。
- 上传：第一次以 32 KiB 创建上传时，文件小于块大小，服务端将其视为单块并要求该块完整包含 20,277 字节；发送 8,192 字节被正确拒绝。取消后以 8 KiB 重建，得到 3 块：8,192 + 8,192 + 3,893 字节。每块独立 gzip + Base64；`received_bytes` 依次达到 8,192、16,384、20,277，完成后得到 `file_id=2dbe48ca0b1c_mcp_direct_import_e2e.csv`。
- 批量绘图：第一次 `create_plots` 因 `plot_configs` 重复指定顶层管理的 `file` 等参数而被正确拒绝；移除 `file`、`mode`、`plot`、`workspace` 后，重提 2 张图均成功，用时约 0.31 秒。
- 成果：散点回归图 `render_id=e2e_signal_scatter_278087bf6136`，输出 `e2e_signal_scatter.png`（2250×1950，约 330 KB）；折线图 `render_id=e2e_signal_line_4d5f2e78a2f0`，输出 `e2e_signal_line.png`（2160×1440，约 388 KB）。两张图均取回到 DSH 会话。

这证明 DSH 工作区中的高熵文件副本可经分块上传进入 MCP 会话私有目录，并完成批量绘图和结果取回。附件原始对象本身没有被 MCP 按路径读取；实际读取的是经 SHA-256 确认与附件内容一致的 DSH 工作区副本。`import_data_file` 绝对路径失败是另一种导入方式的边界限制，不代表分块上传失败。此前 4 KiB Base64 块返回 4,093/4,096 字节是另一轮失败尝试；本次按块 gzip + Base64 的流程通过。

## 测试材料

### 小文件基线

使用本目录中的 [`mcp_upload_small.csv`](mcp_upload_small.csv)，将它放入 DSH 会话工作区后进行小文件单次上传。它用于验证普通工作区文件读取、`upload_data_file`、检查和绘图。

| 属性 | 预期值 |
| --- | --- |
| 文件大小 | 92 字节 |
| 数据行数 | 4（另有 1 行表头） |
| 列 | `sample`, `signal`, `noise` |
| SHA-256 | `fb49d3f7f895b084a866164f8a96dfcd85a77e606a4f053a9f468360891ad696` |

### 高熵分块文件

使用 DSH 会话工作区中的 `mcp_direct_import_e2e.csv` 作为高熵输入；不要调用 `import_data_file`，也不要把源文件复制到 MCP 逻辑工作区根目录。源文件信息如下：

| 属性 | 预期值 |
| --- | --- |
| 文件大小 | 20,277 字节 |
| 数据行数 | 512（另有 1 行表头） |
| 列 | `sample`, `signal`, `noise` |
| 特征 | `noise` 列包含高熵随机字符串 |
| SHA-256 | `09f6e340eee0851d78e5df027912a91c11659f16f976fbc848cc5999adf345aa` |

源文件路径：`/Volumes/柯影数智/研发部/实验/research-draw-mcp-test/mcp_direct_import_e2e.csv`。

## 用例 1：小文件单次上传

在柯影智航中保持当前已选模型，不切换模型。确保 `mcp_upload_small.csv` 在当前 DSH 会话工作区中，发送：

> 请从当前 DSH 会话工作区读取 `mcp_upload_small.csv` 的原始字节，通过 Research Draw MCP 的 `upload_data_file` 上传到默认逻辑工作区。不要调用 `import_data_file`，不要把源文件复制到 MCP 逻辑工作区根目录。上传后调用 `inspect_data_file`，并用 `create_plot` 绘制 `sample` 对 `signal` 的散点图。返回上传大小、行数、列名和绘图路径。

**预期：** 上传成功；文件大小与基线文件一致；4 行、3 列；散点图成功生成。

## 用例 2：高熵文件分块上传

确认 `mcp_direct_import_e2e.csv` 位于当前 DSH 会话工作区，再发送：

> 从当前 DSH 会话工作区读取 `mcp_direct_import_e2e.csv` 的原始字节，仅通过 Research Draw MCP 完成上传、检查和绘图。不要调用 `import_data_file`，不要把源文件复制到 MCP 逻辑工作区根目录，也不要把 MCP 文件反向导入柯影智航。按原始字节切片，不要重建或改写 CSV；调用 `begin_data_upload`，`chunk_size=8192`，每块独立 gzip 后 Base64 上传；如果 gzip 后没有缩小则改用 identity。逐块确认 `received_bytes`，上传完成后调用 `complete_data_upload`。然后调用 `inspect_data_file` 和 `suggest_plots`；把 `noise` 识别为每行唯一的标识列，不按它分组。最后调用 `create_plots` 一次生成 `scatter` 和 `line`，共享映射为 `x_col=sample`、`y_col=signal`。`plot_configs` 中只放各图型专属覆盖项，不要放 `file`、`mode`、`plot` 或 `workspace`。报告上传大小、行数、列名、两个图像及路径。

分块参数预期：

| 项目 | 预期值 |
| --- | ---: |
| `total_size` | 20,277 |
| `chunk_size` | 8,192 |
| `chunk_count` | 3 |
| 最后一个分块 | 3,893 字节 |

每个分块可独立 gzip 后再编码 Base64。若 gzip 后尺寸没有缩小，使用 `identity` 原始块上传。不要把 `chunk_size` 误当成建议上限：创建上传后每个非末块都必须达到该大小，末块必须恰好补齐剩余字节。

**验收标准：** 3 个分块均确认成功；组装文件为 20,277 字节且 SHA-256 与源副本一致；`inspect_data_file` 返回 512 行及 `sample`、`signal`、`noise` 三列；批量绘制散点回归图和折线图均成功。已通过的实际结果见“高熵文件上传与批量绘图：通过”。

如果某块返回实际字节数与预期不符，不要调用 `complete_data_upload`。记录块序号和 MCP 错误，调用 `cancel_data_upload` 清理该次上传，然后用较小的 `chunk_size` 重新开始。不要复用已取消的 `upload_id`。

## 用例 3：完整性核对

上传前，在 DSH 会话工作区中计算源文件 SHA-256：

```bash
shasum -a 256 mcp_direct_import_e2e.csv
```

上传完成后，若 MCP 返回的目标文件路径可由本机文件工具读取，则计算目标 SHA-256 并与测试材料中的预期值比较。比较哈希只用于确认字节完整性，不会把 MCP 文件导入 DSH 会话工作区。

如果客户端无法读取 MCP 返回的目标路径，记录为“当前无法端到端核验字节级完整性”。此时行数、列名和文件大小只能验证结构和长度，不能证明高熵内容逐字节一致。

## 用例 4：未完成上传与取消

使用同一测试文件创建一次分块上传，只上传第 0 块，然后调用 `complete_data_upload`。

**预期：** 返回未完成状态并指出缺失分块；不会生成可检查的 `file_id`。随后调用 `cancel_data_upload`，预期 `cancelled=true`，并且 `list_workspace_files` 中没有这次未完成上传产生的数据文件。

## 用例 5：重复块保护

新建一条小型分块上传，成功上传第 0 块后，再次上传相同 `upload_id` 和 `chunk_index=0`。

**预期：** MCP 拒绝重复块，且原块不被覆盖。完成或取消后清理本用例数据。

## 问题记录模板

```text
柯影智航版本：
模型（使用当前已选模型，不要为本测试切换）：
Research Draw MCP 状态：
用例编号：
文件名 / 大小：
MCP 工具及参数：
失败阶段：
工具原始错误：
失败块序号 / 预期字节 / 实际字节：
上传后 SHA-256：
inspect_data_file 结果：
绘图结果 / 路径：
是否清理 upload_id 和测试输出：
```

## 测试后清理

- 未完成的分块任务：调用 `cancel_data_upload`。
- 已完成的测试导入文件和渲染结果：根据 MCP 返回的精确路径删除本次测试生成的文件。
- 保留本机源文件 `mcp_direct_import_e2e.csv`，供后续人工复测；除非明确结束测试周期再删除。
- 如另行测试聊天附件入口，按柯影智航的附件管理能力清理本次测试附件；不属于当前 DSH 普通文件上传用例。
- 不要清理该工作区中原有的其他文件或历史结果。
