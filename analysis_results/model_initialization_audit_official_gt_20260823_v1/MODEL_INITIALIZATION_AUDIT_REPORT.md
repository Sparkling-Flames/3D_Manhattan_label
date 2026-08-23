# HoHoNet 模型布局初始化代理全量审计（官方 MP3D 原始 GT）

## 结论口径

本报告覆盖 Test 458 张与 Validation 190 张，共 648 张。主 GT 固定为 `data/mp3d_layout/test/label_cor` 与 `data/mp3d_layout/valid/label_cor`；未使用 `test_no_occ`、`valid_no_occ`，也未用人工修订的 `export_label/groudTruth.json` 替代官方 GT。Test 的人工修订另见 `docs/thesis_main/TEST_MANUAL_GT_CORRECTIONS_20260823.md`。

当前产物是 HoHoNet ep300 的**最终布局输出**，仓库没有保存 raw corner probability/优化前峰值，因此本报告严谨称为 `final_layout_as_initialization_proxy`，不是网络内部原始初始化。

二元判定不由 IoU 单独决定：

1. `pair_structure_correct`：模型点对编码可解析，且模型与 GT 角点对数量相同。点对编码校验只检查偶数点、相邻 ceiling/floor 的 x 一致和上下关系；**没有**声称已经验证整圈自交或完整 Manhattan 正交约束。
2. `corner_localization_pass`：采用 ZInD/CVPR 2021 的图宽 1% 距离阈值（10.24 px），配合本项目确定性的 seam-aware greedy exclusive matching；所有 ceiling/floor 角点均匹配才通过。它是 point-level 匹配，不强制同一 wall pair 联合匹配。ZInD 只给出阈值与 P/R/F1，没有规定 greedy 算法，因此这里明确称为 ZInD-inspired 项目实现；在本次 648 张上用最大基数匹配复核，TP 未出现差异。
3. `geometry_acceptable`：本项目 v1 联合门，要求 top-down 2D IoU ≥ 0.90、LayoutNetv2-style derived 3D IoU ≥ 0.80、layout mask difference ≤ 0.05。文献没有统一的逐图二元阈值；`.90/.80/.05` 是本次审计在初次全量输出语义复核后由分析者定义的 post-hoc operational threshold，未预注册、未用独立验证集校准，不应冒充文献标准或无偏 benchmark cutoff。它们从本报告起按 v1 固定，供后续复现或前瞻应用。
4. `initialization_correct = pair_structure_correct AND corner_localization_pass AND geometry_acceptable`。任何角点对数量变化仍先判 `wrong_initialization_topology`，高 IoU 不得覆盖。
5. `nearly_no_difference` 是更严格的展示层：初始化正确、最大循环对齐角点误差不超过 2.56 px、布局 mask 差异不超过 0.01。

本数据中有 6 张拓扑错误图片的 top-down 2D IoU 仍 ≥ 0.95，35 张拓扑错误图片的 layout mask IoU 仍 ≥ 0.95，直接证明面积 IoU 不能替代拓扑门。

`layout_depth_rmse_proxy` 与 `layout_depth_delta1_proxy` 比较的是由模型角点和 GT 角点各自合成的 layout depth，不是真实 Matterport depth map；仓库当前没有为这 648 张绑定真实 depth GT，因此不得把这两列解释成 LayoutNetv2 官方 depth RMSE/δ1。

## 汇总

| split | 总数 | 拓扑一致 | 角点层通过 | 独立几何指标门通过 | 初始化正确 | mask diff≥.10 | 几乎无差异 |
|---|---:|---:|---:|---:|---:|---:|---:|
| test | 458 | 287 | 142 | 127 | 95 | 142 | 2 |
| validation | 190 | 163 | 150 | 158 | 148 | 10 | 27 |
| all | 648 | 450 | 292 | 285 | 243 | 152 | 29 |

“独立几何指标门通过”是在全部图片上单独统计，尚未排除拓扑/角点失败行；“初始化正确”才是三道门的严格合取。

全量类别计数：{'correct_but_visible_difference': 214, 'large_difference_geometry': 49, 'large_difference_localization': 158, 'large_difference_topology': 198, 'nearly_no_difference': 29}

- Test：{'correct_but_visible_difference': 93, 'large_difference_geometry': 47, 'large_difference_localization': 145, 'large_difference_topology': 171, 'nearly_no_difference': 2}
- Validation：{'correct_but_visible_difference': 121, 'large_difference_geometry': 2, 'large_difference_localization': 13, 'large_difference_topology': 27, 'nearly_no_difference': 27}

## 差异大代表图：拓扑错误

| split | image_id | 类别 | 角点对 model/GT | F1@1% | mask diff | 2D IoU |
|---|---|---|---:|---:|---:|---:|
| test | `q9vSo1VnCiC_a6560bae311a403a9bfe94e4c1c645f4` | large_difference_topology | 4/14 | 0.11111111 | 0.2481997 | 0.66548247 |
| test | `q9vSo1VnCiC_a84d84665ef94d0c86f38bc2250bab55` | large_difference_topology | 8/18 | 0.23076923 | 0.15553427 | 0.83525042 |
| test | `UwV83HsGsw3_b979526475874ad68ae33f02d407a1fc` | large_difference_topology | 6/16 | 0.09090909 | 0.15452282 | 0.46266052 |
| test | `X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9` | large_difference_topology | 12/4 | 0.375 | 0.1105654 | 0.77658052 |
| test | `e9zR4mvMWw7_18653fa3d6ba4f82889237201ee07d11` | large_difference_topology | 4/12 | 0.375 | 0.07396313 | 0.62077064 |
| test | `q9vSo1VnCiC_a424533651804a38a55b1252daccc81e` | large_difference_topology | 4/12 | 0.375 | 0.07331887 | 0.65192827 |
| test | `q9vSo1VnCiC_ca6944f5dd334193bb86058ba5ab5dc3` | large_difference_topology | 4/12 | 0.4375 | 0.05362129 | 0.8055411 |
| validation | `pRbA3pwrgk9_03de6e2562bb4f56a88db3ceb681af78` | large_difference_topology | 4/10 | 0.07142857 | 0.29716657 | 0.16153021 |
| test | `uNb9QFRL6hY_a372582c11864f31a9dd174e4a0ae6ad` | large_difference_topology | 14/8 | 0.36363636 | 0.23222693 | 0.82583347 |
| test | `wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6` | large_difference_topology | 14/8 | 0.27272727 | 0.22884028 | 0.87075779 |

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
| validation | `2t7WUuJeko7_edc7b2c25f054ce8992ae3fb66e80881` | nearly_no_difference | 6/6 | 1.0 | 0.0076722 | 0.96191253 |
| validation | `2t7WUuJeko7_53937db036374126830e0f1203b04ead` | nearly_no_difference | 6/6 | 1.0 | 0.00814687 | 0.96401406 |
| validation | `pa4otMbVnkk_faa9b3c493a541d5bcaae52f760b6807` | nearly_no_difference | 4/4 | 1.0 | 0.00833593 | 0.98070097 |
| validation | `jtcxE69GiFV_44661972414d44fabc0799f237e4d7f0` | nearly_no_difference | 4/4 | 1.0 | 0.00835176 | 0.97636406 |
| validation | `ZMojNkEp431_f1bb3acca4ed4aada739514b1f2a44bd` | nearly_no_difference | 4/4 | 1.0 | 0.00838323 | 0.97741764 |

## 指标依据

- [HorizonNet 官方仓库](https://github.com/sunset1995/HorizonNet)：2D IoU、3D IoU、Corner Error、Pixel Error。
- [LayoutNetv2 官方仓库](https://github.com/zouchuhang/LayoutNetv2)：Matterport3D/general Manhattan 使用 3D IoU、top-down 2D IoU、depth RMSE、delta1；其中官方 depth 指标读取真实深度，本报告只有明确标记的 layout-depth proxy。
- [Zillow Indoor Dataset, CVPR 2021](https://openaccess.thecvf.com/content/CVPR2021/papers/Cruz_Zillow_Indoor_Dataset_Annotated_Floor_Plans_With_360deg_Panoramas_and_CVPR_2021_paper.pdf)：角点以训练图宽 1% 为距离阈值并报告 Precision/Recall/F1；本文未规定本项目采用的 greedy 匹配算法。
- [ZInD 补充材料](https://openaccess.thecvf.com/content/CVPR2021/supplemental/Cruz_Zillow_Indoor_Dataset_CVPR_2021_supplemental.pdf)：给出 IoU 超过 95% 但未捕捉 bay-window 结构的反例，说明 IoU 不能覆盖拓扑错误。

## 数据与可复现性

- 全量逐图 CSV：`analysis_results/model_initialization_audit_official_gt_20260823_v1/model_initialization_metrics.csv`
- 运行清单：`analysis_results/model_initialization_audit_official_gt_20260823_v1/run_manifest.json`
- 坐标统一为 1024×512；仅可视化叠加到 2048×1024 原图时才放大 2 倍。
- Validation 模型 txt 在 `output/` 中缺失；本次使用此前由同一 ep300 checkpoint 物化并冻结的 `analysis_results/c2b_validation_static_20260802_v16/validation_prediction_txt`，该限制已写入 CSV 与 manifest，而非把别的模型结果冒充同源输出。
- checkpoint SHA-256：`9f2522c0311064a863e838fa345e9b49dc14f95cb1608ba19e942a875344efa9`。
