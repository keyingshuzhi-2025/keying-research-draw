# 柯影智绘 Atlas · 品牌资源包 v1.0

**品牌**：柯影智绘 Atlas　**产品**：Research Draw 科研绘图工作台<br>
**用途**：Web、App、CLI、GitHub、社交媒体与产品宣传。

## 目录

- `00-preview/` 品牌资源总览图
- `01-original-ai/` AI 生成原始图（未经矢量化）
- `02-vector-svg/` 人工几何重构的 **SVG 可编辑矢量版本**（不是对原图的逐像素精确描摹）
- `03-logo-png/` 透明背景 Logo：横版、竖版、独立符号，适配明/暗底
- `04-app-icons/` App 资源（方形、圆角、Android adaptive、Windows ICO、macOS iconset）
- `05-web-favicon/` Favicon 及网站 PWA 文件
- `06-social-media/` 社交头像、OG 分享卡片、GitHub 与微信封面
- `07-guidelines/` 品牌使用规范 PDF / Markdown
- `08-developer/` 设计令牌 JSON 与 Web head 代码片段

## 重要说明

1. 两张原始图是图像生成作品，**均为位图**；其中完整 Logo 原图为白底 RGB，而 App 图标带透明边缘。
2. `02-vector-svg/` 是为后续产品化额外制作的几何重构稿，**并非将原始 PNG 原样无损转换成 SVG 路径**。细节可能有差异；正式发布前建议确认使用原始视觉版还是几何重构版，并统一版本。
3. App PNG 与 Windows/macOS 图标以原始无字图为基础；`02-vector-svg` 中的图形为独立的几何重构版本，细节与原图略有区别。
4. SVG 字标是可编辑 `<text>`，依赖目标系统的字体可用性；未嵌入或分发任何字体文件。如需供应商印刷，建议在设计软件中确认字体授权后再转曲。
5. 当前资产未进行商标近似检索、商标注册或图标平台专项合规审查。
6. 建议品牌体系统一采用「柯影智绘 Atlas」，对外产品名称与技术项目名可组合写作：`柯影智绘 Atlas · Research Draw`。

## 最快使用

- Web favicon：将 `05-web-favicon` 目录中 favicon 与 manifest 放入网站 public 目录；参见 `08-developer/web-head.html`。
- 浏览器 / PWA：使用 `android-chrome-192.png`、`android-chrome-512.png`。
- Windows：`04-app-icons/atlas-windows.ico`。
- macOS：将 `04-app-icons/Atlas.iconset/` 复制到 macOS，执行 `iconutil -c icns Atlas.iconset`。
- iOS App Store：`04-app-icons/atlas-app-square-1024.png`（不预先切圆角，系统负责裁剪）。
- Android Adaptive Icon：`android-adaptive-foreground-1024.png` 及 `android-adaptive-background-1024.png`；开发时按 Android 规范验证安全区及图层比例。
- GitHub 社交预览：`06-social-media/atlas-github-social-preview-1280x640.png`。

## 颜色

| 名称 | HEX | 用途 |
|---|---|---|
| Deep Navy | #071B35 | 深色背景 |
| Navy | #102A50 | 品牌文字、主色 |
| Azure | #2A78F5 | 科技蓝 |
| Blue | #416DE5 | 强调色 |
| Cyan | #08C4E8 | 数据与轨道 |
| Teal | #19D7BD | 科研青 |
| Paper | #F4F7FB | 浅色背景 |

建议：核心品牌 Logo 周围留白 ≥ 图标高度的 12.5%；透明符号版最低 32px，带文字的横版 Logo 建议宽度不小于 240px。
