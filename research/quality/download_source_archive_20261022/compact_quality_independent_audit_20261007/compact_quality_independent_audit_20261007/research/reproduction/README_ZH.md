# 独立复核代码与复算说明

本目录提供三段独立复核程序及本次已完成的输出。程序没有绑定审核机器的绝对路径；可以在本地指定提取目录。所有输入只读，输出写入 `--output` 指定的目录。

## 1. 需要的实际文件

从 Library 的“3d全景图”文件夹取得并解压：

1. 新回传完整包：`panorama_quality_compact_20261007.zip`
   - `--source` 指向解压后的 `quality_compact_20261007` 目录
   - 目录内应直接有 `inputs/`、`results/`、`src/`、`vendor/`、`reproduce.py`、`requirements.txt`
2. 历史五轮审核包：`quality_audit_five_rounds_20261007.zip`
   - `--prior-review` 指向解压后的 `quality_audit_five_rounds_20261007` 目录
   - 必须能找到 `research/information_study/D_full_panel_metrics.csv`
3. 当时提供给 Pro 的扩展输入包：`pro_quality_expanded_data_20261007.zip`
   - `--expanded` 指向其解压根目录，即包含 `current/panel.json` 的目录

后两包用于核实复用指标和现行输入的来源一致性，不用于重新生成五轮历史实验。旧 Pro 数字包、原图 ZIP 无需另外下载：本次复核使用的必要复用输入已经包含在新完整包中。本代码不将历史复用项改称本轮重新测量。

此外需要 Python 及 compact 包 `requirements.txt` 所列依赖。示例使用虚拟环境，安装不会改动原始输入：

```sh
python -m venv .venv
# macOS / Linux
. .venv/bin/activate
# Windows PowerShell 改用：.venv\Scripts\Activate.ps1
python -m pip install -r "data/compact/quality_compact_20261007/requirements.txt"
```

## 2. 完整执行示例

以下命令假设当前工作目录下采用此布局；名称可以自行修改，只需相应调整参数：

```text
review/research/reproduction/          本审核的三段 .py 文件
data/compact/quality_compact_20261007/ 新完整包解压结果
data/prior/quality_audit_five_rounds_20261007/  历史五轮包解压结果
data/expanded/current/panel.json      扩展输入包中的现行面板
outputs/                             新复算输出的父目录
```

先运行官方入口。`outputs/official` 必须尚不存在；官方脚本不会覆盖已有目录。未传 `--figures`，因此只复算数值与接口/导出：

```sh
python "data/compact/quality_compact_20261007/reproduce.py" --out "outputs/official"
```

先检查路径，不进行数学计算：

```sh
python "review/research/reproduction/independent_audit.py" \
  --source "data/compact/quality_compact_20261007" \
  --prior-review "data/prior/quality_audit_five_rounds_20261007" \
  --expanded "data/expanded" \
  --official-output "outputs/official" \
  --output "outputs/independent" \
  --check-paths
```

正式运行三个独立复核，顺序如下。以下反斜杠是 macOS/Linux 的换行写法；Windows 可将每段命令写成一行：

```sh
python "review/research/reproduction/independent_audit.py" \
  --source "data/compact/quality_compact_20261007" \
  --prior-review "data/prior/quality_audit_five_rounds_20261007" \
  --expanded "data/expanded" \
  --official-output "outputs/official" \
  --output "outputs/independent"

python "review/research/reproduction/api_and_case_checks.py" \
  --source "data/compact/quality_compact_20261007" \
  --official-output "outputs/official" \
  --output "outputs/independent"

python "review/research/reproduction/independent_small_lobo.py" \
  --official-output "outputs/official" \
  --audit-summary "outputs/independent/independent_audit.json" \
  --output "outputs/independent"
```

独立脚本会覆盖指定输出目录中自己的同名结果，建议每次使用新输出目录。输出不应指向原输入包。需要日志时，在命令末尾添加 `> 对应日志路径 2>&1`；重定向的父目录需要已存在。

若不想先重跑官方入口，也可以把 `--official-output` 指向新包中的 `results/`，进行对已交付结果的独立复核。此时不能宣称“官方入口已在此次运行中复算”。本次交付中的 `official_run/` 确实来自一次已成功执行的官方入口。

## 3. 各脚本的范围

- `independent_audit.py`：来源逐字节核对、资格交集、全部主范围重建、自然原答冲突、共同人员面板、较广留建筑检验、融合共同域、官方/原包表格对照
- `api_and_case_checks.py`：新版 API 空/无效参考等回归检查、六份原答的独立原像素空间和角度计算；仅需新包和官方输出，不需两份历史包
- `independent_small_lobo.py`：共同 24 人×6 图的小面板检验；读取第一脚本已经确认的同六图列表

每段程序均支持 `--help`、`--output`、`--check-paths`。后者仅用 Python 标准库检查输入路径；不导入数值库、不运行实验、不覆盖已有结果。缺失输入会给出明确路径并以非零状态退出。

默认目录相对于脚本所在位置解析，适用于本次完整审核工作树：

```text
项目根目录/
  unpacked/quality_compact_20261007/
  prior_unpacked/five_rounds/quality_audit_five_rounds_20261007/
  prior_unpacked/expanded_input/
  research/reproduction/
    independent_audit.py
    api_and_case_checks.py
    independent_small_lobo.py
    official_run/
```

仅下载独立审核代码时，使用上述显式参数即可，不需要重建这个默认目录结构。

## 4. 结果与本次交付检查

审核结论见 `REPRODUCTION_AUDIT_ZH.md`；逐条检查见 `independent_audit.json`、`api_and_case_checks.json`、`independent_small_lobo.json`。原有数值复核结果没有因参数化改动而重新计算或变化。

交付前仅对参数化后的代码做了语法编译、帮助/默认及显式路径检查、跨工作目录检查、缺失路径错误检查，见 `portability_checks.json` 和 `portability_checks.log`。这一步验证可迁移的调用方式，不重复申报为一轮新的科学实验。
