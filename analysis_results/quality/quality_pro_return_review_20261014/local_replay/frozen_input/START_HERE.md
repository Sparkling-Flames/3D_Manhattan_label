# 质量研究交接包：回执与修订已齐

2026-10-14。当前参数`hill_global08`保持不变，数学上等于旧`baseline_quad08`。本包补证据与可执行材料，没有新一轮调参，未修改正式算法、GT、资格或融合，也未自动交给Pro。

## 先做什么

1. 先读CURRENT_STATUS.md与human_review/REVIEW_FINDINGS.md，再读原回执及amendment_01。三例已审核，后两例有修订；不要求用户再审三例。REVIEW.html仅作已有材料备查。
2. Pro读 **PRO_TASK.md**，再读 **SUPPLEMENT.md**、`preparation/EVIDENCE.json`及`stage/README.md`。`notes/`是历史口径与原话来源；其仓库相对路径只作出处，不是启动依赖。
3. 在任意解包目录运行：

```text
python -B run.py
```

Python 3.10及以上，需已有numpy、scipy、shapely。若环境缺库，可按其安装政策使用`python -m pip install -r requirements.txt`；程序本身不联网、不clone、不读取原机器目录。实测环境版本见`runtime_versions.json`。不要求Pro联网取GitHub来补输入。

启动打印并保存`startup_result.json`：574普通（207显式普通/367既有条件）、9严重、217门洞（125完整/92held）；583份既有metrics到工作分；一份真实R03274及两个底点控制从points重建；七份菱形从构造几何重建，含分项、Q、同参考现用3D IoU。启动成功不是效度验证或校准完成。

本包不包含完整原仓库。`run.py`、`engine/`、`data/`已经包含启动所需最小冻结代码和输入；全部907个相关对象的坐标、配对/环序来源、参考身份及几何状态保留，其中5个门洞对象没有可用配对，未生成假几何。21张原图与16组审查图覆盖本轮针对性视觉核验，**不是574份全部原图**。若Pro需要新的真实视觉证据，先列出缺失图片/作答，而不是猜测照片语义。

## 可视材料

REVIEW.html沿用旧`review36-view.js`，含照片/端点局部、共同尺度俯视、白模/原图纹理/线框、同步旋转、缩放/平移、室内视角、相机位置标记。显示的都是固定处理后几何，无自动拟合或修点。网页本地双击即可读取内嵌数据，无远程库/CDN；纹理是原图的JPEG显示副本，原PNG另存photos/。静态备份在review_assets/；金色相机位于几何原点，底面为y=-1。

算法名与分数未进入人审页；真实身份及参考版本在回执bindings中保持。页面保留原默认3例，当前均已有回执，全部16组仅作备查。为了不诱导答案，新问题不展示旧评论，旧原话完整保存在分析数据。不能因为是A或B就推断预设胜者。

浏览器自动化工具的file协议限制阻止了本轮交互页面实机查看；已通过JS语法、材料绑定、分数隐藏与静态图检查。不得把交互视觉验收冒称已完成。用户如发现纹理/相机标记未显示，应保留信息并修页面，不能用静态图假装交互通过。

## 数据合同

- `data/cohorts.json`：574普通、9单列严重、217门洞、历史旁证与既有资格/曝光。仅数值可算不等于参考语义认证；held不补零。
- `data/objects.json`：907个对象、固定points/原始坐标/配对环序证据/参考几何，来自当前统一loader截取。元数据中的历史路径仅供追溯；运行不读取那些路径。
- `data/supplement.json`：17图范围、顶界证据、原话与逐份绑定，普通改分清单、125门洞分母诊断。最大分母项不含分子IoU，不是因果归因。
- `data/held_recheck.json`：92份已有记录复核；没有证据足以新增逐份GT版本绑定或解除资格。
- `data/control_geometries.json`：全部151控制的作答/参考几何及来源；`stage/COARSE.json`保留同名metrics与五候选结果。
- `preparation/BOTTOM_CONTROLS.json`：34份底点控制含原points。`HEIGHT_CONTROLS.json`：110份高度控制（48旧、62此前构造），复用存储metrics；本轮不冒称全部重建。七菱形在粗调阶段新建；启动单独复算七份。
- `preparation/EVIDENCE.json`：13问题组原话/解释/绑定，11弱等级与5项原约束；24派生比较不是24独立评审。
- `stage/COARSE.json.current_iou3d`：583份固定同参考旧3D IoU；门洞完整行metrics内也有同参考IoU。是角点平均高度定义，不是非平顶完整多面体真IoU。
- `data/human_review_manifest.json`：原始发布时3待审/13备查，历史`awaiting_receipt`不代表当前；有效状态见human_review/effective_status.json。新回执必须单独原样追加，不覆盖历史意见或把空选项当认可。

历史运行记录中保存的旧路径或研究状态不覆盖本文件的当前状态。当前研究合同仍为`consensus_research_20260923_v1`。


## 评分版本与有效审核状态

三例回执已收到，Q02/Q03有后续修订；完整质量排序未建立不等于尚未审核，不要求重复审核。`human_review/effective_status.json`是当前审核状态，原manifest的`awaiting_receipt`仅为历史状态。启动输出`review_status=received_with_amendments`，`historical_review_status=awaiting_receipt`；`read_report`指向CURRENT_STATUS.md，`review_findings`指向修订解释。

`data/cohorts.json`普通/严重行的`components`来自旧带方向尾项基线，门洞行的`candidate_components.center`才是新工作版。不要混用这些保存分数。普通/严重统一当前结果读`stage/COARSE.json.records[*].hill_global08`；各层统一复算使用`stage/WORKING_FINAL.json`的config与冻结score引擎。保留历史分数，不覆盖。

现在足以启动Pro普通粗调，不需等待92份门洞held解锁。Q01既有小房间候选核查留作门洞阶段局部待办；未定参考时仅作范围条件诊断，不逼迫调参。Q02/Q03原overall选项不是完整排序约束，分项数据已齐，可由Pro归因。普通粗调→冻结→门洞细调→普通回归；OOS不调参。
