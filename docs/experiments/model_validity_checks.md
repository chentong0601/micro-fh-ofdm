# Python 模型有效性检查

## 目的

该检查不用于新增性能收益，而是验证当前 Python 共同物理栅格实现满足
基础结构不变量和可由封闭形式预期的碰撞规律。

## 运行配置

- `N=512`
- `S=64`
- `S/N=0.125`
- 结构统计来源：读取 `results/advanced/structural_summary.csv`

## 检查结果

| 检查项 | 实测值 | 期望 | 容差 | 结果 |
|---|---:|---:|---:|---|
| random short-delay collision equals active load | 0.124939 | 0.125 | +/- 0.003 | PASS |
| random candidate-aware collision equals active load | 0.125173 | 0.125 | +/- 0.003 | PASS |
| MCSH Lh=2 lag-1 collision is zero | 0 | 0 | <= 1e-12 | PASS |
| MCSH Lh=2 lag-2 collision is zero | 0 | 0 | <= 1e-12 | PASS |
| MCSH Lh=2 worst lag is just outside memory | 3 | 3 | exact lag index | PASS |
| MCSH Lh=2 boundary collision matches closed form | 0.166809 | 0.166667 | +/- 0.002 | PASS |
| MCSH Lh=6 worst lag is just outside memory | 7 | 7 | exact lag index | PASS |
| MCSH Lh=6 exposes concentrated lag spike | 0.499825 | > 0.45 | lower bound | PASS |
| MCSH Lh=6 boundary collision matches closed form | 0.499825 | 0.500000 | +/- 0.002 | PASS |
| PASH-cap reduces worst structural risk vs MCSH Lh=2 | 0.149987 | < 0.167 | strict inequality | PASS |
| PASH-cap sacrifices zero short-delay avoidance | 0.0983235 | > 0 | strict inequality | PASS |
| PASH-cap candidate-aware collision respects p_max | 0.149987 | <= 0.15 | 0.002 Monte Carlo tolerance | PASS |

通过 `12/12` 项。

## 解释

- random hopping 的碰撞率应接近 active load `S/N`。
- MCSH 的记忆内 lag collision 必须为零，否则 recent-set 排斥实现错误。
- MCSH 的 worst lag 出现在 `L_h+1`，说明硬排斥把风险推到记忆边界外。
- PASH-cap 若能降低 worst structural risk，同时短时延碰撞不为零，说明其实现了“牺牲已知短时延最优性以降低可预测性风险”的设计目标。
