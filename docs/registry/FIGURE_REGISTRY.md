# 图表登记表

- 更新日期：**2026-09-23**
- 状态：**已冻结** —— 论文已录用，图不再变更。

## ⭐ 投稿图母版（提交给 IEEE 的版本，2026-09-21 定稿）

| 图 | 母版路径 | 输入数据 | 用途 |
|---|---|---|---|
| Fig. 1 | `paper/accepted/figures/fig1_structural.eps` | `results/comml/stats/structural_summary.csv` | lag spectrum 与风险折中 |
| Fig. 2 | `paper/accepted/figures/fig2_coded_feedback.eps` | `results/comml/stats/coded_summary.csv`, `results/comml/feedback_robustness/summary.csv` | 核心四威胁 BLER 与反馈鲁棒性 |

⚠️ 母版的生成**不能**用 `python run.py comml-plot`（该命令不转发参数，走默认
DejaVu Sans 输出到 `figures/paper/`）。必须直接调用脚本：

```sh
.venv/bin/python redesign/plot_comml.py --camera-ready --out-dir <输出目录>
# 生成后重命名：comml_fig1_structural -> fig1_structural
#               comml_fig2_compact    -> fig2_coded_feedback
```

要求与实现要点：

- 提交要求是 **EPS、每图一个单独文件**（从 PDF/PowerPoint 导出的图形不被接受）。
- 两个 EPS 内字体全部为 **FontType 42**，无 Type 3；字体族为 **Arial**
  （不用 macOS Helvetica：它是 .ttc 集合，嵌入结果为 `/FontName /unknown`）。
- 同目录另存 `.pdf` 副本，仅便于本地查看，**不是**提交件。
- ⚠️ EPS 第 3 行 `%%Title` 仍是生成时的旧名
  （`comml_fig1_structural.eps` / `comml_fig2_compact.eps`）：matplotlib 的 `%%Title`
  取自 `savefig()` 文件名，重命名后必然如此，`metadata=` 参数对 PS/EPS 无效。
  已确认**不影响任何投稿要求**，故保留原样、不人工改写。

## 论文图（工作副本，`figures/paper/`）

| 图 | 路径 | 输入数据 | 生成命令 |
|---|---|---|---|
| Fig. 1 | `figures/paper/comml_fig1_structural.pdf` | `results/comml/stats/structural_summary.csv` | `python run.py comml-plot` |
| Fig. 2 | `figures/paper/comml_fig2_compact.pdf` | `results/comml/stats/coded_summary.csv`, `results/comml/feedback_robustness/summary.csv` | `python run.py comml-plot` |

两图同时保留 PNG 预览版本。正式 LaTeX 只引用 PDF。

## 支持性与诊断图

- `figures/paper/fig1_ber_common_grid.*` 至 `figures/paper/fig8_pash_parameter_sweep.*`：
  长稿或内部支持材料，不进入短稿主稿。
- `figures/paper/fig9_pash_optimization.*`：失败 PASH-opt 探索的遗留副本，
  仅诊断，不得被主稿引用。
- `figures/paper/comml_fig2_coded.*`、`figures/paper/comml_fig3_feedback_robustness.*`：
  被 `comml_fig2_compact` 合并取代的支持性产物，不被主稿引用。

## 维护规则

1. 短稿主稿只引用本表 Fig. 1–2。
2. 投稿图只能从 `results/comml/stats/` 与
   `results/comml/feedback_robustness/` 的正式输出生成。
3. 新图必须登记输入数据、生成脚本和论文用途。
