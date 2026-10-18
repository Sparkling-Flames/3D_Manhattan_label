# 多人单人替换页：交付与字段说明

入口[personnel_exchangeability.html](personnel_exchangeability.html)，直接双击离线打开。原[4人页](personnel_composition.html)保留结果，并增加6条已绑定人工反馈；两页互相链接。

## 数据与展示

当前3840请求、3839个不同团队、2560单人替换对、8图。默认比较全部人数时，V只取四个k的同类／跨类两臂都有效的固定背景链；质量另取全部可评分的链。选单个k时使用该k共同块。先图内平均再图间等权，不将交换对当作独立图片。每种分类的V固定链为76／77／104条，Q为62／61／83条；来源是人员包的`fixed_chain_curve_summary.csv`。

可筛绝对Q／相对Q／相对Q×速度、原人员类别（包括高Q快）、场景、图片、人数；切换B8L2/D10只改终点评价。散点比较原答范围距离与融合变化。两侧同时显示替换个人作答、整队融合和固定参考，支持ERP／BEV／3D及独立图层显隐。相同节点数、数值近零V、严格几何相同分开；不把`V≤1e-12`冒称严格坐标相同。

另一背景复核面板只用背景0定义发现条件，背景1给出实际变化。两个背景共享人员，不称独立验证；筛选时不会保留与当前条件不符的汇总。16人例子按结果后较大V挑选，仅供机制查看，不参与分类或正式抽组。失败、用途限制及缺失质量不填0。

## 构建与字段

```powershell
python -m tools.thesis_main.analysis.build_worker_exchangeability_view_20261018
python -m tools.thesis_main.analysis.build_worker_composition_view_20261018
```

新页面读取本地派生`exchangeability-data.js`，schema=`worker_exchangeability_display_20261018_v1`。`teams/pools`复用前轮精确成员与保存几何绑定；`pairs`与冻结设计的全部comparison_id严格一致，每对同图、同人数且恰好替换一人，方向不反转。`profiles/support/by_k/fixed_curves/transfers`直接来自[人员包](../../workers/worker_exchangeability_20261018/FIELD_CONTRACT.json)；`feedback`保存用户原话和旧六例的准确左右团队。显示脚本不重新聚类、拟合、评分或融合。

## 验证

相关31项测试通过（输入显示绑定、单人替换、分类、既有融合、原答相似性）：

```powershell
python -m pytest tests/test_worker_exchangeability_20261018.py tests/test_worker_fine_composition_20261018.py tests/test_worker_composition_fusion_20261018.py tests/test_wall_consensus_v1_process_20261017.py tests/test_worker_annotation_similarity_20261018.py tests/test_worker_composition_view_20261018.py tests/test_worker_exchangeability_view_20261018.py -q
python -m tools.thesis_main.analysis.worker_annotation_similarity_20261018 --check
```

`exchangeability-ui.test.cjs`在本地无头Edge检查：3分类×4人数、8张本地原图实际加载、高快类筛选、门洞筛选、固定链均值与CSV一致、ERP/BEV/3D、个人图层显隐、导出、窄视口及旧6例人工反馈绑定。无页面JS错误，无HTTP(S)请求。视觉截图查看后清理；不依托本地HTTP服务器。

独立审查核对1280共同锚点块、320嵌套链、72行固定链汇总、240条高快方向、1280背景匹配和60行复核汇总，以及全部2560原答距离／簇联接。完整状态逆序重算、主资格和参考核验见[融合CHECKS](../../fusion/worker_exchangeability_fusion_20261018/CHECKS.json)。资料目录和相对路径检查见`EXCHANGEABILITY_CHECKS_20261018.json`。

## 边界与后续

修改工具、测试、页面、研究解释和目录；未改原始导出、分数参数、参考采用、人员资格、Label Studio运营或旧结果。地图、统一研究模型、收尾细则、当前入口与catalog同步新包。本轮不读取模拟数据，N1未接入。

未跑无关全库测试，未新增人工墙线认证或未来人员验证。下一步用同一组交换对比较不同标签的解释力，再在发现建筑以外检验新的可替换类别；当前本图作答簇不能直接升级为跨图人员类型。16人无完整团队时间支持，不据历史快标签宣称实测成本最优。
