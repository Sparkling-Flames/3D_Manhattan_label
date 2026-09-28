# 给 ChatGPT Pro 的全景布局研究包

日期：2026-09-27。状态：探索性交接，非正式分析发布。

先读 `docs/thesis_main/PRO_CLOUD_LAYOUT_GEOMETRY_QUALITY_TASK_20260927.md`，再读同目录讨论纪要。最新任务书优先于历史讨论，包括新增的启发式／退火搜索减法问题。

## 内容及边界

- 八张用户指定图片的160份历史坐标输入；153份有可独立计算的几何，24名包内重新编号的人员。人员别名跨这八图保持一致；不提供原编号映射、任务ID、原始导出或私人路径。
- `inputs/eight_image_panel.json`：原始点、原始点对、共享x点对、既有邻接、来源状态的必要子集；GT的原版／修订版只用于评价。字段是本交接包的派生格式，不是正式协议字段。
- 六个核心源码文件和四个现有测试文件，保持本地相对路径。`MANIFEST.json`列全部包内文件及大小；不依赖仓库其他代码。
- 不公开全景原图或本地论文PDF。可以重算坐标几何、mask和合成反例，不能凭包内数据验证视觉墙角、遮挡或真实结构。正式研究的图像许可与取用仍按原数据源办理。
- 角点顺序、排除、OOS／门洞分类尚未完成；历史状态原意保留，不能当成全量审核完成。`core_record=null`属于未获得独立可用几何，不等同于应排除的坏标注。两种分母均须报告。
- 输入来自 `analysis_results/union_branch_consensus_20260926/input_panel.json` 的显式字段投影。它是历史派生快照，不是真源替代品；原件在本地保留。文档部分背景链接指向完整仓库，不是承诺所有背景资料均已装入此最小运行包。

## 运行

在解压根目录执行（需要Python 3.10或以上）：

```sh
python -m pip install -r requirements.txt
python -B verify_bundle.py
python -B -m pytest -q -p no:cacheprovider tests
python -B -m tools.thesis_main.analysis.layout_metric_probe_20260926 --out synthetic_results
```

已有依赖时跳过安装。SimpleITK是STAPLE可选依赖，未安装应返回unavailable，不能称作已跑STAPLE。`verify_bundle.py`在八图上实际调用旧核心方法，验证分母、人数守恒及便携性；这不是新增搜索算法验证，也不是重跑历史全部重放曲线。

`fit_union_branches`接受每图非空的`core_record`列表，不接收GT。它目前只研究已观测整环的分支；自由删点、束搜索或退火需要Pro另行设计与验证。候选池的并集不是一个已知合理的房间。`consensus_region.wall_mask`会按横坐标构造单值包络，因此不敏感于输入排列；显式3D邻接是另一种表示，不能混为一谈。

## 重点研究输出

三套可实施方案、独立的人员权重／指标权重／几何约束／结构排序参数、具体试验初值和校准方法。已验证数字与假说分开；不要为了漂亮几何删掉所有细节，不用目标GT调参。小样本、无简单图对照、非随机选图，只允许试探性比较。

Lee论文：https://ceur-ws.org/Vol-2173/paper10.pdf

IEEE 8031037：https://ieeexplore.ieee.org/document/8031037

对应作者公开稿：https://infoscience.epfl.ch/server/api/core/bitstreams/249ef735-e04a-42bd-b31c-6f39041e2fc1/content

本轮只新增任务书与交接工件；没有修改原始数据、既有算法、GT、排序、排除裁决或规范合同。代码与数据公开不表示重新授予第三方原始数据的版权许可。
