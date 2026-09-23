# Changelog

本文件记录项目结构、实验与论文产物的高层技术变更。
（投稿、评审相关的过程性记录不在公开范围内。）

## 2026-07

### 理论加固

- **新增 Proposition 3**（PASH-cap 最坏情况保证）：$R_{\text{cand}} \leq p_{\max}$
  对任意深度 $H$ 和衰减参数 $\alpha$ 独立成立，与 MCSH 的无界增长形成直接对比。
- **Proposition 2**（不可避免的可预测性代价）：形式化论证任何保证零短滞后碰撞的
  规则必然在首个未保护滞后产生 $S/(N-L_hS)$ 的可预测性集中。
- Proposition 1 证明改写为分步推导。
- 计算复杂度语境化：约 3000 操作/符号，相对于典型 CP 时长可忽略。
- $\eta_m$ 角色明确为 bisection 规范化因子。
- 新增 `redesign/validate_pash_bounds.py`：数值验证所有理论边界成立
  （5000 符号 × 5 种子，最大 $C_d=0.131$，$R_{\text{cand}}=0.150$）。

### 论文叙事重构

- 核心贡献表述从"提出 PASH-cap"改为"诊断硬排斥的结构不可能性 + 提出 PASH-cap
  作为处方"。
- Abstract / Introduction 重写：诊断先行、处方随后；明确区分 wide-gap/NHZ
  （pairwise FH）与 RL（闭环）两类不同工作。
- 全文移除过度声称的 "optimal" 表述。
- 外部基线缺口系统性讨论：解释为何 wide-gap/NHZ 与已发表 RL 方法不能直接移植到
  当前公共网格（威胁模型不同）。
- Scope 小节改写为决策框架而非普遍推荐。

### 实验补充

- 新增 SNR=9 dB 敏感性实验（`comml-stats-9db`）与 JSR=10 dB 敏感性实验
  （`comml-stats-jsr10`）。9 dB 下方法排序与 12 dB 完全一致，
  PASH-cap 改善倍数保持实质性。
- 新增 PASH-cap + causal 延长运行至 100 错误帧（`redesign/extend_causal_run.py`）。
- 新增 ε-greedy 在线学习基线（`redesign/epsgreedy_baseline.py`）：对全部 4 种威胁
  BLER ≈ 0.99–1.00，策略收敛到静态集合被干扰机完美跟踪；即使 ε=0.50 仍远差于
  Random (0.0425)。作为反面证据说明**在线学习若无显式可预测性控制可能比不学习更差**。

## 2026-06

### 核心实验与短稿

- 修复 causal jammer 的跨帧/接收机状态泄漏，改为显式状态与共享攻击轨迹。
- 对抗威胁有效性检查扩至 7 项，全部通过。
- 正式运行 `comml-stats`，生成 `results/comml/stats/` 与两幅最终图。
- 将 SBS 纠正为**项目内部 adapted stress baseline**，不再视为外部方法复现。
- 新建独立短稿 `paper/comml_ieee.tex`，新增 `comml-paper` / `comml-preflight` 入口。
- 预注册并运行不完美反馈鲁棒性实验：MCSH-L2 的 `d=3` 边界暴露在 30% 报告腐化与
  额外 4 时隙反馈延迟下**仍可学习**。
- 新增 `redesign/pash_parameter_sweep.py`：当前最佳可行结构点为
  `alpha=1.40, floor=0.20, cap=0.14`。

### 模型有效性

- 新增 `redesign/model_validity_checks.py`，验证共同栅格模型的结构不变量，9/9 通过。
- 新增可选 MATLAB clean-room 复核脚本（`archive/validation/`，未实际运行）。

### 工程与工具

- 新增统一运行入口 `run.py`，实验/检查与论文编译分离：
  `quick` 不编译论文，`paper` 只编译论文，`preflight` 执行完整交付流程。
- 新增 `redesign/check_project_structure.py`（结构不变量检查）与 `outputs`（输出规范检查）。
- 建立 `docs/registry/`：数据、图表、论文产物登记表。
- `docs/` 按 experiments / registry 分类；早期 MATLAB 原型归档，顶层仅保留 Python 代码。

### 已知的失败与退出项

- **PASH-opt**：解析端点审计失败，已退出主线，仅作为诊断性失败实验保留
  （`redesign/pash_optimization_experiment.py`、`results/pash_opt/`）。
