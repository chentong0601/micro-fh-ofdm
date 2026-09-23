# Communications Letters 核心实验结果

配置：N=512, S=64, M=32, SNR=12.0 dB, JSR=10.0 dB。

Causal adaptive jammer 使用跨帧连续显式状态；每个时隙先基于历史选择 lag，再在时隙结束后观察精确归一化碰撞反馈。每个方法-威胁组合只生成一条攻击轨迹。

## Mixture-LLR BLER

| 方法 | 威胁 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 | 达到目标 |
|---|---|---:|---:|---:|---:|
| Random | fixed_d1 | 0.0515 [0.0425, 0.0615] | 103/2000 | 0.1252 | YES |
| Random | fixed_d3 | 0.0520 [0.0425, 0.0625] | 104/2000 | 0.1249 | YES |
| Random | causal_adaptive_lag | 0.0525 [0.0430, 0.0620] | 105/2000 | 0.1250 | YES |
| Random | candidate_aware | 0.0510 [0.0415, 0.0605] | 102/2000 | 0.1250 | YES |
| MCSH $L_h=2$ | fixed_d1 | 0.0008 [0.0002, 0.0016] | 4/5000 | 0.0039 | NO |
| MCSH $L_h=2$ | fixed_d3 | 0.1760 [0.1590, 0.1940] | 352/2000 | 0.1628 | YES |
| MCSH $L_h=2$ | causal_adaptive_lag | 0.1525 [0.1375, 0.1690] | 305/2000 | 0.1470 | YES |
| MCSH $L_h=2$ | candidate_aware | 0.1825 [0.1665, 0.2000] | 365/2000 | 0.1647 | YES |
| PASH-cap $p_{\max}=0.15$ | fixed_d1 | 0.0164 [0.0130, 0.0200] | 82/5000 | 0.0953 | NO |
| PASH-cap $p_{\max}=0.15$ | fixed_d3 | 0.0188 [0.0152, 0.0228] | 94/5000 | 0.1002 | NO |
| PASH-cap $p_{\max}=0.15$ | causal_adaptive_lag | 0.0194 [0.0158, 0.0232] | 97/5000 | 0.0956 | NO |
| PASH-cap $p_{\max}=0.15$ | candidate_aware | 0.1155 [0.1020, 0.1295] | 231/2000 | 0.1484 | YES |

## 解释边界

- Random 是 candidate-aware 场景不可省略的核心比较对象。
- MCSH-L2 是已知短时延 follower 的强基线。
- PASH-cap 的主张是跨威胁折中，不是所有场景最优。
- causal adaptive 结果依赖较强的精确 post-slot collision feedback 假设。
