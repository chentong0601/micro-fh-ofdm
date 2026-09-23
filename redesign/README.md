# 公平共同栅格实验

本目录是对原 MATLAB 原型的独立重设计，不覆盖历史代码或结果。实验用于验证：

1. 盲部分带干扰下，公平口径的跳变不会自动产生平均未编码增益。
2. 扫频干扰下，跳变通过降低碰撞突发性改善匹配编码性能。
3. 一拍延迟反应式干扰下，独立跳变把平均碰撞率降到约 `S/N`。
4. 实用擦除检测器与 oracle 上界之间的差距。

## 运行

```sh
python run.py baseline-smoke
python run.py baseline-paper
```

`smoke` 用于快速检查仿真，结果单独写入 `tmp/smoke-results/`，不会覆盖正式
结果；`baseline-paper` 重新生成正式结果和图，不编译论文。

## 输出

- `results/redesign/summary.csv`：全部 BER、碰撞与检测统计。
- `results/redesign/config.json`：固定随机种子和实验配置。
- `figures/redesign/`：论文图及辅助分析图。
- `docs/experiments/redesign_results.md`：从结果自动生成的中文结果报告。
- `paper/letter_ieee.tex`、`paper/letter_ieee.pdf`：新 IEEE 短文。

oracle erasure 仅作为不可实现上界，不应作为实际接收机性能宣传。

## 第二阶段：MCSH-BRW 方法论文

第一阶段短文主要建立公平基线。第二阶段在此基础上加入有限记忆集合排斥
跳变 MCSH 与 Bayesian reliability weighting (BRW)，并扩展到延迟/记忆
消融、负载边界、JSR、Ped-A/Veh-A、CSI、方差失配、图案失步和零延迟攻击。

```sh
python run.py phase2-smoke
python run.py phase2-paper
```

正式输出位于 `results/innovation/`、`figures/innovation/`、
`docs/experiments/phase2_results.md`。论文编译必须单独使用
`python run.py paper`。MCSH 的主张只适用于有限延迟跟随干扰与可行负载；
BRW 需要噪声/干扰方差估计。

## 第三阶段：强对抗与 PASH/PASH-cap

实验专项审查发现，硬 MCSH 虽然能消除设计记忆内的 follower 碰撞，但会在
`L_h+1` 等滞后产生碰撞尖峰，并让候选池被更聪明的干扰机利用。第三阶段加入
PASH/PASH-cap、best-lag jammer、candidate-aware jammer，以及 no weighting /
BRW / exact mixture-LLR 的公平接收机消融。

```sh
python run.py advanced-smoke
python run.py advanced-paper
```

`smoke` 输出位于 `tmp/smoke-advanced/`，不会覆盖正式论文数据。
正式输出位于 `results/advanced/`、`figures/advanced/`、
`docs/experiments/advanced_experiment_design.md`、
`docs/experiments/advanced_experiment_results.md`。
论文中的新增图 `figures/advanced/fig7_adversarial_pash.pdf` 表明：
MCSH 更适合已知短时延 follower；PASH-cap 更适合时延不确定或干扰机能利用
候选池结构的强对抗场景。
