# 图表登记表

- 更新日期：2026-06-11

## Communications Letters 当前投稿图

| 图 | 路径 | 输入数据 | 生成命令 | 用途 |
|---|---|---|---|---|
| CommL Fig. 1 | `figures/paper/comml_fig1_structural.pdf` | `results/comml/stats/structural_summary.csv` | `python run.py comml-plot` | lag spectrum 与风险折中 |
| CommL Fig. 2 | `figures/paper/comml_fig2_compact.pdf` | `results/comml/stats/coded_summary.csv`, `results/comml/feedback_robustness/summary.csv` | `python run.py comml-plot` | 核心四威胁 BLER 与反馈鲁棒性 |

两图同时保留 PNG 预览版本。正式 LaTeX 只引用 PDF。

## 支持性与诊断图

- `figures/paper/fig1_ber_common_grid.*` 至 `figures/paper/fig8_pash_parameter_sweep.*`：
  长稿或内部支持材料，不进入 CommL 主稿。
- `figures/diagnostics/fig9_pash_optimization.*`：失败 PASH-opt 探索，仅诊断。
- `figures/paper/fig9_pash_optimization.*`：旧遗留副本，不得被当前主稿引用。

## 维护规则

1. CommL 主稿只引用本表的两幅投稿图。
2. 投稿图只能从 `results/comml/stats/` 与
   `results/comml/feedback_robustness/` 的正式输出生成。
3. 新图必须登记输入数据、生成脚本和论文用途。
