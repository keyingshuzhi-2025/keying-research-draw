# -*- coding = utf-8 -*-
# @Time: 2025/10/23 上午10:35
# @Author: 柯影数智
# @File: config.py
# @Email: 1090461393@qq.com
# @SoftWare: PyCharm

"""
config.py — Matplotlib 跨系统图形渲染配置（集成 .env 参数）

功能：
- 自动识别操作系统（macOS / Windows / Linux）并设置合适的中文字体
- 可从 .env / 环境变量读取：后端、字体、主题、DPI、导出格式、保存目录、负号修复
- 激活后端（默认 TkAgg），统一解决负号显示问题
- 主题占位（Nature/Science/IEEE/Default），可扩展为论文风格
- 提供上下文管理器便于临时切换配置
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass
from typing import Optional

import matplotlib

# 尝试加载 .env（若未安装 python-dotenv，不报错）
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()


def _set_matplotlib_backend(backend: Optional[str]) -> None:
    if not backend:
        return
    if "MPLBACKEND" not in os.environ:
        os.environ["MPLBACKEND"] = backend
    if "matplotlib.pyplot" in sys.modules:
        return
    try:
        matplotlib.use(os.environ["MPLBACKEND"])
    except Exception:
        print(f"⚠️ 后端 {backend} 不可用，使用默认设置。")


def ensure_matplotlib_backend() -> None:
    _set_matplotlib_backend(os.getenv("PLOT_BACKEND", "TkAgg"))


ensure_matplotlib_backend()


def _get_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _mkdir_p(path: str) -> None:
    if not path:
        return
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass


@dataclass
class PlotConfig:
    # 基础渲染
    backend: str = "TkAgg"
    mac_font: str = "STHeiti"
    win_font: str = "SimHei"
    linux_font: str = "Noto Sans CJK SC"
    fix_minus: bool = True

    # 主题与输出
    theme: str = "DEFAULT"  # DEFAULT | NATURE | SCIENCE | IEEE
    dpi: int = 300
    fmt: str = "PNG"
    save_dir: str = "outputs/figures"

    # 行为控制
    auto_apply: bool = False

    # ========== 构造器 ==========
    @classmethod
    def from_env(cls) -> "PlotConfig":
        """根据环境变量/.env 创建配置实例。"""
        return cls(
            backend=os.getenv("PLOT_BACKEND", "TkAgg"),
            mac_font=os.getenv("MAC_FONT", "STHeiti"),
            win_font=os.getenv("WIN_FONT", "SimHei"),
            linux_font=os.getenv("LINUX_FONT", "Noto Sans CJK SC"),
            fix_minus=_get_bool("FIX_UNICODE_MINUS", True),
            theme=os.getenv("PLOT_THEME", "DEFAULT").upper(),
            dpi=int(os.getenv("PLOT_DPI", "300")),
            fmt=os.getenv("PLOT_FORMAT", "PNG").upper(),
            save_dir=os.getenv("PLOT_OUTDIR_OVERRIDE")
            or os.getenv("PLOT_SAVE_DIR", "outputs/figures"),
            auto_apply=_get_bool("PLOT_AUTO_APPLY", False),
        )

    # ========== 应用配置 ==========
    def apply(self) -> None:
        """根据当前系统与主题，应用 matplotlib 全局设置。"""
        # 1) 后端
        _set_matplotlib_backend(self.backend)

        # 2) 字体
        system = platform.system()
        if system == "Darwin":
            font = self.mac_font
        elif system == "Windows":
            font = self.win_font
        else:
            font = self.linux_font
        matplotlib.rcParams["font.family"] = font
        if self.fix_minus:
            matplotlib.rcParams["axes.unicode_minus"] = False

        # 3) 主题（占位实现，可按需细化）
        self._apply_theme(self.theme)

        # 4) 输出目录
        save_dir = os.getenv("PLOT_OUTDIR_OVERRIDE") or self.save_dir
        _mkdir_p(save_dir)

        print(
            f"✅ Matplotlib 配置完成 | OS: {system} | 字体: {font} | 后端: {self.backend} | "
            f"主题: {self.theme} | DPI: {self.dpi} | 格式: {self.fmt} | 目录: {save_dir}"
        )

    # ========== 主题实现（可扩展） ==========
    def _apply_theme(self, theme: str) -> None:
        t = theme.upper()
        if t == "NATURE":
            matplotlib.rcParams.update({
                "figure.dpi": self.dpi,
                "savefig.dpi": self.dpi,
                "axes.labelsize": 11,
                "xtick.labelsize": 10,
                "ytick.labelsize": 10,
                "axes.linewidth": 1.0,
                "lines.linewidth": 1.5,
                "legend.frameon": False,
                "grid.linestyle": ":",
                "grid.alpha": 0.25,
            })
        elif t == "SCIENCE":
            matplotlib.rcParams.update({
                "figure.dpi": self.dpi,
                "savefig.dpi": self.dpi,
                "axes.labelsize": 12,
                "xtick.labelsize": 10,
                "ytick.labelsize": 10,
                "axes.linewidth": 1.1,
                "lines.linewidth": 1.8,
                "legend.frameon": False,
            })
        elif t == "IEEE":
            matplotlib.rcParams.update({
                "figure.dpi": self.dpi,
                "savefig.dpi": self.dpi,
                "axes.labelsize": 9,
                "xtick.labelsize": 8,
                "ytick.labelsize": 8,
                "lines.linewidth": 1.2,
            })
        else:  # DEFAULT
            matplotlib.rcParams.update({
                "figure.dpi": self.dpi,
                "savefig.dpi": self.dpi,
            })

    # ========== 辅助：保存路径拼接 ==========
    def outpath(self, name: str, fmt: Optional[str] = None) -> str:
        save_dir = os.getenv("PLOT_OUTDIR_OVERRIDE") or self.save_dir
        _mkdir_p(save_dir)
        ext = (fmt or self.fmt).lower()
        return os.path.join(save_dir, f"{name}.{ext}")

    # ========== 上下文管理器：临时应用配置 ==========
    def __enter__(self):
        self.apply()
        return self

    def __exit__(self, exc_type, exc, tb):
        # 这里可按需恢复旧 rcParams；当前保持全局设置
        return False


# 可选：在 import 时自动应用
if _get_bool("PLOT_AUTO_APPLY", False):
    PlotConfig.from_env().apply()
