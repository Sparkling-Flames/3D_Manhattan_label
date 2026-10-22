# 云端质量研究运行依赖补齐
2026-10-13。审计基线 d443132a18f053ad913332947fee16379bbb317f。

## 查到的实际缺口
最新 quality_manual_expansion_20261013.engine() 以及引用它的整体准备/高度脚本，指向：
research/quality_parallel_local_20261012/source_package/quality_parameter_calibration_20261012/
此前该目录被本地 .gitignore 排除，远程目录不存在。已保存报告与评分函数，不等于 fresh clone 已具备几何执行依赖。

本次新增 8 个原字节文件：冻结几何/验证/高度/传统 IoU 模块、centered_height.py，以及含 922 条旧条件输入和相应几何的 calibration_records.json。来源为已经验证过的 quality_multispace_joint_calibration_20261013.zip 的 baseline 子目录；完整 ZIP SHA-256 与逐文件哈希见 MANIFEST.json。文件放回现有代码期待的路径，无需修改公式或参数。被 gitignore 匹配的路径一旦提交为 tracked 文件，正常 clone 仍会取得它们。

这是当前几何入口所需的最小依赖，不是旧 78 MB 全交付的完整恢复。旧包的全量 reproduce/intake 脚本可能仍要求其他历史证据；不要把最小目录当成完整旧包。需要全量历史重放时，使用原完整包与其清单。

## 先验证，再研究
在仓库根目录：
python -m pip install numpy scipy shapely
python research/quality_execution_support_20261013/verify_support.py

该检查无需原图：逐个核验 8 文件哈希，并独立从六份冻结几何复算 IoU、球面底边距离、方向残差、整体/局部高度和传统 3D IoU。结果见 VERIFICATION.json，最大差小于 1e-15。
此结果不等于全 3152 当前 loader、全部人评和门洞阶段已独立重放。开始新研究时还应执行现有准备测试，核对最新资料实际读入，不能从路径存在直接推断全部执行成功。

## 本轮研究的数据入口
- 第一阶段：research/quality_calibration_preparation_20261013/BASELINE.json（574 普通 + 9 严重，分层使用）、EVIDENCE.json、PROTOCOL.json。
- 控制：同目录 BOTTOM_CONTROLS.json；quality_height_calibration_ready_20261013/CONTROLS.json。
- 全量来源、参考与阶段：quality_data_admission_audit_20261013、quality_scope_resolution_20261013/STAGE_LEDGER.json、quality_data_closeout_20261013。
- 当前完整坐标/有效更新：使用 tools.thesis_main.data_prep.consolidate_research_input.load_current_bundle()；旧 922 冻结几何不能代替当前全量 loader。
- 已归档的 35 图、429 份多空间材料：quality_pro_joint_archive_20261013/source/routing/inputs/prepared_input.json。
- 第二阶段门洞清单及其来源、参考、原留出限制来自当前 STAGE_LEDGER，不把全部 217 条阶段记录直接当作合资格拟合样本。
- 原图不在本次补齐中。继续使用 Library 的三个 pro_quality_original_images_01_of_03.zip 至 03_of_03.zip；pro_quality_expanded_data_20261007.zip 是扩展数据包，并非第四个纯原图包。
- 若需要旧完整联合研究包：Library 的 quality_multispace_joint_calibration_20261013.zip；其 381 个成员不是本轮新研究交付。

## 研究与验证边界
先正常图片调大致参数，再加入有可靠参考的门洞交界细调，并回查正常图片；OOS 不调参。保持既有 GT、点对与环序、人员资格、原留出和多空间参考选择规则。新结果独立保存。
本次只补运行依赖与复现说明，不调参、不修改算法、不新增参考、不重新发布人评。
如果工具返回的是错误、空内容或不可读的仓库页面，应立即区分“工具读取失败”与“资料缺失”，列出具体路径和报错，不用历史结果冒充当前研究完成。
