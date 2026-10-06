# 九图交接核验与结构续审

先读 REVIEW_ZH.md。此前缺失的工作树包已经取得，本报告不再把该资料列为阻塞。

## 先看三个结果

- e9z_audit/e9z_seam_sources.png：源观察与接缝候选的原图对照
- e9z_audit/e9z_range_compensation.png：为何删除不合理转折会降低参考IoU
- nine_image_study/REPORT_ZH.md：九图全池结构对照，含rpc9°的局部正结果及失败

## 内容

- baseline_reproduction：108基线、全库统计账本和即时邻点复算
- nine_image_study：自包含的九图结构实验、压缩路径账本、候选/成员变化、七项控制与复算入口
- e9z_audit：独立球面几何、全部255右侧子集、范围补偿与关键图
- panel_evidence：五张定向困难图的像素/来源解释及B6By120°域诊断
- intake：新旧输入/代码差异、来源与影像尺寸核对
- PROVENANCE.json：本次输入身份及边界
- MANIFEST_SHA256.json：本包所有其他文件的最终哈希

## 一条命令运行九图新实验

进入 nine_image_study，安装requirements所列依赖，运行：

```
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reproduce.py --out NEW_results
```

该子包自带150份记录和所需代码，不需要GT、原图、远端仓库或最新工作树。NEW_results必须不存在。Windows可先设置相应环境变量，再运行Python命令。

## 重新核验原108基线

解压你上传的 pro_structure_constraints_20261006.zip，将完整目录作为SOURCE。该输入不在本输出包里重复放一份原图。

```
bash baseline_reproduction/run_replay.sh /path/to/SOURCE /path/to/NEW_baseline_audit
```

53状态完全相等，55状态仅浮点尾差；不能用一次严格字节不等便判断算法改变。

## 重新核验e9z及画图

```
python e9z_audit/audit_e9z.py --handoff /path/to/SOURCE --out NEW_e9z
python e9z_audit/clique_gate_audit.py --out NEW_e9z
python e9z_audit/render_audit.py --handoff /path/to/SOURCE --out NEW_e9z
python e9z_audit/summarize_followups.py --handoff /path/to/SOURCE --out NEW_e9z --structure-file nine_image_study/results/e9zR4mvMWw7-15/pair_12.json
```

五图科学叠加与域诊断：

```
python panel_evidence/build_evidence.py --handoff /path/to/SOURCE --out NEW_panel
python panel_evidence/diagnose_domains.py --handoff /path/to/SOURCE --out NEW_panel
```

库版本、初次失败与恢复、未执行项在各子报告中保留。图像只作证据定位，不产生新的人工gold；所有几何与投票结果是开发面板上的条件结果，不是总体准确率。

## 拆分交付

为保证附件能发送，交付分成四个ZIP。请把四个ZIP都解压到同一目录，它们使用相同根目录并自动合并；文件内容不重叠，不覆盖彼此。第一个包有主报告。完整运行代码或查看全部图之前，请先解压全部四包。每包的清单仅覆盖其实际文件。
