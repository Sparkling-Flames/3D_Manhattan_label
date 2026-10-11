# 30份独立标注审核：最终渲染交付（已主审验收）

主审已批准冻结30行清单并实际查看24张原图；现已生成最终用户包及独立私有映射。该批准不表示每段墙/顶面或参考语义已被严格认证。用户仍可选参考/目标有疑问、无法判断并说明原因。主审已核对30个唯一作答、留出隔离、照片哈希，查看全部30份叠线/BEV/3D，并核验空白回执。详见[主审报告](owner_review/README.md)和[交付检查](owner_review/delivery_validation.json)。人类质量判断仍为空，尚未选定最终阈值。

- [用户ZIP：30独立作答＋可选成对题](artifacts/quality_review30_user_20261011.zip)
- [评分与来源映射ZIP：建议完成盲审后再查看](artifacts/quality_review30_private_mapping_20261011.zip)
- [最终交付说明](research/FINAL_DELIVERY.md)
- [复现与浏览器测试命令](research/RUN_COMMANDS.md)
- [精确字节数与SHA256](results/final_delivery_summary.json)
- [实际浏览器14组测试](results/review30_browser_tests.json)
- [固定种子展示顺序](results/display_order.json)
- [六例渲染抽查图](results/render_small_preview_private.jpg)
- [初始30行清单及边界缺口](research/COVERAGE_AND_GAPS.md)
- [私有选择CSV](results/selection_private.csv)
- [完整来源/资格/五原方案](results/selection_private.json)
- [24原照片ZIP](results/selected_original_photos_private.zip)

24质量＋6空间，30个不同record_id及object_id。120张主视图，成对题P01复用T23/T24的8图，不新增作答。固定种子2026101130打乱展示；case_id和原选择映射不改。同图几何视图共享坐标范围，所有空间B仅底面、top_pending，不造完整B GT/Q。用户页隐藏Q、公式、身份和选样理由；默认回答全空。

Q95/85/50双侧全池真实最近邻仍全部覆盖。D20/F8上侧、受控F6上侧及补充Q90/60和Q75上侧紧邻缺口保留。F7.640835是混杂诊断。质量开发池907/83图，冻结282留出交集0。阈值导向30份不能估计总体严重比例，不能调66组后宣称泛化成功。

旧8例、原数据、GT、资格、分数均未改。选样阶段清单和报告保留原历史状态文本；当前状态以FINAL_DELIVERY.md及本README为准。原ARTIFACT_MANIFEST另存为SELECTION_STAGE_ARTIFACT_MANIFEST，不删除选样证据。

本轮源main基线9c1d91173bf8ec50de4983daaff325b339965e04；云端完成后由主线程统一验收并发布。测试使用云端预装Chromium、本地回环HTTP，因管理策略阻止file://，不声称实际验证了Windows双击路径。独立原Pro/官方IoU与许可证仍在既有归档中，本目录是新增适配。

使用：解压用户 ZIP，打开 user/index.html；填写后下载 JSON 回执返回。新30份与旧8例格式独立，旧回执不能直接导入。浏览器草稿不替代下载保存。
