# 数据登记表

- 更新日期：2026-06-10

## 当前投稿正式数据

| 数据集 | 路径 | 生成命令 | 状态 |
|---|---|---|---|
| CommL structural | `results/comml/stats/structural_summary.csv` | `python run.py comml-stats` | 正式 |
| CommL coded BLER | `results/comml/stats/coded_summary.csv` | `python run.py comml-stats` | 正式 |
| CommL config | `results/comml/stats/config.json` | `python run.py comml-stats` | 正式 |
| CommL manifest | `results/comml/stats/run_manifest.json` | `python run.py comml-stats` | 正式 |
| Feedback robustness | `results/comml/feedback_robustness/summary.csv` | `python run.py feedback-stats` | 正式补充实验 |
| Feedback robustness manifest | `results/comml/feedback_robustness/run_manifest.json` | `python run.py feedback-stats` | 正式补充实验 |
| Adversarial threat checks | `results/model_validity/adversarial_threat_checks.csv` | `python run.py threat-validity` | 正式验证 |
| Model validity checks | `results/model_validity/model_validity_checks.csv` | `python run.py validity` | 正式验证 |

## 支持性数据

| 数据集 | 路径 | 用途 | 状态 |
|---|---|---|---|
| Advanced paper profile | `results/advanced/paper/` | 中等规模完整矩阵 | 支持性 |
| Advanced stats profile | `results/advanced/stats/` | 旧完整 stats 矩阵 | 支持性；causal 结果已被 CommL stats 取代 |
| PASH parameter sweep | `results/pash_sweep/summary.csv` | 参数选择诊断 | 诊断 |
| PASH-opt | `results/pash_opt/` | 失败优化探索 | 诊断，不进入投稿 |
| Baseline common-grid | `results/redesign/` | 历史公平基线 | 支持性 |
| MCSH-BRW phase 2 | `results/innovation/` | 历史长稿实验 | 支持性 |

## 临时数据

所有 smoke 输出位于 `tmp/`，不得写入论文。

## 维护规则

1. 投稿正文数字只能来自 `results/comml/stats/`。
2. 每个正式目录必须包含 config、manifest 和 CSV。
3. smoke、paper、stats 与 diagnostic 不得互相覆盖。
4. causal 结果必须来自显式状态和共享攻击轨迹实现。
5. 不完美反馈实验不得覆盖 `results/comml/stats/` 冻结核心数据。
