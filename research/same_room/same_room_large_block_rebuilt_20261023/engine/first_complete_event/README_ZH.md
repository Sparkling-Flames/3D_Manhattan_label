# 一个已经实际算完的新严格 ABC 单元

**身份：`new_design_complete_case_not_restored_original`。这不是遗失的大块原件。**

实际 main 为 `e92abe8631d7f01dc192ee796b46f295ece37a6d`。从已冻结新设计中的 29,543 个普通、范围可比 Manual 结构分类事件，按 `event_id` 字典序取首个，未依据目标 Q 选择。事件为 `ABC_0001066d44f97b218867`，既有声明组 G130 的 `pa4otMbVnkk-42` 与 `pa4otMbVnkk-44`，两图已有难度均为“简单”。

本目录是可先交付的最小完整研究单元，完整总体实验仍在另外目录执行。额外执行的 6 次原生调用已登记；它们全部属于总体 311,333 个唯一端点，不增加唯一团队数。

## 精确对照

冻结楼外结构分类 V3_BEHAVIOR，源类 **常规转折**，目标类 **较多转折**；此楼折中是 M2→M3。对应楼外类中心、定义及全成员在 `FROZEN_CLASS_ROLES_AND_MEMBERS.csv`，不是把其它折同编号直接合并。

| 块 | 实际人员 |
| --- | --- |
| 固定 D | W109；历史类为较多转折 |
| 原块 X | W030、W101、W103、W113、W131 |
| 同类 Y | W106、W107、W108、W110、W118 |
| 跨类 Z | W102、W115、W122、W126、W130 |

两视角完全重复同一批成员。A=D∪X，B=D∪Y，C=D∪Z；三块 X/Y/Z 及 D 两两不重叠。`n=6,m=5,m/n=5/6`，属于有一名固定背景的混合团队，替换比例较高。A/B 是 5 名常规转折+1 名较多转折，C 是 6 名较多转折。

## 此单元实际观察到什么

| 视角 | A 的 Q | B 的 Q | C 的 Q | 同类 B−A | 跨类 C−A | C−B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| pa4otMbVnkk-42 | 93.130 | 91.478 | 99.272 | −1.652 | +6.142 | +7.794 |
| pa4otMbVnkk-44 | 91.708 | 96.436 | 99.011 | +4.728 | +7.303 | +2.575 |

此单元中，跨类替换的升质在两个视角同向，同类换人的质量作用反向。六队都形成完整可评候选，B8L2/D10 可用；全尝试分母是 6 队，失败为 0。

六队均为 **4 个实际转折、0 个短转折、0 个近共线冗余点**。因此不能把此事件解释为“较多转折类补了更多转折”。C 的底点误差、方向误差和高度误差在两图均小于 A/B；遗漏和外扩项仍有各自取舍。具体分项保存在 `CASE_SIX_ENDPOINTS_READABLE.csv`。

同角点数的冻结对应结果进一步显示，质量变化与几何变化幅度不是同一个结论：

| 视角 | A↔B 平均 BEV 角点距 | A↔C | B↔C |
| --- | ---: | ---: | ---: |
| -42 | 0.191629 h | 0.108429 h | 0.084241 h |
| -44 | 0.100685 h | 0.078392 h | 0.053946 h |

这里 `h` 是相机高度单位，不是米。六个同视角比较都满足角点数相同，得到原冻结算法的唯一循环对应候选。跨类 Q 的变化较大，但其对称几何幅度在这一个事件的两图都小于 A↔B；历史类别不能替代对具体位置响应的检查。

劳动时间也有可用支持边界：B、C 六名成员均为同来源时间，-42 为 516.015→874.797 秒，-44 为 632.632→814.434 秒，即 C−B 分别增加 358.782 和 181.802 秒。A 含不同记录语义，正式合并劳动时间保持缺失，不能把它强行放入三臂同口径省时比较。按来源的已知机会数和耗时仍保存在原端点标量中。

这些描述只针对这个按预定规则选出的完整单元，不据此推断总体多数比例或方向推荐。总体分析使用全部新冻结事件的实际完成结果。

## 文件及复算

- `STRICT_ABC_EVENT.csv.gz`：精确设计一行、两视角六个团队键、D/X/Y/Z、n/m、角色、历史特征和关系版本。
- `ENDPOINT_REQUESTS.csv.gz`：六个精确请求，逐人原答 object_id 可连回输入。
- `FROZEN_TWO_POOLS.json.gz`：两个冻结正式池，含 70 份原答、参考及原池元数据。
- `TWO_POOL_RECORD_TIMES.csv.gz`：上述 70 份记录的原时间字段及来源语义。
- `native/ENDPOINT_SCALARS.csv.gz`：完整六队标量；`native/parts/` 有同键完整几何、身份组、票账、对应和连接 state。
- `geometry/EVENT_GEOMETRY_RESULTS.csv.gz`：两视角各 AB/AC/BC，共六行原冻结角点对应结果。
- `CASE_PROVENANCE.json`：选择规则、源设计 SHA、来源和额外调用登记。

共享运行代码是上级目录 `native_team_runner.py`、`compare_event_geometry.py`；原生依赖固定于 `RUNTIME_SOURCE_MANIFEST.json`。例如在上级 engine 目录运行：

```bash
python native_team_runner.py --requests first_complete_event/ENDPOINT_REQUESTS.csv.gz --output first_complete_event/recomputed_native --jobs 1
python compare_event_geometry.py --events first_complete_event/STRICT_ABC_EVENT.csv.gz --endpoints first_complete_event/recomputed_native --output first_complete_event/recomputed_geometry --jobs 1
```

`native/OUTPUT_VALIDATION.json` 与 `geometry/COMPLETION.json` 已记录对本目录各 CSV/gzip 到 EOF 的读取、行数及精确关联检查。ZIP 成品仍由最终交付流程另外从包内读取验证。
