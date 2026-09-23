# PASH-opt 科学有效性审计结果

审计日期：2026-06-09
审计依据：`docs/plans/next_stage_execution_plan_v2.md` 阶段 2

## 审计测试

### λ=0 解析端点（纯 candidate-aware 最小化）

- **最优解析解**: uniform p_k = S/N = 0.125, top-S sum = S²/N = 8.000
- **PASH-opt 输出**: top-S sum = 8.037
- **结论**: FAIL。PASH-opt 未收敛到均匀解，偏差约 0.46%

根因：PASH-cap warm-start 将近期使用的频点 p_k 压低，提升未使用频点的 p_k。
λ=0 的子梯度（top-S indicator）无法在 500 次迭代内将解推回均匀分布。

### λ=1 解析端点（纯短时延最小化）

- **最优解析解**: 排序 costs，贪心分配 p_max=0.15 给最低 cost 频点
  - 解析 cost = 6.352
- **PASH-opt 输出**: cost = 8.698
- **结论**: FAIL。相对差距 36.95%

根因：PASH-cap warm-start 已偏离最优解，投影子梯度步长太小（step0=0.5/512≈0.001），
500 次迭代不足以跨越 warm-start 与最优解之间的距离。

### 约束可行性

- sum(p)=S: PASS（投影算子保证）
- 0 ≤ p_k ≤ p_max: PASS（投影算子保证）

## 决策

按照 v2 执行方案 7.3 节决策规则：

> 解析测试失败：立即退出投稿线。

PASH-opt 不满足继续进入投稿工作的条件。执行以下操作：

1. PASH-opt 标记为失败的探索实验
2. Fig. 9 移入 `figures/diagnostics/`
3. 从 Communications Letters 提纲、摘要和贡献中删除 PASH-opt 相关内容
4. 保留失败原因文档（本文），避免后续重复犯错
5. `results/pash_opt/` 标记为 diagnostic 结果

## 后续建议

若未来重新尝试 PASH-opt：
- λ=0 应直接返回均匀解（解析最优），跳过优化
- λ=1 应使用 cost-sorted greedy（解析最优），跳过优化
- 中间 λ 值需要多初值 + 更长的迭代 + 更大的初始步长
- 必须区分近似包含概率（p_k）与加权无放回采样的真实包含概率
