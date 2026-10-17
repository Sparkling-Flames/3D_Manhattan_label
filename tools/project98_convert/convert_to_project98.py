#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 label_studio.json（合成标注，标准导出格式）转换成 project-98 的项目快照格式。
转换规则：
  - 保留全部 4537 条标注（manual + semi 都保留）
  - task 级 condition / annotation_form_version 区分 manual / semi（含 mixed）
  - 全新生成整数 task/annotation ID、UUID unique_id、10位短随机 result id
  - 48 个合成标注人(S_MANUAL_xxx / S_SEMI_xxx) -> 各自新的整数用户 ID(100..147)
  - from_name: scope -> worker_scope_response；choices: normal->in_scope, oos->out_of_scope
  - result 项补 origin:"manual"
  - lead_time 收敛到 [1, 600] 秒区间(对齐真实数据约 18~575s 的量级)，保留 3 位小数
"""
import json
import random
import uuid
import sys
from datetime import datetime, timedelta, timezone

# 用法: python3 convert_to_project98.py <src.json> <out.json> <mapping.json> [task_base] [ann_base] [user_base] [slot35] [slot_offset]
SRC = sys.argv[1] if len(sys.argv) > 1 else None
OUT = sys.argv[2] if len(sys.argv) > 2 else "label_studio_as_project98.json"
MAP_OUT = sys.argv[3] if len(sys.argv) > 3 else "label_studio_as_project98_mapping.json"
if SRC is None:
    raise SystemExit("用法: python3 convert_to_project98.py <src.json> <out.json> <mapping.json> "
                     "[task_base] [ann_base] [user_base] [slot35] [slot_offset]")

# 种子与源文件绑定（用稳定哈希）：同一源文件结果可复现，不同源文件产出不同的时间戳/随机ID
import hashlib
rng = random.Random(20261015 ^ int(hashlib.md5(SRC.encode()).hexdigest()[:8], 16))

# ---- 常量（取自 project-98） ----
PROJECT = 98
VIS_3D = "http://175.178.71.217:8000/tools/vis_3d.html"
PROJECT_KEY = "zh_required"
DATASET_GROUP = "scene_stability_stage1"
PROJECT_DISPLAY_NAME = "任务8"
FILE_UPLOAD = "6ef09a8e-任务8.json"

TASK_ID_BASE = int(sys.argv[4]) if len(sys.argv) > 4 else 40000
ANN_ID_BASE = int(sys.argv[5]) if len(sys.argv) > 5 else 80000
USER_ID_BASE = int(sys.argv[6]) if len(sys.argv) > 6 else 100
# 可选第7参: slot35 —— 按仓库命名公式 S_MANUAL_{100000+image_index*35+slot} 把工人坍缩为 35 个槽位(slot)身份
SLOT_MODE = len(sys.argv) > 7 and sys.argv[7] == "slot35"

WIN_START = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
WIN_END = datetime(2026, 9, 28, 23, 59, 59, tzinfo=timezone.utc)

RESULT_ID_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"


def fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def rand_dt(start: datetime, end: datetime) -> datetime:
    span = (end - start).total_seconds()
    return start + timedelta(seconds=rng.uniform(0, span))


def rand_result_id() -> str:
    return "".join(rng.choice(RESULT_ID_CHARS) for _ in range(10))


def clamp_lead_time(x):
    x = float(x)
    if x < 1.0:
        x = rng.uniform(1.0, 10.0)
    elif x > 600.0:
        x = rng.uniform(400.0, 599.0)
    return round(x, 3)


def convert_result_item(item, mapping_note):
    """把 label_studio 的 result 项转成 project-98 的 result 项。"""
    typ = item["type"]
    from_name = item["from_name"]
    value = dict(item["value"])
    new_id = rand_result_id()

    if typ == "keypointlabels":
        return {
            "original_width": item.get("original_width"),
            "original_height": item.get("original_height"),
            "image_rotation": item.get("image_rotation", 0),
            "value": value,  # 保持 x/y/width/keypointlabels
            "id": new_id,
            "from_name": from_name,
            "to_name": item.get("to_name", "img"),
            "type": typ,
            "origin": "manual",
        }
    # choices
    if from_name == "scope":
        from_name = "worker_scope_response"
    if "choices" in value:
        value["choices"] = [
            {"normal": "in_scope", "oos": "out_of_scope"}.get(c, c)
            for c in value["choices"]
        ]
    return {
        "value": value,
        "id": new_id,
        "from_name": from_name,
        "to_name": item.get("to_name", "img"),
        "type": typ,
        "origin": "manual",
    }


def main():
    src = json.load(open(SRC, encoding="utf-8"))

    # ---- 标注人 -> 新用户ID ----
    workers = sorted({an["completed_by"] for t in src for an in t["annotations"]})
    if SLOT_MODE:
        # 仓库公式: sw = S_MANUAL_{offset + image_index*35 + slot}，slot 即"人"的身份
        # offset 默认 100000（round1），round2 等批次用 200000（第8参）
        offset = int(sys.argv[8]) if len(sys.argv) > 8 else 100000
        def slot_of(w):
            n = int(w.rsplit("_", 1)[-1])
            return (n - offset) % 35
        slots = sorted({slot_of(w) for w in workers})
        assert all(0 <= s < 35 for s in slots), f"slot 集合异常: {slots}"
        worker2user = {w: USER_ID_BASE + slot_of(w) for w in workers}
    else:
        worker2user = {w: USER_ID_BASE + i for i, w in enumerate(sorted(workers))}

    tasks_out = []
    mapping_tasks = {}
    mapping_annotations = {}
    ann_counter = ANN_ID_BASE

    for i, t in enumerate(src):
        task_id = TASK_ID_BASE + i
        inner_id = i + 1
        mapping_tasks[t["id"]] = task_id

        conds = sorted({an.get("condition", "manual") for an in t["annotations"]})
        if conds == ["manual"]:
            condition, form_version = "manual", "manual_scope_only_v1"
        elif conds == ["semi"]:
            condition, form_version = "semi", "semi_scope_only_v1"
        else:
            condition, form_version = "mixed", "mixed_manual_semi_v1"

        # task 时间：落在 project-98 同窗口
        t_created = rand_dt(WIN_START, WIN_END)
        t_updated = min(t_created + timedelta(seconds=rng.uniform(0, 86400 * 2)), WIN_END)

        annotations_out = []
        for an in t["annotations"]:
            ann_id = ann_counter
            ann_counter += 1
            mapping_annotations[an["id"]] = ann_id

            uid = worker2user[an["completed_by"]]

            # 标注时间：draft 先于 created，lead_time 为活跃时长
            a_created = rand_dt(t_created, t_updated)
            lead_time = clamp_lead_time(an.get("lead_time", 60.0))
            a_draft = a_created - timedelta(seconds=lead_time)
            a_updated = a_created + timedelta(seconds=rng.uniform(0, 2))

            result = [convert_result_item(it, None) for it in an["result"]]

            annotations_out.append({
                "id": ann_id,
                "completed_by": uid,
                "result": result,
                "was_cancelled": bool(an.get("was_cancelled", False)),
                "ground_truth": bool(an.get("ground_truth", False)),
                "created_at": fmt(a_created),
                "updated_at": fmt(a_updated),
                "draft_created_at": fmt(a_draft),
                "lead_time": lead_time,
                "prediction": {},
                "result_count": len(result),
                "unique_id": str(uuid.uuid4()),
                "import_id": None,
                "last_action": None,
                "bulk_created": False,
                "task": task_id,
                "project": PROJECT,
                "updated_by": uid,
                "parent_prediction": None,
                "parent_annotation": None,
                "last_created_by": None,
            })

        # 任务 updated_by 取该任务最后一条标注的标注人（模拟真实行为）
        task_updated_by = annotations_out[-1]["updated_by"] if annotations_out else 1

        tasks_out.append({
            "id": task_id,
            "annotations": annotations_out,
            "file_upload": FILE_UPLOAD,
            "drafts": [],
            "predictions": [],
            "data": {
                "image": t["data"]["image"],
                "vis_3d": VIS_3D,
                "base_task_id": t["data"]["image_id"],
                "title": t["data"]["image_id"] + ".jpg",
                "condition": condition,
                "dataset_group": DATASET_GROUP,
                "project_key": PROJECT_KEY,
                "annotation_form_version": form_version,
                "package_task_code": "%03d" % (i + 1),
                "project_display_name": PROJECT_DISPLAY_NAME,
            },
            "meta": {},
            "created_at": fmt(t_created),
            "updated_at": fmt(t_updated),
            "inner_id": inner_id,
            "total_annotations": len(annotations_out),
            "cancelled_annotations": 0,
            "total_predictions": 0,
            "comment_count": 0,
            "unresolved_comment_count": 0,
            "last_comment_updated_at": None,
            "project": PROJECT,
            "updated_by": task_updated_by,
            "comment_authors": [],
        })

    json.dump(tasks_out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)

    # 追溯映射
    mapping = {
        "workers": worker2user,
        "tasks": mapping_tasks,
        "annotations": mapping_annotations,
    }
    if SLOT_MODE:
        offset = int(sys.argv[8]) if len(sys.argv) > 8 else 100000
        slot_to_user = {
            (int(w.rsplit("_", 1)[-1]) - offset) % 35: u
            for w, u in sorted(worker2user.items())
        }
        mapping["slot_mode"] = True
        mapping["slot_offset"] = offset
        mapping["slot_to_user"] = slot_to_user
    json.dump(
        mapping,
        open(MAP_OUT, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )

    print("tasks:", len(tasks_out))
    print("annotations:", sum(len(t["annotations"]) for t in tasks_out))
    print("workers:", len(worker2user))
    print("written:", OUT)
    print("mapping:", MAP_OUT)


if __name__ == "__main__":
    main()
