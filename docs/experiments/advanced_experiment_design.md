# 高水平实验增强设计：从 MCSH 到 PASH

## 新科学问题

上一轮审查发现，MCSH 的 hard exclusion 会把风险集中到 `L_h+1` 附近，并使
下一跳候选池变小。新的实验不再只证明“固定一拍 follower 下 MCSH 有效”，
而是研究：

> 在未知或智能延迟干扰机下，如何在短时延碰撞规避和历史条件可预测性之间
> 取得可调折中？

## 新方法：PASH

PASH（predictability-aware soft hopping）用软概率排斥替代 MCSH 的硬排斥。
对每个候选子载波计算最近 `H` 拍使用次数 `r_k`，令

```text
w_k = floor + exp(-alpha r_k).
```

然后按 `w_k` 无放回抽样 `S` 个激活子载波。`alpha` 越大，越接近硬排斥；
`floor` 防止最近使用过的子载波概率变成零，从而降低候选池暴露。

当前实现包括：

- `PASH alpha=0.8, H=6, floor=0.25`
- `PASH alpha=1.4, H=6, floor=0.20`

这些参数先作为论文实验中的可调折中点，后续可升级为带最坏候选池约束的
优化问题。

## 新强干扰机

新增威胁模型：

- `fixed_d1`：传统一拍 follower。
- `fixed_d3`：攻击 MCSH `L_h=2` 的尖峰时延。
- `delay_uniform`：每拍从 `1...6` 随机选择 follower delay。
- `best_lag`：在最近 `1...6` 拍中选择与当前集合重叠最大的历史集合，是
  非因果上界型压力测试。
- `candidate_aware`：知道历史和算法但不知道随机 tie-break，攻击预测包含
  概率最高的 `S` 个子载波。

## 新接收机消融

- `none`：标准 K7 soft Viterbi。
- `brw`：原 BRW 有效方差近似。
- `mixllr`：clean/jammed 两方差模型下的精确 mixture LLR。

论文后续应把 BRW 定位为低复杂度近似，并用 `mixllr` 给出接收机上界。

## 输出

运行：

```sh
sh redesign/run_advanced.sh paper
```

输出：

- `results/advanced/structural_summary.csv`
- `results/advanced/coded_summary.csv`
- `figures/advanced/fig7_adversarial_pash.pdf`
- `docs/experiments/advanced_experiment_results.md`
