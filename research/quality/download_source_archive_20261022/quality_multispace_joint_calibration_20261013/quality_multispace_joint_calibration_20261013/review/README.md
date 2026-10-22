# 三项有区分力的复核

打开 `blind_review.html`。它不含算法名称、分数或损失字段；`diagnostic_review.html` 单独提供这些数值。两者都使用已取得的原始 PNG，支持原图叠加、同步三维旋转/缩放、共同尺度底面和 JSON 答案导出。全部脚本、几何及原图随包提供，无外部 CDN。

- **J01**：R03346 与 R03347。旧/新公式顺序改变。B 已有单例开发判断，故不是完全未曝光的新独立样本。
- **J02**：R02049 与 R02244。极短异常边与广泛轻度歪斜的权衡；主式与局部联合 hinge 相反，两份人员资格未知，只作方法诊断。
- **J03**：同一 R03197 作答，分别与已确认参考 A/B 对照。用于区分 IoU 与归一化边界兜底。两侧都只展示参考底面，不从其他参考拼接顶面。

近似相当、犹豫、参考问题分别记录；未选择始终是未审查。页面隐藏数值不会使开发时见过的图片重新成为独立验证集。file:// 的跨页 localStorage 行为因浏览器而异，曝光字段只帮助记录，不作为身份认证。

`J01_static.png` 等为带原图的静态联系图，方便不支持交互预览时查看；它们由绘图库生成，不是浏览器截图。实际验证保存在 `UI_EXECUTION_VERIFICATION.json`：交付脚本的 8 种页面/宽度组合已执行；没有完成原生浏览器布局和实际下载点击验收。

重新生成（原图已在 `images/`，不需要原图大 ZIP）：

```bash
python review/build_review.py
node review/verify_review.mjs review
```

生成的 `blind_review_standalone.html` 与 `diagnostic_review_standalone.html` 嵌入原图，可单文件携带；ZIP 中标准 HTML 和图片组合已经能离线使用。
