# Scope 附文的独立证据审查

本审查对象为 `project_sources/01-scope-.md`。该文件是待审观点，不能授权修改本轮冻结的参考、质量评分、OOS、暂停或普通／门洞／Semi 资格。本轮没有按附件的建议更换参考，也没有据其文字重新裁定图片。

## 能成立的解释边界

表征能否容纳某种空间、单图是否能充分看见、标注任务采用 enclosed 还是 extended 规则、具体工人是否遵守规则，是不同的问题。Manhattan 约束不会自动确定所有被遮挡的墙面位置。玻璃或镜面的材质本身也不能唯一决定某条轮廓应否进入布局。上述区别对解释人员类别有用，尤其能提醒我们：局部标法的多峰分布既可能涉及范围政策，也可能来自几何误差、低质量、遮挡和来源差异。

但是，多个标法簇本身不能证明存在多个同样正确的任务协议。没有原始指令、可定位图片及人工几何证据时，不能把这些簇直接标成“协议类”，更不能将其直接变成跨图人员类别。Scope 的答题倾向、机会数、已裁定正确率与未知必须分别报告；本项目新旧来源的这几种证据也不能合并成同一正确率。

## 关键外部论据及核验状态

| 附文论点 | 核验与实际可用范围 |
|---|---|
| MatterportLayout 的 opening 处存在 enclosed／extended 标法歧义 | Bi-Layout 原论文支持这一背景。论文为约 15% 的整体数据重标 enclosed 分支；其原测试划分与原测试标签保留不变。该数据集层面的比例不能用作本项目异常图比例。 |
| extended 可见范围与完全不可见的完整空间不同 | Bi-Layout 对 extended 的定义覆盖 opening 中可见的区域。它没有证明任意遮挡图片应立即停止硬评分，也没有逐图裁定本项目样例。 |
| 可以采用多参考取最高 IoU | 这是可另行登记研究的建议。Bi-Layout 的相关评价是在两份模型预测中选择对单一 GT 较好的匹配；并不等同于本项目对单份工人答案更换为多份 GT 后取最高值。不能据此修改当前 B8L2/D10。 |
| ZInD 对 opening、door、raw／visible layout 作区分 | 官方仓库支持此区分；并提示 visible 裁切可能局部非 Manhattan、非平天花板高度含近似、小房间相机位于布局之外时可能没有 visible 几何。这些是 ZInD 自身的定义与可用性说明，不能自动覆盖本项目任务合同。 |
| 超过四分之一 LayoutMP3D 原布局修改，且 3D IoU 至少变化 10%；排除 corridors／stairs 等细项 | 本次已核到 Comparative Study 的作者、题目及摘要，但未成功获取并逐项核对其全文中的这些具体数量与排除清单。本轮不以这些未复核的细项作本项目图像裁决。 |
| 本附件所说的具体玻璃／反射样例一定是 in_scope_but_unresolved | 附文没有可用的确切 image_id、原图—参考映射和可核验人工记录。文中的旧引用占位符不能代替这些证据。因此本次无法独立作该样例裁定；既不能确认，也不能用缺证据反向断言其 OOS。 |

## 对本轮实验的落实

保留冻结主评价与失败分母。新的形状诊断只并列描述边界、真实转角、bottom-y 与高度变化，不能命名为已验证的必要结构正确率或 N1。若观察到总分相近而形状不同，先保存精确成员、固定参考和最终几何，再作机制解释；不得将“不喜欢此参考”的案例直接剔除。人物分类历史特征继续隔离目标建筑；当图标法簇或节点票数只能解释作答后的机制，不能伪装成采集前选人成功。

附件提出的 `primary_full_layout_worker_scoring=false`、多参考、局部可见评价和新的 scope 流程均是未来可登记方案。它们不是本轮已实施的规则，也不构成改变已有研究资格的证据。

## 可定位的主要来源

1. Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, Ming-Hsuan Yang. 2024. *No More Ambiguity in 360° Room Layout via Bi-Layout Estimation*. CVPR, 28056–28065. 作者公开 PDF：<https://liagm.github.io/Bi_Layout/pdf/3739.pdf>；官方 CVF PDF：<https://openaccess.thecvf.com/content/CVPR2024/papers/Tsai_No_More_Ambiguity_in_360deg_Room_Layout_via_Bi-Layout_Estimation_CVPR_2024_paper.pdf>。
2. Steve Cruz, Will Hutchcroft, Yuguang Li, Naji Khosravan, Ivaylo Boyadzhiev, Sing Bing Kang. 2021. *Zillow Indoor Dataset: Annotated Floor Plans With 360° Panoramas and 3D Room Layouts*. CVPR, 2133–2143. 官方数据说明：<https://github.com/zillow/zind>。
3. Chuhang Zou, Jheng-Wei Su, Chi-Han Peng, Alex Colburn, Qi Shan, Peter Wonka, Hung-Kuo Chu, Derek Hoiem. *Manhattan Room Layout Reconstruction from a Single 360° Image: A Comparative Study of State-of-the-art Methods*. 2019 年预印本；2021 年 IJCV。元数据和摘要：<https://arxiv.org/abs/1910.04099>。本审查不把摘要未列出的具体排除与数量当成已核验事实。

网页来源读取时点与本地源代码审查不同：这些论文只支持背景解释；冻结输入与原生融合是否改变的证据见 `SOURCE_PARITY_AUDIT.json`，451 事件复算范围见 `FOLLOWUP_REAGGREGATION_AUDIT.json`。
