# Communications Letters 核心实验结果

配置：N=512, S=64, M=32, SNR=9.0 dB, JSR=5.0 dB。

Causal adaptive jammer 使用跨帧连续显式状态；每个时隙先基于历史选择 lag，再在时隙结束后观察精确归一化碰撞反馈。每个方法-威胁组合只生成一条攻击轨迹。

## Mixture-LLR BLER

| 方法 | 威胁 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 | 达到目标 |
|---|---|---:|---:|---:|---:|
| Random | fixed_d1 | 0.1380 [0.1225, 0.1530] | 276/2000 | 0.1252 | YES |
| Random | fixed_d3 | 0.1315 [0.1160, 0.1460] | 263/2000 | 0.1249 | YES |
| Random | causal_adaptive_lag | 0.1230 [0.1090, 0.1375] | 246/2000 | 0.1250 | YES |
| Random | candidate_aware | 0.1160 [0.1010, 0.1305] | 232/2000 | 0.1250 | YES |
| MCSH $L_h=2$ | fixed_d1 | 0.0036 [0.0020, 0.0052] | 18/5000 | 0.0039 | NO |
| MCSH $L_h=2$ | fixed_d3 | 0.3170 [0.2970, 0.3380] | 634/2000 | 0.1628 | YES |
| MCSH $L_h=2$ | causal_adaptive_lag | 0.2930 [0.2745, 0.3135] | 586/2000 | 0.1470 | YES |
| MCSH $L_h=2$ | candidate_aware | 0.3210 [0.3010, 0.3415] | 642/2000 | 0.1647 | YES |
| PASH-cap $p_{\max}=0.15$ | fixed_d1 | 0.0470 [0.0385, 0.0559] | 100/2129 | 0.0955 | YES |
| PASH-cap $p_{\max}=0.15$ | fixed_d3 | 0.0500 [0.0410, 0.0595] | 100/2000 | 0.1002 | YES |
| PASH-cap $p_{\max}=0.15$ | causal_adaptive_lag | 0.0565 [0.0465, 0.0665] | 113/2000 | 0.0958 | YES |
| PASH-cap $p_{\max}=0.15$ | candidate_aware | 0.2165 [0.1985, 0.2340] | 433/2000 | 0.1484 | YES |

## 解释边界

- Random 是 candidate-aware 场景不可省略的核心比较对象。
- MCSH-L2 是已知短时延 follower 的强基线。
- PASH-cap 的主张是跨威胁折中，不是所有场景最优。
- causal adaptive 结果依赖较强的精确 post-slot collision feedback 假设。
