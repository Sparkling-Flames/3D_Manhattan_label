# 玻璃邻近遮挡延伸空间的全景 Room-Layout 定义与工作流裁决

## 核心裁决

你最新的澄清改变了问题的性质：

> 争议并不是“玻璃是不是墙”，而是**玻璃、镜面或反射构件附近存在一个向后延伸的结构空间，但其末端和完整拓扑被前景墙体或隔断遮挡，单张全景图无法看全**。

对这类情况，最严格、最符合现有 room-layout 文献的裁决是：

1. **它通常不应仅因遮挡而被判为 OOS。**只要真实空间仍可由当前的单地面、单天花板、Manhattan 墙体表示，它在“表示能力”上仍可能属于 in-scope。
2. **但它可能不适合进入完整布局的硬 GT 评分。**如果从工人看到的单张 RGB panorama 无法唯一确定隐藏空间究竟是浅凹槽、长通道、额外转角或更大空间，就属于 `in_scope_but_unresolved`，而不是要求工人猜出数据集完整 GT。
3. **必须预先冻结 enclosed 或 extended policy。**CVPR 2024 的 Bi-Layout 研究明确指出，同一个 opening 可以有两种合理标法：一种在歧义区域停止并封闭最近空间；另一种延伸到 opening 内所有可见区域。MatterportLayout 本身混用了这两种政策。citeturn21view0
4. **即使采用 extended policy，也只能延伸到“有可见证据的区域”，不等于补全完全不可见的隐藏空间。**
5. **你图中的稀疏 GT 与更密集的工人标注，很可能首先是目标政策不一致，而不一定是工人几何能力差。**在政策未冻结前，不能把其中一类自动定义为错误。
6. **Matterport3D 的 depth、mesh 和多视图信息可以用于研究者仲裁真实完整空间，但不能直接等同于“单图工人可恢复真值”。**此外，镜面和透明表面本身可能造成深度传感或重建错误，因此即使使用 RGB-D，也需要结合 mesh、邻近视角和结构连续性复核。citeturn20search7turn23search20turn23search0

因此，对当前样例最合适的 provisional 标签是：

```text
task_representation_scope = in_scope
layout_policy = enclosed / extended_visible，必须事前冻结
portal_type = doorless_opening_or_structural_role_uncertain
observability_status = ambiguous_occluded_extension
reference_class = partial_visible 或 hard_multi
primary_full_layout_worker_scoring = false
```

若后续借助 MP3D mesh、depth 或邻近 panorama 证明隐藏拓扑唯一存在，可以保留一份 `dataset_complete_reference`；但它不能无条件作为仅看当前 RGB panorama 的工人能力硬评分参考。

## 图像中的真正几何争议

从你提供的原始 panorama、稀疏红点 GT、较密集的工人标注和局部裁剪可以区分出三个不同问题。

**反射构件的材质不是决定 Scope 的核心。**图中黑框构件从反射内容看更接近镜面或折叠式反射面，但仅凭一张 RGB panorama，无法完全确认它是固定镜墙、折叠镜、玻璃门还是具有其他结构功能的构件。Room-layout 应首先判断它在建筑空间中究竟属于：

- 固定围护墙面；
- 门或可关闭 portal；
- 无门 opening；
- 非围护性的内部物体；
- 无法从当前图像确定的结构。

不能使用“玻璃透明，所以继续标”或“镜子反射，所以这里是墙”这样的单一材料规则。

**你指出的向后延伸确实有视觉依据。**在中央隔断、镜面构件及其相邻区域，地面、顶面和侧墙存在一定连续性，说明最近可见边界后方或侧后方可能继续存在一个 recess、通道或更大的空间。因此，将布局简单截断到前景隔断的正面，可能遗漏了可见的空间延伸。

**但完整末端拓扑并不唯一。**从当前单张 panorama 看，被遮挡区域至少可能兼容以下多种 Manhattan 解释：

```text
浅矩形凹槽
较深的矩形延伸
延伸后左转或右转
隔断后形成额外凹角
与相邻衣帽间或走廊相连
```

这些解释均有可能保持墙体正交，却对应不同角点数、不同 floor polygon 和不同 3D IoU。Manhattan 约束只能限制墙的方向，不能凭空确定一面被完全遮挡的终止墙位于多远，也不能自动确定隐藏区域包含几个转角。单图布局方法通常需要在多个几何假设之间进行选择；遮挡稳健性本身也是当前研究专门处理的问题，而不是一个由 Manhattan 假设自动消除的问题。citeturn18view1turn22search2turn22search11

因此，这个样例不应被表述为：

> “镜子或玻璃后面一定有一个完整房间，工人必须补出来。”

也不应被表述为：

> “相机看不到，所以延伸空间一律不属于布局。”

更准确的表述是：

> **可见证据支持空间在该方向上继续，但当前信息未必足以唯一确定其完整闭合拓扑。**

## 文献中的目标定义并不唯一

当前争议的根源，是 room layout 文献中实际存在多种不同的“完整布局”定义。

| 定义 | 对 opening 的处理 | 对当前样例的含义 |
|---|---|---|
| `enclosed layout` | 在歧义 opening 处停止，封闭最近空间 | 可以在向后延伸变得不可确定之前停止 |
| `extended-visible layout` | 延伸到 opening 内所有**可见**区域 | 应纳入可见的向后延伸，但不能随意补全不可见末端 |
| `dataset-complete layout` | 借助完整房屋、mesh、depth、多视图或人工 floor plan 表示完整空间 | 可能包含单图中无法唯一恢复的隐藏结构 |
| `visible/local geometry` | 仅表达当前视角可以支持的局部几何 | 遮挡区域可以截断或使用可见 mask |
| `semantic room` | 按卧室、走廊、衣帽间等语义划分 | 不应直接用作几何布局边界 |

Bi-Layout 对 MatterportLayout 的系统分析明确指出，已有 GT 在 opening 处混合了 enclosed 与 extended 两类标注。论文将 enclosed 定义为在歧义处停止并包围最近房间，将 extended 定义为扩展至 opening 内的所有可见区域；作者为约 15% 的 MatterportLayout 标签重新建立 enclosed 版本，说明这并非极少数偶发错误，而是足以影响训练和评价的系统性目标歧义。citeturn21view0

尤其需要强调“**可见区域**”四个字。Bi-Layout 的 extended 定义并没有授权标注者补全所有不可见空间。对于已看到 opening 内的一段走廊或 recess，extended policy 应继续覆盖；但如果远端完全被隔断遮挡，且可能存在多个合理闭合方式，仍然需要 `unresolved`、多参考或局部可见评价。citeturn18view0turn21view0

ZInD 提供了另一个重要但不完全相同的范式。ZInD 区分 raw、complete、visible 等几何；其官方说明指出，visible geometry 会在局部被截断到可观察范围，因此即使真实房间是 Manhattan，局部 visible geometry 也可能不再保持完整 Manhattan 多边形。ZInD 还明确规定 complete 和 visible geometry 都不穿过 door，只穿过其定义的 opening；其中 opening 是为标注流程暂时拆分大空间的人工结构，后续 room merging 时会被移除。citeturn17search0

这说明此前讨论中把：

```text
ZInD raw = enclosed
ZInD visible = extended
```

直接视为严格等价，并不准确。Bi-Layout 论文只称它们“相似”；ZInD 的 visible 更接近局部可观测几何，而 extended 是一套 opening 标注政策。citeturn21view0turn17search0

MatterportLayout 的原始构建也不是单纯由单张图上的红点点击产生。研究者使用 PanoAnnotator，通过自动提取的 2D/3D 特征初始化 Manhattan layout，再由人工增加、删除、推拉 3D 墙片以及调整地面和天花板；后续比较研究报告，超过四分之一的 LayoutMP3D 初始布局被显著修改，3D IoU 差异至少达到 10%。citeturn20search0turn18view1

这意味着你的实验必须区分：

\[
\text{数据集作者可利用的信息}
\neq
\text{当前 crowd worker 实际看到的信息}.
\]

如果数据集 GT 的隐藏延伸来自 depth、mesh、邻近 panorama 或交互式 3D refinement，而你的工人只看到单张 RGB panorama，那么直接要求工人与完整 GT 一致，会混淆“工人能力”与“信息条件不对称”。

## 对现有讨论内容的客观审查

你上传的那段讨论中，有一部分判断是正确的，但也存在几个需要实质修正的地方。fileciteturn0file0

| 讨论中的观点 | 裁决 | 原因 |
|---|---|---|
| OOS 与边界看不清必须拆开 | 正确，应正式采用 | 表示模型不适用与证据不足是两个不同变量 |
| 隐藏角只在唯一可推断时补全 | 正确，应作为硬规则 | Manhattan 约束不保证隐藏距离和隐藏转角唯一 |
| 不使用语义化的“camera room”，改用结构空间 | 基本正确 | 走廊、衣帽间等语义名称不能决定几何边界 |
| 透明玻璃仍然可以是围护边界 | 原则正确但不完整 | 是否为边界取决于结构角色，不取决于透明性 |
| 无门 opening 就应一直继续 | 过强，不能直接采用 | enclosed 与 extended 都是文献承认的合理政策 |
| complete layout 应补全隐藏部分 | 需要限定 | 只能补全可见或唯一可推断部分，不能要求猜测 |
| ZInD visible/complete 可直接对应 enclosed/extended | 不够准确 | 两套定义有相似性，但并非严格同义 |
| 所有人即使选 OOS 仍必须画完整几何 | collection 层可以，analysis 层必须降级 | 可以收集 best-effort geometry，但不代表其具有可硬评分的唯一 GT |

修订后的 Scope 方案正确区分了任务级 protocol reference 与工人 response，也正确提出工人选择 OOS 不应自动删除几何。但其中“无论如何完成同一标准的完整几何”仍需改为：

> **无论 Scope 回答如何，均提交 mandatory best-effort geometry；是否存在唯一、完整、可正式评分的 reference，由任务级 representation scope 与 observability status 决定。**

否则，在隐藏区域不可唯一确定时，工人会被迫制造一个闭合多边形；随后这个被迫猜测的结果又可能被当成工人错误，形成设计诱发的测量偏差。fileciteturn0file1

此前上传的众包共识论文也不能解决这一政策歧义。Kara 等人的模型假定每个样本存在一个潜在真值，并利用工人参数形成共识；论文同时明确警告，在小规模 crowd 中，如果系统早期被错误或低能力工人主导，真正正确的工人可能被当成离群者。因而“多数人选择截断”或“多数人选择延伸”都不能替代事前定义 target estimand。fileciteturn0file2

对当前样例而言，如果一组工人遵循 enclosed 思路，另一组工人遵循 extended 思路，Geometry LOO 出现两个簇，首先应标记：

```text
protocol_multimodality
```

而不是直接标记：

```text
worker_quality_multimodality
```

因为分歧可能来自未冻结的目标定义，而不是一部分工人不会标。

## 建议冻结的工作流合同

你目前最需要的不是再增加一个模糊的 OOS subtype，而是建立三个正交判断轴。

**表示能力轴**

问题是：

> 假设完整三维几何已经知道，该空间能否被当前布局表示表达？

```text
in_scope
    单一主地面
    单一主天花板
    垂直墙面
    Manhattan 水平轴系
    可表达为当前支持的闭合 polygon

out_of_scope
    非 Manhattan 主墙
    多层主地面
    多层 enclosing ceiling
    atrium / stairwell hole
    无法由当前拓扑表示的开放空间
    其他 representation break
```

MatterportLayout 的构建本身排除了 corridors、stairs 等开放 3D 空间、非平地面、非 Manhattan 布局、室外和严重拼接伪影，说明该数据集所使用的 Scope 本来就比数学意义上的 Manhattan 更窄。citeturn18view1

**标注政策轴**

问题是：

> 遇到与相机空间连通的 opening 时，本研究究竟要哪一种布局？

```text
enclosed
    在歧义 opening 处停止
    封闭最近的主要空间

extended_visible
    穿过无门 opening
    纳入 opening 内所有有结构证据的可见区域
    不补全无法唯一确定的隐藏末端
```

Paper A 若重点是工人能力测量，最稳健的方案不是强行选一边，而是为 opening ambiguity 建立双参考：

```text
reference_enclosed
reference_extended_visible
```

对于非歧义图，两者可以相同；对于当前这类图，两者分开。

**可观测性轴**

问题是：

> 在给定工人实际看到的信息条件下，完整几何是否可唯一恢复？

```text
fully_visible
unique_manhattan_inference
ambiguous_occluded_extension
insufficient_evidence
```

可以形式化为候选布局集合：

\[
\mathcal H_t=
\left\{
L:
L\text{ 满足可见图像证据、Manhattan约束和冻结政策}
\right\}.
\]

相应处理为：

\[
|\mathcal H_t|=1
\Rightarrow
\text{hard-single reference},
\]

\[
1<|\mathcal H_t|<\infty
\text{ 且候选可被专家明确列出}
\Rightarrow
\text{hard-multi reference},
\]

\[
\mathcal H_t
\text{ 高度欠定或无法穷举}
\Rightarrow
\text{partial-visible / unresolved}.
\]

这一规则比“看不见就不标”或“Manhattan 下可以猜”严格得多。Shape-Net、Bi-Layout 以及多视图 panorama layout 研究均把遮挡或多视角互补作为需要专门建模的问题，进一步证明单视图隐藏空间不是天然确定量。citeturn22search11turn21view0turn22search5turn22search8

建议最终数据表至少加入：

```text
task_representation_scope
layout_policy
portal_type
observability_status
reference_class
reference_source
auxiliary_evidence_used
worker_information_condition
visible_boundary_mask
accepted_reference_ids
```

推荐枚举如下：

| 字段 | 推荐值 |
|---|---|
| `portal_type` | `hard_wall`, `transparent_wall`, `door`, `doorless_opening`, `internal_object`, `reflection_confounded`, `unknown` |
| `observability_status` | `fully_visible`, `unique_manhattan_inference`, `ambiguous_occluded_extension`, `insufficient_evidence` |
| `reference_class` | `hard_single`, `hard_multi`, `partial_visible`, `reference_suspect`, `not_applicable` |
| `reference_source` | `rgb_only_expert`, `rgbd`, `mesh`, `multi_view`, `dataset_original`, `adjudicated` |
| `worker_information_condition` | `single_rgb_panorama`, `rgbd`, `multi_view`, `model_assisted` |

其中 `portal_type` 与 `layout_policy` 必须分开。例如一个 doorless opening 在 enclosed policy 下可以停止，在 extended-visible policy 下则继续。相反，一块透明玻璃若实际是固定 façade，应作为 hard wall；一块玻璃门则是 door；一个三折镜只是内部物体，不应成为房间 polygon 的结构墙。

## 当前样例、GT与工人评分的具体处理

基于你提供的图像，我对这一任务的建议处置如下。

**任务级判定**

```text
task_representation_scope = in_scope
```

目前没有足够证据表明真实空间必然违反 Manhattan、单主地面或单主天花板模型。问题主要是遮挡，而不是表示不能表达。

```text
portal_type = doorless_opening_or_unknown
```

向后延伸区域看起来可能与当前空间通过无门 opening 或开放通道连接，但反射面和前景隔断使结构判断受到干扰，应允许 expert review 后更新。

```text
observability_status = ambiguous_occluded_extension
```

可见证据支持一定程度的延伸，但完整终止墙和隐藏角点数量无法从当前图像唯一确定。

**在 enclosed policy 下**

可以在进入不可确定延伸之前封闭最近空间。此时稀疏 GT 可能是合法的 enclosed reference，但必须验证其封闭面确实遵循冻结规则，而不是为了凑四角而任意截断。Bi-Layout 明确承认这种“在歧义处停止”的标注类型。citeturn21view0

**在 extended-visible policy 下**

应纳入能够从图像确认的向后延伸部分，包括可见 floor、ceiling 和侧墙连续区域；但对于被隔断完全遮挡的远端，不应要求工人选择一个未经证据支持的深度或转角。更密集的工人标注可能更接近 extended-visible，但若它包含了不可见末端的任意闭合，也不能自动视为正确。

**在 dataset-complete policy 下**

应调用 Matterport3D 的 depth、camera pose、mesh、floor plan、region annotation 或同一位置的邻近 panorama 仲裁隐藏结构。Matterport3D 官方数据确实提供颜色、深度、相机位姿、纹理 mesh、building floor plan 和 region annotation，因此具备进行这种二次审查的条件。citeturn20search7

但应同时检查反射区域。Mirror3D 专门基于 Matterport3D、NYUv2 和 ScanNet 收集镜面平面，说明镜面是原始传感深度和重建中的显著误差来源；透明物体研究同样指出反射和折射可能产生错误或噪声深度。citeturn23search20turn23search0

因此仲裁优先级应是：

```text
多视图 mesh / 全局 floor plan 一致性
>
邻近 panorama 与相机位姿
>
非反射区域的可靠 depth
>
当前 panorama 的 RGB 视觉推断
>
单独依赖镜面或玻璃区域的 raw depth
```

**对工人 \(Q_{GT}\) 的评分**

对于 `hard_single`：

\[
Q_{t,u}=IoU(A_{t,u},G_t).
\]

对于两种事前认可政策对应的 `hard_multi`：

\[
Q_{t,u}
=
\max_{g\in\mathcal G_t}
IoU(A_{t,u},g),
\]

其中 \(\mathcal G_t\) 必须在查看工人身份和分数之前冻结，不能在结果出来后为某个工人补 reference。

对于 `partial_visible`：

不应计算完整 3D IoU，而应仅在可观测 mask 上计算 ceiling-wall、floor-wall 或 wall-wall boundary error。HorizonNet 的输出本身就是逐列 floor-wall boundary、ceiling-wall boundary 和 wall-wall existence，因此可以自然地建立 `visible_boundary_mask` 或 column-wise observable metric。citeturn17search2

例如：

\[
Q^{visible}_{t,u}
=
1-
\frac{
\sum_x M_t(x)\,
d\!\left(B_{t,u}(x),B^{ref}_t(x)\right)
}{
\sum_x M_t(x)
},
\]

其中 \(M_t(x)=1\) 只表示该列边界具有充分可观测证据。

**对 LOO 共识的处理**

这一任务不应让 enclosed 和 extended 标注互相竞争同一个共识簇。应先按政策兼容性或参考类型进行归类：

```text
enclosed-compatible cluster
extended-visible-compatible cluster
unsupported-hidden-completion cluster
```

如果前两个簇都获得实质支持，应标记：

```text
task_consensus_status = protocol_multimodal
```

不能根据哪一簇人数更多就定义另一簇为低质量。小样本 crowd 的多数意见可能形成错误的自我强化，共识论文自身也明确警告了这一风险。fileciteturn0file2

**对 structural failure 的处理**

以下现象不能在本任务上自动算工人结构失败：

- enclosed 与 extended 导致角点数不同；
- 工人因隐藏区域欠定而选择不同合法闭合；
- 工人仅画可见部分，而工具强制其补闭合；
- 工人拒绝猜测隐藏末端。

真正可以计入 structural failure 的是：

- 自交；
- ceiling-floor pairing 错乱；
- 非法序列化；
- 明显违反已冻结 Manhattan 轴；
- 在完全可见、唯一 reference 区域遗漏必要墙体；
- 与任何认可 reference 都不兼容。

## 最终可执行规则与关键文献

建议将 worker instruction 冻结为以下内容：

> 标注相机所在的结构布局单元，而不是依据卧室、走廊或衣帽间等语义名称划分。
>
> 玻璃、镜面或透明性本身不决定边界；应判断该构件是固定围护墙、门、无门 opening 还是内部物体。
>
> 当使用 enclosed policy 时，在无法唯一确定的 opening 处停止并封闭最近的主要空间。
>
> 当使用 extended-visible policy 时，继续纳入 opening 内所有具有可见结构证据的区域。
>
> 只有当隐藏角的位置与拓扑可由可见墙面、Manhattan 延长关系和协议约束唯一确定时，才能推断隐藏角。
>
> 如果空间仍符合布局表示，但完整隐藏边界无法唯一确定，应选择 `Boundary unclear / ambiguous occluded extension`，而不是 OOS，也不得凭空补角。
>
> OOS 只用于空间本身无法由当前单地面、单天花板、Manhattan 闭合布局表示的情况。

对你当前这张图的最终结论是：

> **向后延伸应被承认为真实的标注问题，但从当前单张 panorama 看，远端完整拓扑不应被视为唯一可恢复。它应当是 in-scope 的 opening/occlusion ambiguity，而不是玻璃导致的 OOS。稀疏 GT 与密集工人标注在没有冻结 enclosed/extended policy 前不能直接比较优劣。**

关键原始文献如下：

| 完整引用 | 对工作流的直接意义 |
|---|---|
| Yu-Ju Tsai, Jin-Cheng Jhang, Jingjing Zheng, Wei Wang, Albert Y. C. Chen, Min Sun, Cheng-Hao Kuo, and Ming-Hsuan Yang. 2024. “No More Ambiguity in 360° Room Layout via Bi-Layout Estimation.” *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 28056–28065. | 直接定义 enclosed 与 extended 两类合理布局，并证明 MatterportLayout GT 存在 opening policy 混用。citeturn21view0 |
| Chuhang Zou, Jheng-Wei Su, Chi-Han Peng, Alex Colburn, Qi Shan, Peter Wonka, Hung-Kuo Chu, and Derek Hoiem. 2021. “Manhattan Room Layout Reconstruction from a Single 360° Image: A Comparative Study of State-of-the-Art Methods.” *International Journal of Computer Vision*, 129:1410–1431. | 说明 MatterportLayout 的 Scope、PanoAnnotator 标注流程、RGB-D 辅助信息以及大量 GT 后续修订。citeturn18view1 |
| Steve Cruz, Will Hutchcroft, Yuguang Li, Naji Khosravan, Ivaylo Boyadzhiev, and Sing Bing Kang. 2021. “Zillow Indoor Dataset: Annotated Floor Plans With 360° Panoramas and 3D Room Layouts.” *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 2133–2143. | 提供 visible、complete、door、opening 与多 panorama 合并的成熟参照。citeturn22search3turn17search0 |
| Shang-Ta Yang, Chi-Han Peng, Peter Wonka, and Hung-Kuo Chu. 2018. “PanoAnnotator: A Semi-Automatic Tool for Indoor Panorama Layout Annotation.” *SIGGRAPH Asia 2018 Posters*, Article 34:1–34:2. | 证明原始 layout GT 是自动 2D/3D 特征、人工编辑和几何 refinement 的联合产物，不等同于 crowd 单图点击。citeturn20search0turn20search2 |
| Cheng Sun, Chi-Wei Hsiao, Min Sun, and Hwann-Tzong Chen. 2019. “HorizonNet: Learning Room Layout With 1D Representation and Pano Stretch Data Augmentation.” *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 1047–1056. | 为逐列可见边界评分和 observable mask 提供直接表示基础。citeturn17search2 |
| Fu-En Wang, Yu-Hsuan Yeh, Min Sun, Wei-Chen Chiu, and Yi-Hsuan Tsai. 2020. “LayoutMP3D: Layout Annotation of Matterport3D.” *arXiv:2003.13516*. | 明确 layout annotation 与 Matterport3D ToF depth 同时存在，可用于 GT 复核，但二者不是同一种真值来源。citeturn20academia48 |
| Mizuki Tabata, Kana Kurata, and Junichiro Tamamatsu. 2023. “Shape-Net: Room Layout Estimation From Panoramic Images Robust to Occlusion Using Knowledge Distillation With 3D Shapes As Additional Inputs.” *CVPR Workshops*, 3552–3561. | 说明遮挡下的隐藏 layout 是需要额外三维先验和专门建模的困难问题。citeturn22search11 |
| Jiaqi Tan, Weijie Lin, Angel X. Chang, and Manolis Savva. 2021. “Mirror3D: Depth Refinement for Mirror Surfaces.” *Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition*, 15990–15999. | 说明镜面区域会污染 Matterport3D 等 RGB-D 数据的原始深度，不能机械地把镜面 depth 当作无误 GT。citeturn23search20 |