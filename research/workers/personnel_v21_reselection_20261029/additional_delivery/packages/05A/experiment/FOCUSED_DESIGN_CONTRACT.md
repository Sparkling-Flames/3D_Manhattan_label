# 广筛之后的重点成员、背景及规模设计

本文件说明广筛后实际登记的三个补充实验。具体采用的方法、角色和 n/m 已在完整 45 法广筛比较后写入 `focused_selection/SELECTED_CONDITIONS.csv` 及同目录选择依据；登记器不读目标效果、不重拟人员类别，继续使用 `MAIN45_LABELS_ALL_LOBO.csv.gz`。登记完成与端点计算完成分开：本文件列注册规模，实际完成状态以相应 `RUN_RECEIPT.json` 和测量回执为准。

|补充实验|可行池×条件格|去重事件|去重端点请求|实际池／图片／建筑|
|---|---:|---:|---:|---|
|32 条条件的成员与背景扩展|2,900|10,980 严格 ABC|30,166|187／187／22|
|两个方向在 n12/20/26 的真实最大 m 路径|1,134；其中至少两 m 点者实际形成路径|5,191 严格 ABC，1,380 条路径|11,693|196／195／22|
|两个方向的大团队直接 AC|1,285|1,622 直接 AC|2,852|191／190／22|

第一批含 187 个主目标池；固定 A 路径含 195 主目标池及 1 其它合法目标池；直接 AC 含 185 主目标池及 6 其它合法目标池。类别和容量不足的池保留在各 `POOL_CONDITION_ENTRY_AND_EXIT.csv.gz`，没有因结果方向退出。

## 1. 同 n/m、改变成员与背景

`select_focused_conditions.py` 将历史语义角色映射为每个目标楼对应的实际类别，记录全部池的进入/退出原因；`register_adaptive.py` 再登记互斥 D/X/Y/Z。输入条件表的必要列是 `condition_id,method,role_axis,source_rank,target_rank,n,m`；可指定 `k,condition,layer,scope`。`role_axis` 指角色表中真实存在的秩字段，如 `challenge_turn_rank_asc`、`q_rank_asc` 或 `size_rank_desc`，不会把跨折 C 编号视作相同角色。

既定框架的 `SCREEN_POOL_FRAME.csv` 含全库存，需使用 `selected=True` 识别初筛范围。映射表分别保留是否在初筛池、是否在初筛建筑。相同历史 v2/v2.1 材料已经多轮使用，框架外结果称本次选型之外的内部扩展。

## 2. 原队 A 不变的替换规模路径

`register_fixed_A_m_paths.py` 读取最大块条件，固定 Xmax、Ymax、Zmax 的有序成员和 D0；对各 m 使用同一顺序的前缀：

- A = D0 ∪ Xmax，整个路径始终相同。
- D_m = D0 ∪ (Xmax \ X_m)。
- B_m = D_m ∪ Y_m；C_m = D_m ∪ Z_m。

最大块可在条件表设 `m=capacity`，对固定 n 按每池实际来源类/目标类容量计算 `min(S//2,T,(N−n)//2,n)`，没有统一截在 7 或 8 人。`--m-values quarter,half,three_quarter,max` 取该池最大块约 1/4、1/2、3/4 及全容量（向上取整并去重）；只有一个可用 m 点的池不称规模路径。

实际采用 `TARGET_DSTRUCT_K3` 的历史困难转折秩 2→3 与 `OPPGEOM_K3` 的历史面积秩 2→3；各池 1 组 XYZ，D0 取可达 low/high 各 1 组。真实容量在 n12 下最高 m8、n20 下最高 m7、n26 下最高 m4；这是这两个冻结角色方向的容量结果，不是程序设定的上限。完整分布在 `fixed_A_m_design/PATH_CAPACITY_SUMMARY.csv`。

每个 m 都保持严格互斥 ABC。总人数固定，人数引起的投票门槛项固定；对应分组、实际支持票、位置和连接仍可能随换入成员变化。D0 可取可行目标类人数的低/高层，另抽具体成员。输出 `PATHS_EXACT.csv.gz`、`PATH_EVENT_LINKS.csv.gz` 和 `EXACT_M_PATH_PAIR_LINKS.csv.gz`，同时保存每个端点的精确请求。

对 m1→m2，分别报告 C_m2−C_m1、B_m2−B_m1，以及 (C_m2−B_m2)−(C_m1−B_m1)。净优势增加不直接等于 C 队升质。该路径与广筛已经保存的“相同 XYZ、D 严格嵌套、改变 n”的 46,851 条人数链接分开。

## 3. 较大团队的直接 AC 尾部

`select_focused_conditions.py --design AC` 使用 N≥n+m、源类≥m、目标类≥m 的容量；`n=capacity` 明确表示该池的 N−m，而不是把小池写成固定 30 人。`register_direct_AC_tail.py` 登记 D/X/Z，保持共同 D 和实际换人数 m。可用的固定人数例为 n28/m7、n30/m5、n32/m3，实际是否登记仍以选择表和该池容量为准。

这些事件没有 B：只比较 C−A 及几何、结构、时间和失败，不能进入“同类变化比跨类变化小”的估计。输出保留 `comparison_has_B=False`。当不同条件入口对应同一端点时，事件和端点分别去重，`EVENT_CONDITION_LINKS.csv.gz` 保存它属于哪些条件。

## 4. 保存与恢复

登记输入及条件 SHA 在任何新融合前保存；精确端点继续交由原 `run_registered.py` 计算。融合与评分合同不变，每 100 个端点原子保存。`finalize_cumulative_provenance.py` 在全批完成后由端点来源重新统计累计新算/复用数量，避免把恢复启动后的新算数误写成整轮总数。
