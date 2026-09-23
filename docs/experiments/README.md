# 实验文档

本目录保存实验设计、自动结果报告和诊断报告。凡是论文数字、图表或实验结论
依赖的内容，应能从这里追溯到 `results/` 和 `figures/`。

## 当前文件

- `redesign_spec.md`：第一阶段公平共同栅格实验规范。
- `redesign_results.md`：第一阶段自动结果报告。
- `phase2_innovation_design.md`：MCSH-BRW 方法设计。
- `phase2_results.md`：第二阶段自动结果报告。
- `lag_predictability_diagnostic.md`：MCSH lag spike 与候选池暴露诊断。
- `advanced_experiment_design.md`：PASH/PASH-cap 强对抗实验设计。
- `advanced_experiment_results.md`：第三阶段自动结果报告。
- `model_validity_checks.md`：Python 共同物理栅格模型不变量检查。

## 写作规则

新增实验必须先写 design，再跑 smoke/paper，最后写 results。自动报告可以由脚本
生成，但必须有清楚的输入数据路径和输出图表路径。
