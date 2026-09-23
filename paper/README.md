# Paper 目录说明

## 短稿（IEEE Communications Letters）

- `comml_ieee.tex`：五页限制内的短稿源码。作者块为**双盲占位符**
  （`Author 1, Author 2, and Author 3`），用于匿名评审场景。
- `comml_ieee.pdf`：由 `python run.py comml-paper` 编译得到的工作 PDF。
- `references_ieee.bib`：IEEE 参考文献库。

工作 PDF 与交付 PDF（`output/pdf/comml_ieee.pdf`）应保持哈希一致。

## `accepted/` —— 录用版（实名）

- `accepted/manuscript.tex` / `manuscript.pdf`：**正式录用的实名版本**
  （含真实作者、单位与通信作者脚注），即投稿时提交的最终文件。
- `accepted/figures/`：图母版，每图一个单独的 `.eps` 文件（另附 `.pdf` 便于本地查看）。

该目录内容与提交给 IEEE 的终稿**逐字节一致**，仅供阅读和编译复现，请勿改写 ——
如需修改请改 `comml_ieee.tex` 后重新编译。版权说明见根目录 README 的「许可与引用」。

## 支持性长稿

- `full_ieee.tex` / `full_ieee.pdf`：八页支持性长稿，不作为短文提交稿，
  作者块为匿名占位符。

## 中文翻译

- `i18n-cn/comml_ieee_cn.tex` / `comml_ieee_cn.pdf`：短稿中文翻译版。

## 模板

- `IEEEtran.cls`：IEEE 期刊 LaTeX 类文件，编译所需（编译器为 Tectonic）。

## 约定

不要把审查报告、提纲或过程文档放入 `paper/` —— 这些内容属于 `docs/`。
