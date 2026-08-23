# Test 人工 GT 修订审计说明（2026-08-23）

## 结论

用户已确认：下表 30 张均为其人工审核与调整，不应再解释为未知来源差异。当前人工文件为 `export_label/groudTruth.json`，共覆盖 Test 458 张；相对官方 `data/mp3d_layout/test/label_cor`：

- 428 张在 1 px 容差内点集一致；
- 30 张存在实质几何差异，其中 21 张角点对数量改变，9 张数量相同但坐标改变；
- 另有 1 张 `rPc6DW4iMge_fbc169773c954580baea6d2798c0d486` 仅点对顺序不同，点集与归一化几何一致，不计入 30 张实质修订。

“约 10 张”可由历史记录解释：`c21a70e` 到 `ef343e9` 之间确实触及 10 张，但其中 8 张此前已经偏离官方 GT，仅 2 张在该次首次进入“相对官方不同”的集合。当前 30 张是多次人工修订累积，不是一次操作产生，也未发现曾修订后又恢复为官方几何的图片。

本说明只记录来源和几何差异，不判断人工修订与官方标注孰优孰劣，也不改写 `export_label/`。模型初始化审计的当前 v2 主口径为：这 30 张采用用户确认的人工 GT，其余 428 张 Test 采用官方原始 MP3D GT；Validation 190 张采用官方原始 GT；全程不采用 no-occ。

## 30 张实质修订清单

`mask difference` 为两套布局在 1024×512 坐标系下的 seam-aware 墙面区域 mask 差异（`1 - IoU`），仅用于描述改动幅度。

| image_id | 当前角点对 | 官方角点对 | mask difference | 改动类型 |
|---|---:|---:|---:|---|
| `7y3sRwLe3Va_9bbf903d50da4ffd9e5d1fb7c9f4d69b` | 8 | 4 | 0.02838803 | 数量改变 |
| `B6ByNegPMKs_48ee619d38b142f88914e7e2582bc1d8` | 4 | 4 | 0.00016762 | 坐标改变 |
| `B6ByNegPMKs_75327de9719945aa8b893a6404667884` | 4 | 4 | 0.37942413 | 坐标改变 |
| `b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15` | 4 | 8 | 0.30897985 | 数量改变 |
| `e9zR4mvMWw7_409f2a738bf54153b9b77c39e7a4ea45` | 4 | 6 | 0.08082874 | 数量改变 |
| `e9zR4mvMWw7_4fb8c9be319e4784b4b66f9ca5d839ab` | 6 | 12 | 0.36132840 | 数量改变 |
| `q9vSo1VnCiC_1cd414875b9b4311bc6a179d91e6270d` | 4 | 8 | 0.03418074 | 数量改变 |
| `q9vSo1VnCiC_3e5aacbc10904d4b88660a3cb91efcb9` | 4 | 8 | 0.28142683 | 数量改变 |
| `q9vSo1VnCiC_3e7f67e8969f434b9a4aec0c68668b20` | 10 | 10 | 0.09093372 | 坐标改变 |
| `q9vSo1VnCiC_69591068e5614642b710a8fb7733bdeb` | 4 | 12 | 0.11893738 | 数量改变 |
| `q9vSo1VnCiC_9c9fb1fccf4e46a597a9510a1938c8b4` | 12 | 8 | 0.25808293 | 数量改变 |
| `q9vSo1VnCiC_e74e843601574864a14517f990c748a0` | 4 | 8 | 0.08253862 | 数量改变 |
| `rPc6DW4iMge_acbe920a0c5d4c018b1803ee9b1f331a` | 6 | 12 | 0.09458659 | 数量改变 |
| `uNb9QFRL6hY_07a43087f1e54e3f828851d8e457a283` | 4 | 8 | 0.15907303 | 数量改变 |
| `uNb9QFRL6hY_1096f195d3294cefa462add5ab0c342e` | 4 | 6 | 0.08276180 | 数量改变 |
| `uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97` | 6 | 4 | 0.11819464 | 数量改变 |
| `uNb9QFRL6hY_978d7a8eb0794936bd8fd092306e1dc5` | 8 | 8 | 0.29221915 | 坐标改变 |
| `uNb9QFRL6hY_aed830f085ee4ad88ef6bed7f66f1359` | 4 | 4 | 0.00171241 | 坐标改变 |
| `uNb9QFRL6hY_bcce4f23c12744c782c0b49b24a0331a` | 4 | 4 | 0.01803478 | 坐标改变 |
| `uNb9QFRL6hY_c1ebb8b34eb846ba9b5ce23b30b299a7` | 4 | 6 | 0.11713666 | 数量改变 |
| `UwV83HsGsw3_7482b1a2655e4655ae4ab58749f43f65` | 8 | 10 | 0.14723024 | 数量改变 |
| `wc2JMjhGNzB_1d8917d25abb4a77a0da9583dc82c17c` | 4 | 4 | 0.14634675 | 坐标改变 |
| `wc2JMjhGNzB_40ea4145b9e946aab5d56de3ce179c8e` | 8 | 4 | 0.07553204 | 数量改变 |
| `wc2JMjhGNzB_4884da3227464ab5b82f631ff22205bd` | 8 | 6 | 0.09815508 | 数量改变 |
| `X7HyMhZNoso_28ada927582d4d6ea7cf44cabf31527a` | 6 | 6 | 0.19511387 | 坐标改变 |
| `x8F5xyUWy9e_a51a0e2811f342a599ae4cdb9b84ff23` | 6 | 6 | 0.04807792 | 坐标改变 |
| `yqstnuAEVhm_26b2e92ccd314a2da1a4fc8dfc6e6f56` | 4 | 8 | 0.38152861 | 数量改变 |
| `yqstnuAEVhm_c93bf298b1cb41a1b368a6ce8bcff53d` | 14 | 18 | 0.04110305 | 数量改变 |
| `yqstnuAEVhm_e3face7b2196414d95ed97151aa13058` | 10 | 8 | 0.09019028 | 数量改变 |
| `yqstnuAEVhm_e650c19e3eb34cc0b98374e5a23d1f65` | 12 | 16 | 0.00971629 | 数量改变 |

## 顺序与历史核验

- 455/458 张当前人工 GT 可直接按原始相邻点配对，并与独立的按 x 配对结果一致；另 3 张触发循环 x 配对，其中 1 张几何一致、2 张有配对歧义。
- 采用原始顺序与顺序无关配对分别计算模型—GT mask 差异，只有 1 张发生变化，变化约 `4.7e-6`，不能解释此前观察到的大差异。
- 历史版本相对官方的实质差异数依次为：21、21、21、23、24、27、27、29、30；历史差异集合并集恰为当前 30 张。
- 四个 `export_label/人工精标 project-20` 快照相对官方的实质差异数为 17、20、20、21；最后快照的 21 张全部仍包含在当前 30 张中，之后新增 9 张。

## 已生成人工审查图

- `analysis_results/gt_manual_batch_review_20260823_v1/manual_gt_review_1.png`
- `analysis_results/gt_manual_batch_review_20260823_v1/manual_gt_review_2.png`
- `analysis_results/gt_manual_remaining_review_20260823_v1/remaining_gt_review_1.png`
- `analysis_results/gt_manual_remaining_review_20260823_v1/remaining_gt_review_2.png`
