# CommL 不完美反馈鲁棒性实验设计

- 预注册日期：2026-06-10
- 目标：检验反馈辅助 causal jammer 的结论是否依赖精确、即时碰撞反馈
- 状态：运行前冻结

## 研究问题

1. 当反馈报告发生腐化或额外延迟时，causal jammer 是否仍能学习 MCSH-L2 的
   `d=3` 记忆边界暴露？
2. PASH-cap 相对 MCSH-L2 的优势是否只在理想反馈攻击者下成立？
3. 当攻击者反馈质量下降时，结果是否逐渐接近较弱的固定或随机历史攻击？

## 反馈模型

每个时隙结束后，攻击者获得归一化碰撞反馈。反馈在动作完成后生成，因此即使额外
延迟为 0，也只能用于下一时隙动作。

- **反馈腐化概率 `q`**：以概率 `q`，真实碰撞报告被替换为无信息基线 `S/N`；
  否则报告真实归一化碰撞。
- **额外反馈延迟 `D_f`**：报告在额外等待 `D_f` 个时隙后才用于 lag-score 更新。
- pending feedback 跨帧保留，攻击者状态按方法-条件连续。

腐化与延迟分开扫描，避免不必要的全组合扩张：

| 扫描 | 条件 |
|---|---|
| corruption | `q = 0, 0.1, 0.2, 0.3`，`D_f=0` |
| delay | `D_f = 0, 1, 2, 4`，`q=0` |

理想条件 `(q=0,D_f=0)` 只运行一次，共 7 个唯一反馈条件。

## 实验矩阵

- 方法：Random、MCSH-L2、PASH-c15。
- 威胁：仅 feedback-aided `causal_adaptive_lag`。
- 接收机：mixture-LLR。
- 物理配置：与 CommL 核心实验完全一致。
- Smoke：每点 20 帧。
- 正式统计：每点最少 1000 帧、最多 3000 帧、目标 100 个错误帧。
- 指标：BLER、bootstrap 95% CI、碰撞率、lag 选择分布、最终 lag score。

## 运行命令

```sh
python run.py feedback-smoke
python run.py feedback-stats
python run.py feedback-plot
```

## 输出

- 正式数据：`results/comml/feedback_robustness/summary.csv`
- 配置与 manifest：`results/comml/feedback_robustness/`
- 自动报告：`docs/experiments/comml_feedback_robustness_results.md`
- 候选补充图：`figures/paper/comml_fig3_feedback_robustness.pdf`

## 预注册决策规则

1. 若 MCSH-L2 在所有非理想反馈条件下仍明显劣于 PASH-c15，则可加强“边界暴露可被
   不完美反馈攻击者学习”的主张。
2. 若 MCSH-L2 随反馈质量下降快速改善，但 PASH-c15 保持稳定，则论文应表述为：
   PASH 的优势主要针对信息充分的历史自适应攻击。
3. 若 PASH-c15 在非理想反馈下明显恶化或不再优于 MCSH-L2，则 causal 鲁棒性结果不
   进入主稿，只作为失败边界记录。
4. Random 必须保留，用于判断攻击弱化后是否接近无结构基线。
5. 仅当该实验提供独立于 Fig. 2 的新科学结论时，Fig. 3 才进入短稿。
