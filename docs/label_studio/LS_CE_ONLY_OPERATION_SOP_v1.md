# LS CE-only Operation SOP v1

> Last updated: 2026-04-17

本 SOP 只回答一件事：

> 在**单实例、Community Edition、不改代码**的前提下，后续 `P1 / C1 / C2 / T1 / V1` 怎么运营。

## 1. 总原则

- LS 不是权限系统
- LS 不是分发真源
- 外部 manifest 是唯一分发真源
- 项目切分优先于复杂 tabs/filter
- GT 可与 worker-facing 项目共实例存在，但不共路径

这意味着：

- `P1` 用独立项目切三池
- `C1/C2/V1` 用按轮次/批次拆项目
- 只有项目内最小识别与核对才依赖现有字段

## 2. 现有可用字段

当前 frozen import 可直接用于最小识别和核对的字段包括：

- `dataset_group`
- `condition`
- `final_role` 或 `semi_role`
- `scope_gold` / `scope_target`
- `base_task_id`
- `task_id`

这些字段用于：

- 项目内最小过滤
- 核对导入是否正确
- 审计导出是否串池

当前**不要求**为了运营 SOP 先补这些字段：

- `round_id`
- `task_role`
- `source_split`
- `is_active_package`
- `assignment_batch`

## 3. 项目命名与使用方式

### 3.1 P1

固定项目名：

- `P1_manual`
- `P1_semi`
- `P1_oos`

使用方式：

- 所有通过 pilot 的 worker 完成三项目中的各自完整任务
- 不做 per-worker tabs
- 不在 `P1` 阶段做复杂追加派单

### 3.2 C1

固定项目名：

- `C1_anchor_all`
- `C1_core_batch_01`
- `C1_core_batch_02`
- `...`

使用方式：

- `C1_anchor_all` 面向所有通过 `P1` 的 worker
- `C1_core_batch_*` 按外部 `assignment_manifest_C1.csv` 切分
- 一个 batch 一个项目，不在单项目内用 tabs 模拟多批次

### 3.3 C2

固定项目名：

- `C2_reserve_batch_01`
- `C2_reserve_batch_02`
- `...`

使用方式：

- reserve 只开短时项目
- 补派完成即关闭项目
- 不保留常驻 reserve 池
- 不在 LS 内临时“看情况加任务”

### 3.4 T1

固定项目名：

- `T1_manual`
- `T1_semi`

### 3.5 V1

固定项目名：

- `V1_full_batch_01`
- `V1_full_batch_02`
- `...`

使用方式：

- 若真实部署只跑 `Full`，则只开 `V1_full_batch_*`
- `Random / Global` 的比较证据留在 offline replay / shadow support，不在 LS 里并跑

## 4. GT 共实例但非共路径

GT 在同实例下允许存在，但必须满足：

- GT 项目不属于 worker-facing active project set
- GT 导入、核对、导出只在管理员维护窗口进行
- 工人活跃标注时段不操作 GT 项目
- 管理员账号与工人账号分离
- 管理员维护 GT 时不使用工人日常浏览器 profile / 登录态
- 所有普通用户通过邀请制加入，不开开放注册
- GT 项目采用明显管理员命名，不与 worker-facing 项目混淆

这里的边界要写死：

> 这是运营隔离，不是权限隔离。

## 5. 每轮操作清单

### 开轮前

- 确认本轮 assignment manifest 已冻结
- 确认要开的 LS 项目名与 manifest 一致
- 确认导入任务数与 manifest 一致
- 确认本轮不需要的旧 batch 项目已关闭或明确标记为停用

### 运行中

- worker 只进入本轮指定项目
- 不在 LS 内临时重分配任务
- 不用 tabs 替代 batch 项目做主分发

### 收轮后

- 导出项目结果
- 记录实际参与 worker
- 核对实际导入任务数与完成数
- 对照 manifest 核对 worker/task 映射
- 关闭本轮短时项目（尤其 `C2_reserve_batch_*`）

## 6. 审计顺序

每轮审计顺序固定为：

1. assignment manifest
2. LS 项目名
3. LS 实际导入任务数
4. LS 实际参与 worker
5. 项目内字段过滤与页面状态

若冲突：

- 以 manifest 为准
- 以项目名与任务数核对为第一排查入口
- 不把 tabs/filter 视为正式合同

## 7. 当前不做的事

- 不做双实例
- 不改 userscript
- 不改 Nginx 路由
- 不改导入脚本
- 不把 LS 变成真正的任务分发器
- 不依赖 CE 权限保护 GT

## 8. 一句话执行口径

当前 CE-only 单实例方案的正式执行口径是：

> **P1 三池拆项目，C1/C2/V1 按轮次/批次拆项目；GT 同实例但不进入 worker 路径；真正的分发合同全部外置到 manifest。**
