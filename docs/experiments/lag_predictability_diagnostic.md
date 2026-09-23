# MCSH 时延碰撞谱与候选池暴露诊断

该诊断使用 20 个独立种子、每个种子 4000 个连续符号。随机跳频基准
`S/N=0.125`。

| 方法 | 最大时延碰撞 | 尖峰时延 | 候选池感知攻击期望碰撞 | 使用频率 CV |
|---|---:|---:|---:|---:|
| Random | 0.125 | 12 | 0.125 | 0.0419 |
| MCSH L_h=1 | 0.143 | 2 | 0.143 | 0.0364 |
| MCSH L_h=2 | 0.167 | 3 | 0.167 | 0.0306 |
| MCSH L_h=4 | 0.250 | 5 | 0.250 | 0.0193 |
| MCSH L_h=6 | 0.500 | 7 | 0.500 | 0.0079 |

## 结论

- MCSH 将前 `L_h` 个时延的碰撞压到零，但在 `L_h+1` 附近形成明显尖峰。
- 记忆越长，候选池越小，history-aware jammer 的可利用概率质量越集中。
- 当前 MCSH 适合已知固定延迟，但不适合直接宣称对未知智能 follower 稳健。
- 新方法应联合优化短时延碰撞与条件可预测性，而不是仅做 hard exclusion。

数据：`results/lag_predictability_audit/lag_spectrum.csv`。
图：`figures/audit/lag_predictability_diagnostic.pdf`。
