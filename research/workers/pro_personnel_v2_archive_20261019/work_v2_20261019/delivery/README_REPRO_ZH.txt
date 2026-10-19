v2人员分类与融合共识｜复现说明
===========================

一、先阅读

research_report_v2_zh.html（另保留research_report_zh.html）：主判断、完整证据、失败与限制。
personnel_fusion_v2_viewer.html：单文件离线展示，包含196图全部7302份合格几何、
229池四套分簇、60人及22折训练画像、57,062个真实团队请求的浏览子集、583条完整真实路径。
该HTML约81MB，建议桌面现代浏览器打开；需要DecompressionStream支持。它不联网。
浏览子集在VIEWER_SELECTION_MANIFEST中明示；总体统计不以该显示子集计算。
中文人员CSV为全量描述，不是测试建筑外选人时直接使用的表。预测读取fold_profiles。

二、四个归档如何放置

将“方法与结果A”“方法与结果B”“团队几何A”“团队几何B”四个ZIP解压至同一个新目录，保留相同路径。
合在一起包含固定main源快照repo_main_20261019/和工作目录work_v2_20261019/。
两个方法结果包合起来包含全部统计明细、画像、审计、全局团队CSV、全部成对比较、代码与冻结注册。
两个几何包只分担按pool保存的真实最终状态、成员、请求结果与原生节点来源证据。
每文件上限512MiB，因此按文件均衡无损拆分方法结果包；这不是新版本、不同行为组或新实验。
没有使用模拟或生成的独立真人标注。每个ZIP均可独立解压，不需二进制拼接或专用解压工具。
每个文件归属与SHA详DELIVERY_MANIFEST.json；文件缺少时显示缺少哪个包，不补造内容。

三、运行环境

本轮Python为3.12.14。安装requirements.txt列出的数值与制图库。
数值重放使用Linux／WSL，或支持fcntl.flock的POSIX Python环境；原生Windows可读HTML和表格，
完整计算请在WSL运行。该标准库锁接口不是pip依赖，不能仅靠安装requirements补齐。
若只做数值分析，不需浏览器、原图或JavaScript依赖。字体用于生成中文PNG/SVG，许可证随附。
原图Release压缩包与完整原图不重复放入大包；其官方下载脚本和逐图/压缩包SHA已附。
读取已交付HTML不需要再下载原图。重新构建HTML才需要本地原图或明确运行--fetch-originals。
可选展示交互检查使用Node 24.19.0、jsdom 30.1.3、@napi-rs/canvas 0.1.100；
在presentation目录npm install后运行npm run qa。它只做DOM和原生canvas检查，不是浏览器布局测试。

四、统一入口

在新解压目录运行：

  python work_v2_20261019/REPRODUCE.py --stage verify
  python work_v2_20261019/REPRODUCE.py --stage verify --full-hash

前者核对固定仓库源及代码，后者核对完整交付载荷。两者仅验文件，不声称重新计算。
先查看将执行的命令（无写入）：

  python work_v2_20261019/REPRODUCE.py --stage all

实际全流程重新计算（请在独立解压副本里执行）：

  python work_v2_20261019/REPRODUCE.py --stage all --execute --fresh-fusion --jobs 3

--fresh-fusion将该副本的旧pools移入带时间后缀备份，不删除；迫使完整真实团队重新计算。
不加该参数时原生融合引擎会复用相同上下文/成员集合缓存，actual_new_fusions如实记录新调用数量。
不能把缓存复用称为144253个融合已重新运行。新计算、比较和下游分析按顺序执行，禁止并行写同目录。

阶段选项：audit、profiles、clusters、fusion、comparisons、summaries、reverse、report、viewer。
audit从冻结已审计坐标开始，不重建采集、原始导出、全部历史人工审核。
profiles独立运行Q/T/难度9步，包括v1复核和双排除画像。
clusters重建局部标法分区，保留同点数、循环/反向语义和9°/12°敏感性。
fusion只重放已登记真实名单与顺序，不按新输出重调选人。
comparisons保留失败；summaries按图和建筑汇总；reverse联合真实局部簇和楼外人员特征。
all不自动下载原图，也不自动运行体积较大的HTML构建。需要重建展示时执行：

  python work_v2_20261019/REPRODUCE.py --stage comparisons --execute --jobs 3
  python work_v2_20261019/REPRODUCE.py --stage viewer --execute --fetch-originals

第一步恢复省略的逐池比较表；入口在缺少它们时会明确停止，不会静默生成不完整比较页。

五、结果API

人员：profiles/records_flat.csv、full_profiles.csv、fold_profiles.csv、nested_fold_features.csv。
分簇：clusters/assignments.csv、pair_distances.csv.gz、CLUSTER_API.json.gz。
团队：fusion/team_results.csv主键request_id；team_id代表同池无序成员集合；顺序字段单独保留。
完整几何：fusion/pools/<pool_id>/states.json.gz顶层states，每项以team_id关联。
每池request_results.json.gz含全部评分分项、失败、时间、真实请求元数据。
与之重复的scores缓存不交付，已逐个团队逐字段比对零缺项；可从冻结几何重算。
全局比较：replacements、random_same_k、composition_comparisons、policy_comparisons、prefix_transitions。
比较保留两侧request/team ID，可回查成员、顺序和几何；失败团队未移出分母。

所有最终全局替换均来自初始固定背景设计；扩展无新固定背景请求。因此若省了重复INITIAL副本，
统一入口在reverse前将最终replacements无损复制为兼容别名INITIAL_replacements。
这不是不同数据版本；两份逻辑内容一致已在原始收据核查。
为节省空间，逐池重复比较不额外打包；运行comparisons可从完整states重建这些浏览所需分池表。
读取现成HTML不需要分池比较文件。

swap_transfer完整模型预测保存在heldout_predictions_wide.csv.gz：270370事件一行，
无损涵盖原6370576个模型预测/真实值。可重建长表：

  python work_v2_20261019/clusters/compact_swap_predictions.py --expand-to work_v2_20261019/clusters/swap_transfer

六、已经完成的独立检查

GEOMETRY_REPLAY_CHECKS：全部9363完整、941底面、135不可计算；无参考/点位/评分重造。
INTEGRATED_STATISTICS_REPLAY：44/51原生表从最小源列计算并逐值通过；余7表缺旧生成源，明确未复放。
profiles/END_TO_END_REPRODUCTION：独立目录9步骤，48/48数值表一致。
clusters/FINAL_VALIDATION：14个gzip全流CRC通过，完整宽预测重算16296逐图误差等价。
fusion/FINAL_RUN_RECEIPT：144253不同集合实际融合，五表双新进程CRC/字段/行数/SHA通过。
presentation/qa为Node DOM＋原生canvas检查，不是实际浏览器布局自动化；12例视觉范围另有收据。
个别压缩文件缺尾及修复过程保留；已知并发写原因与未确定根因分开记载，未改统计设计。

七、不能由本轮计算升级为已证明的内容

没有复现完整采集流程；没有全量确认初始化修好；没有OOS人员scope金标；没有新人工验收全部环。
没有证明永久人员类型或同类完全互换；目标图实际簇属于事后/oracle，不能冒充预测选人。
结果阈值是研究建议；用户许可执行与保存并不自动批准某个新考核、参考或融合规则。

可读运行证据见run_evidence_v2.html。最终文件列表和归档哈希见交付收据。
