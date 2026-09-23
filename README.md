# Predictability-Aware Soft Set Hopping Against Reactive Jamming

面向**延迟反应式干扰**的 OFDM 可预测性感知稀疏子载波跳频（PASH）研究代码与实验数据。

本仓库是论文 *Predictability-Aware Soft Set Hopping Against Reactive Jamming*
（IEEE Communications Letters，已录用）的**可复现材料**：完整的仿真代码、正式实验
数据、绘图脚本与论文 LaTeX 源码。

> **本仓库只含学术材料。** 稿件评审、编辑通信等过程性材料不在公开范围内。

## 研究问题

跳频抗干扰系统常在"记忆最近被干扰子载波"这一硬排斥规则下工作（本文记为 **MCSH**）。
本文的核心发现是：这类硬排斥在**已知短延迟**下确实能消除稳态碰撞，但它有结构性代价 ——

- 一旦干扰方的延迟超出记忆窗口，会形成 **lag spike**；
- 硬排斥本身使候选集合**可被干扰方预测**（candidate-aware 暴露）。

据此提出 **PASH**（Predictability-Aware Soft Set Hopping）：用**软排斥**替代硬排斥，
并对**包含概率设上限**（PASH-cap），在短延迟保护与抗自适应/候选感知干扰之间取得折中。

配套的接收机侧方法是 **BRW / mixture-LLR** 软判决译码，用于把跳频结构带来的增益与
接收机软信息的增益**分离**开来做消融。

## 仓库结构

```text
micro_fh_ofdm-public/
├── run.py                  # 统一入口（唯一的命令入口，见下）
├── redesign/               # 全部 Python 代码：仿真库 + 各实验 + 绘图
│   ├── fair_grid_sim.py    #   共享库：OFDM 网格、QPSK、卷积码、统计
│   ├── innovation_sim.py   #   共享库：BRW 译码器、后验碰撞
│   ├── advanced_experiment.py   # 主实验：MCSH vs PASH vs Random
│   ├── plot_comml.py       #   图 1/图 2 绘制脚本
│   └── validate_*.py       #   模型有效性与理论边界校验
├── results/                # 正式实验数据（CSV + JSON + run_manifest）
├── figures/paper/          # 论文图（PDF + PNG）
├── paper/
│   ├── comml_ieee.tex      # 短稿源码（双盲版，作者为占位符）
│   ├── full_ieee.tex       # 支持性长稿
│   ├── accepted/           # 录用版：实名 manuscript.tex/.pdf + EPS 图母版
│   └── i18n-cn/            # 中文翻译版
├── docs/                   # 实验设计/结果报告、复现说明、登记表
└── output/pdf/             # 编译交付 PDF
```

## 快速开始

需要 Python ≥3.10 与 LaTeX 编译器 [Tectonic](https://tectonic-typesetting.github.io/)。

```sh
python -m venv .venv && source .venv/bin/activate
pip install numpy scipy matplotlib tqdm

python run.py quick           # 结构检查 + Python 编译 + 模型有效性检查（约 3 分钟）
python run.py comml-smoke     # 轻量冒烟实验（输出到 tmp/）
python run.py comml-stats     # 正式核心实验（输出到 results/comml/stats/）
python run.py comml-plot      # 生成论文图
python run.py comml-paper     # 编译短稿
```

**所有命令都走 `python run.py <command>`**，不要直接运行 `redesign/` 下的脚本
（脚本内部用相对路径解析输出目录）。完整命令列表见 `python run.py --help`。

## 关键实验

核心实验为 3 方法 × 4 威胁的 BLER 矩阵，接收机统一使用 mixture-LLR：

| 维度 | 取值 |
|---|---|
| 方法 | Random、MCSH-L2、PASH-c15 |
| 威胁 | `fixed_d1`、`fixed_d3`、`candidate_aware`、`causal_adaptive_lag` |
| 停止规则 | 2000–5000 帧，或累计 100 个错误帧 |

威胁模型的有效性由 7 项独立检查把关（`python run.py threat-validity`），
确保干扰方**不访问当前真实跳频集合**、碰撞反馈只在时隙结束后更新。

## 结果与可复现性

- 正式数据：`results/`（每个目录含 `run_manifest.json`，记录源文件哈希与配置）
- 复现命令与数据来源：`docs/reproducibility.md`
- 实验设计与结果报告：`docs/experiments/`
- 数据/图表/产物登记表：`docs/registry/`

所有随机性均通过 `fair_grid_sim.seeded_rng(seed)` 控制，不使用全局 `np.random`。

## 已知限制

本仓库的结论**不**支持以下主张，使用时请注意：

1. 不完美反馈仍是抽象的报告腐化/延迟模型，未绑定具体感知或控制信道。
2. 没有外部 SOTA 方法的数值复现 —— 仓库内的 SBS 只是**项目内部**的 adapted
   stress baseline，**不可**用于 SOTA 对比。
3. 核心矩阵限于单一 SNR/JSR、AWGN 信道与 K7 卷积码。
4. **PASH-cap 不是全场景最优**：在 `candidate_aware` 威胁下 Random 反而优于
   PASH-c15。PASH 的正确定位是**跨威胁折中**，而非全面优势。

## 许可与引用

- **代码**（`run.py`、`redesign/`）：MIT，见 [LICENSE](LICENSE)。
- **论文**（`paper/` 下的正文、图、PDF）：版权归 © 2026 IEEE。`paper/accepted/`
  是作者**录用版**（author-accepted manuscript），依 IEEE 自存档政策在此公开；
  正式出版版本请以 IEEE Xplore 为准。
- 若本工作对你的研究有帮助，请引用正式发表版本（卷期与 DOI 见 IEEE Xplore）。
