# 当前项目状态

- 更新日期：2026-09-23
- 当前阶段：**短稿已录用**，论文与实验代码已冻结；本仓库为公开发布的可复现材料

## 论文主线

硬排斥 MCSH 能有效抵抗已知短时延 follower，但会在记忆边界外产生 lag spike 与
候选暴露。PASH-cap 通过概率上限约束，在短时延保护和历史感知攻击风险之间提供折中。

**论文不得宣称 PASH-cap 全场景最优或优于外部 SOTA** —— 见下文「当前不足」。

## 论文与代码位置

- 短稿源码：`paper/comml_ieee.tex`（双盲占位作者）
- 短稿工作 PDF：`paper/comml_ieee.pdf`
- 交付 PDF：`output/pdf/comml_ieee.pdf`
- **录用版（实名）**：`paper/accepted/manuscript.tex` / `.pdf`，图母版在
  `paper/accepted/figures/`（每图一个单独 `.eps`）
- 长稿源码：`paper/full_ieee.tex`（支持性材料，未作为独立投稿推进）
- 中文翻译：`paper/i18n-cn/comml_ieee_cn.tex`

## 核心实验

- 设计：`docs/experiments/final_comml_experiment_design.md`
- 结果：`results/comml/stats/`
- 报告：`docs/experiments/final_comml_experiment_results.md`
- 运行命令：`python run.py comml-stats`
- 方法：Random、MCSH-L2、PASH-c15
- 威胁：`fixed_d1`、`fixed_d3`、`candidate_aware`、`causal_adaptive_lag`
- 接收机：mixture-LLR
- 停止规则：2000–5000 帧，目标 100 个错误帧

威胁有效性检查：

- 命令：`python run.py threat-validity`
- 结果：`results/model_validity/adversarial_threat_checks.csv`
- 状态：**7/7 通过**

## 核心结果（mixture-LLR BLER）

| 威胁 | Random | MCSH-L2 | PASH-c15 |
|---|---:|---:|---:|
| fixed_d1 | 0.0425 | 0.0010 | 0.0172 |
| fixed_d3 | 0.0535 | 0.1375 | 0.0200 |
| candidate_aware | 0.0422 | 0.1435 | 0.0870 |
| causal_adaptive_lag | 0.0476 | 0.1230 | 0.0180 |

可支持的结论：

1. MCSH-L2 在已知 `d=1` follower 下最强。
2. MCSH-L2 在记忆边界外 `d=3` 出现明显退化。
3. PASH-c15 在 `d=3` 与反馈辅助 causal attack 下比 MCSH-L2 更稳健。
4. **Random 在 candidate-aware 下优于 PASH-c15**；PASH 的正确定位是跨威胁折中。
5. causal attack 的主要 lag 选择与结构暴露一致：MCSH-L2 主要学习选择 `d=3`。
6. 在 30% 报告腐化或额外 4 时隙反馈延迟下，MCSH-L2 仍将 80.0–83.6% 动作集中于
   `d=3`；该边界暴露不依赖理想反馈。

## 敏感性实验

- SNR = 9 dB：`python run.py comml-stats-9db` → `results/comml/stats_9dB/`
- JSR = 10 dB：`python run.py comml-stats-jsr10` → `results/comml/stats_jsr10dB/`
- 反馈鲁棒性：`python run.py feedback-stats` → `results/comml/feedback_robustness/`
- 理论边界验证：`results/comml/bound_validation/`
- RL 基线对比：`results/comml/rl_baselines/`

## 当前不足

1. 不完美反馈模型仍是抽象的报告腐化/延迟模型，尚未连接具体感知或控制信道。
2. PASH-c15 的 `fixed_d1` 与 causal 点在 5000 帧时分别为 86 和 90 个错误帧，
   略低于 100 目标；置信区间已报告，需如实说明。
3. **没有外部方法直接数值复现**，因此不能使用 SOTA 表述。
4. 正式核心矩阵仍限于单一 SNR/JSR、AWGN 和 K7 卷积码。
5. 补充反馈实验中的 PASH 点只有 50–65 个错误帧，估计精度低于 MCSH 点。

## 已退出主线的项

- **PASH-opt**：解析端点审计失败，已退出投稿线，仅保留为诊断性失败实验
  （`redesign/pash_optimization_experiment.py`、`results/pash_opt/`），不作为论文贡献。
- **SBS**：仅为项目内部 adapted stress baseline，不是外部文献方法复现，
  **不用于 SOTA 主张**。

## 后续可做的方向

1. 把抽象的不完美反馈模型连接到具体感知/控制信道。
2. 引入频率选择性多径信道（ITU 车辆 A/B 或 TDL）评估。
3. 扩展到非均匀功率分配（注水/功率集中）的干扰方。
4. 在不同 S/N 占用率下扫掠 (α, p_floor, p_max)。
5. 补齐统计精度不足的 PASH 点（提高错误帧目标）。
