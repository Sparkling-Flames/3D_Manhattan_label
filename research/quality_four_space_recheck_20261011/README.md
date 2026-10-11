# T30四空间补画与历史反馈复核

最新回执增量：用户已于2026-10-11 07:15明确确认C/D底面并指定T30对应D；原30回答和本目录初始种子保留。最新参考清单、局部结构优先证据及底面复算见 [quality_four_space_recompute_20261011](../quality_four_space_recompute_20261011/README.md)。下文为早先工作台交付记录，其中“仍待补画C/D”属于历史状态；当前缺口是C/D完整顶界，而不是底面未画。

本轮只交付单图工作台与反馈分层，不改变分数、GT、资格、hold、公式或融合算法。主线程负责研究设计、人工验收和后续复算。

- 检查到的main：`159eac10e077834dd0f8e7fd3f9832b5242c529b`。
- T30：`uNb9QFRL6hY-88 / R02962 / new_93_3608_7113_W006`。同图20份当前作答按正式输入/冻结几何取用。
- 复用恢复17分卷中的v3.4.2原编辑器；原 `geometry.js` 字节不变，SHA256 `eccaf1f5e8555b05cace741059915450922d6f55fbceabc74b9f0c5f248a6be3`。原实现与新适配分别存于 `vendor/` 和 `code/`。
- A为原GT底面，B为已认可底面；基线不可被导入替换。C/D初始为空，不猜坐标或哪两个没有作答支持。四空间可独立命名、编辑、显示、确认。底面确认与实际作答支持分开。
- 原始Library回执：`libfile_f704466496208191a307dced921787ab`，version 0，11,986 bytes，SHA256 `8e26b9cd8fa4fc1f978fb0b71453e2142878eca667cd5c525dd913d8077ad35c`。本执行器的原字节下载失败；完整Library文本补末尾LF，与主线程独立物化原件SHA逐字节交叉核验一致，已保留原件并关联原Library身份/version。
- 历史30回答只读预填；新T30复核另层，初始“参考待补充”。原T30“两者均不匹配 / 另一种空间”不变。T29按用户指定A，T21/T22备注仅研究警报。24质量题为2可接受、10轻微、12明显、0严重；差距9很小、15中等，不能推作全体分布。P01原空白。

## 交付

`artifacts/quality_four_space_recheck_20261011_user.zip` 为独立用户包。解压后入口 `index.html`；四空间页 `editor/index.html`，历史页 `review30/index.html`。工作台数据嵌入HTML，打开文件不依赖JSON fetch。可部署到HTTP；本执行器以HTTP真实浏览器验收（管理策略阻止file://访问，不宣称file://实际验收通过）。

`user/` 同时提供可阅读源码版本。原照片是真实1536×768 JPEG，复用历史30题的120个原视图，不伪称新GT/顶界重渲染。截图与QA临时判断仅在 `results/browser_evidence`，不进入用户ZIP，也不是用户新反馈。源代码依赖清单见 `DEPENDENCIES_AND_SOURCES.md`。

`code/prepare_inputs.py` 恢复审计后的单图输入并检查20份当前坐标哈希；`code/adapt_legacy_workbench.py` 生成适配工作台；`code/build_history.py` 从上一轮用户视图构建不可覆盖的历史回答页。

```bash
python code/prepare_inputs.py
python code/adapt_legacy_workbench.py
python code/build_history.py
node vendor/v3.4.2/qa-geometry-v2.cjs
node code/geometry_qa.cjs
python code/browser_qa.py
python code/package_deliverable.py
```

构建默认使用随包冻结的原页面模板与现有120张图片；需要重新取得图片时，`--prior-user` 可指向已交付上一轮用户ZIP解压目录。已经生成的 `user/review30/` 带所有历史视图；日常使用不需要原17分卷或额外Python依赖。运行浏览器QA需要Playwright和系统Chromium；只使用当前云端执行器。

## 验收证据与边界

实际Chromium/Playwright执行263条断言，包含30份原值锁定、4空间空/确认状态往返、重复导入、独立复核、参考变动后旧独立复核存档并要求重新复核、错误导入原子拒绝、真实原图像素、原GT/人员配色、两窗口尺寸及缩放后的14–1闭合边真实指针操作、撤销/取消、浏览器保存失败仍可导出。`results/browser_qa.json` 是详细清单。另86条真实T30几何检查覆盖全部14种环起点、13/12点闭合边处理、已存线重放、14条有限GT边9/11像素等效距离；原49条几何回归通过。没有把旧mock DOM检查冒称实际浏览器测试。

仍待用户补画和确认C/D、主线程验收新增底面以及是否有作答支持；未自动分配空间、校准阈值或重算Q。原顶界及错误GT/hold不因本工作台恢复。所有输入和旧交付保留，本轮新增在独立研究目录，只提交研究分支。
