# Results 目录说明

`results/` 保存正式实验数据。临时、冒烟或探索性结果必须写入 `tmp/`。

## 当前正式结果

- `comml/stats/`：Communications Letters 最终核心实验，当前投稿数字唯一来源。
- `comml/feedback_robustness/`：Communications Letters 不完美反馈正式补充实验。
- `redesign/`：第一阶段公平共同栅格实验。
- `innovation/`：第二阶段 MCSH-BRW 实验。
- `lag_predictability_audit/`：MCSH 滞后碰撞谱审计。
- `advanced/`：第三阶段 PASH/PASH-cap 强对抗实验。

`advanced/stats/` 的旧 causal 结果已被显式状态修复后的 `comml/stats/` 取代。

## 历史 MATLAB 结果

早期 MATLAB `.mat` 文件已移动到 `archive/matlab_legacy/results/`，保留用于
历史追溯，不作为当前 `full_ieee.tex` 的主要数值来源。当前论文数字应优先
追溯到本目录子目录中的 CSV/JSON 文件和 `docs/experiments/` 报告。
