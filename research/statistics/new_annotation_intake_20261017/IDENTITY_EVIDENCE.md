# Project98七个源账号与既有W身份的证据核验

核验日期：2026-10-17。只读原导出、当前bundle与活动日志；本文件不修改主输入、原导出、人员资格或评分。不输出姓名、邮箱或其它无关个人信息。

**结论：现有证据足以支持Project98七个账号沿用既有W身份。依据是“同一项目导出＋93→98同一页面session桥＋Project93原件到W的唯一对应”，不是单凭数字相同。没有需要另外逐人确认的账号；不要求七人分别拥有跨项目session。** 此结论是研究源账号命名空间映射，不是额外的自然人实名认证。

本报告补充先前audit.json中“仅同号候选、采集实例待核”的状态；先前未核到的项目层实例桥现已查实。该JSON与主输入未由本子任务回写，主线程可据本报告更新正式接入映射。

## 一、Project98是同一个项目导出

来源：`export_label/新增中文标注/project-98-at-2026-10-16-13-59-e351a09f.json`。

已逐条验证：19个task的project均为98；70条annotation各自的project=98、task与所属task.id一致；completed_by集合恰为1、6、8、10、12、15、17，分别各10条。没有从多个采集实例文件按账号数字拼成同一个项目，也没有发现同一source_id对应多个账号。

活动日志70个`98|task|annotator`键与这些作答的账号／任务逐键一致。原导出与日志使用同一Project98命名空间。

## 二、93→98的项目层实例桥

同一个session：`1789983329125-ab5009b5c6a748`。

对`active_logs/new_server/`递归核对，该session共72条：Project93为9条、Project98为63条，annotator_id始终为6，script_version始终为manual_scope_only_20260913_v10，没有在该session中切为另一个账号。

|来源位置|项目／任务／账号|客户端UTC时间|
|---|---|---|
|`active_logs/new_server/active_times_2026-09-21.jsonl:41`|93／3599／6|2026-09-21T09:36:21.183Z|
|`active_logs/new_server/active_times_2026-09-21.jsonl:48`|93／3605／6|2026-09-21T09:38:03.515Z|
|`active_logs/new_server/active_times_2026-09-23.jsonl:1`|93／3605／6|2026-09-23T06:11:17.131Z|
|`active_logs/new_server/active_times_2026-09-23.jsonl:2`|98／3674／6|2026-09-23T06:15:29.110Z|
|`active_logs/new_server/active_times_2026-09-23.jsonl:64`|98／3691／6|2026-09-23T06:47:27.751Z|

日志location_path分别为`/projects/93/data`与`/projects/98/data`。正式脚本`tools/label_studio/official/ls_userscript_annotator.js:3243-3253`在当前页面脚本实例初始化时生成新的随机sessionId，代码未从旧日志或用户编号构造它，也没有将其作为跨实例账号别名。因此这里不是两个来源中碰巧都出现账号6，而是同一计时页面实例在两个项目之间连续使用账号6的直接证据。

项目93任务3599的原件annotation7500 completed_by=6，精确对应当前bundle对象`new_93_3599_7500_W006`。原件来源为下节Project93导出。它把页面session桥锚定到既有W006；Project98任务3674中的annotation7503 completed_by=6又将该桥锚定到本批作答。

服务器接收时间为naive墙钟，未用于证明先后；表中只使用客户端epoch timestamp转换的UTC。没有仅凭`new_server`目录名称、相同图片URL或相同数字声称同实例。

## 三、旧Project93的七个账号均有原件到W的准确对应

旧导出：`export_label/新增中文20图/project-93-at-2026-09-21-09-42-4609125d.json`。

已用当前`load_current_bundle()`的source.project／source.task／source.annotation精确定位原导出的annotation，读取其真实completed_by，再与对象worker_id核对。对该Project93中涉及这7个账号的全部当前对象检查，均只有下列单一W对应，没有冲突。下表每项列一个可复核示例，不用旧分析脚本中`W{数字}`的格式化语句替代原件核验。

|Project98 completed_by|既有W身份|Project93原件task／annotation示例|Project98 source_id示例|
|---:|---|---|---|
|1|W001|3577／6868|ls98:3674:7571|
|6|W006|3575／7064；另有session桥3599／7500|ls98:3674:7503|
|8|W008|3579／7393|ls98:3674:7521|
|10|W010|3578／7255|ls98:3674:7560|
|12|W012|3576／7134|ls98:3674:7540|
|15|W015|3576／7196|ls98:3674:7531|
|17|W017|3578／6920|ls98:3674:7552|

账号6具有个人页面session直接桥，其余六个账号没有各自跨项目session，但这不妨碍项目层采用：它们与账号6同属一份Project98导出，项目层实例已与93连接，旧Project93又有同一账号命名空间下的全部七项原件映射。把“每个账号都必须跨项目保留同一个页面session”设为额外门槛，没有必要。

## 四、反例检查与采用边界

在本批导出、对应日志、旧93原件和当前bundle中，未发现Project98账号重建、同账号映射不同W、同source_id跨账号冲突或93→98桥中账号切换的反例。原导出没有直接携带采集数据库UUID或用户姓名／邮箱；本结论采用已有页面实例连续性和项目命名空间证据，不虚构服务器UUID。没有为寻找个人信息另行扫描其它用户资料。

七个映射均不指向既有排除W019或W026。**这不自动授予新增作答的清洗、独立性、几何、排序、参考或时间分析资格。** 既有W参与过同一图片时，后续必须按该W核对历史暴露与重复作答，不能把新项目号当成新增独立人员；对同图重复也不能挑较高分的一份。

新增两图的“中等（偏简单）”规划裁定与身份映射分开。scope仍为原导出的in_scope／out_of_scope，不因账号映射自动绑定参考几何。当前源账号证据不再需要用户另外逐人确认；若后续出现实际数据库重建／账号重分配原件，应以该反例重新核对受影响部分，而非静默沿用数字映射。

本次新增仅为本证据文档；无主数据或原始文件写入，无截图。只读断言检查包括19task／70annotation项目身份一致、7账号集合、Project93全部相关原件映射唯一、同session项目／账号集合与源行位置，均通过。
