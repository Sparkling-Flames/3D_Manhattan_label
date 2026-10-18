# 从这里开始：独立人员研究包

本ZIP是当前本地材料快照，不依赖GitHub最新代码；用户未更新GitHub，本次也未提交、推送或发布。先读`PRO_PROMPT.md`，再按下列入口使用。

## 最新方向

人员分类已恢复，使用全部现有合格质量图片；重点Q＋T＋难度，并继续从作答簇反向寻找人员规律。历史“暂停人员分类”“仅八图”只解释当时阶段，不覆盖最新任务。B8L2主线、D10敏感性；N1尚未并入默认实现，不是研究前置。

## 核心入口

1. 全量画像与当前发现：`research/workers/worker_difficulty_profiles_20261018/README.md`。质量1911份／136图，普通Manual1258份／103图；全量描述与原开发1048份分开。
2. 处理后的当前输入：`research/data/processed_input_review_20261018/manifest.json`及同目录全部entrypoints，含坐标、参考、身份、评论、环序和用途。历史原始export路径仅为溯源，本包不包含原始导出。
3. **扩展融合优先读根目录`CURRENT_POOLS.json`**：保留广图已准备池，以修订九池覆盖旧同pool_id记录。所有池内点坐标已与当前处理输入按声明环序逐一核对。池存在不代表主质量资格，要读layer、成员quality_usable、original_holdout及reference。难度以当前image_metadata.csv连接，不沿用池内历史难度字段。
4. 质量与参考：`research/quality/quality_b8l2_d10_20261017/`（quality_records/shared_records/reference_catalog/shared_bindings/source_pools）。B8L2/D10参数已附。其旧CROSS_MODULE_INPUTS中历史manifest路径是来源记录，当前输入用第2项，不需要调用旧prepare流程。
5. 广图已有组合：`research/workers/worker_v1_composition_20261017/`、`worker_v1_pro_integration_20261017/`，及`research/fusion/wall_consensus_v1_process_20261017/`；后者含原始请求、结果、逐池保存状态。R01424相关旧缓存不可当当前值，读取`research/fusion/worker_composition_fusion_20261018/`的修订结果。
6. 八图已有实验：`worker_fine_composition_20261018`、`worker_exchangeability_20261018`及对应fusion包；含准确成员、原反馈和失败。这些不是新研究的范围上限。
7. 分簇：`research/statistics/cluster_review_20261018/`，包含同距离完整链接/全局亲近度结果；从同一函数扩展到其它图，不重新删点或改参考。
8. Semi、scope：`research/workers/worker_v1_pro_integration_20261017/`的机会与原始响应表，及`worker_quality_scope_review_20261018/README.md`。未知不作错误、未改不自动盲信。

## 可执行核心

Python 3.11或以上，依赖见requirements.txt。从ZIP解压根目录运行：

```sh
python -m pytest tests/test_worker_difficulty_profiles_20261018.py tests/test_cluster_review_20261018.py tests/test_worker_annotation_similarity_20261018.py -q
python -m tools.thesis_main.analysis.worker_difficulty_profiles_20261018
python -m tools.thesis_main.analysis.build_cluster_review_20261018
```

第二、三条重算本包对应派生结果，不修改坐标、参考或资格。本包附上述核心及融合模块的递归Python导入依赖；不是整个仓库备份，历史脚本中未用到的旧资料路径可能不随包附带，不要盲目重跑每个历史main。

新组合从CURRENT_POOLS选择合格记录，调用`tools.thesis_main.analysis.consensus_delivery_20261008.fuse(records,gap=WORKING_GAP)`；原有`scope_quality_scoring_20261016.scoring_engine`及`quality_b8l2_d10_20261017.dual_scores`可复用。冻结测量引擎ZIP及工作模型代码已附。身份/参考/资格必须由调用方保持，不以可算分恢复主质量门。

运行`python smoke_core.py`可检查当前bundle、单图实际融合及冻结评分引擎自比。它不是全库重新验证。独立解压验证的真实结果见VALIDATION.json。

## 展示与图片

打开`research/statistics/research_explorer_v1_r2_20261017/index.html`。页面无需服务器，默认261张包内预览图；原图单独从既有Release下载，见ORIGINAL_IMAGES.md和IMAGE_INDEX.csv。本包未把预览重命名为原图，打包时仅调整展示photo链接，数值几何保持原字节。未打包完整工作台的统计索引，使用此独立入口。

PACKAGE_FILES.json为载荷路径与大小清单；BUILD_CHECKS.json记录处理坐标和图片覆盖核对。只交接研究所需材料，无模拟包、凭据、Git目录或运行环境。原评论与研究身份仍是内部研究材料，不因打包自动公开。
