# 连续短路径与局部结构对应：有限原型 / 2026-10-06

## 先说明资料边界

本轮用户提到的“最新本地工作树附件”没有进入当前会话或运行容器。没有读到其 README，也没有运行该附件的基线。当前包是**使用此前实际收到的四图完整输入开展的独立、部分研究**，不能作为新附件验收。

未复算：137图/1520份及29/10/5不足四对清点；e9z当前八人窗口；五张12°仍不足四对图；新附件的即时邻点基线；新原图。本包不假定 GitHub main 与本地工作树一致，也没有通过仓库历史 e9z 图猜测当前案例。

实际输入：2t7-06 / 7y3s-04 / rPc-06 / uNb-67，完整名单3/24/24/15，共66份、24个不同worker ID、400个原角点对。来源是已挂载的 point_correspondence_20261006_delivery.zip；四份原参考从此前 layout_reliability_20261005_delivery.zip 单独恢复。源点、共享x、源环、资格、票权未改；相同坐标的不同人员不去重。

## 一条复算命令

在包根、已有 NumPy / SciPy / Shapely / Numba / pytest 的 Python 环境执行：

```bash
python reproduce.py --out NEW_results
```

NEW_results 必须不存在。Numba仅加速，缺少时可运行纯Python后备，但没有对该后备完成全量时长基准。为减少多线程开销可先设置 OPENBLAS_NUM_THREADS=1 和 OMP_NUM_THREADS=1。依赖范围及本次实际环境见 requirements.txt / environment.json。

测试：`python -m pytest tests -q`。本轮22项新增测试通过；一次完整重放200个数值工件逐字节相同。不是全仓库测试，也不是最新本地基线验收。

## 方法与复算次序

1. `src/run.py`：按固定5/9/12°、pair/bottom/top，重算旧距离MV与严格短路径门。保留全部实际达票身份，包括0/1/2/3对，不补矩形。
2. `src/analysis.py`：严格门实跑后追加的三状态对照，以及明确使用旧开发人工关系的辅助对照。人工解释不传给自动构造。
3. `src/controls.py`：共线细分、短凸起、窄凸起、上下目标分离、接缝近邻与候选域反例。
4. `src/patches.py`：所有两对/三对局部匹配与双向替换候选；保留源上下曲线、内部观察与域外状态。候选不计票。
5. `src/evaluate.py`：构造工件已保存后才读取 evaluation；所有预设候选分别评价，不按GT挑选。
6. `src/summarize.py`：汇总、旧5°分区/中心比对、后中心化诊断及unb上下目标账本。

原严格政策见 config.json。amendment_01 / 02明确记录开发中追加的对照，不冒称所有对照事前注册；也没有追改源数据或先前严格门结果。

## 快速查看

- REPORT_ZH.html：离线中文报告。
- EVIDENCE_VIEWER_ZH.html：离线数值叠加。默认不读GT；可以在浏览器本地载入自己的全景PNG，只用于叠加，不上传。
- results/summary/all_MV_comparisons.csv：全部36个距离/阈值/图片状态。
- results/*/*_path_evidence.jsonl.gz：全部尝试的短路径、锚点、域外、通过/拒绝/数值未决。
- results/patches/*_local_matches.json：两对/三对路径，含不同原身份组的竞争锚点假设。
- results/patches/*_candidate_rings.jsonl.gz：所有生成的条件候选、原路径及中心影响。
- results/analysis/*_human_assisted.json：单独的人工关系辅助结果。
- FIELD_CONTRACT.md：支持、候选、连接、失败、单位的具体含义。

取出一个候选：

```bash
python extract_candidate.py --results results --id uNb9QFRL6hY-67_5_L0_R02929 --out candidate.json
```

不是新的正式合同或生产算法。真实细节真假仍需局部人审；未知项不得从几何门或高IoU补为确定。
