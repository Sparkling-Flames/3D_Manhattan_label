# v2.1 描述性人员画像

复用原`personnel_v2_20261019`定义，以当前8,154份正式质量作答重新生成画像、难度偏好和组表。`profiles.csv`有712条“人员×用途面板×难度”记录；普通Manual难度偏好覆盖60人。`SUMMARY.json`保留分母和原探索性门槛。

相对Q仍在相同图片、条件和参考内计算，再形成个人均值；Q三分档、时间60/180秒及90/240秒敏感性阈值均未重定。时间沿用原来源证据。scope与Semi可靠性计数复用原任务裁决，未知纠错不当作成功。

这些是描述性细类，不能当作经验证的人员类型或代替当前DSTRUCT、V3联合分类和RFUSE。楼外分类分别见同级`condition_classification/`、`joint_history_classification/`和`fusion_role_classification/`。
