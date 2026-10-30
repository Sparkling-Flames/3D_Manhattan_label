# 门洞视觉初筛

入口：[复核页](index.html)。覆盖20图、708份；102份进入复核，其中8份为预处理点对为空。

人工视觉观察记录在 VISUAL_NOTES.json；生成的 REVIEW_QUEUE.json 包含图片、人员、原答ID、定位序号及疑点。只做全量联系表初筛，不能当作逐份高分辨率精审；未入队不等于已合格。不修改初审、原答、切分、GT或评分。

图级另查：2t7WUuJeko7-07 的GT漏点与旧边界；7y3sRwLe3Va-18 修改后的切分；q9vSo1VnCiC-24 门洞身份。预切宽度仍需人工确认。

字段：record_number为工作台从1开始序号；category区分空间范围待复核/数据待查；status统一待用户复核，first_review仅保留旁证。
