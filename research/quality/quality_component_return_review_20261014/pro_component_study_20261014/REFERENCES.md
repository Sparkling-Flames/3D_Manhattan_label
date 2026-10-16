# 原始文献、官方实现与适用差异

检索核验日期：2026-10-14。论文论断以原文及官方实现为依据；这些文献均没有验证本项目的35/30/10/20/5权重或A/RA总分。

## 1. HoHoNet与原始3D IoU

Cheng Sun, Min Sun, and Hwann-Tzong Chen. 2021. **HoHoNet: 360 Indoor Holistic Understanding With Latent Horizontal Features.** Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 2573–2582.

作者公开PDF：https://arxiv.org/pdf/2011.11498

官方CVF PDF：https://openaccess.thecvf.com/content/CVPR2021/papers/Sun_HoHoNet_360_Indoor_Holistic_Understanding_With_Latent_Horizontal_Features_CVPR_2021_paper.pdf

官方实现：https://github.com/sunset1995/HoHoNet/blob/master/eval_layout.py

使用点：实现以恢复的水平多边形及角点均高计算棱柱体积重合；不是逐墙高变化的任意三维实体积分。因此固定底面、角点均高不变的顶部起伏可能不改变此IoU。原实现的异常处理规则不覆盖本研究缺值合同，本研究仍保持NA。本轮真实记录复用冻结的同参考IoU字段，没有逐记录从原始点重跑官方实现。

## 2. 当前布局表示与墙角几何

Cheng Sun, Chi-Wei Hsiao, Min Sun, and Hwann-Tzong Chen. 2019. **HorizonNet: Learning Room Layout With 1D Representation and Pano Stretch Data Augmentation.** Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 1047–1056.

作者公开PDF：https://arxiv.org/pdf/1901.03861

官方CVF PDF：https://openaccess.thecvf.com/content_CVPR_2019/papers/Sun_HorizonNet_Learning_Room_Layout_With_1D_Representation_and_Pano_Stretch_CVPR_2019_paper.pdf

使用点：单地面、平行天花板、upright输入与墙体几何约束；上下角点对共享水平位置。本文的有向内角等于垂直墙体相交角的解释依赖这一表示。文献不是用户所有图像已满足标定和表示前提的证据。

## 3. 不同合理范围不是墙角错误

Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, and Ming-Hsuan Yang. 2024. **No More Ambiguity in 360° Room Layout via Bi-Layout Estimation.** Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), 28056–28065.

作者公开PDF：https://arxiv.org/pdf/2404.09993

官方CVF PDF：https://openaccess.thecvf.com/content/CVPR2024/papers/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.pdf

作者项目：https://liagm.github.io/Bi_Layout/

使用点：§3的enclosed与extended-visible目标差异，及论文讨论的大开口边界不明确等限制，说明opening处的不同完整布局不能全部解释为工人画错。本文没有据此给任何真实样例自动恢复多参考/同范围资格，也没有移植论文利用GT消歧的评估步骤作为“挑最高分参考”。

## 4. 权重、归一化与补偿

OECD/European Union/EC-JRC. 2008. **Handbook on Constructing Composite Indicators: Methodology and User Guide.** OECD Publishing, Paris. DOI: 10.1787/9789264043466-en.

官方出版页：https://www.oecd.org/en/publications/handbook-on-constructing-composite-indicators-methodology-and-user-guide_9789264043466-en.html

官方PDF：https://www.oecd.org/content/dam/oecd/en/publications/reports/2008/08/handbook-on-constructing-composite-indicators-methodology-and-user-guide_g1gh9301/9789264043466-en.pdf

使用点：书中聚合章节区分线性/几何聚合及补偿，指出权重需连同尺度和替代关系解释。本研究借鉴的是组合指标设计方法，不是把国家指标指南当全景标注的质量标准。已查看PDF印刷页103（文件第105页）的线性聚合式及假设说明；部分CVF页面403、部分论文PDF截图失败，不声称已视觉核验未成功加载的论文插图。

## 仓库原始证据（固定版本）

根地址：https://github.com/Sparkling-Flames/3D_Manhattan_label/tree/134e7c775b9ea25a076851c0605571ba0ea0ac31

- research/quality_model_closeout_20261014/README.md
- research/quality_pro_return_review_20261014/README.md
- research/quality_candidate_review_20261014/README.md
- research/quality_candidate_review_20261014/quality_candidate_review_20261014_v1.json
- research/quality_targeted_review_workbench_20261012/README.md
- research/quality_top_height_response_20261012/CANDIDATE_DIRECTION.md

仓库报告的718条全量复算属于前轮Pro及本地审核证据，不算本轮实际重建。本文全部新数值的直接依据是本包inputs、代码及results。
