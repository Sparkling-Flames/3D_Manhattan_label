# AC 六个直接对手的既有人工顺序复用补核

## 结论

**新增指定的六个端点均没有可直接复用的已确认人工顺序。** 已读取它们原先保存的冻结节点，分别与本次 57 组及历史 33 个 accepted 顺序核对。同图候选共比较 16 次；完整点对坐标集合、节点 ID 与坐标绑定的精确匹配均为 0。没有生成排序、重新融合或评分，也没有修改已完成的 `ac_peer` 核心材料。[检查回执](CHECKS.json)

这六端涉及 7 个不同登记事件、11 条 Q 翻向统计记录和 15 条“翻向条件×事件”引用。它们均在已确认 57 组之外，均为至少 4 节点的 `no_connection`，且同一事件的另一端在 57 组内。与此前已经核查的两个 wc2-26 RAW3 C 端合计，本次被指出的八个直接对手均未发现漏用现有适用绑定的证据。

该结论只解决“是否漏用了已有顺序”。这些端点的真实 Q 仍缺失，人工处理机会仍不完整；不能据此声称完整 AC 登记队列已获同等人工处理，或推断所有其它残余端点均没有可复用顺序。

## 精确核查结果

下表的“差异”是对同节点数候选，将完整点对按坐标排序后所得最大坐标绝对差的最小值，仅用于证明它们不完全相同，不用于近似匹配或移植顺序。坐标沿用冻结的 1024×512 标注空间。

|残余团队完整身份|节点数|57 中同图候选|旧 33 中同图候选|与同节点数候选的最小差异（像素）|精确匹配|
|---|---:|---:|---:|---:|---:|
|`uNb9QFRL6hY-14__manual__a49483b09b__22afa302626e9568a313`|5|1|0|2.004157|0|
|`wc2JMjhGNzB-26__manual__other_space_25__aded3cfb3abdc44b9bd3`|7|3|0|12.227390|0|
|`wc2JMjhGNzB-26__manual__other_space_25__f67d7dd1e0f1832854e1`|7|3|0|9.843043|0|
|`wc2JMjhGNzB-26__manual__other_space_25__86b5e7542694daa077c3`|7|3|0|6.084557|0|
|`wc2JMjhGNzB-26__manual__other_space_25__6c237b9d1101dc208d66`|7|3|0|9.793047|0|
|`wc2JMjhGNzB-26__manual__other_space_25__b80f6ab07a23aaed22a2`|6|3|0|不适用：三个候选均为 7 节点|0|

完整候选逐对比较保存在 [SAME_IMAGE_BINDING_COMPARISONS.csv](SAME_IMAGE_BINDING_COMPARISONS.csv)。[SIX_ENDPOINT_REUSE_RESULTS.csv](SIX_ENDPOINT_REUSE_RESULTS.csv) 同时记录参考身份、参考版本、全部关联事件 ID、翻向记录 ID 和已处理对手的完整团队身份。有限输入范围与筛选回执见 [INPUT_EXTRACTION.json](INPUT_EXTRACTION.json)。

## 来源、方法与边界

筛选只使用 `ac/Q_RESIDUAL_ENDPOINTS_OWN.csv.gz` 中“失败端不在 57、对手在 57、无连接、节点至少 4”的队列，排除此前已核查的两个 wc2-26 RAW3 C 端，得到六个新端点。再与 `ac/ALL_AFFECTED_RESIDUAL_EVENT_STATES.csv.gz` 核对对应七个事件的两端团队、失败臂、节点数和状态；15 条条件引用的事件身份一致。输入子集与原表 SHA256 均已保存。

本次读取的是冻结提交 `ac395e703d1fef573d1ef3e105df0286d62a0468` 中已有的 prepared 节点，使用 `sha256(team_key)[:24]` 定位保存身份。六条 prepared 保留节点点对、票数、成员、原记录和参考，不改变其内容。它们从不可变 GitHub ZIP 分片按字节范围提取，核对 ZIP 中央目录、条目头、CRC 及提取文件 SHA256；没有下载并重新计算整个分片集合的 SHA256。[PREPARED_SOURCE_MANIFEST.json](PREPARED_SOURCE_MANIFEST.json) 明确记录这一验证边界。

当前 57 组按完整同图点对集合核对，并另核同一图片及参考上下文；历史 33 组登记 `order_import.json` 的冻结 Git blob 为 `40dc17ed0f8337ab3154e3b9cc7fa06c33e13ade`，这两张图片均没有历史 accepted 条目。未导出的浏览器本地判断未被假定存在。

无精确绑定可复用，所以本附录不触发既有顺序传播或重评分。若以后要求这些端点的实际辅助 Q，仍需要新的人工判断及相应几何验收；目前保留缺失和条件支持即可。RAW3 三个残余 C 的合法 Q 界限分析仍以此前 [ac_peer 回执](../ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json) 的特定条件为限，不能移用于本附录的其它条件。

## 复现

在 HOHONET 根目录运行：

```bash
python research/fusion/manual_order_acceptance_20261104/ac_peer_addendum/audit_specific_residual_reuse_20261104.py
```

默认只读取包内六条节点、输入子集和前批 57/33 登记。只有显式加 `--fetch` 才重新读取冻结 ZIP 中这六条 prepared；该选项仍不执行融合或评分。脚本只写本附录目录。文件散列见 [ARTIFACT_MANIFEST.csv](ARTIFACT_MANIFEST.csv)。

一手来源：Sparkling-Flames（仓库维护账号），2026，*3D_Manhattan_label / HOHONET v2.1*，GitHub 研究代码和数据仓库，[冻结提交](https://github.com/Sparkling-Flames/3D_Manhattan_label/commit/ac395e703d1fef573d1ef3e105df0286d62a0468)。各 ZIP 源文件的精确 URL 和 Git blob 见本附录来源清单；历史 33 组原始登记及来源摘要沿用 `ac_peer/source_cache`，没有重新编造或推断顺序。
