# 论文产物登记表

更新日期：2026-06-11

## 当前产物

| 产物 | 路径 | 说明 | 状态 |
|---|---|---|---|
| CommL 投稿稿 LaTeX | `paper/comml_ieee.tex` | Communications Letters 五页限制内独立短稿 | 当前投稿稿 |
| CommL 投稿稿 PDF 工作副本 | `paper/comml_ieee.pdf` | `python run.py comml-paper` 编译输出 | 当前投稿稿 |
| CommL 投稿稿 PDF 交付副本 | `output/pdf/comml_ieee.pdf` | 当前短文审阅与提交副本 | 当前投稿稿 |
| 长稿 LaTeX | `paper/full_ieee.tex` | 八页支持性长稿 | 支持性 |
| 长稿 PDF | `paper/full_ieee.pdf`, `output/pdf/full_ieee.pdf` | 长稿工作与交付副本 | 支持性 |
| 当前参考文献 | `paper/references_ieee.bib` | IEEE BibTeX | 当前 |
| VS Code 工作区 | `micro_fh_ofdm.code-workspace`, `.vscode/tasks.json` | 项目预检、实验和论文编译入口 | 当前维护 |
| 下一阶段执行计划 2.0 | `docs/plans/next_stage_execution_plan_v2.md` | 基于投稿准备度评审的门控式实验与短文执行方案 | 当前有效 |
| Communications Letters 提纲 | `paper/OUTLINE_CommL.md` | 当前短文写作依据 | 当前 |
| CommL 最终实验设计与结果 | `docs/experiments/final_comml_experiment_design.md`, `docs/experiments/final_comml_experiment_results.md` | 投稿数字与实验边界 | 当前 |
| CommL 投稿图 | `figures/paper/comml_fig1_structural.pdf`, `figures/paper/comml_fig2_compact.pdf` | 短稿使用的两幅紧凑图 | 当前 |
| 投稿准备度评审 | `docs/reviews/comml_submission_readiness_review_2026-06-09.md` | 项目、结果、图片和提纲的阻断项审查 | 当前依据 |

## 历史产物

| 产物 | 路径 | 说明 |
|---|---|---|
| 第一阶段短文 | `paper/letter_ieee.tex`, `paper/letter_ieee.pdf` | 公平共同栅格短文，保留复现 |
| 下一阶段执行计划 1.0 | `docs/plans/next_stage_execution_plan.md` | 已由 2.0 版本取代，仅保留历史追溯 |
| MATLAB clean-room 复核脚本 | `validation/matlab_crosscheck/structural_crosscheck.m` | 可选独立语言结构验证，当前未运行 |
| 旧中文稿/早期改写稿 | `archive/papers/legacy/` | 仅历史追溯 |
| 旧 LaTeX 中间文件 | `archive/papers/build/`, `tmp/latex-build/` | 可删除或重建 |

## 检查规则

1. `paper/comml_ieee.pdf` 与 `output/pdf/comml_ieee.pdf` 应哈希一致。
2. 当前 CommL 交付只看 `output/pdf/comml_ieee.pdf`。
3. 不再把审查报告、gap 分析或过程日志放到 `paper/`。
