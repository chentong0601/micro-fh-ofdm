# CommL SNR 敏感性实验：9 dB

- 日期：2026-06-11
- 入口：`python run.py comml-stats-9db`
- 配置：N=512, S=64, M=32, SNR=9.0 dB, JSR=5.0 dB
- 方法：Random, MCSH-L2, PASH-cap（3 种）
- 威胁：fixed_d1, fixed_d3, causal_adaptive_lag, candidate_aware（4 种）
- 接收机：mixture-LLR
- 输出：`results/comml/stats_9dB/`

## Mixture-LLR BLER @ 9 dB

| 方法 | 威胁 | BLER [bootstrap 95% CI] | 帧错误/总帧 | 碰撞率 |
|---|---:|---:|---:|---:|
| Random | fixed_d1 | 0.1380 [0.1225, 0.1530] | 276/2000 | 0.1252 |
| Random | fixed_d3 | 0.1315 [0.1160, 0.1460] | 263/2000 | 0.1249 |
| Random | causal_adaptive_lag | 0.1230 [0.1090, 0.1375] | 246/2000 | 0.1250 |
| Random | candidate_aware | 0.1160 [0.1010, 0.1305] | 232/2000 | 0.1250 |
| MCSH $L_h=2$ | fixed_d1 | 0.0036 [0.0020, 0.0052] | 18/5000* | 0.0039 |
| MCSH $L_h=2$ | fixed_d3 | 0.3170 [0.2970, 0.3380] | 634/2000 | 0.1628 |
| MCSH $L_h=2$ | causal_adaptive_lag | 0.2930 [0.2745, 0.3135] | 586/2000 | 0.1470 |
| MCSH $L_h=2$ | candidate_aware | 0.3210 [0.3010, 0.3415] | 642/2000 | 0.1647 |
| PASH-cap | fixed_d1 | 0.0470 [0.0385, 0.0559] | 100/2129 | 0.0955 |
| PASH-cap | fixed_d3 | 0.0500 [0.0410, 0.0595] | 100/2000 | 0.1002 |
| PASH-cap | causal_adaptive_lag | 0.0565 [0.0465, 0.0665] | 113/2000 | 0.0958 |
| PASH-cap | candidate_aware | 0.2165 [0.1985, 0.2340] | 433/2000 | 0.1484 |

* 标记表示帧错误数未达到 100 的统计目标。

## 与 12 dB 的对比

### 方法排序一致性

所有 4 种威胁下，3 种方法的性能排序在 9 dB 和 12 dB 之间完全一致：

| 威胁 | 12 dB 排序 | 9 dB 排序 | 一致？ |
|------|-----------|----------|:---:|
| d=1 | MCSH < PASH < Random | MCSH < PASH < Random | ✅ |
| d=3 | PASH < Random < MCSH | PASH < Random < MCSH | ✅ |
| Causal | PASH < Random < MCSH | PASH < Random < MCSH | ✅ |
| Prob-aware | Random < PASH < MCSH | Random < PASH < MCSH | ✅ |

### PASH-cap 改善倍数对比

| 对比 | 12 dB | 9 dB |
|------|------|------|
| PASH vs MCSH @ d=3 | 6.9× | 6.3× |
| PASH vs MCSH @ causal | 6.8× | 5.2× |
| PASH vs Random @ d=3 | 2.8× | 2.6× |

改善倍数略有下降但保持实质性（2.6--6.3×）。

### 边界尖峰效应

- MCSH-L2 d=1→d=3 BLER 跳变：12 dB 下 138×，9 dB 下 88×
- 边界尖峰在低 SNR 下仍然显著，但相对幅度减小（因 uncoded BER 底噪升高稀释了碰撞效应）

## 解释

9 dB 下的结果验证了论文核心主张的 SNR 鲁棒性：
- 方法排序在所有威胁下保持一致
- PASH-cap 的跨威胁折中特性不依赖于特定 SNR 工作点
- 边界尖峰效应在更低 SNR 下仍然存在且可被因果攻击者学习
