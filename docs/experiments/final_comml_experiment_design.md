# Communications Letters 最终核心实验设计

- 设计日期：2026-06-10
- 执行入口：`python run.py comml-smoke`、`python run.py comml-stats`
- 正式输出：`results/comml/stats/`

## 研究问题

验证 PASH-cap 是否在保留部分短时延保护的同时，比 MCSH-L2 更能抵抗记忆外固定
时延、候选感知和因果自适应 lag 攻击；同时必须报告 Random 基线，避免选择性比较。

## 方法

- Random：均匀随机跳频基线。
- MCSH-L2：硬排斥短时延基线。
- PASH-c15：论文候选方法，`alpha=1.4, floor=0.20, p_max=0.15`。

BCD 和 SBS 仅作为内部压力诊断，不进入最终编码主图，也不作为外部 SOTA 基线。

## 威胁

- `fixed_d1`：已知一时隙 follower。
- `fixed_d3`：MCSH-L2 记忆边界外固定 follower。
- `candidate_aware`：选择当前条件包含概率最高的 S 个频点。
- `causal_adaptive_lag`：反馈辅助的因果自适应 lag 攻击。

`causal_adaptive_lag` 使用显式连续状态。每个时隙的执行顺序为：

1. 仅基于历史 lag score 和历史反馈选择 lag；
2. 使用对应历史集合形成 jammer action；
3. 时隙结束后观察精确归一化碰撞反馈；
4. 使用 EMA 更新 lag score。

该攻击假设能够获得精确 post-slot collision feedback，是强但明确的反馈辅助攻击。
每个方法-威胁组合只生成一条攻击轨迹；所有接收机必须复用同一轨迹。

## 接收机与指标

- 接收机：mixture-LLR。
- 主指标：BLER。
- 辅助指标：BER、碰撞率、帧错误数、bootstrap 95% CI。
- causal 审计：最终 lag 选择次数和 lag score。

## 样本规模与停止规则

- 最小帧数：2000。
- 最大帧数：5000。
- 最小目标：100 个错误帧。
- 达到最小帧数且累计 100 个错误帧后允许提前停止。
- 达到最大帧数仍不足时，保留结果并明确标记统计目标未满足。

## 有效性检查

正式运行前必须通过：

```sh
python run.py threat-validity
python run.py comml-smoke
python run.py advanced-smoke
```

必须满足：

- causal action API 不接收当前真实集合；
- causal action 均来自可用历史集合；
- 固定随机种子下攻击轨迹可复现；
- 接收机运行顺序不改变攻击轨迹；
- 完整 advanced smoke 中同一方法-威胁的所有接收机碰撞率一致。

## 决策规则

- 若 PASH-c15 只优于 MCSH-L2、但不优于 Random，论文必须表述为风险折中。
- 若修复后的 causal 结果不再支持 PASH 优势，删除 causal 主张。
- 若 PASH-c15 在 `fixed_d1` 退化但在记忆外/自适应攻击下改善，可支持折中主线。
- 不使用“全场景最优”“SOTA”或“optimal”等未经验证的表述。

