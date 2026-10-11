# uNb88四空间确认增量与复算

结论和局部结构证据见 [RESULTS_ZH.md](RESULTS_ZH.md)。本轮只落实新回执、核验数据绑定与确认版本、重算底面量，不修改工作台UI、旧公式、旧结果、GT、资格或hold，也不追加旧功能测试。

提交前实际main已前进至 `0c9f2fcd05cf5fa3fb86d9482f975353caad9938`，本分支已正常合并保留其改动。本计算输入源main为 `90d7fc75cad0fe7eb224aa62f13026b1ffd744c2`；回执来自该版本工作台，数据绑定仍为工作台冻结输入的 `159eac10e077834dd0f8e7fd3f9832b5242c529b`，不是版本冲突。

新回执 `libfile_477d2fe4a0ec8191937721f30ba67c8a`，version0，70795 bytes，SHA256 `754507bd4774baacdb2a8f4336b6a7af84387e4c39f2db39515180b4e9b4276e`。通过已解析Library引用获取元数据，分页read完整2759行，恢复字节后与主线程独立原件SHA一致；原件及Library身份/version保留。原11986-byte历史回执原样保存，新增回执内历史30份语义、清单、顺序、T29人工A指令完全相同。

A/B继承既有合理参考；C/D取本次明确确认版本，分别11/10顶点，07:15:53.390Z / 07:15:42.772Z，操作重放与当前草稿一致。四底面均有效；C/D仍top_pending，T30人工指定D优先。原空间名字中的“待用户补画”留在原件中，不能据名字把已确认坐标误判为空。

20个编辑器对象均追到人员manual源标注，不是GT或工作台参考对象。当前点位20份均能重建有效底面；旧缓存19份非空，其中R01808仍hold；R02963旧缓存为空但更新点位有效，仍excluded。`in_current_manual_pool`与`primary_included`都是18份。各分母和几何对照分别列出，不把展示清单当正式人员统计或新批准质量。

机器入口：[reference_ledger.json](results/reference_ledger.json)、[floor_recompute_20.csv](results/floor_recompute_20.csv)、[floor_metrics_80_long.csv](results/floor_metrics_80_long.csv)、[local_structure_20.csv](results/local_structure_20.csv)、[object_identity_20.json](results/object_identity_20.json)。原I/S/Hstar/D/F/Q输入冻结于 `inputs/frozen_components_20.json`；没有新完整Q或3D IoU。

优先级为人工指定→区分空间的局部结构→局部残缺/歪斜/模糊时的底面IoU兜底。GT第5/8对是入口，第6/7对为远端；不能仅凭入口附近有点判包含，也不能凭缺一个角点判缺区域。全20份保留区域覆盖、深半区覆盖、邻边深度、近邻角点距离及最高/次高IoU差；没有把自动候选等同真实意图。

## 复现

在该目录下使用Python3、NumPy、Shapely、Matplotlib与Pillow，Node用于纯数据绑定/操作重放。原工作台纯模块及真实照片从相邻 `../quality_four_space_recheck_20261011` 冻结交付读取，不需要原17分卷或本地用户电脑。

```bash
node code/verify_receipt.cjs
python code/trace_identities.py --repo ../..
python code/recompute_floor.py
python code/local_structure.py
python code/render_key_evidence.py
python code/write_report.py
```

本执行器通过 `PYTHONPATH=/workspace/quality_runtime_20261010` 使用已有研究运行时；实际Python/NumPy/Shapely版本写在 `results/summary.json`。输入原注释摘录和源文件SHA均保留于 `inputs/selected_raw_annotation_evidence.json`，源身份、资格和派生声明可独立抽核。

只做字节/历史绑定、确认重放、当前点位哈希、有效多边形与正分母、面积守恒、旧缓存一致性及冻结A-IoU一致性的必要检查。没有重跑工作台测试矩阵，也没有校准新的最终阈值。当前局部覆盖量自然分成远端未表达与几乎完整表达两类，宽证据带是展示标记；中间/斜跨/畸形仍可不确定。

## 来源与未完成项

正式几何源 `24360ad8544d76d8aba18a8e641f784a76ca0d42`，范围基线 `42f7ea569c591c0cb3472e1b8bb8c0d883bbd3cb`；复算组件源于已交付冻结研究。原代码/数据/照片许可证保持原归档状态，不另赋许可；新脚本直接调用已有研究环境中的库，不新增第三方vendor。

用户局部截图 `libfile_31d539c46e7c81919f8ff808adef8f6c` 的像素已由主线程核对。本执行器截图原字节传输失败，仍待可读取云端转存；本轮独立读取真实原照片并生成配对编号/3例同尺度BEV图，未冒称看过无法取得的截图。此缺口不阻断绑定GT坐标的底面计算。

C/D完整顶界未确认；完整Q、3D IoU及顶界相关S/H尚不能复算。未恢复任何错误GT/hold，未给其他人自动最终空间分配。用户后续工作台偏好云端链接，本轮只交付云端可读取研究结果，不新增ZIP或UI。由主线程独立抽核并统筹main发布。
