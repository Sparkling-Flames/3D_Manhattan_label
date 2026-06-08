**Label Studio 管理结论（2026-04-17）**

## 1. 当前正式口径

当前项目在 Label Studio Community Edition 下采用：

- **单实例**
- **不新增公开端口**
- **不修改 userscript / Nginx / 导入脚本**
- **项目切分优先于复杂 tabs/filter**

这套方案的核心边界是：

> Label Studio CE 只能支持**流程分发**，不能支持**权限分发**。

因此，LS 在当前体系中的定位固定为：

- worker-facing 的**展示与采集前端**
- 不是权限系统
- 不是任务分发真源

真正的分发真源固定为外部 manifest，例如：

- `assignment_manifest_C1.csv`
- `assignment_manifest_C2.csv`
- `assignment_manifest_V1.csv`

若 LS 页面状态与 manifest 冲突，以 manifest 为准。

---

## 2. 当前仓库现实

按当前仓库实查，已经落地的是：

- 单一 LS CE 实例
- 现有公网入口
- `tools/label_studio/official/ls_userscript_annotator.js` 的当前匹配与 active-time 上报逻辑
- `Nginx /ls/ -> 8080` 的同源代理思路
- Stage 1 frozen import JSON

当前**没有**落地的是：

- 双实例 GT 隔离
- 同一公网端口下的双内部实例 path proxy
- 基于 LS 权限的 GT 隐藏
- LS 内部的精确 annotator-task assignment

因此，当前最稳的说法是：

> 继续单实例是合理的；GT 风险依靠运营隔离与项目切分控制，而不是依靠 CE 权限。

---

## 3. 当前可直接使用的导入字段

当前正式 frozen import 已经带有一部分可用于项目内识别与最小过滤的字段，并不是只有：

- `image`
- `vis_3d`
- `title`

例如 Stage 1 frozen import 中，已存在或可直接使用：

- `dataset_group`
- `condition`
- `final_role` 或 `semi_role`
- `scope_gold` / `scope_target`
- `base_task_id`
- `task_id`

这些字段当前的定位是：

- 支持项目内最小过滤
- 支持人工核对与导出审计
- 不承担 round/batch 的主分发合同

当前**不作为 blocker** 的字段有：

- `round_id`
- `task_role`
- `source_split`
- `is_active_package`
- `assignment_batch`

这些字段未来可以补，但**不是当前单实例 CE-only 方案的前置条件**。

---

## 4. 当前正式项目切分模型

### 4.1 P1 / PreScreen

`P1` 阶段固定采用三项目切分：

- `P1_manual`
- `P1_semi`
- `P1_oos`

规则固定为：

- `P1_manual`：所有通过 pilot 的 worker 完成同一批任务
- `P1_semi`：所有通过 pilot 的 worker 完成同一批任务
- `P1_oos`：独立 OOS gate 项目，不并入主几何可靠度链

`P1` 阶段**不做** per-worker 分派，也不要求 per-worker tabs。

### 4.2 C1 / Calibration

`C1` 阶段固定采用：

- `C1_anchor_all`
- `C1_core_batch_01`
- `C1_core_batch_02`
- `...`

规则固定为：

- `C1_anchor_all`：全员完成
- `C1_core_batch_*`：按 assignment manifest 切成多个批次项目，每个批次项目只导入该批任务

### 4.3 C2 / Calibration Reserve

`C2` 阶段固定采用短时项目：

- `C2_reserve_batch_01`
- `C2_reserve_batch_02`
- `...`

规则固定为：

- reserve 只做短时批次
- 完成即关闭
- 不保留常驻 reserve 池
- 不允许把 reserve 变成新的长期 worker-facing 项目

### 4.4 T1 / Main-Test

`T1` 阶段固定采用：

- `T1_manual`
- `T1_semi`

### 4.5 V1 / Main-Validation

`V1` 阶段固定采用：

- `V1_full_batch_01`
- `V1_full_batch_02`
- `...`

若真实部署只跑 `Full`，则：

- 只开 `V1_full_batch_*`
- `Random / Global` 不在 LS 内并跑补主证据

---

## 5. GT 在同实例下的正式边界

GT 项目允许继续存在于同一实例，但只按**管理员维护项目**处理。

固定规则：

- GT 项目不属于 worker-facing active project set
- GT 导入、核对、导出只在管理员维护窗口进行
- 工人活跃标注时段，不进行 GT 项目操作
- 管理员账号与工人账号分离
- 管理员维护 GT 时，不使用工人日常浏览器 profile / 登录态
- 所有普通用户通过邀请制加入，不开开放注册
- GT 项目名称必须采用明显管理员命名，不与 worker-facing 项目混淆

这里要明确：

> 这不是权限隔离，只是运营隔离。

---

## 6. 审计优先级

当前 thesis-facing 审计优先级固定为：

1. 外部 assignment manifest
2. 导入项目名 / 导入任务数
3. 实际参与 worker
4. LS 页面中的 tab/filter 视图状态

每轮结束后必须核对：

- 实际导入项目名
- 实际导入任务数
- 实际参与 worker
- manifest 预期 worker/task 映射

若不一致，以外部 manifest 为准，LS 页面状态只作为排查线索。

---

## 7. 当前明确不做的事

当前方案明确不做：

- 不做双实例
- 不改 userscript
- 不改 Nginx 路由
- 不改导入生成脚本
- 不把 LS 变成真正的任务分发器
- 不依赖 CE 权限来保护 GT
- 不把项目内 tabs 作为后续 round/batch 的唯一主承载

---

## 8. 一句话结论

当前最稳的 CE-only 运营方案是：

> **继续单实例，把 LS 固定为展示与采集前端；P1 用三项目切分，C1/C2/V1 用按轮次/批次拆项目；GT 留在同实例但只走管理员维护路径；真正的分发合同全部外置到 manifest。**
