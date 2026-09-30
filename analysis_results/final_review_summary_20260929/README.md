# 最终审核统计

[浏览分类及评语](index.html)。当前全部指定排序队列闭合；未逐份人工确认对象、5份配对不可用及三维表示限制继续独立记录。

## 统计汇总

```json
{
  "annotations": 3152,
  "images": 259,
  "confirmed_orders": 1295,
  "annotation_order_states": {
    "four_pairs_default_skip": 1308,
    "confirmed": 1265,
    "excluded": 218,
    "not_triggered": 312,
    "user_no_recall": 44,
    "pairing_deferred": 5
  },
  "cleaning": {
    "retained": 2923,
    "excluded_by_review": 85,
    "historical_not_accepted": 133,
    "retained_pending": 11
  },
  "geometry": {
    "surface_valid": 3000,
    "pairing_unavailable": 143,
    "representation_limited": 9
  },
  "retained_geometry": {
    "surface_valid": 2921,
    "pairing_unavailable": 5,
    "representation_limited": 8
  },
  "manual_gt_confirmed": 30,
  "batches": [
    {
      "batch": "after_pairing23",
      "objects": 23,
      "images": 18,
      "changes": {
        "unchanged": 10,
        "adjacency_changed": 13
      }
    },
    {
      "batch": "first_merged",
      "objects": 1160,
      "images": 121,
      "changes": {
        "unchanged": 1025,
        "adjacency_changed": 134,
        "equivalent": 1
      }
    },
    {
      "batch": "followup77",
      "objects": 77,
      "images": 24,
      "changes": {
        "adjacency_changed": 6,
        "unchanged": 71
      }
    },
    {
      "batch": "same_image35",
      "objects": 35,
      "images": 5,
      "changes": {
        "unchanged": 34,
        "adjacency_changed": 1
      }
    }
  ],
  "scene_images": {
    "oos": {
      "not_oos": 22,
      "not_recorded": 212,
      "confirmed": 24,
      "pending": 1
    },
    "doorway": {
      "none": 23,
      "difficult": 17,
      "not_recorded": 217,
      "annotatable": 2
    },
    "both": 2
  },
  "scope_detail": {
    "scope_explicit_tag": 24,
    "detail_explicit_tag": 15,
    "scope_existing_ledger": 79,
    "detail_existing_ledger": 46,
    "scope_comment_candidate": 107,
    "detail_comment_candidate": 75
  },
  "scope_collected_images": 118,
  "detail_collected_images": 86,
  "room_registry_groups": 260,
  "room_candidates": 259,
  "supported_room_candidates": 155,
  "original_room_classification": {
    "优先候选": 63,
    "不支持": 67,
    "待定": 58,
    "基础候选": 51,
    "对照候选": 21
  },
  "research_supported_rooms": 102,
  "research_images_with_room": 204,
  "unchanged_model_coordinates": 100,
  "user_comment_model_influence": 4,
  "order_queue_complete": true,
  "all_annotations_individually_confirmed": false,
  "formal_analysis_connected": false
}
```

## 同房、场景与差异口径

同房全库组、拆分候选组和259图覆盖使用不同分母。原始完整记录保留physical_same、主视觉空间一致性、标注范围一致性、难度相似性、决策、评论、候选拆分及暂缓原因。只在physical_same_supported的组内汇集，其他图片逐图单列。

OOS与门洞相互独立，可重叠；not_recorded不是正常。空间/细节收集包括历史排除评语和保留评语，不因现已排除而丢掉场景线索。explicit_tag是用户结构化标签；existing_ledger含旧语义归纳；comment_candidate是宽检索，含疑问/否定/历史意见，不自动认定差异。没有记录为未知，不能算阴性；同房其他视角不自动继承分类。

## 排序与共性

13份本批真实邻接改动、10份未改；环起点/方向等价独立。首轮为归并后的对象统计，不能加总审核者事件充当独立样本。逐对象表保留审核者；原首轮按本人/一正的独立分析见order_pattern_recall_20260929/顺序规律_summary.json。新特征比较沿用45度锐角、24px密集及1.5深度比，基于每批改前排列；几何不可计算单列。批次筛选不同，比例仅描述；同图历史改序召回参考order_model_same_image_20260929/summary.json，35份补查仅1份实际改邻接，不宣称总体规律或因果。

## 模型与GT

模型影响仅按comment明确的4份；100份原提交坐标未改与模型影响不是同义，可能重叠。保留完整证据表，预处理不改写原提交对比结论。原始与人工GT差异按既有1px口径，30份实质修订已排序确认，纯次序差异另列，不把原始GT当待审任务。

## 数据包与限制

同房汇集_Matterport.json包含原始GT、人工GT和人员对象，按最终确认环输出上点/下点交替数组。默认未审环仅标default_unreviewed；不可配对points为null；每项保留清洗、资格、表示状态和原来源。不修改原始导出，不开展正式共识或IoU重算。初始几何的默认环可有自交，不等于人员错误。

uNb9QFRL6hY-19/W010的第2、3对上端点y约261，下方端点约289，虽可配对但上点低于当前相机水平线，因此wrong_hemisphere，涉及它们的曲线缺失。现行模型下完整3D不可构造，不能靠排序修复，也不自动增加OOS裁决。

## 复现与验证

生成命令：`python -m tools.thesis_main.analysis.final_review_summary_20260929`。独立字段合同见field_contract.json。定向Python与浏览器验证包括3152份闭合、1295确认绑定、3441对象连接数组还原、分类不传播、评语去重、最新队列确认接收及地平线限制提示。截图检查后清理；未运行无关全仓测试或正式实验。首轮按审核者统计及历史补充已另存本目录，不能把审核事件数相加作为独立标注数。
