# 数据登记表

- 更新日期：**2026-09-23**
- 状态：**已冻结** —— 论文已录用且终稿已提交，`results/` 不再变更。
  新增数据必须在此登记，并同步 `docs/CHANGELOG.md`。

## 正式数据（论文数字来源）

| 数据集 | 路径 | 生成命令 | 状态 |
|---|---|---|---|
| CommL structural | `results/comml/stats/structural_summary.csv` | `python run.py comml-stats` | 正式（论文核心） |
| CommL coded BLER | `results/comml/stats/coded_summary.csv` | `python run.py comml-stats` | 正式（论文核心） |
| CommL config | `results/comml/stats/config.json` | `python run.py comml-stats` | 正式 |
| CommL manifest | `results/comml/stats/run_manifest.json` | `python run.py comml-stats` | 正式 |
| Feedback robustness | `results/comml/feedback_robustness/summary.csv` | `python run.py feedback-stats` | 正式（Fig. 2 右半） |
| Feedback robustness manifest | `results/comml/feedback_robustness/run_manifest.json` | `python run.py feedback-stats` | 正式 |
| SNR = 9 dB 敏感性 | `results/comml/stats_9dB/` | `python run.py comml-stats-9db` | 正式（v2.0 新增） |
| JSR = 10 dB 敏感性 | `results/comml/stats_jsr10dB/` | `python run.py comml-stats-jsr10` | 正式（v2.0 新增） |
| RL 基线对比矩阵 | `results/comml/rl_baselines/summary.csv` | ⚠️ `python redesign/epsgreedy_baseline.py paper` | 正式（v2.0 新增） |
| 理论边界验证 | `results/comml/bound_validation/{cd,rcand}_validation.csv` | ⚠️ `python redesign/validate_pash_bounds.py` | 正式（v2.0 新增） |
| Adversarial threat checks | `results/model_validity/adversarial_threat_checks.csv` | `python run.py threat-validity` | 正式验证（7/7 通过） |
| Model validity checks | `results/model_validity/model_validity_checks.csv` | `python run.py validity` | 正式验证 |
| Lag predictability audit | `results/lag_predictability_audit/lag_spectrum.csv` | ⚠️ `python redesign/audit_lag_predictability.py` | 正式（Fig. 1 输入） |

⚠️ **三处例外**：`rl_baselines`、`bound_validation`、`lag_predictability_audit` 由
`redesign/` 下脚本直接生成，**没有对应的 `run.py` 命令** —— 这与「所有命令都走
`python run.py <command>`」的约定不符。这三条数据进入论文，因此是该约定的既存缺口；
补 `run.py` 入口时可一并消除（不影响已提交数据）。

## 支持性数据

| 数据集 | 路径 | 用途 | 状态 |
|---|---|---|---|
| Advanced paper profile | `results/advanced/paper/` | 中等规模完整矩阵 | 支持性 |
| Advanced stats profile | `results/advanced/stats/` | 旧完整 stats 矩阵 | 支持性；causal 结果已被 CommL stats 取代 |
| PASH parameter sweep | `results/pash_sweep/summary.csv` | 参数选择诊断（定出 cap=0.14） | 诊断 |
| PASH-opt | `results/pash_opt/` | 失败优化探索 | 诊断，**不进入投稿** |
| Baseline common-grid | `results/redesign/` | 历史公平基线 | 支持性 |
| MCSH-BRW phase 2 | `results/innovation/` | 历史长稿实验 | 支持性 |
| `results/cross_validation/` | — | **空目录**（预留，从未产出） | 空 |
| `results/comml/deterministic_construction/` | — | **空目录**（预留） | 空 |

## 临时数据

所有 smoke 输出位于 `tmp/`，不得写入论文。`tmp/` 是**运行时目录**（已被 `.gitignore`
排除，仓库中不含），由脚本按需创建。

## 维护规则

1. 投稿正文数字只能来自 `results/comml/stats/`（敏感性结论可引 `stats_9dB`/`stats_jsr10dB`）。
2. 每个正式目录必须包含 config、manifest 和 CSV。
3. smoke、paper、stats 与 diagnostic 不得互相覆盖。
4. causal 结果必须来自显式状态和共享攻击轨迹实现。
5. 不完美反馈实验不得覆盖 `results/comml/stats/` 冻结核心数据。
