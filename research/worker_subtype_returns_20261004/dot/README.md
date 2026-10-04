# 新线程研究独立复审

先读《独立综合审查.md》。本包覆盖2026年10月3日19:05完整布局交付、19:44的ad12d64仓库版本，以及20:57人员子类交付。最终来源检查至21:39 UTC，main仍为ad12d64，未检出21:00之后新交付。

各部分用途：

- `oct4-layout-reproduction/`：完整布局原包复算、源摘录核对、独立公式及模拟验证
- `oct4-correspondence-audit/`：三人实际对应越界反例、原版失败证据、隔离补丁及25+6回归；补丁未应用远程仓库
- `oct4-repo-audit/`：最新全员点方法的61图共同面板、状态分层、ID重命名并列反例
- `personnel_repro_audit_20261004/`：人员原包35测试、11阶段41结果复算、输入/隔离/精确式审核及GEOS运算路径诊断
- `personnel_inference/`：嵌套收益集中度。可直接运行`python audit_nested_influence.py --out new_results`，默认读取本目录`source/`的必要输入
- `ten_image_subtype_check/`：固定10图子类稳定性扩展，输入及独立脚本自包含
- `source_docs/`：固定ad12d64下的研究方向与报告原文，供版本对照，不冒称它们全是本次独立执行

各子目录README给出环境、命令和未执行项。通常需要Python、NumPy、SciPy、pandas、Shapely等常规依赖；以各子包实际要求为准，不需用户本地电脑或原图。代码写入各自指定新输出目录，请勿将输出位置设为原仓库已有研究结果。

所有结果是有限历史池的重放或定向反例，不是新真人采样或视觉GT认证。`SHA256SUMS.json`对应最终交付文件；各子包原有manifest保留其各自实验快照。原始失败、环境差异和未执行项目没有删除。
