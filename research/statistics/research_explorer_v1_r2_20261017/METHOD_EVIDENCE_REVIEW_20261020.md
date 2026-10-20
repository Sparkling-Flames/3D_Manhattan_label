# 方法证据工作台：实现与验收记录

基于 main `1048c38b9cde986af14557d7af8fe5ea2c2f040a`。本次为工作台源码 PR，不表示既有私有云站已部署。显示修订与原 v2 数据快照分开；不更新生产评分、正式人员类别或参考裁定。

## 实现

- 统一入口新增六项贡献候选导航及“方法与证据”四页：任务与门洞、质量度量、融合机制、研究支持。
- 门洞图示是概念示意，不是对真实相机位置的测量。19 张既有门洞图中17张非OOS；未知光心位置保留待核验。
- 质量展示 S1/S2/S3 全部 ABC 冻结团队及 YQ24 两份原答；B8L2、D10及分项保持原值，不画可相加的虚假扣分条。
- 融合接入 q9 的5—20人保存整数节点，以及 G046/G057 七个视角的前后事件，串联原答、身份、票数、位置和连接账本。
- 354个图×条件×参考支持单元；库存62人与保留60人分开。总记录数不等同独立样本量。
- 对照严格绑定图片、Manual/Semi、参考坐标及快照；切换后不继承不兼容团队。支持冻结链接、匿名盲审及JSON/CSV反馈导出。
- 复核反馈仅留在当前页面会话，刷新或关闭前须导出。盲审隐藏界面身份与分数；导出文件为追溯保留真实上下文，并非匿名分享数据。

## 验证与限制

- Python方法证据与既有构建器测试：17项通过。
- comparison及workbench-core针对性Node测试通过；方法面板12项Node测试通过。
- 607组JSON/JS伴随载荷一致；261张PNG引用与文件签名检查通过。
- q9全部16个保存人数节点与源状态逐项一致；构建器核对2863个组成员点对与当前原答坐标一致。
- 使用真实离线载荷进行26项DOM交互测试通过，零网络请求及脚本错误；覆盖条件隔离、冻结链接、盲审、反馈导出内容、参考/快照拒绝和同房关系选择。
- 当前执行环境无法启动可用的渲染浏览器。因此没有宣称完成视觉布局、窄屏渲染或原生文件下载验收；这些仍需在可用浏览器中检查。

生成数据沿用既有忽略规则，不重复提交原图与大载荷。按 README 构建后，同名JS伴随文件供双击HTML加载；本次无新增HTTP运行依赖。没有完整打包124924条前缀，也不即时重算任意团队融合。

参见[数据接入说明](../../../docs/thesis_main/研究工作台方法证据接入_20261020.md)和[源清单](METHOD_EVIDENCE_SOURCES_20261020.json)。

## 复核命令

仓库根目录：

```sh
python -m tools.thesis_main.analysis.build_research_workbench_v2_20261019
python -m pytest tests/test_workbench_method_evidence_20261020.py tests/test_research_workbench_v2_20261019.py -q
node research/statistics/research_explorer_v1_r2_20261017/research-evidence.test.cjs
node research/statistics/research_explorer_v1_r2_20261017/research-comparison.test.cjs
node research/statistics/research_explorer_v1_r2_20261017/workbench-core.test.cjs
```

方法面板测试的真实载荷部分使用上一步生成结果；源清单和既有输入须先拉取。浏览器待验收项：桌面/窄屏布局、ERP/BEV/3D视觉叠加、键盘切换、离线打开与原生下载。

[机器可读DOM验收记录](METHOD_EVIDENCE_DOM_QA_20261020.json)。
