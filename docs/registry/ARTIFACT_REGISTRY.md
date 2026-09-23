# 论文产物登记表

更新日期：**2026-09-23**
状态：**已冻结** —— 论文已录用，除勘误外不再产生新产物。

## 论文产物

| 产物 | 路径 | 说明 | 状态 |
|---|---|---|---|
| 短稿 LaTeX（双盲） | `paper/comml_ieee.tex` | 匿名评审形态，作者块为占位符 `Author 1, Author 2, and Author 3` | 工作源码 |
| 短稿 PDF 工作副本 | `paper/comml_ieee.pdf` | `python run.py comml-paper` 编译 | 工作副本 |
| 短稿 PDF 交付副本 | `output/pdf/comml_ieee.pdf` | 与工作副本哈希一致 | 交付副本 |
| ⭐ **录用版（实名）** | `paper/accepted/manuscript.tex`, `paper/accepted/manuscript.pdf` | 实际提交给 IEEE 的终稿，含真实作者与单位 | 已录用 |
| ⭐ **录用版图母版** | `paper/accepted/figures/*.eps`（另附 `.pdf` 预览） | 每图一个单独 EPS 文件，FontType 42 | 已录用 |
| 长稿 LaTeX | `paper/full_ieee.tex` | 八页支持性长稿，作者块为匿名占位符 | 支持性 |
| 长稿 PDF | `paper/full_ieee.pdf`, `output/pdf/full_ieee.pdf` | 长稿工作与交付副本 | 支持性 |
| 参考文献 | `paper/references_ieee.bib` | IEEE BibTeX | 当前 |
| 中文翻译 | `paper/i18n-cn/comml_ieee_cn.tex`, `.pdf` | 短稿中文版 | 当前 |
| 模板 | `paper/IEEEtran.cls` | IEEE 期刊类文件，编译所需（编译器 Tectonic） | 当前 |
| VS Code 工作区 | `micro_fh_ofdm.code-workspace`, `.vscode/tasks.json` | 预检、实验和论文编译入口 | 当前维护 |
| 实验设计与结果 | `docs/experiments/final_comml_experiment_design.md`, `docs/experiments/final_comml_experiment_results.md` | 论文数字与实验边界 | 当前 |
| 投稿图 | `figures/paper/comml_fig1_structural.pdf`, `figures/paper/comml_fig2_compact.pdf` | 见 `FIGURE_REGISTRY.md` | 当前 |

⚠️ **双盲版与实名版的区别**：`paper/comml_ieee.tex` 与 `paper/accepted/manuscript.tex`
相差 **4 处 / 16 行** —— 作者块（实质差异）加 3 处路径/文件名
（`figures/…` 对 `../figures/paper/…`、`references` 对 `references_ieee`）。
引用论文内容时以 `paper/accepted/manuscript.tex` 为准。

⚠️ `paper/accepted/manuscript.tex` 与提交件**逐字节一致**，请勿改写；如需修改请在
`paper/comml_ieee.tex` 上改后重新编译。

## 历史产物（不在本仓库）

初期的 MATLAB 原型、第一阶段短文、早期的 MDPI 投稿材料与投稿过程文档不在本公开
仓库内，属私有归档。本表只登记本仓库中真实存在的路径 —— 每次移动文件必须同步本表
（2026-09-23 订正了 10 处失效路径）。

## 检查规则

1. `paper/comml_ieee.pdf` 与 `output/pdf/comml_ieee.pdf` 应哈希一致。
2. 不再把审查报告、gap 分析或过程日志放到 `paper/`。
3. 本表所列路径必须真实存在。
