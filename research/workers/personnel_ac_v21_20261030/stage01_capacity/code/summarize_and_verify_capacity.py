"""Write a data-linked Chinese capacity guide and fully read every artifact.

No fusion, scoring, target-outcome selection, or historical label modification.
"""
from pathlib import Path
import csv, gzip, hashlib, json
import pandas as pd

OUT = Path(__file__).resolve().parents[1]


def table(frame):
    def cell(x):
        if pd.isna(x):
            return "—"
        if isinstance(x, float) and x.is_integer():
            return str(int(x))
        return str(x).replace("|", " / ")
    lines = ["| " + " | ".join(map(str, frame.columns)) + " |",
             "| " + " | ".join("---" for _ in frame.columns) + " |"]
    lines.extend("| " + " | ".join(cell(x) for x in row) + " |"
                 for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def main():
    receipt = json.loads((OUT / "CAPACITY_RECEIPT.json").read_text())
    roles_receipt = json.loads((OUT / "ROLE_PARENT_RECEIPT.json").read_text())
    inv = pd.read_csv(OUT / "POOL_INVENTORY_ALL_DOMAINS.csv")
    pm = pd.read_csv(OUT / "POOL_METHOD_CAPACITY.csv.gz")
    brief = pd.read_csv(OUT / "MAIN_SCALE_BRIEF.csv")
    whole = pd.read_csv(OUT / "WHOLE_CLASS_AND_ALLIANCE_SUMMARY.csv")
    inventory = inv.groupby(["scope", "condition", "layer"]).agg(
        pools=("pool_id", "size"), images=("image", "nunique"),
        buildings=("building", "nunique"), N_min=("pool_n", "min"),
        N_max=("pool_n", "max")).reset_index()
    max_blocks = pm[pm.scope.eq("primary")].groupby("method").agg(
        max_m=("max_m_AC", "max"), unknown_max=("unknown_n", "max"),
        pools_with_unknown=("unknown_n", lambda s: int((s > 0).sum()))).reset_index()
    direction_roles = pd.read_csv(OUT / "M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv")
    # Verify that the role enrichment did not replace exact local identity lists
    # by similarly named global class-size fields.
    for prefix in ["source", "target"]:
        sizes = direction_roles[prefix + "_workers"].str.split("|").map(len)
        assert sizes.eq(direction_roles[prefix + "_n"]).all()
    target10 = direction_roles[(direction_roles.method == "TARGET_DSTRUCT_K3") &
                               (direction_roles.m == 10) &
                               (direction_roles.source_class < direction_roles.target_class)]
    target10 = target10[["image", "building", "source_class", "target_class", "source_n",
                         "target_n", "pool_n", "source_parent_class", "role_direction"]]
    max_m = pd.read_csv(OUT / "POOL_FRONTIER_CAPACITY_SUMMARY.csv")
    high_m = max_m[(max_m.scope == "primary") & max_m.m.ge(13) &
                  max_m.class_feasible_pools.gt(0)][["method", "m", "class_feasible_pools",
                    "buildings", "frontier_n_min", "frontier_n_max"]]
    extra = whole[whole.scope.eq("other_admitted")][["method", "whole_equal_pools",
        "whole_unequal_pools", "alliance_teams", "alliance_teams_n_ge3"]]
    nread = receipt["all_legal_AC_direction_n_m_cells"]
    doc = f"""# HOHONET v2.1：直接 AC、整类替换与完整类别联盟的逐池容量

## 1. 本阶段结论及边界

本阶段已完成 **236 个普通 Manual 合法目标池 × 7 种冻结分类**的容量计算。
其中原主目标为 206 池、206 图、22 楼；其它准入目标为 30 池、28 图、9 楼。
不同目标不混池。容量只由该池实际合格原答人员与该楼外折的冻结标签决定。
没有使用目标图片的 B8L2、D10、记录劳动或融合结果选择设计，也没有重聚类。

来源提交：`{receipt['source_commit']}`。逐来源 SHA-256、标签重合一致性和计算公式见
`CAPACITY_RECEIPT.json`。采用已确认与当前提交一致的两个池快照，以及
`stage00_intake/current_source/` 中当前交付的冻结标签。本阶段未重新审查原答资格、排除清单、参考或空间归属。
这是一份容量交付；实际登记与执行必须回连后续阶段的事件表和端点表。

交接表中 n=20、m=10 的所有可行方向、人数和池一一复现，原主目标容量为
TARGET K3 **3 图**、RAW3 K3 **19 图**、OPPJOINT K3 **82 图**、OPPJOINT K4 **107 图**。
这些数字是可组成至少一个方向的图片数，既不是已执行图片数，也不是效果显著的图片数。

## 2. 各数据域库存

{table(inventory)}

普通 Manual 以外的 58 池仅作库存：门口/特殊 Manual 和 Semi 均没有混入主分析。
主目标表中的原始 `layer` 保留，OOS 的后续分析需独立说明合法条件。
其它准入目标的 30 池只有 28 张图，同图多目标的池数不能直接写作图片数。

## 3. 直接 AC 的完整合法条件

设池中共有 N 人，来源类 s 人、目标类 t 人，X/Z 为两个纯类块，各 m 人；
D 为相同背景，d=n−m 人。三块互不重叠，A=D∪X、C=D∪Z。
本阶段列出全部满足以下条件的整数 n、m 和方向：

- m≥1、n≥3、n≥m。
- s≥m、t≥m。
- N≥n+m，因此最多可取 n=N−m。

背景 D 可以来自任何剩余合格人员，包括来源/目标类的未抽中成员与未知类人员。
背景可以为空，此时 n=m；这样的全队替换必须与存在共同背景的条件分开解释。
每个方向及 n/m 的组合数为
`C(s,m) × C(t,m) × C(N−2m,n−m)`，保存为十进制字符串，不用浮点近似。
完整表含 **{nread:,}** 个合法方向×n×m 单元；这不是独立实验或独立思想的数目。

`at_pool_frontier=true` 表示 n=N−m，此时固定 X/Z 后背景就是所有剩余人员，
背景选择数为 1。前沿条件用于研究接近实际池规模的团队，但不同池的 n 可能不同。
`mv50_threshold=ceil(n/2)` 和 `block_can_reach_MV50` 只表示人数能否独立达到名义门槛；
它不证明块内任一节点具有一致支持，更不能代替完整票账。

正反两个方向在容量表均保留，交换 A/C 后是同一物理端点对，不能作独立重复证据。

## 4. 重点规模的主目标覆盖

`any_n_pools` 是至少有一种合法 n 的池数；其它列固定 n。
每行对所有合法类别方向取图片并集。表内建筑数是 any-n 范围，固定 n 的建筑数需查细表。

{table(brief)}

n=24、m=12 需要 N≥36，而普通 Manual 当前最多 N=35，所以全部方法在该条件为零。
这不说明 m=12 不可行：n=20/22 或各池前沿均可能合法。
各方法最大可行替换块如下。

{table(max_blocks)}

超过 12 人的容量也已经列出，不会因为默认 20 人团队而被漏掉：

{table(high_m)}

## 5. 大块替换的角色含义必须回到真实父类

已用冻结成员逐个验证现有父子关系，不按类编号猜测语义。
完整映射见 `FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv`，440 个楼外折类别；
每个有父层的子类均精确落于一个现有父类。

**TARGET K3 的全部 m=9/10 可行方向都在同一个 TARGET K2 父类内。**
它们是困难图历史有效转折较少/中等两层的替换；不能写成 K2 主分界上的“更多转折人群大块换入”。
TARGET K2 最大块为 8 人，TARGET K3 的增加来自细层；这既说明细层的容量贡献，也限定其解释。
n=20、m=10 的具体图片如下，逆向行已省略：

{table(target10)}

**OPPJOINT K3/K4 的全部 m=10/12 可行方向均不含相应楼外折的历史最高 Q 角色。**
JOINT K3 的该类大块方向是 Q 排名 1/3 与 2/3 互换；JOINT K4 主要是 1/4 与 2/4，
个别折可为 2/4 与 3/4。不能把较广的容量解释为最高 Q 小类能整块换入。
角色来自已有楼外训练中心的历史描述，不是目标图 Q，也不是对该图实际效应的预测。
RAW3 与 OPPSTRUCT 的各方向角色亦单列；跨方法对应 TARGET K2 的交叉表不是它们自己的层级父类。

逐池方向、class ID、精确成员、历史排名、真父类和 n20/22/24 可行标记见
`M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv`。
较早的 m7/8 联系保存在 `M7_M8_M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv.gz`。

## 6. 单图整类与完整类别联盟

“整类”始终是该图、该目标、该楼外折中该类别全部可用成员。

### 6.1 等人数整类

若来源 s≤目标 t，则令 m=s，把全部来源类放在 X，目标类取等量 Z；
若目标 t≤来源 s，则令 m=t，把全部目标类放在 Z，来源取等量 X。
s=t 时两边均全类。全部可行 n 均保留，模式分别为
`whole_source_out`、`whole_target_in`、`both_whole_equal`。
同一物理对若换成反向表述，需复用端点与事件身份。

等人数整类容量 **{receipt['whole_equal_cells']:,}** 个方向×n 单元。
不能只抽一组就声称类别的总体作用：X/Z 多组合与 D 多组合均有精确总数可供抽样覆盖判断。

### 6.2 不等人数整类

X 和 Z 分别取来源与目标全部人员；D 仅来自两类以外的剩余人员。
枚举 d，要求 A/C 各至少 3 人，保存 n_A=d+s、n_C=d+t、人数差 t−s。
共有 **{receipt['whole_unequal_cells']:,}** 个方向×背景人数单元。
配套 `equal_match_m=min(s,t)`、`equal_match_n=d+min(s,t)` 是可供解释人数与构成的匹配等人数条件，
不是已经执行的匹配对照。若这时匹配总人数不足 3，后续登记不得强行执行。

### 6.3 完整类别联盟

对每个池每种方法，将所有出现类别的每个非空子集所含的全部成员组成一队。
例如三类人数 8/17/10 时，完整单类、两类叠加、三类叠加都在库存。
存在未知类时，同时保留“不加未知人员”与“固定加入全部未知人员”的两个背景版本。
每种背景版本内部列出联盟间对照，避免把未知背景改变混成类别替换。

联盟队伍表 **{receipt['alliance_teams']:,}** 行、联盟对照 **{receipt['alliance_edges']:,}** 行。
n<3 的联盟仅保留库存，并通过 `n_at_least3` / `both_n_at_least3` 排除默认执行。
对照区分类别增加、减少、等人数全类互换和不等人数互换。
不同方法命中同一精确成员队伍可通过 `member_identity_key` 合并，不能重复计算成独立证据。
该 key 包含 pool_id，因此不同目标空间或不同原图不合并。

### 6.4 其它准入目标单列

{table(extra)}

其它准入目标 N 为 3–17，人少时适合小块整类或完整联盟；不能强行纳入主目标 m10/12 大块比较。
完整方法/数据域汇总见 `WHOLE_CLASS_AND_ALLIANCE_SUMMARY.csv`。

## 7. 人数、历史、类别容量与设计缺失分开

`KEY_N_M_POOL_FUNNEL.csv.gz` 为重点 n/m 的逐池原因表，依次区分：

- `n_less_than_m`：条件本身不合法。
- `total_pool_people_insufficient`：池总人数不足 n+m。
- `known_class_history_total_insufficient`：有足够合格原答但有类历史者不足 2m。
- `class_distribution_insufficient`：有类总人数够，但没有两个类各达到 m。
- `feasible_not_yet_designed`：容量满足，等待本轮登记。

前述原因是按门槛顺序互斥归类；未知历史可同时加重具体类容量不足。
若要区分“未知历史恰好造成哪个方向不足”，需结合实际逐人标签作额外条件判断，
不能由已知总人数这一层独立断言。

未知类不作 X/Z，但可留在 D；TARGET/RAW3/OPPSTRUCT/RFUSE 中可见 W022，
OPPJOINT 另有依折未知的 W014/W018/W034。保留这些人员的原答资格，不把分类历史缺失改写为整人排除。
全体被排除人员没有被加入本阶段池。

`designed_pools=0`、`executed_pools=0` 和 `capacity_only_not_yet_designed` 仅表示
**本轮容量阶段尚未登记/执行**；不代表没有可复用的历史端点或既有实验。
设计遗漏、运行失败、输出不可评分必须由后续阶段按实际状态补齐，不能在容量阶段凭空归类。

## 8. 主要接口与复现

| 文件 | 主要键/字段 | 下游用途 |
| --- | --- | --- |
| `SCORE_BLIND_POOL_INPUTS.json` | `pools`: pool_id, meta, workers, members(worker_id/object_id), scope | 不读目标分数即可冻结设计 |
| `POOL_INVENTORY_ALL_DOMAINS.csv` | pool_id,scope,condition,layer,workers | 普通/其它数据域库存 |
| `FROZEN_LABELS_USED_ALL_LOBO.csv.gz` | method,heldout_building,worker_id,class_id,known | 当前冻结分类输入 |
| `POOL_METHOD_CAPACITY.csv.gz` | pool_id,method,class_members_json,class_counts_json,unknown_workers,max_m_AC | 登记脚本推荐入口 |
| `POOL_CLASS_MEMBERS.csv.gz` | pool_id,method,class_id,class_n,class_workers | 逐池精确类名单 |
| `DIRECTED_CLASS_CAPACITY.csv.gz` | pool_id,method,source_class,target_class,source/target_n,source/target_workers,max_m | 全方向容量 |
| `ALL_LEGAL_AC_N_M_DIRECTION_CAPACITY.csv.gz` | pool_id,method,source_class,target_class,n,m,d,三种组合数 | 所有合法 AC 条件 |
| `WHOLE_CLASS_EQUAL_CAPACITY.csv.gz` | pool_id,method,source_class,target_class,n,m,whole_mode | 等人数整类 |
| `WHOLE_CLASS_UNEQUAL_CAPACITY.csv.gz` | pool_id,method,source_class,target_class,D_n,n_A,n_C,D_candidates | 不等人数整类 |
| `ALL_CLASS_ALLIANCE_TEAMS.csv.gz` | pool_id,method,alliance_classes,members,member_identity_key | 完整类组合队伍 |
| `ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz` | A/C_identity_key,n_A/n_C,D_n,X_n,Z_n,comparison_type | 联盟配对及构成改变 |
| `FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv` | method,heldout_building,class_id,parent_method,parent_class,primary_role_axis/rank | 冻结角色及层级解释 |
| `M9_M10_M12_DIRECTION_ROLES_AND_PARENTS.csv` | pool_id,method,m,source/target_class,source/target_workers,source/target_global_class_n | 大块具体人员及角色 |
| `KEY_N_M_AC_CAPACITY_FUNNEL.csv` | method,scope,n,m,各门槛数量 | 可覆盖范围及限制 |

`source_workers`/`target_workers` 一律是该池精确人员串。
`source_global_class_n`/`target_global_class_n` 则是历史楼外分类的全类人数，二者不可互换。
`FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv` 中原字段 `workers` 保留既有语义（全类人数），`members` 才是全类名单。

在交付的工作区根目录依次运行：

```bash
python HOHONET_v21_AC_population_20261029/stage01_capacity/code/compute_ac_capacity.py
python HOHONET_v21_AC_population_20261029/stage01_capacity/code/add_frozen_roles_and_parents.py
python HOHONET_v21_AC_population_20261029/stage01_capacity/code/summarize_and_verify_capacity.py
```

来源不覆盖。所有 CSV/gzip 均以 UTF-8 读到结尾并检查列宽，所有 JSON 完整解析，
代码完成语法检查；结果写入 `CAPACITY_FILE_MANIFEST.csv` 与 `CAPACITY_READABILITY_RECEIPT.json`。
CSV 中组合数应按字符串/任意精度整数读取，人员串分隔符为 `|`，JSON 类成员字段不可当自然语言拆分。
最终压缩包层面的可读性验证由总交付再进行，不能由本目录文件可读性替代。
"""
    (OUT / "CAPACITY_AND_DESIGN_BOUNDARIES_ZH.md").write_text(doc, encoding="utf-8")
    manifest = []
    excluded = {"CAPACITY_FILE_MANIFEST.csv", "CAPACITY_READABILITY_RECEIPT.json"}
    for path in sorted(OUT.rglob("*")):
        if not path.is_file() or path.name in excluded or "__pycache__" in path.parts:
            continue
        content = path.read_bytes()
        count = None
        columns = None
        reader_kind = "utf8"
        if path.name.endswith(".csv") or path.name.endswith(".csv.gz"):
            opener = gzip.open if path.suffix == ".gz" else open
            with opener(path, "rt", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream)
                header = next(reader)
                assert len(header) == len(set(header)), str(path)
                columns = len(header)
                count = 0
                for row in reader:
                    assert len(row) == columns, (str(path), count, len(row), columns)
                    count += 1
            reader_kind = "gzip_csv_to_eof" if path.suffix == ".gz" else "csv_to_eof"
        elif path.suffix == ".json":
            json.loads(content.decode("utf-8-sig"))
            reader_kind = "json_full_parse"
        else:
            text = content.decode("utf-8")
            if path.suffix == ".py":
                compile(text, str(path), "exec")
                reader_kind = "python_compile"
        manifest.append(dict(path=str(path.relative_to(OUT)), bytes=len(content),
                             sha256=hashlib.sha256(content).hexdigest(), rows=count,
                             columns=columns, verification=reader_kind))
    pd.DataFrame(manifest).to_csv(OUT / "CAPACITY_FILE_MANIFEST.csv", index=False,
                                  encoding="utf-8-sig")
    expected = {"ALL_LEGAL_AC_N_M_DIRECTION_CAPACITY.csv.gz": receipt["all_legal_AC_direction_n_m_cells"],
                "WHOLE_CLASS_EQUAL_CAPACITY.csv.gz": receipt["whole_equal_cells"],
                "WHOLE_CLASS_UNEQUAL_CAPACITY.csv.gz": receipt["whole_unequal_cells"],
                "ALL_CLASS_ALLIANCE_TEAMS.csv.gz": receipt["alliance_teams"],
                "ALL_CLASS_ALLIANCE_CONTRASTS.csv.gz": receipt["alliance_edges"]}
    got = {r["path"]: r["rows"] for r in manifest}
    assert all(got[k] == v for k, v in expected.items())
    proof = dict(status="passed", files=len(manifest), bytes=sum(r["bytes"] for r in manifest),
                 all_csv_read_to_eof=True, all_gzip_crc_checked=True,
                 csv_row_widths_and_headers_checked=True, all_json_fully_parsed=True,
                 all_python_syntax_checked=True, largest_tables_match_capacity_receipt=True,
                 exact_pool_members_preserved_in_role_directions=True,
                 source_commit=receipt["source_commit"], role_parent_checks=roles_receipt,
                 does_not_claim_archive_verified=True)
    (OUT / "CAPACITY_READABILITY_RECEIPT.json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in proof.items() if k != "role_parent_checks"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
