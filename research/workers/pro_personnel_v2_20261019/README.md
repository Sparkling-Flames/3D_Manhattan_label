# v2人员研究输入索引

用户自行提交main，给Pro的交接内容只需[提示词](../../../docs/thesis_main/Pro_v2人员细类与反向分簇研究提示词_20261019.md)。本目录是研究上下文和索引，不是新交接ZIP。

- `INPUT_MANIFEST.json`：研究消费所需路径、分母和可用性。
- `analysis_context.json.gz`：匿名化的261图难度/场景、334个参考及既有直接关系上下文。
- `IMAGE_INDEX.csv`：原图Release位置与预览可用性。旧Release覆盖259张当前研究图；`2t7WUuJeko7-02/-03`仅提供预览，数值几何不缺。
- `SCORE_REPLAY_CHECKS.json`：从匿名逐份证据及指定参考重算的8个分层样例，最大分差0；不是重新全量评分的证明。

完整逐份资料在[证据包](../../statistics/v2_evidence_audit_20261019/README.md)，交叉表与缺口在[综合统计](../../statistics/v2_integrated_analysis_20261019/README.md)。原始账户导出、日志和本地缓存不属于这些匿名研究载荷。历史来源生成器仍有本地依赖，不声称采集全过程已便携复现。

在仓库根执行以下命令可从匿名压缩输入重建完整研究台的本地显示载荷，不需要原始账户数据：

```powershell
python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019
```

随后可直接打开研究台`index.html`，不依赖HTTP服务。原图未在本地时，视觉查看仍需相应图片资产。可再生CSV、未压缩大表及显示分片已纳入Git忽略，代码、字段合同、匿名压缩研究证据及说明保留。
