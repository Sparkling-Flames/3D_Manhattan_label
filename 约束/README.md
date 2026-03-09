# 约束目录说明

本目录收纳当前项目的字段契约、发布契约、分析契约与模块级实现规范。

使用原则：

1. 先看论文正文 1-4 章与附录，再看本目录约束。
2. 若多个约束冲突，以论文正文、附录和发布层真源约束为准。
3. 约束文件的作用不是重复写实现细节，而是冻结字段语义、输入输出边界、失败处理和审计要求。

## 一、发布层与总门槛

- [A\_约束清单.md](A_%E7%BA%A6%E6%9D%9F%E6%B8%85%E5%8D%95.md)
  - Dev A 的总 release gate。
  - 用于提交前核对主表字段、可追溯性、`d_t*` 状态字段、`worker_group` 可复现性、Type 4 审计链是否齐全。

- [merged_all.md](merged_all.md)
  - 发布层 `merged_all.csv` 的 schema 真源。
  - 规定主键、字段名、值域、NA 处理、兼容字段地位、可靠度字段、风险字段和审计字段的统一语义。

- [formal_annotation_analysis.md](formal_annotation_analysis.md)
  - 正式实验阶段的主分析契约。
  - 用于新服务器、正式 userscript、正式 ontology 冻结后的分析链，不再把旧兼容字段当主路径。

- [visualize_output_v2.md](visualize_output_v2.md)
  - Dev A 和 Dev B 之间的绘图数据契约。
  - 规定图表层只能从 `merged_all.csv` 或可由其重建的聚合表读取，不能在 notebook 里重新发明字段语义。

## 二、Dev C 模块规范

- [perturbation_operators.md](perturbation_operators.md)
  - 扰动算子主规范。
  - 对齐论文附录 A1 与 Label Studio XML 的 `model_issue` alias，冻结算子家族、表示层、全景 wrap/clamp 规则、失败码和审计字段。

- [compute_dt_score约束规范.md](compute_dt_score%E7%BA%A6%E6%9D%9F%E8%A7%84%E8%8C%83.md)
  - `compute_dt_score.py` 的详细实现规范。
  - 规定 `d_t` 的输入防泄漏、参考池 manifest、embedding 抽取、主参数、失败熔断和审计输出。

- [compute_spammer_score约束规范.md](compute_spammer_score%E7%BA%A6%E6%9D%9F%E8%A7%84%E8%8C%83.md)
  - `compute_spammer_score.py` 的详细实现规范。
  - 规定 worker 异常度 `S_u` 的输入、聚合方式、样本量门槛、输出字段和审计 JSON。

- [difficulty_split约束规范.md](difficulty_split%E7%BA%A6%E6%9D%9F%E8%A7%84%E8%8C%83.md)
  - `difficulty_split.py` 的详细实现规范。
  - 规定难度映射、任务级共识、split 模式、泄漏检查、KL 验证与 split manifest 输出。

- [offline_replay约束规范.md](offline_replay%E7%BA%A6%E6%9D%9F%E8%A7%84%E8%8C%83.md)
  - `offline_replay.py` 的详细实现规范。
  - 规定离线回放的输入依赖、策略接口、候选池过滤、结果字段和 replay manifest。

- [test_perturbation_operators约束规范.md](test_perturbation_operators%E7%BA%A6%E6%9D%9F%E8%A7%84%E8%8C%83.md)
  - `tests/test_perturbation_operators.py` 的测试契约。
  - 规定算子测试的最小覆盖范围、fixture、seed 可复现性、intentional-invalid 语义和 freeze plan 回放测试。

## 三、兼容与历史文件

- [92e57018c84704a7398331e795dee3b6.md](92e57018c84704a7398331e795dee3b6.md)
  - 旧版 C2 占位文件，内容已被新版 `compute_dt_score约束规范.md` 与当前论文方法口径取代。
  - 仅用于防止历史引用失效，不应继续作为实现依据。

- [d9b8ba20915270289fe3def7fca49a78.md](d9b8ba20915270289fe3def7fca49a78.md)
  - 旧版 C1 占位文件，内容已被新版 [perturbation_operators.md](perturbation_operators.md) 取代。
  - 仅作历史兼容占位，不应再摘取字段或规则。

- [legacy/](legacy/)
  - 历史约束与旧稿归档目录。
  - 仅在追溯历史口径时查阅，不作为当前开发入口。

## 四、推荐阅读顺序

1. 论文正文 1-4 章与附录 A1/A4。
2. [merged_all.md](merged_all.md) 和 [A\_约束清单.md](A_%E7%BA%A6%E6%9D%9F%E6%B8%85%E5%8D%95.md)。
3. 按模块读取对应详细规范，如 `d_t`、扰动算子、split、replay、测试。
4. 若进入正式实验主分析，再读 [formal_annotation_analysis.md](formal_annotation_analysis.md)。

## 五、一句话区分

- `merged_all.md` 管发布层真源。
- `A_约束清单.md` 管 Dev A 提交门槛。
- `visualize_output_v2.md` 管 B 线图表读取契约。
- `perturbation_operators.md` 和 5 份新规范管 Dev C 模块实现与测试。
- `formal_annotation_analysis.md` 管正式实验分析主链。
