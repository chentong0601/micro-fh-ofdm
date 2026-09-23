# 重设计实验规范

## 研究问题

在相同分配系统频带、共同物理栅格、平均功率、激活子载波数和信息速率下，
固定子带 OFDM 与稀疏子载波跳变 OFDM 面对盲 PBJ、扫频干扰和一拍延迟反应式
干扰时有何差异？
可靠度擦除何时产生净收益？

## 共同物理模型

- 物理 FFT 栅格：`N_phys = 512`
- 每个 OFDM 符号激活子载波：`N_active = 64`
- QPSK，单位符号能量
- 固定 OFDM 与跳变 OFDM 均在 512 栅格上发送
- 每个物理 OFDM 符号携带相同数量的调制符号
- 主编码基线均使用相同的 rate-1/2, K=7, `(171,133)_8` 终止卷积码

## 干扰模型

### Blind PBJ

每帧随机选择连续频带，干扰机不知道当前激活位置。用于验证：公平口径下，
未编码固定/跳变方案的平均 BER 应接近。

### Sweep jammer

连续窄带块按固定步长扫过物理栅格。固定子带产生突发碰撞；跳变方案把碰撞
分散到不同编码位置。

### One-symbol-delayed reactive jammer

干扰机在第 `m` 个符号攻击第 `m-1` 个符号的激活位置。固定 OFDM 会被持续命中；
跳变 OFDM 的平均碰撞比例约为 `N_active/N_phys`。

## 比较方案

- Fixed, uncoded
- Hopping, uncoded
- Fixed + K7
- Hopping + K7
- Hopping + K7 + practical erasure
- Hopping + K7 + oracle erasure

oracle 仅作为上界，不能作为可实现方案宣传。

## 统计规范

- 每点记录 `bit_errors`, `total_bits`, `frame_errors`, `total_frames`
- 采用 Wilson 95% 置信区间
- 低 BER 点采用最小错误数/最大帧数停止准则
- 固定随机种子并记录配置 JSON

## 论文主图规划

1. 共同栅格模型与碰撞示意图
2. 盲 PBJ 下未编码公平性验证
3. 扫频干扰下匹配编码基线与擦除上界
4. 反应式干扰下 BER 与碰撞率
5. 实用擦除检测器的 `P_d/P_fa` 与净 BER 收益
