# 项目文档地图

本目录保存可追溯的研究文档。论文、代码和实验产物分别在
`paper/`、`redesign/`、`results/`、`figures/` 和 `output/`。

## 必读入口

- `PROJECT_STATUS.md`：当前状态、核心结果、已知不足。
- `PROCESS.md`：实验改进与论文改写必须遵守的流程规范。
- `reproducibility.md`：正式实验、冒烟测试、图表和 PDF 的复现命令。
- `CHANGELOG.md`：项目结构、实验和论文产物的高层变更记录。

## 分类目录

- `experiments/`：实验设计、自动结果报告、诊断报告。
- `registry/`：数据、图表和论文产物登记表。

## 文档维护原则

1. 每次实验改进必须有实验设计、运行命令、输出路径、主要结果和不足记录。
2. 自动生成结果报告放入 `docs/experiments/`。
3. 当前状态只更新 `PROJECT_STATUS.md`，避免在多个文件里重复写"最新版说明"。
4. 任何目录移动必须同步更新脚本输出路径和 `reproducibility.md`。
5. 正式结论以 `results/`、`figures/` 和自动报告为准。
