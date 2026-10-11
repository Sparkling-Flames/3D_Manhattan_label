# 八例回执交付修订

只更新回执页面、打包入口和独立研究映射。16张JPEG逐字节保持，八个case_id顺序与13个CSV数据字段保持；公式、数值结果、完整计算ZIP与第一阶段ZIP均未改变。C02/C05在独立答案映射中明确为general_quality_observation_only、penalty_fitting_allowed=false；其余人员、配对、分数和选例依据均不改。

页面现在尝试在当前浏览器写入草稿，并在顶部显示空白/已写入/已恢复/存储不可用状态。读取或写入localStorage失败均捕获，明确显示“必须下载回执”；不保证浏览器自动保存或持久保存。关闭/刷新前请下载备份；输入不是上传到服务器。

可以直接下载JSON或CSV回执并导入续填。默认文件和无草稿的新浏览器上下文全部回答为空。已有合法本浏览器草稿恢复后会明确显示已恢复。JSON格式版本为quality_blind_sample_receipt_v1；CSV首行含#format_version及同版本，第二行为原13字段，其后八例数据。读取CSV到分析工具时需跳过版本行。导入只读取回答字符串，不执行HTML；所有字段、版本、八例ID/类型、选择项和长度均核验，任何不匹配在更改现有输入前拒绝。每字段最多2000字，文件最多1 MiB；不导入局部、不改变图片/题序。

最小要求已以实际Chromium页面通过：JSON与CSV导出再导入（含逗号/引号/换行）、缺字段/非法ID/重复ID/错误版本/额外字段/长度错误拒绝且保留现有输入、过大文件拒绝、HTML样式文字只作为普通值、刷新恢复、localStorage读取失败、写入失败时提示且仍能下载当前回答，共9组。测试使用环境预装/usr/bin/chromium并通过回环地址提供静态页面；托管浏览器禁止file://导航，因此没有冒称在此环境完成直接文件URL测试。失败日志保留在云端；没有绕过浏览器管理策略，也没有下载额外浏览器。测试回答未进入交付默认值。

运行本修订测试需Playwright与已有Chromium：python code/test_review_receipt.py。若把本提交回执代码用于已解压的完整计算包，请复制code/build_review_receipt_page.py、code/review_receipt.js和code/render_blind_sample.py到该包code/；仅运行build_review_receipt_page.py可重建页面而不重渲染图片。用户直接解压当前用户ZIP打开index.html即可，页面脚本无外部依赖。ZIP内当前文件校验清单已重建。
