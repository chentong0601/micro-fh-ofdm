# Figures 目录说明

`figures/paper/` 保存论文图（PDF + PNG，同名成对）。

## 当前短稿正式图

- `comml_fig1_structural.pdf`：结构机制与风险折中图（Fig. 1）。
- `comml_fig2_compact.pdf`：三方法四威胁编码 BLER + 不完美反馈鲁棒性紧凑图（Fig. 2）。

生成命令：

```sh
python run.py comml-plot
```

Fig. 1–2 的数据源是 `results/comml/stats/`；Fig. 2 的反馈鲁棒性部分来自
`results/comml/feedback_robustness/`。

## 其他图

`fig1`–`fig9` 系列（BER 网格、碰撞检测、方法概念、延迟负载、鲁棒性、接收机极限、
对抗 PASH、参数扫掠、PASH-opt 诊断）属于长稿、支持性或诊断实验用图，
**不由当前短稿引用**，保留以备查阅。其中 `fig9_pash_optimization.*` 来自一个
已判定为失败的诊断性实验，仅作记录，不作为论文贡献。

## 图母版

投稿用图母版（每图一个单独 `.eps`）在 `paper/accepted/figures/`。
