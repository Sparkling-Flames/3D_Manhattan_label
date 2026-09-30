# 合规、排序与配对评论独立机器表

入口：`comments.json`。先读`rules`，再读`comments`及其`occurrence_ids`对应的`occurrences`。`summary.json`仅为规模索引，出现次数不是独立审核次数。

保留七批合规原件、历史排序/配对原件、撤销与继承记录、traits、续审卡、覆盖补审、旧评语释义、聊天澄清及冻结簇关联。来源清单见`sources`；每次出现附文件、JSON指针、时间、原选项及对象信息。图片评语不因为view_context而变为个人裁决。没有记录作者时保持null；文件归属提示不是作者证据。聊天澄清与派生解释不冒充原始反馈。

已向用户指定的合规线程`01a0c84e-942f-71a1-9ab0-a9f8bb84b70f`核对来源及绑定规则。附带粘贴文本文件为0字节，未作为评论输入。

生成：`python -m tools.thesis_main.analysis.build_review_comment_table_20260929`。
定向验证：`python -m pytest tests/test_review_comment_table_20260929.py -q -p no:cacheprovider`。
未改原件、排序、坐标或裁决；不新增审核任务，无UI改动及截图。
