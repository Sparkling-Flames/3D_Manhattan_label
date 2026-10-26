# 本轮交付检查

## 已通过

- 输入对象为冻结的真实 v2 保存团队；没有调用融合、评分或分类拟合。
- 231 个 Manual 面板，每面板 924 个成员集合；标签、成员与端点关联一致。
- 4 个重要数学边界单元测试通过。
- 924 条旧结构 Q/D10 逐面板方差独立复算一致，误差为浮点数量级。
- 总／内／间恒等式、22 折嵌套映射与 K3 不低于 K2 检查通过；完整数值在 CHECKS.json。
- Node 语法检查覆盖新页面脚本、改动的 personnel-main.js 和 personnel-methods.js。
- 新脚本的轻量渲染器测试覆盖 4 方法×5 指标、常数面板、缺失时间、231 个面板选项、28,775 条配比指标行的字段和分位顺序。测试是 Node 模拟 DOM 字符串渲染，不是真实浏览器渲染或下载验收。
- 展示保留全指标各自有效分母、不可评状态、单团队格与分位区间含义；整体汇总不是百分比简单平均。
- 主人员报告、CONTEXT 和研究台入口同步到新衔接，旧进入策略、同房及 RFUSE 没有改名。仓库已删除的旧 DOCX 未恢复；其失效链接改为当前提纲同步说明。

- 总体 Q 方差 SVG 已通过 Inkscape 静态导出并直接查看，文字与条形未截断；临时检查用 PNG 已清理。这不代替 HTML 浏览器验收。

## 尚未完成的视觉与环境验证

云端 Chromium 在启动时因 socket 权限失败；执行环境的授权启动路线随后发生运行环境挂载错误，未成功启动。备用云端浏览器拒绝 file 协议。没有绕过访问限制，没有因此启动额外 Work/Codex 任务。

因此，**真实浏览器宽窄屏布局、控件点击和原生 CSV 下载未验收**。没有声称整体工作台全量构建、全部回归或部署成功。页面使用普通本地 script 引用，不依赖 HTTP 服务；这是实现设计，经源文件／逻辑检查，不冒称已在真实浏览器确认。

## 复现检查

```bash
python -m unittest discover -s research/workers/dstruct_composition_bridge_20261026 -p 'test_bridge.py' -v
python research/workers/dstruct_composition_bridge_20261026/build_bridge.py
python research/workers/dstruct_composition_bridge_20261026/build_presentation.py
node --check research/statistics/research_explorer_v1_r2_20261017/composition-variance.js
node research/statistics/research_explorer_v1_r2_20261017/composition-variance.test.cjs
```

数值输出与源表逐项对应，全部配比可由生成代码重新得到。独立统计复算和图表整理已经完成；浏览器视觉验收的未完成不改变这些计算结果。
