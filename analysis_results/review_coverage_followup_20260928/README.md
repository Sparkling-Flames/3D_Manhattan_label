# 图片覆盖补审

4张旧评论语义补充与20张本轮未覆盖核查分区显示。后者不是已判异常。已二审明确选项及已解决续审均不重新送审。只显示最新CSV保留作答的有效点；原始/人工修订GT可切换。

导出schema为coverage_followup_decisions_v1，binding为coverage_followup_20260928_v1，decisions以image_id为键；status为draft/pending/resolved。OOS与门洞独立；tags记录参考/空间属性。view_context保存作答canonical ID、GT版本/来源与是否多人叠加。浏览器独立保存；新导出尚不自动应用到CSV。导入绑定与枚举校验，冲突拒绝覆盖。
