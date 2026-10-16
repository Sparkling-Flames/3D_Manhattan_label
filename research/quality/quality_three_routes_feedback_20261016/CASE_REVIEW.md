# 24例评论与独立解释

原始comment原文保留；档位只作辅助。A/B/C指GQS三路线，旧B8L2单列。分值来自被审查Pro244快照，未重新调参。解释为本线程结合原图、叠线与三维的判断，不冒充用户原话。

|例子|图片|旧B8L2|GQS A|GQS B|GQS C|底面IoU|
|---|---|---:|---:|---:|---:|---:|
|K01|uNb9QFRL6hY-14|80.30|87.10|87.35|77.87|0.873|
|K02|yqstnuAEVhm-10|83.74|85.90|88.76|57.75|0.860|
|K03|yqstnuAEVhm-09|44.73|26.34|46.99|35.83|0.734|
|K04|7y3sRwLe3Va-21|33.90|15.68|49.01|27.01|0.649|
|K05|Z6MFQCViBuw-06|46.49|60.54|69.40|20.48|0.621|
|K06|uNb9QFRL6hY-45|83.87|88.56|90.98|86.38|0.935|
|K07|VFuaQ6m2Qom-10|57.38|74.27|56.98|51.63|0.817|
|K08|uNb9QFRL6hY-07|27.08|70.84|74.45|49.71|0.735|
|K09|VFuaQ6m2Qom-04|55.78|9.76|60.40|51.11|0.850|
|K10|VFuaQ6m2Qom-04|52.82|12.26|61.81|52.06|0.863|
|K11|VFuaQ6m2Qom-04|76.17|76.16|58.00|49.44|0.831|
|K12|uNb9QFRL6hY-53|50.36|30.53|83.83|64.23|0.886|
|C01|wc2JMjhGNzB-53|40.18|54.84|63.50|50.03|0.773|
|C02|VFuaQ6m2Qom-07|72.61|70.78|58.16|56.97|0.861|
|C03|uNb9QFRL6hY-12|58.85|65.97|85.41|73.75|0.920|
|C04|wc2JMjhGNzB-59|98.94|99.01|99.03|99.04|0.990|
|C05|uNb9QFRL6hY-40|86.96|89.50|91.06|91.05|0.957|
|C06|uNb9QFRL6hY-09|49.40|44.52|66.11|33.81|0.721|
|C07|wc2JMjhGNzB-60|39.18|57.96|60.18|39.86|0.589|
|C08|X7HyMhZNoso-19|79.91|89.34|91.20|88.38|0.924|
|C09|7y3sRwLe3Va-04|94.04|95.25|96.02|93.23|0.952|
|C10|yqstnuAEVhm-08|63.57|76.97|74.34|62.53|0.860|
|C11|uNb9QFRL6hY-48|90.52|92.05|93.07|86.06|0.920|
|C12|uNb9QFRL6hY-78|82.56|87.68|88.22|72.08|0.889|

## K01 uNb9QFRL6hY-14

记录：`R03058`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_23ed105b1f0f48bbb6ec025df9d313e7.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 就在较好 这个阈值的边上,很接近较好

辅助档位：较好与一般之间。

独立解释：整体较近参考，主要为有限的范围定位差；不据阈值边缘措辞设固定分数。

## K02 yqstnuAEVhm-10

记录：`R03278`。原图：[打开](../../../data/mp3d_layout/test/img/yqstnuAEVhm_4ab11dce32f346b2becac29e0ac6e526.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 2d上很接近,3d上和gt略有偏差.单单来看独立3d还不错.  和gt来比,勉强站在较好的边上

辅助档位：较好。

独立解释：自身三维规整且近GT，仍有范围偏差；C明显更严，需检验边界尺度及叠加。

## K03 yqstnuAEVhm-09

记录：`R00166`。原图：[打开](../../../data/mp3d_layout/test/img/yqstnuAEVhm_48447297e8444171a5db34ccf38bc229.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 明显的墙角没标(r6),包括r0 r1 r2 r3 这里,不过这里不标还情有可原  . 

辅助档位：一般。

独立解释：确有结构遗漏并形成替代斜连接，不能只按漏点数量评价；可理解的操作原因不免除参考误差。

## K04 7y3sRwLe3Va-21

记录：`R01299`。原图：[打开](../../../data/mp3d_layout/test/img/7y3sRwLe3Va_b47475370e824b9e923a4a96bc98e1e3.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 遗漏了4对墙角.但是剩余点标的还行

辅助档位：一般与较差之间。

独立解释：剩余点可接近GT，但遗漏后形成长斜墙；点位与最终连线分开解释，完整GT不变。

## K05 Z6MFQCViBuw-06

记录：`R00726`。原图：[打开](../../../data/mp3d_layout/test/img/Z6MFQCViBuw_59aed460238643f48f593e9b9ba1c17d.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 2d差距不大,就是bottom y 整体偏高,x坐标都是差不多的, 这也导致了和gt有所差距  .但是单单看 3d表现还行

辅助档位：一般。

独立解释：二维底点的有限位移对应明显三维范围膨胀；自身方正不能抵消与GT差异。

## K06 uNb9QFRL6hY-45

记录：`R00002`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_8b6f1b0b025848b482e747ab6a027b97.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 已经标的角点和gt都很接近,但是最后两对角点没标,有点遗漏,导致3d上也有瑕疵,墙面不是这么正交

辅助档位：较好。

独立解释：遗漏两对小结构，整体仍近GT；遗漏数量不是统一严重程度。

## K07 VFuaQ6m2Qom-10

记录：`R00215`。原图：[打开](../../../data/mp3d_layout/valid/img/VFuaQ6m2Qom_f0be18aa2f1d4aa2b6adf355a86f34b8.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 大幅简化的标法.但看 3d标注很不错,但是遗漏很多细节.你也不能完全说他错了.  这个质量我也不太好衡量

辅助档位：一般。

独立解释：规整粗化保留主空间但缺较多细节，需同时表达正确部分与结构不完整。

## K08 uNb9QFRL6hY-07

记录：`R02826`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_104d12b732794414a42edd37ac554bff.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 右边两对角点标了 柜子后面的地方,也不能说错. 但是光看3d表现也不好, 单看 和gt差距也有

辅助档位：一般。

独立解释：柜子后方的解释可说明动机，但本次固定GT下仍属位置和范围偏差，不换参考。

## K09 VFuaQ6m2Qom-04

记录：`R00751`。原图：[打开](../../../data/mp3d_layout/valid/img/VFuaQ6m2Qom_5fb269a812f349b4bc2ad5dfac000b85.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 标了一点细节,但是没标全,导致点位之间的连接是斜的,墙面不正交,整体特别奇怪

辅助档位：一般。

独立解释：部分细节造成真实斜连接和奇怪三维；不能奖励意图，也不能凭此确认A约10分的处罚幅度。

## K10 VFuaQ6m2Qom-04

记录：`R01933`。原图：[打开](../../../data/mp3d_layout/valid/img/VFuaQ6m2Qom_5fb269a812f349b4bc2ad5dfac000b85.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 想标细节,但是没标好,有些遗漏,有些不准确导致3d 很奇怪

辅助档位：一般。

独立解释：同时存在遗漏和歪连，需检查远距角点匹配是否承担同一结构作用；不据距离单独断言错配。

## K11 VFuaQ6m2Qom-04

记录：`R00550`。原图：[打开](../../../data/mp3d_layout/valid/img/VFuaQ6m2Qom_5fb269a812f349b4bc2ad5dfac000b85.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 大幅简化的标法.但看 3d标注很不错,但是遗漏很多细节.你也不能完全说他错了.  这个质量我也不太好衡量

辅助档位：一般。

独立解释：规整矩形遗漏许多结构；不能预定其必然比K09/K10差，也不能忽略其遗漏。

## K12 uNb9QFRL6hY-53

记录：`R03149`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_a728d2eef41b449f82357899de802dd3.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 最右边标的两对点很奇怪,最右边虽然注意到了 墙面凸起(gt没标),但是应该标两对点,而不是一对点

辅助档位：一般。

独立解释：GT外额外角形成斜切并影响对应，按实际几何改变评价，不按应补两对点建立新GT。

## C01 wc2JMjhGNzB-53

记录：`R02104`。原图：[打开](../../../data/mp3d_layout/test/img/wc2JMjhGNzB_b41b10699d614f24851b56a9a0e743c6.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 标注了 厕所空空(我认为不该标),而且墙面细节和最右边停止的点标的都是不对的

辅助档位：一般与较差之间。

独立解释：额外空间、停止位置和细节共同偏离指定GT，属于范围及结构问题。

## C02 VFuaQ6m2Qom-07

记录：`R01078`。原图：[打开](../../../data/mp3d_layout/valid/img/VFuaQ6m2Qom_ad4c387f8175498491966703c8441e0d.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 这细节算是这张图里所有人中标的比较好的,虽然仍有些不足

辅助档位：较好与一般之间。

独立解释：同图人群中细节较好的相对评价不等于绝对高质量；仍有遗漏及形变，B转角差需归因。

## C03 uNb9QFRL6hY-12

记录：`R03050`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_1b7bf6673ca74809a141b57da1d6357f.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 最左边是对无用的角点.在"一般"中算是 比较好的

辅助档位：一般。

独立解释：额外点并非完全共线无影响，还伴随墙线偏斜；按实际折线改变而非点数处罚。

## C04 wc2JMjhGNzB-59

记录：`R00045`。原图：[打开](../../../data/mp3d_layout/test/img/wc2JMjhGNzB_dc4a9f470b834de1983c7e605ff06b2e.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 几乎完美

辅助档位：较好。

独立解释：几乎重合的正向锚点，三路线均接近99分。

## C05 uNb9QFRL6hY-40

记录：`R03111`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_748279b5d6e740c4b2cba9fc78d6fc62.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 很接近了

辅助档位：较好。

独立解释：整体接近，仍有有限角度偏差；不为接近措辞强行给满分。

## C06 uNb9QFRL6hY-09

记录：`R03037`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_13a430466eb64e2087e7fb5acde7a398.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 想标右边的墙面拐角(gt没标),但是没标好,而且应该标两对点

辅助档位：一般与较差之间。

独立解释：添加GT未建模结构同时导致明显范围及形状损害；评价结果，不奖励补细节动机。

## C07 wc2JMjhGNzB-60

记录：`R02366`。原图：[打开](../../../data/mp3d_layout/test/img/wc2JMjhGNzB_dda6efcba51c40de8552408953719515.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 偏离比较大

辅助档位：一般与较差之间。

独立解释：虽较规整，底面范围明显偏离GT；低重合确有对应几何原因。

## C08 X7HyMhZNoso-19

记录：`R01734`。原图：[打开](../../../data/mp3d_layout/test/img/X7HyMhZNoso_b6f452209a62499795e5bd137214a7f9.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 想标中间隔墙(gt没标),但是没标好,应该是4对点的

辅助档位：较好与一般之间。

独立解释：新增点对主轮廓影响较小，粗尺度下消退；高分可解释，不因应补四对点评论建立隐含参考。

## C09 7y3sRwLe3Va-04

记录：`R00478`。原图：[打开](../../../data/mp3d_layout/test/img/7y3sRwLe3Va_1410b021e1c14f529188eb026fbb369a.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 很不错

辅助档位：较好。

独立解释：与GT接近的正向锚点，三路线均给高分。

## C10 yqstnuAEVhm-08

记录：`R01428`。原图：[打开](../../../data/mp3d_layout/test/img/yqstnuAEVhm_4642492bb42d40debb1a3bad0ea7a24f.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 这图确实很难,他确实忽略了一些细节,也标歪了一些地方

辅助档位：一般。

独立解释：困难解释操作背景，遗漏和偏斜仍按同一GT标准衡量，难度不直接调分。

## C11 uNb9QFRL6hY-48

记录：`R03134`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_9b675f28ab5f4345bf06ed5c77097426.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 很接近,虽有一点偏差. 应该是  属于中等的较好

辅助档位：较好。

独立解释：整体接近，主要为有限定位偏差。

## C12 uNb9QFRL6hY-78

记录：`R02940`。原图：[打开](../../../data/mp3d_layout/test/img/uNb9QFRL6hY_e0b8950793b447bd8b9f916e98e849d1.png)。完整作答和固定参考见`reviewed_snapshot.json`中同题号。

用户comment：

> 属于偏低的较好,有一定的偏差

辅助档位：较好。

独立解释：存在一定范围偏差但结构较规整，C比A/B更严；需统一定位尺度。
