# 合成标注 → project-98 格式转换方法总结

脚本：`convert_to_project98.py`（本仓库 `tools/project98_convert/`，与教学文档 §9 配套；产物与映射文件不入库，见 §6）

## 1. 输入 vs 目标

| | 输入（合成数据标准导出） | 目标（project-98 项目快照） |
|---|---|---|
| 结构 | `[task...]`，task 只有 `id/data/annotations/meta` | `[task...]`，19 个字段（含 `file_upload/drafts/predictions/created_at/inner_id/project` 等 DB 字段） |
| 标注人 | 合成工人名 `S_MANUAL_xxx`/`S_SEMI_xxx` | 整数用户 ID |
| 范围选项 | `from_name:"scope"`，choices `normal/oos` | `from_name:"worker_scope_response"`，choices `in_scope/out_of_scope` |
| result 项 | 无 `origin` | 带 `origin:"manual"` |
| ID | 字符串 `ST_xxx/SA_xxx/kp_N` | 整数 task/ann ID + UUID `unique_id` + 10 位短随机 result id |

## 2. 转换规则

### 结构（逐字段对齐 project-98，键序也一致）
- **task**：19 字段；`data` 10 字段（`image/vis_3d/base_task_id/title/condition/dataset_group/project_key/annotation_form_version/package_task_code/project_display_name`）
- **annotation**：21 字段（含 `prediction:{}`、`import_id/last_action/parent_*:null`、`bulk_created:false`、`updated_by=completed_by`）
- **result**：keypointlabels 键序 `original_width/original_height/image_rotation/value/id/from_name/to_name/type/origin`；choices 无宽高字段

### 字段映射
- `image`→`data.image`，`image_id`→`data.base_task_id`，`title = image_id + ".jpg"`
- `scope`→`worker_scope_response`；`normal`→`in_scope`，`oos`→`out_of_scope`；补 `origin:"manual"`
- 常量（取自 project-98）：`vis_3d`、`project_key:"zh_required"`、`dataset_group:"scene_stability_stage1"`、`project_display_name:"任务8"`、`file_upload:"6ef09a8e-任务8.json"`、`project:98`
- 合成专有字段（`simulation_id/generation_parameters/difficulty_wild_metadata` 等）丢弃，不在目标结构内

### condition → annotation_form_version（task 级）
- 全 manual → `manual_scope_only_v1`；全 semi → `semi_scope_only_v1`；混合 → `mixed_manual_semi_v1`，`condition` 字段同理为 `manual/semi/mixed`

### 标注人 → 用户 ID
- 默认模式：每个工人名分配一个新整数 ID（按名字排序连续分配）
- `slot35` 模式：按仓库命名公式 `S_MANUAL_{offset + image_index*35 + slot}` 取 `slot = (编号 - offset) % 35`，**同 slot = 同一个人**，全批次只产生 35 人；offset 默认 100000（round1），round2 用 200000（第 8 参）

### ID 与时间生成（确定可复现）
- task ID = task_base + 序号；ann ID = ann_base + 全局序号；`unique_id` = UUID4；result id = 10 位随机 base64url
- 时间窗口 2026-09-22 ~ 2026-09-28（对齐真实数据）：task created/updated → 标注 created = task 窗口内随机 → `draft_created_at = created_at - lead_time` → `updated_at = created_at + 0~2s`
- 随机种子 = 常量 ⊕ md5(源文件路径)：**同一源文件重跑结果完全一致**，不同源文件时间戳/随机 ID 不同
- `lead_time` 收敛到 [1, 600] 秒（对齐真实 18~575s 量级），保留 3 位小数
- `inner_id`/`package_task_code` 按 1..N 编号；合并多批次时需重编号为连续 1..总任务数

## 3. 用法

```bash
python3 convert_to_project98.py <源.json> <输出.json> <映射.json> \
  [task_id起始] [ann_id起始] [user_id起始] [slot35] [slot_offset]
```

| 参数 | 默认 | 说明 |
|---|---|---|
| task_id起始 | 40000 | 新任务整数 ID 起点 |
| ann_id起始 | 80000 | 新标注整数 ID 起点 |
| user_id起始 | 100 | 用户 ID 起点（slot 模式下 = 起点+slot） |
| slot35 | 不启用 | 启用 35 槽位身份坍缩 |
| slot_offset | 100000 | 槽位公式的偏移（round2 用 200000） |

不同批次用**不同 ID 区间**避免冲突（当前已分配：file1=40000/80000/100、file2=41000/90000/100、round1=42000/100000/200、round2=43000/110000/200；新批次请沿用下一个区间）。

## 4. 已转换批次（产物不入库，本地保存）

| 源文件 | 产物（本地） | 规模 | 用户 |
|---|---|---|---|
| 第一轮 full/label_studio_synthetic.json | label_studio_synthetic_as_project98.json | 259 任务 / 6678 标注 | 35 人 slot（200–234） |
| 第二轮 round2_gallery_144_.../label_studio_synthetic.json | label_studio_round2_as_project98.json | 144 任务 / 2740 标注 | slot 0–19（200–219） |
| 早期 label_studio.json / label_studio_1.json | label_studio{,_1}_as_project98.json | 368 / 378 任务 | 48 人（100–147） |

合并时：无图片重叠 → 直接拼接 + 重编号 `inner_id`/`package_task_code`；同 slot 映射保证同一批人跨文件一致。

## 5. 校验清单

1. task/ann/data 键名键序与 project-98 参考文件一致（脚本外对比脚本）
2. `from_name` 只有 `kp` + `worker_scope_response`；choices 只有 `in_scope/out_of_scope`；`origin` 全为 `manual`
3. 用户集合符合预期（slot 模式 = 起点..起点+34）
4. task/ann/unique_id/inner_id 全部唯一；与其它产物 ID 零冲突
5. lead_time 在 [1, 600]；时间戳在窗口内且 draft < created < updated

## 6. 入库边界（与教学文档 §4 底线一致）

- **只提交方法与工具**（本脚本 + 本文档），**不提交转换产物 JSON 与映射文件**——产物体积大（数十 MB）且 `project-98` 快照结构里没有 `synthetic` 字段，产物本身不含合成标记；溯源必须依赖源合成文件（`synthetic=True` + donor/seed 全溯源）与本地映射文件（原 ID → 新 ID、slot → 用户）。
- 下游若把转换产物与真人数据混用，务必先对映射文件核身份，不能把转换产物当作"已认证真人"。
