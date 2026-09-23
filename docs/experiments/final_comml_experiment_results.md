# Communications Letters 核心实验结果

配置：N=512, S=64, M=32, SNR=12.0 dB, JSR=5.0 dB。

Causal adaptive jammer 使用跨帧连续显式状态；每个时隙先基于历史选择 lag，再在时隙结束后观察精确归一化碰撞反馈。每个方法-威胁组合只生成一条攻击轨迹。

## Mixture-LLR BLER

| 方法 | 威胁 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 | 达到目标 |
|---|---|---:|---:|---:|---:|
| Random | fixed_d1 | 0.0425 [0.0348, 0.0506] | 100/2354 | 0.1252 | YES |
| Random | fixed_d3 | 0.0535 [0.0440, 0.0640] | 107/2000 | 0.1249 | YES |
| Random | causal_adaptive_lag | 0.0530 [0.0430, 0.0630] | 106/2000 | 0.1250 | YES |
| Random | candidate_aware | 0.0422 [0.0346, 0.0506] | 100/2370 | 0.1250 | YES |
| Block-Cyclic Det. | fixed_d1 | 0.0006 [0.0000, 0.0014] | 3/5000 | 0.0039 | NO |
| Block-Cyclic Det. | fixed_d3 | 0.0060 [0.0040, 0.0082] | 30/5000 | 0.0117 | NO |
| Block-Cyclic Det. | causal_adaptive_lag | 1.0000 [1.0000, 1.0000] | 2000/2000 | 0.6851 | YES |
| Block-Cyclic Det. | candidate_aware | 1.0000 [1.0000, 1.0000] | 2000/2000 | 1.0000 | YES |
| LFSR Pseudo-Random | fixed_d1 | 0.0690 [0.0575, 0.0805] | 138/2000 | 0.1304 | YES |
| LFSR Pseudo-Random | fixed_d3 | 0.0274 [0.0222, 0.0329] | 100/3649 | 0.1240 | YES |
| LFSR Pseudo-Random | causal_adaptive_lag | 0.0845 [0.0725, 0.0970] | 169/2000 | 0.1278 | YES |
| LFSR Pseudo-Random | candidate_aware | 1.0000 [1.0000, 1.0000] | 2000/2000 | 1.0000 | YES |
| MCSH $L_h=2$ | fixed_d1 | 0.0010 [0.0002, 0.0020] | 5/5000 | 0.0039 | NO |
| MCSH $L_h=2$ | fixed_d3 | 0.1375 [0.1225, 0.1530] | 275/2000 | 0.1628 | YES |
| MCSH $L_h=2$ | causal_adaptive_lag | 0.1255 [0.1115, 0.1400] | 251/2000 | 0.1479 | YES |
| MCSH $L_h=2$ | candidate_aware | 0.1435 [0.1285, 0.1585] | 287/2000 | 0.1647 | YES |
| PASH-cap $p_{\max}=0.15$ | fixed_d1 | 0.0172 [0.0138, 0.0208] | 86/5000 | 0.0953 | NO |
| PASH-cap $p_{\max}=0.15$ | fixed_d3 | 0.0200 [0.0164, 0.0240] | 100/4999 | 0.1002 | YES |
| PASH-cap $p_{\max}=0.15$ | causal_adaptive_lag | 0.0450 [0.0369, 0.0535] | 100/2223 | 0.1179 | YES |
| PASH-cap $p_{\max}=0.15$ | candidate_aware | 0.0870 [0.0750, 0.0990] | 174/2000 | 0.1484 | YES |
| PASH-linear | fixed_d1 | 0.0305 [0.0244, 0.0366] | 100/3275 | 0.1099 | YES |
| PASH-linear | fixed_d3 | 0.0251 [0.0204, 0.0304] | 100/3979 | 0.1111 | YES |
| PASH-linear | causal_adaptive_lag | 0.0428 [0.0351, 0.0509] | 100/2336 | 0.1200 | YES |
| PASH-linear | candidate_aware | 0.0655 [0.0550, 0.0765] | 131/2000 | 0.1379 | YES |
| PASH no-cap | fixed_d1 | 0.0058 [0.0038, 0.0080] | 29/5000 | 0.0688 | NO |
| PASH no-cap | fixed_d3 | 0.0082 [0.0058, 0.0106] | 41/5000 | 0.0733 | NO |
| PASH no-cap | causal_adaptive_lag | 0.0880 [0.0755, 0.1005] | 176/2000 | 0.1363 | YES |
| PASH no-cap | candidate_aware | 0.3545 [0.3335, 0.3745] | 709/2000 | 0.2027 | YES |

## 解释边界

- Random 是 candidate-aware 场景不可省略的核心比较对象。
- MCSH-L2 是已知短时延 follower 的强基线。
- PASH-cap 的主张是跨威胁折中，不是所有场景最优。
- causal adaptive 结果依赖较强的精确 post-slot collision feedback 假设。
