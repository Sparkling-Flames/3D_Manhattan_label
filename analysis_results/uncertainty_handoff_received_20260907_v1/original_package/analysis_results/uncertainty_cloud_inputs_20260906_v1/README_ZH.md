# 不确定性研究：云端输入包

本包完成本地数据整理，供云端独立分析。没有重新分簇、开展模拟、生成新的视觉裁决或制定论文方案。先读本页，再读 [字段说明](FIELDS_ZH.md) 和 [云端接手任务](CLOUD_HANDOFF_ZH.md)。实际生成及验证结果见 `BUILD_QA.json`、`VALIDATION.json` 和 `DELIVERY_MANIFEST.json`。

## 数据范围

| 对象 | 本包内容 |
|---|---|
| 历史标注 | 214图、26名人员、2501条 canonical 响应；另保留12条非canonical版本，共2513条版本记录 |
| 候选图 | 另列166张无历史标注候选，不计入真人分歧样本 |
| 模型输出 | 380图的Bi两头及HoHoNet ep300离线回放；候选图另保留166份历史预筛HoHoNet输出，共1306份模型布局 |
| 参考 | 603份参考变体：公开导入参考、历史人工裁决参考、候选图原始数据集标签；没有强制合成单一GT |
| 工作分簇 | 扩展73单元＋旧42图，共115份有版本区分的分区、2498条成员记录；已有k回放与阈值敏感性完整保留 |
| 其他旧分簇 | 保留816条历史人员分簇记录，以及213单元旧分区和已有代表标注；使用范围单独标记 |
| 审核资料 | 人工30张与AI50建议原样分开保存；AI50没有历史真人响应，不能作为真人模式证据 |
| 图片 | 原图不重复入Git；380条实际来源URL均已完成HEAD访问检查。访问成功只表示该时点可取得图像，不表示已做视觉审查 |

旧实验 eligibility、scope、正式使用状态均保留为历史属性，不作为总入口过滤。当前20人只标记为 `current20_member`。阶段、block、条件和同人重复不能混为独立响应。

## 最短读取路径

在仓库根目录运行，不需要GPU、模型权重或第三方Python包：

```bash
python -I -S analysis_results/uncertainty_cloud_inputs_20260906_v1/cloud_inputs.py validate --package analysis_results/uncertainty_cloud_inputs_20260906_v1
```

也可以只下载本目录，把命令中的目录换成下载位置。`validate` 与 `image` 不读取任何本地外部资产；`build` 是本地材料生成入口，需要原始仓库来源和Bi本地文件，不能误称为云端完全重做模型推理。

有 pandas 的环境可以直接读取：

```python
import json
from pathlib import Path
import pandas as pd

p = Path("analysis_results/uncertainty_cloud_inputs_20260906_v1")
responses = pd.read_csv(p / "annotations.csv.gz", dtype=str, keep_default_na=False)
links = pd.read_csv(p / "response_links.csv.gz", dtype=str, keep_default_na=False)
members = pd.read_csv(p / "clusters/memberships.csv.gz", dtype=str, keep_default_na=False)
models = {r["layout_id"]: r for r in map(json.loads, (p / "models/layouts.jsonl").read_text(encoding="utf-8").splitlines())}

# canonical ID只连接实际选定版本；raw_version_only另取原始版本，不能丢失或冒充canonical几何。
matched = members[members.mapping_status == "matched"].merge(responses, on="canonical_annotation_id", validate="many_to_one")
```

核心连接为：`images.image_id` → `annotations.base_task_id` → `response_links.canonical_annotation_id` → 模型、参考、实际初始化及分簇ID。CSV中的 `*_json` 字段需要JSON解析。所有布局统一记录1024×512坐标；不得自动按x排序原始点或假设不同点数已完成对应。

获取某张原图时运行：

```bash
python analysis_results/uncertainty_cloud_inputs_20260906_v1/cloud_inputs.py image --package analysis_results/uncertainty_cloud_inputs_20260906_v1 --image-id UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972 --output /tmp/panorama.jpg
```

省略 `--output` 只做HEAD访问检查。视觉网络访问与坐标离线完整性分别评价；不得在没有打开图片时声称做过视觉分析。完整访问记录在 `checks/image_access.csv`。

## 重要的来源和语义核对

1. 重新读取18个导出来源，2501条canonical原始坐标均与归档吻合；2513个版本实际坐标与原始关键点结果也已入包。修复几何与原始几何分开。
2. 历史214图中，Bi两头212图可作当前坐标比较、2图退化。旧线性距离为零的47图，两头原始坐标也完全相同；这仍然不是47张“无歧义真值”。`dual_equality_checks.csv`没有歧义标签或新的分类阈值。
3. 扩展73单元的簇定义来自相同全量响应集合，k不足的空白回放行没有当作分区变化；原438行回放保留。它与前置报告的严格N≥20共70单元分母不同。
4. 旧42分簇中的一条成员引用 `C1|66|3192|34|6053`。该版本存在，但当前底座选定的是同组6052；成员保留 `raw_version_only`，原版本坐标可直接取得，相关canonical ID仅用于追溯，不能拿其几何替换旧成员。
5. 旧213分区的代表标注关联中，224项可连接，112项未保存，90项原资料明确为 `not_identifiable`。这些项不是224个独立图像，也不能充当扩展73分区的新medoid。
6. 旧几何比较的左右身份已全部关联，共32497行；其中21856行是同分析单元的双人响应，112行跨分析单元，10529行不是双人响应。`metric_identity_links.csv.gz`恢复各自block/条件身份；不要只凭旧表“同stage”等描述判断独立性。
7. 房间类别不是实体房间ID。当前380图的 `room_instance_id` 全部留空，building和类别不能填进去代替。同一building的多图不自动独立。
8. 模型名称、checkpoint和推理split保留来源，但本包未独立验证模型训练集与全部研究图像的交集。实际历史初始化只以 `facts/proposal_fact.csv.gz`／`proposal_response.csv.gz` 为准，不能用离线Bi结果倒填历史暴露。

## 文件分工

- 根目录：统一图像、响应、连接、原始版本和参考；`FIELD_INDEX.csv`枚举各表顶层字段。
- `facts/`：既有事实底座快照，保留上游字段合同；事件表只保留已展开的观测字段，未复制嵌套 `raw_event_json`，不声称完整原始日志独立封装。
- `models/`：原始模型坐标及文本、floor UV、推理manifest、运行元数据和配置；本机路径是来源定位文字，不是云端读取依赖。
- `clusters/`：分区、成员和历史代表标注身份连接；`semantic_label`故意为空。
- `archive/`：原分析及审核资料的保存版本，不作为新结论。 broader source catalog保存底座之外的来源线索，不把所有快照都计为独立人类响应。
- `checks/`：坐标、图片访问及版本差异记录。缺失／未识别状态继续保留，不补成零、正确或无歧义。

旧分簇主要使用边界与墙线相似度、点对应兼容性和complete-link分区规则；旧线性墙面带距离是另一个代理。二者阈值不能互换。几何可解析、Manhattan合法性、当前房间范围和参考正确性分别判断。

## 生成与验证

本地生成入口为仓库 `tools/thesis_main/data_prep/build_uncertainty_cloud_inputs.py build`，默认原包及外部Bi来源均保持只读。包内 `cloud_inputs.py` 是该入口源码副本，方便云端直接执行离线检查。

生成器将已归档分析材料作为需要溯源的输入，原始坐标则重新回到导出文件核对。它不承诺复算所有旧统计或重新证明旧几何规范化正确。新增字段解释见 `FIELDS_ZH.md`；研究解释与本次独立审查见仓库相邻的 `preflight_independent_audit_20260906_v1`。

最终交付核验覆盖真实文件、源表解压后一致性、包内链接和远端回读。图像素材通过既有URL获取，未打包模型权重或原图大文件，不需要Git LFS。
