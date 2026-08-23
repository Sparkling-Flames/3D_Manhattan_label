# HoHoNet 模型布局初始化代理全量审计（旧版 post-hoc v1 阈值保留版）

## 结论口径

本文件完整保留旧报告的二元判定体系，供历史结果复核和纵向比较；它不是唯一主分析。角点对数量门保持不变，`.90/.80/.05`、图宽 1% 角点门和较宽松的 `.75/.65/2%` 仍按旧版原样计算，但后几组数值均属分析者定义的 post-hoc operational thresholds，不能解释为文献统一标准或独立校准的最佳阈值。另见同目录的 `MODEL_INITIALIZATION_AUDIT_TOPOLOGY_PRIMARY.md`，其中只把角点对数量一致作为硬二元门，其余误差按连续量和多阈值敏感性报告。

本报告覆盖 Test 458 张与 Validation 190 张，共 648 张。Test 严格采用混合 GT：从 `export_label/groudTruth.json` 顺序无关识别出用户确认的 30 张实质修订并采用人工 GT，其余 428 张采用 `data/mp3d_layout/test/label_cor` 官方 GT；Validation 190 张全部采用 `data/mp3d_layout/valid/label_cor` 官方 GT。全程未使用 `test_no_occ` 或 `valid_no_occ`。30 张清单另见 `docs/thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md`。

当前产物是 HoHoNet ep300 的**最终布局输出**，仓库没有保存 raw corner probability/优化前峰值，因此本报告严谨称为 `final_layout_as_initialization_proxy`，不是网络内部原始初始化。

二元判定不由 IoU 单独决定：

1. `pair_structure_correct`：模型点对编码可解析，且模型与 GT 角点对数量相同。点对编码校验只检查偶数点、相邻 ceiling/floor 的 x 一致和上下关系；**没有**声称已经验证整圈自交或完整 Manhattan 正交约束。
2. `corner_localization_pass`：采用 ZInD/CVPR 2021 的图宽 1% 距离阈值（10.24 px），配合本项目确定性的 seam-aware greedy exclusive matching；所有 ceiling/floor 角点均匹配才通过。它是 point-level 匹配，不强制同一 wall pair 联合匹配。ZInD 只给出阈值与 P/R/F1，没有规定 greedy 算法，因此这里明确称为 ZInD-inspired 项目实现；在本次 648 张上用最大基数匹配复核，TP 未出现差异。
3. `geometry_acceptable`：本项目 v1 联合门，要求 top-down 2D IoU ≥ 0.90、LayoutNetv2-style derived 3D IoU ≥ 0.80、layout mask difference ≤ 0.05。文献没有统一的逐图二元阈值；`.90/.80/.05` 是本次审计在初次全量输出语义复核后由分析者定义的 post-hoc operational threshold，未预注册、未用独立验证集校准，不应冒充文献标准或无偏 benchmark cutoff。它们从本报告起按 v1 固定，供后续复现或前瞻应用。
4. `initialization_correct = pair_structure_correct AND corner_localization_pass AND geometry_acceptable`。任何角点对数量变化仍先判 `wrong_initialization_topology`，高 IoU 不得覆盖。
5. `initialization_acceptable` 是“可作为人工编辑起点”的较宽松辅助口径：角点对数量一致、top-down 2D IoU ≥ 0.75、derived 3D IoU ≥ 0.65、归一化角点均值误差 ≤ 2%。它同样是分析者定义、非文献统一阈值；严格失败不自动等于不可用。
6. `nearly_no_difference` 是更严格的展示层：初始化严格正确、最大循环对齐角点误差不超过 2.56 px、布局 mask 差异不超过 0.01。

本数据中有 5 张拓扑错误图片的 top-down 2D IoU 仍 ≥ 0.95，35 张拓扑错误图片的 layout mask IoU 仍 ≥ 0.95，直接证明面积 IoU 不能替代拓扑门。

`layout_depth_rmse_proxy` 与 `layout_depth_delta1_proxy` 比较的是由模型角点和 GT 角点各自合成的 layout depth，不是真实 Matterport depth map；仓库当前没有为这 648 张绑定真实 depth GT，因此不得把这两列解释成 LayoutNetv2 官方 depth RMSE/δ1。

## 汇总

| split | 总数 | 拓扑一致 | 可用初始化 | 严格正确 | mask diff≥.10 | 几乎无差异 |
|---|---:|---:|---:|---:|---:|---:|
| test | 458 | 287 | 238 | 95 | 142 | 2 |
| validation | 190 | 163 | 156 | 148 | 10 | 27 |
| all | 648 | 450 | 394 | 243 | 152 | 29 |

这里的“严格正确”应完整表述为**事后定义的严格审计通过**：它是三道门的合取，不是 HoHoNet benchmark 的“成功率”。“可用初始化”也是辅助运营口径；两者都不得与连续 IoU 均值混写成同一种百分比。

## 与 HoHoNet 官方连续指标对照

| 口径 | N | 2D IoU(%) | 3D IoU(%) | layout-depth RMSE | delta1 |
|---|---:|---:|---:|---:|---:|
| Test 官方原始 GT（benchmark 对照） | 458 | 81.97 | 79.52 | 0.22 | 0.94 |
| Test 混合 GT（30人工+428官方） | 458 | 82.12 | 79.68 | 0.22 | 0.94 |
| Validation 官方原始 GT | 190 | 92.58 | 91.64 | 0.09 | 0.98 |

Test 官方原始 GT 的 2D/3D IoU 已与仓库 `eval_layout.py` 对齐；v2 曾在计算前按 x 重排角点，破坏了全景布局的原始环序，现已改为保留 consecutive ceiling/floor pair 的原始 cyclic order。Test 的 81.97% 是 458 个连续 2D IoU 的均值，不是“458 张中 81.97% 严格成功”。

| split | GT角点对 | N | 2D IoU(%) | 3D IoU(%) |
|---|---:|---:|---:|---:|
| Test 官方 | 4 | 262 | 84.76 | 82.15 |
| Test 官方 | 6 | 84 | 84.80 | 82.15 |
| Test 官方 | 8 | 63 | 74.38 | 72.46 |
| Test 官方 | 10+ | 49 | 71.89 | 70.00 |
| Validation | 4 | 108 | 93.74 | 92.72 |
| Validation | 6 | 46 | 94.28 | 93.33 |
| Validation | 8 | 21 | 90.34 | 89.45 |
| Validation | 10+ | 15 | 82.18 | 81.73 |

Validation 相对 Test 的优势在 4、6、8、10+ 每个复杂度层都存在，因此不是仅由角点数量构成造成。两个 split 的建筑 ID 完全不重叠；Validation 是开发/调参集，Test 才是最终泛化集，当前差距应解释为 split 难度与开发集选择偏差，而不是把 Validation 当作对 Test 成功率的先验保证。

## Test GT 修订前后敏感性

| Test GT 口径 | 拓扑错误 | 定位错误 | 几何错误 | 可用初始化 | 严格正确（含 nearly） | nearly |
|---|---:|---:|---:|---:|---:|---:|
| 全部官方 GT（旧敏感性口径） | 168 | 151 | 46 | 233 | 93 | 1 |
| 30张人工 + 428张官方（当前主口径） | 171 | 145 | 47 | 238 | 95 | 2 |

30 张人工 GT 中，`initialization_class` 相对官方敏感性口径改变 16 张，拓扑一致状态改变 13 张。混合 GT 把 Test 严格正确从 93 张调整为 95 张、可用初始化从 233 张调整为 238 张。

## 为什么修订后仍有较多严格失败

- 其余 428 张完全沿用官方 GT，其中仍有 151 张模型/GT 角点对数量不同；这部分与 30 张人工 GT 无关。
- 30 张人工修订在全官方敏感性口径下有 17 张拓扑不一致；换成人工 GT 后为 20 张，其中修正 5 张、同时新增 8 张，净变化为 Test `168 → 171`。
- Test 中模型角点对多于 GT 的有 86 张、少于 GT 的有 85 张，方向基本对称，不像单纯误用 no-occ 所造成的单向删角。
- 独立复核确认：458 个模型 TXT 与 `output/layout_json` 逐点一致，均为 ep300；Label Studio import proposal 与这些输出的图片 ID/坐标绑定无误；模型与 GT 均在 1024×512 坐标系。未发现目录、尺度或图片错绑制造这些拓扑错误。v2 的**指标实现**确有环序重排错误，已在 v3 修复；它影响连续 IoU 与少量阈值边界分类，但不制造 model/GT 角点对数量差。
- 当前“严格失败”规则故意很严：任何多/少一个墙角对都直接失败。Test 的严格正确为 95/458，但较宽松的可用初始化为 238/458；两者回答的问题不同。

全量类别计数：{'correct_but_visible_difference': 214, 'large_difference_geometry': 49, 'large_difference_localization': 158, 'large_difference_topology': 198, 'nearly_no_difference': 29}

- Test：{'correct_but_visible_difference': 93, 'large_difference_geometry': 47, 'large_difference_localization': 145, 'large_difference_topology': 171, 'nearly_no_difference': 2}
- Validation：{'correct_but_visible_difference': 121, 'large_difference_geometry': 2, 'large_difference_localization': 13, 'large_difference_topology': 27, 'nearly_no_difference': 27}

## 差异大代表图：拓扑错误

| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |
|---|---|---|---:|---:|---:|---:|
| test | `q9vSo1VnCiC_a6560bae311a403a9bfe94e4c1c645f4` | large_difference_topology | 4/14 | 0.11111111 | 0.2481997 | 0.67198518 |
| test | `q9vSo1VnCiC_a84d84665ef94d0c86f38bc2250bab55` | large_difference_topology | 8/18 | 0.23076923 | 0.15553427 | 0.82072148 |
| test | `UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc` | large_difference_topology | 6/16 | 0.09090909 | 0.15452282 | 0.35380593 |
| test | `X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9` | large_difference_topology | 12/4 | 0.375 | 0.1105654 | 0.77658052 |
| test | `e9zR4mvMWw7_18653fa3d6ba4f82889237201ee07d11` | large_difference_topology | 4/12 | 0.375 | 0.07396313 | 0.49046656 |
| test | `q9vSo1VnCiC_a424533651804a38a55b1252daccc81e` | large_difference_topology | 4/12 | 0.375 | 0.07331887 | 0.78269574 |
| test | `q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3` | large_difference_topology | 4/12 | 0.4375 | 0.05362129 | 0.81518489 |
| validation | `pRbA3pwrgk9_03de6e2562bb4f56a88db3ceb681af78` | large_difference_topology | 4/10 | 0.07142857 | 0.29716657 | 0.13341824 |
| test | `uNb9QFRL6hY_a372582c11864f31a9dd174e4a0ae6ad` | large_difference_topology | 14/8 | 0.36363636 | 0.23222693 | 0.88134458 |
| test | `wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6` | large_difference_topology | 14/8 | 0.27272727 | 0.22884028 | 0.8533556 |

## 差异大代表图：角点定位错误

| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |
|---|---|---|---:|---:|---:|---:|
| test | `B6ByNegPMKs_f701cece31304e16a3faa7f225bfdaa8` | large_difference_localization | 4/4 | 0.0 | 0.35132937 | 0.56066629 |
| validation | `jh4fc5c5qoQ_755d110c2ed84d76be11ad56ae00b53f` | large_difference_localization | 4/4 | 0.0 | 0.24818421 | 0.31128046 |
| test | `wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c` | large_difference_localization | 4/4 | 0.0 | 0.19463693 | 0.23094433 |
| test | `UwV83HsGsw3_6faf5c6575694e52882985ae8538f498` | large_difference_localization | 4/4 | 0.0 | 0.19278537 | 0.7306247 |
| validation | `zsNo4HB9uLZ_4c0aab63a4434cf4878e6f5b3ce9a70b` | large_difference_localization | 4/4 | 0.0 | 0.11272255 | 0.5715299 |
| test | `B6ByNegPMKs_5b3d1c9fefb64512b0c9750a00feece4` | large_difference_localization | 4/4 | 0.0 | 0.10711062 | 0.75839132 |
| test | `uNb9QFRL6hY_68efbeec805f437bb3f3421f93fa4f56` | large_difference_localization | 4/4 | 0.0 | 0.05796554 | 0.76648805 |
| test | `B6ByNegPMKs_4e537870fc094609a7eda53d1e313fa8` | large_difference_localization | 4/4 | 0.125 | 0.21272011 | 0.61115262 |
| test | `wc2JMjhGNzB_7d90b6268a79425cb15a26ef91d68c96` | large_difference_localization | 4/4 | 0.125 | 0.08778729 | 0.80137865 |
| test | `wc2JMjhGNzB_1d1b27d1b8db40f99e2fa3af6e237ce9` | large_difference_localization | 4/4 | 0.125 | 0.06709954 | 0.69638072 |

## 差异大代表图：角点层通过但几何门失败

| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |
|---|---|---|---:|---:|---:|---:|
| test | `B6ByNegPMKs_e52609aae11f42a79f6cf50360180fd5` | large_difference_geometry | 4/4 | 1.0 | 0.15015229 | 0.7606089 |
| test | `B6ByNegPMKs_dd1319e5f88a4dd88ccceee489e790cd` | large_difference_geometry | 4/4 | 1.0 | 0.11555656 | 0.88058836 |
| test | `B6ByNegPMKs_5b5bd1eac4e6462d8c6677b90a4cf9a9` | large_difference_geometry | 4/4 | 1.0 | 0.10141063 | 0.7729039 |
| test | `B6ByNegPMKs_2a1bc1a10d7b45ad902e09cd71767fd9` | large_difference_geometry | 4/4 | 1.0 | 0.09957878 | 0.86176763 |
| test | `B6ByNegPMKs_8c414a8052c844b4bcd5dc3fadde7f8c` | large_difference_geometry | 4/4 | 1.0 | 0.0803562 | 0.81140131 |
| test | `B6ByNegPMKs_e5567bd5fa2d4fde8a6b9f15e3274a7e` | large_difference_geometry | 4/4 | 1.0 | 0.06752422 | 0.81216444 |
| test | `X7HyMhZNoso_2bb4931911e4412cb51f6437a82c5b6c` | large_difference_geometry | 4/4 | 1.0 | 0.06651198 | 0.87871619 |
| test | `uNb9QFRL6hY_23ed105b1f0f48bbb6ec025df9d313e7` | large_difference_geometry | 4/4 | 1.0 | 0.06647207 | 0.83272335 |
| test | `B6ByNegPMKs_cfb2c926a80a4fde93b0d58d49af6549` | large_difference_geometry | 4/4 | 1.0 | 0.06239835 | 0.92226225 |
| test | `Z6MFQCViBuw_543e6efcc1e24215b18c4060255a9719` | large_difference_geometry | 4/4 | 1.0 | 0.06174131 | 0.89299578 |

## 几乎无差异代表图

| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |
|---|---|---|---:|---:|---:|---:|
| test | `uNb9QFRL6hY_978d7a8eb0794936bd8fd092306e1dc5` | nearly_no_difference | 8/8 | 1.0 | 0.0018502 | 0.9972425 |
| validation | `pRbA3pwrgk9_b1477ef96be5470d9881a9f6c9f825ae` | nearly_no_difference | 6/6 | 1.0 | 0.00415171 | 0.97984466 |
| validation | `2t7WUuJeko7_7b017f053981438a9c075e599f2c5866` | nearly_no_difference | 4/4 | 1.0 | 0.00515366 | 0.97995224 |
| validation | `pa4otMbVnkk_a1243ae1c9e7407794464678be846819` | nearly_no_difference | 4/4 | 1.0 | 0.00565769 | 0.96897369 |
| validation | `2t7WUuJeko7_218fdf5321f9482e85e828c56f2c0c94` | nearly_no_difference | 6/6 | 1.0 | 0.00609923 | 0.99029248 |
| validation | `pa4otMbVnkk_fc4ee7e59f32491d9817b3a9a5b5e9b1` | nearly_no_difference | 4/4 | 1.0 | 0.00642293 | 0.96410444 |
| validation | `2t7WUuJeko7_b72b7b78675f429a9f382a44e551cffc` | nearly_no_difference | 4/4 | 1.0 | 0.00659757 | 0.97649001 |
| test | `UwV83HsGsw3_bc29294428a647038f70e0ea31ea8972` | nearly_no_difference | 4/4 | 1.0 | 0.0067475 | 0.9698578 |
| validation | `jtcxE69GiFV_eb93e479aeae4b59a26c3ea106f9be7a` | nearly_no_difference | 4/4 | 1.0 | 0.00699741 | 0.97160022 |
| validation | `jtcxE69GiFV_f473cf5a09a64090acec3bfe8fccaacd` | nearly_no_difference | 4/4 | 1.0 | 0.00710437 | 0.97209376 |
| validation | `pa4otMbVnkk_88c758f7e35244fd8f5693913f329805` | nearly_no_difference | 4/4 | 1.0 | 0.00715307 | 0.98736317 |
| validation | `S9hNv5qa7GM_27869fb0e3414f2687b9580b335ec615` | nearly_no_difference | 8/8 | 1.0 | 0.00727339 | 0.98171186 |
| validation | `pa4otMbVnkk_fd3034fe3cf6425ea2810f42656766cf` | nearly_no_difference | 4/4 | 1.0 | 0.00744703 | 0.98268654 |
| validation | `pRbA3pwrgk9_285b697fed754f86a09602c93628cfb4` | nearly_no_difference | 4/4 | 1.0 | 0.00750072 | 0.97617864 |
| validation | `zsNo4HB9uLZ_b6ca0cc195da4688ba67fa53f0345b98` | nearly_no_difference | 4/4 | 1.0 | 0.00756853 | 0.97398927 |
| validation | `2t7WUuJeko7_edc7b2c25f054ce8992ae3fb66e80881` | nearly_no_difference | 6/6 | 1.0 | 0.0076722 | 0.96493138 |
| validation | `2t7WUuJeko7_53937db036374126830e0f1203b04ead` | nearly_no_difference | 6/6 | 1.0 | 0.00814687 | 0.95969487 |
| validation | `pa4otMbVnkk_faa9b3c493a541d5bcaae52f760b6807` | nearly_no_difference | 4/4 | 1.0 | 0.00833593 | 0.98070097 |
| validation | `jtcxE69GiFV_44661972414d44fabc0799f237e4d7f0` | nearly_no_difference | 4/4 | 1.0 | 0.00835176 | 0.97636406 |
| validation | `ZMojNkEp431_f1bb3acca4ed4aada739514b1f2a44bd` | nearly_no_difference | 4/4 | 1.0 | 0.00838323 | 0.97741764 |

## 指标依据

- [HorizonNet 官方仓库](https://github.com/sunset1995/HorizonNet)：2D IoU、3D IoU、Corner Error、Pixel Error。
- [LayoutNetv2 官方仓库](https://github.com/zouchuhang/LayoutNetv2)：Matterport3D/general Manhattan 使用 3D IoU、top-down 2D IoU、depth RMSE、delta1；其中官方 depth 指标读取真实深度，本报告只有明确标记的 layout-depth proxy。
- [Zillow Indoor Dataset, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Cruz_Zillow_Indoor_Dataset_Annotated_Floor_Plans_With_360deg_Panoramas_and_CVPR_2021_paper.pdf)：角点以训练图宽 1% 为距离阈值并报告 Precision/Recall/F1；本文未规定本项目采用的 greedy 匹配算法。
- [ZInD 补充材料](https://openaccess.thecvf.com/content/CVPR2021/supplemental/Cruz_Zillow_Indoor_Dataset_CVPR_2021_supplemental.pdf)：给出 IoU 超过 95% 但未捕捉 bay-window 结构的反例，说明 IoU 不能覆盖拓扑错误。

## 数据与可复现性

- 全量逐图 CSV：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/model_initialization_metrics.csv`
- 运行清单：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v4/run_manifest.json`
- 坐标统一为 1024×512；仅可视化叠加到 2048×1024 原图时才放大 2 倍。
- Validation 模型 txt 在 `output/` 中缺失；本次使用 `analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt`。已用 GPU、同一 config/checkpoint 和 190 张原图独立重跑到 `analysis_results/model_initialization_validation_ep300_replay_20260823_v1/prediction_txt`：旧/新 188/190 张角点对数量一致，174/190 张的全点最大偏差不超过 2 px；官方 evaluator 的连续指标分别为旧产物 92.58/91.64、新重跑 93.48/92.79（2D/3D IoU）。因此旧产物来源得到实证支持，但二元后处理在少数近阈值样本上有环境敏感性。
- GPU 重跑命令、输入/输出聚合哈希与旧/新逐图对照：`analysis_results/model_initialization_audit_hybrid_gt_20260823_v3/GPU_REPLAY_MANIFEST.json`。
- checkpoint SHA-256：`9f2522c0311064a863e838fa345e9b49dc14f95cb1608ba19e942a875344efa9`。
