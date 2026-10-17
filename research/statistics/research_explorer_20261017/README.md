# 全维度研究浏览台 · 2026-10-17

[已部署的交互浏览台](https://panorama-quality-review-20261016.fringnb.chatgpt.site/explorer.html) · [已部署的研究建议](https://panorama-quality-review-20261016.fringnb.chatgpt.site/research-advice.html) · [仓库内研究建议](../../../docs/thesis_main/研究进度与独立建议_20261017.md)

这是只读、可复现的研究快照，固定来源为 `Sparkling-Flames/3D_Manhattan_label` 的提交 `090883fab97298fb18033638487b0f4a84bf0d54`。不会自动追随 main，也不会修改正式算法、参考、质量资格或人员类别。已部署站点沿用原有访问范围；仓库归档不改变站点或仓库权限。

GitHub 的文件页面只展示 HTML 源码，不运行这个浏览台。可使用上方已部署入口，或按下文在本机生成数据并通过 HTTP 打开。仅双击 HTML 的 `file://` 方式可能被浏览器阻止读取 JSON。

## 内容与数据边界

- 195 张表：124 张当前表、71 张明确标识的历史表；共 234,232 个存储行。表间重复视图、路径、子集与重叠组不是独立样本。
- 当前库存 3,222 份 / 261 图；共同质量集合 1,911 份 / 136 图 / 25 人；普通 Manual 人员 Q 训练面板另为 1,048 份。
- 保留 B8L2 主线与 D10 敏感性，区分 Manual/Semi、普通/门洞/专项、资格/诊断、当前/历史、来源时间/同目标时间。缺失值不补零。
- 全字段表可搜索、筛选、排序、查看详情、追踪对象及导出 CSV；图表支持分布、散点和分类比较。笔记只保存在当前浏览器，需导出备份；不上传、不写回仓库。
- 现有 24 例原图核验入口与旧核验页使用经过核对的部署地址，不要求把整套旧站点和图片重复提交到此目录。
- 29 项原先未接通的补充材料仍显式保留缺口；有些源目录的其余图片、几何或模型文件仅提供链接。全量克隆不会悄悄扩大本次浏览台的选取范围。
- 不包含原始输入、评论全文、身份映射或直接姓名/联系方式字段；源文件 SHA-256 对应原 CSV 字节。本包只保存已用于展示的研究源选择及可核对证据。

## 新克隆中的复现方法

需要 Python 3.10+ 和 Git；构建及服务只用 Python 标准库，浏览台无前端安装步骤。从仓库根目录运行：

```sh
python tools/thesis_main/analysis/build_research_explorer_20261017.py
python -m http.server 8000 --bind 127.0.0.1
```

然后打开：

```text
http://127.0.0.1:8000/research/statistics/research_explorer_20261017/explorer.html
```

构建器通过 `git show 固定提交:路径` 读取固定 Git 对象，而非当前工作树文件。即使 main 已前进或工作树有未提交修改，也不能混进新的快照。260 个输入文件逐一检查大小与 SHA-256，随后检查生成的 195 个 JSON 文件与原展示包逐字节一致。缺失输入、不同哈希或 Git LFS 指针均停止，不使用示例或最新数据补齐。

若浅克隆不包含固定提交，先取得该提交：

```sh
git fetch origin 090883fab97298fb18033638487b0f4a84bf0d54
```

已导出的固定来源文件也可使用 `--source-dir /path/to/source-root`；该目录仍须通过全部 260 个哈希，`.source_commit` 声明本身不构成验证。`--repo /path/to/repository` 可指定 Git 来源仓库；输出仍默认写到当前构建器所在仓库的本工作台目录。

默认输出为本目录下的 `explorer-data/`，已由局部 `.gitignore` 排除。193 个表分片合计 159,485,375 字节，另有 index 与 overview。它们由仓库已有 CSV 派生，因此不重复提交。构建过程另需临时保存约 152 MiB 的验证输入，请预留数百 MiB 磁盘空间。

为避免覆盖不明文件，构建器要求输出目录为空。重复检查现有输出：

```sh
python tools/thesis_main/analysis/build_research_explorer_20261017.py --verify-only
```

重新生成时可选一个新的目录，例如 `--out /path/to/new-explorer-data`。若要通过本目录 HTML 读取，请把已验证的新数据放在本目录的 `explorer-data/`；不要将它提交进 Git。

## 文件说明

- `explorer.html`、`explorer.css`、`explorer.js`：浏览台静态源码
- `research-advice.html`：与浏览台本地互链的独立建议页面
- `source-manifest.json`：固定输入哈希、原展示选择、可用性目录与展示口径修订；可用性描述原包状态，不表示当前电脑上存在这些文件
- `expected-data.json`：195 个生成数据文件的大小及 SHA-256
- `data-inventory.json`：195 张表的源路径、粒度、行列数、状态与分片目录
- `verification/`：数值合成、字段契约、全表逐值核对、包形状及交互测试的结果
- `tests/`：可移植的构建安全测试、独立数值核对及可选 DOM 测试
- `../../../tools/thesis_main/analysis/build_research_explorer_20261017.py`：固定快照数据构建器

## 验证与复跑

```sh
python research/statistics/research_explorer_20261017/tests/test_builder.py
python research/statistics/research_explorer_20261017/tests/verify_scores.py
```

第二条读取工作树的质量 CSV，并要求与固定快照的整份检查结果及源哈希一致。若当前工作树已经更新，可用 `--source-dir` 指向固定快照的导出或 worktree。

可选 DOM 行为测试需要 Node.js 22.22.2+（22.x）、24.15.0+（24.x）或 26+，以及锁定的 jsdom 依赖：

```sh
cd research/statistics/research_explorer_20261017/tests
npm ci
npm test
```

测试亦可指定数据目录：`node explorer_ui.cjs /path/to/explorer-data`。jsdom 仅用于 QA，不参与生产浏览台或数据构建。

这次验证已完成：所有 260 个输入哈希、195 个输出逐字节一致、9 个构建守护测试、1,911 条保存测量的 B8L2/D10 重合成，以及文件驱动 DOM 的模块/筛选/详情/笔记/导出/导航/错误处理。此前原展示包还保存了 195 表逐值检查与 90 项字段契约检查。实测重合成最大差为约 `4.27e-14`。

边界：没有重新运行全库几何、loader、训练或融合；文件驱动 DOM 测试不等同经过登录的真实浏览器视觉验收；没有通过新一轮线上完整克隆复测下载过程。固定 Git 对象读取路径已用独立临时 Git 仓库测试，完整数据重建已用全部哈希一致的导出输入验证。
