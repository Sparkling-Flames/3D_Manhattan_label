# 排序候选整理

既有清洗问题已处理，不等于所有作答逐份人工审查；本次只整理候选，不接入全量排序。

人员使用最新有效点与清洗裁决；明确排除85份和历史未纳入133份不召回。GT原始/人工修订按源文件区分、相同源文件别名去重，并回读源坐标核验。没有将模型预测作为GT。

复用现有几何初筛：相机高度1的地面投影非邻边相交、相邻角度均小于45度、周期24像素内至少三对。四对不因弱线索进入排序；失败另外记录。不按IoU筛选，不修改点对或顺序。人工修订GT的唯一水平匹配仅为诊断，未确认连接次序。

GT原始环保留文件原始点对顺序，不自动按x排序；GT评论未指明版本时并列核验两版，不冒称两版都错。GT不继承某个人的排除，但服从图片暂停与OOS/门洞分层。

待排序候选.csv只列priority/weak；配对与表示待核.csv单列配对、四对异常、投影/来源问题；全量排序初筛.csv保留全部状态和证据。63份人员候选与27份GT候选涉及45张图片。10例已确认需要排序，其他仍是初筛提示，不能当已确认错误。

```json
{
  "schema": "order_candidate_inventory_v1",
  "formal_data_connected": false,
  "annotation_count": 3152,
  "images": 259,
  "gt_sources": 287,
  "annotation_queues": {
    "normal": 2332,
    "later": 515,
    "excluded": 218,
    "pairing": 14,
    "weak": 51,
    "priority": 12,
    "hold": 9,
    "geometry": 1
  },
  "gt_queues": {
    "normal": 208,
    "later": 44,
    "weak": 18,
    "priority": 9,
    "geometry": 5,
    "hold": 3
  },
  "candidate_objects": 90,
  "candidate_images": 45,
  "accepted_individually_reviewed": 1540,
  "accepted_without_individual_record": 1479,
  "completion": "既有清洗问题已处理，不等于所有作答逐份人工审查；本次只整理候选，不接入全量排序。"
}
```
