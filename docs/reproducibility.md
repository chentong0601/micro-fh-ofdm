# 可复现性说明

- 更新日期：2026-06-11
- Python 环境：`.venv`
- 统一入口：`run.py`
- LaTeX 编译器：Tectonic

## 当前 Communications Letters 工作流

威胁模型有效性：

```sh
python run.py threat-validity
```

精简 smoke：

```sh
python run.py comml-smoke
```

最终核心统计与投稿图：

```sh
python run.py comml-stats
```

只重新生成投稿图：

```sh
python run.py comml-plot
```

只编译 CommL 投稿稿：

```sh
python run.py comml-paper
```

CommL 投稿前完整检查：

```sh
python run.py comml-preflight
```

不完美反馈鲁棒性实验：

```sh
python run.py feedback-smoke
python run.py feedback-stats
python run.py feedback-plot
```

正式输出：

- `results/comml/stats/structural_summary.csv`
- `results/comml/stats/coded_summary.csv`
- `results/comml/stats/config.json`
- `results/comml/stats/run_manifest.json`
- `docs/experiments/final_comml_experiment_results.md`
- `figures/paper/comml_fig1_structural.pdf`
- `figures/paper/comml_fig2_compact.pdf`
- `results/comml/feedback_robustness/summary.csv`
- `results/comml/feedback_robustness/run_manifest.json`
- `paper/comml_ieee.pdf`
- `output/pdf/comml_ieee.pdf`

`comml_fig2_compact.pdf` combines the coded BLER comparison and the
feedback-degradation lag-selection audit. The older separate coded and
feedback figures remain supporting artifacts and are not referenced by the
current manuscript.

## CommL 正式实验配置

- 方法：Random、MCSH-L2、PASH-c15。
- 威胁：`fixed_d1`、`fixed_d3`、`candidate_aware`、`causal_adaptive_lag`。
- 接收机：mixture-LLR。
- 最小帧数：2000。
- 最大帧数：5000。
- 目标：100 个错误帧。

Causal jammer 使用显式连续状态。每个方法-威胁组合只生成一条攻击轨迹；接收机必须
复用同一轨迹。攻击动作选择不访问当前真实集合，碰撞反馈仅在时隙结束后更新状态。

## 通用命令

```sh
python run.py --help
python run.py quick
python run.py outputs
python run.py paper
python run.py preflight
```

`quick` 当前包含完整结构有效性检查，耗时约三分钟，不是瞬时 lint。

## 其他实验入口

```sh
python run.py advanced-smoke
python run.py advanced-paper
python run.py advanced-stats
python run.py baseline-paper
python run.py phase2-paper
python run.py pash-paper
```

这些结果属于长稿、支持性或诊断实验，不是当前 CommL 正文数字来源。
