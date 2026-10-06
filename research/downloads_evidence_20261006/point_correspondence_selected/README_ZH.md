# 局部替代对应与上下目标分离：复算入口

先读`REPORT_ZH.md`。本包是独立研究，不是已接入仓库的修复；没有GT或原图。固定main为`4716aef3c8453779633a0a4aadf44105afb3b733`，四图66份记录、24人、400个原角对，五档均未校准。

## 运行

Python 3.10以上，NumPy、SciPy、pytest。无需完整仓库、Shapely、图像或网络。

```bash
python -m pip install -r requirements.txt
python -m pytest -p no:cacheprovider tests -q
python reproduce.py --out NEW_results
python src/summarize.py --root . --out NEW_results/summary
```

NEW_results不得已存在。运行全三阶段将生成完整分区、域内全部合法候选、人工辅助/自动结果、unb分层和540次变换控制。按阶段可用`--stage domains`、`--stage diagnostics`、`--stage controls`；diagnostics需要同一NEW_results下先有domains。

本包`results/domains`已有41域的全部1,328,993个合法候选。JSONL用gzip压缩，避免在编辑器直接打开大文件。它们属于计算状态，不是新增样本。

```bash
python extract_candidate.py --domain rPc6DW4iMge-06_pair_5_d0 --candidate 2018 --out one_candidate.json
```

这个例子恢复5°绑定主要域的人工辅助候选。编号只用于定位，不提供语义排名。提取文件含原节点、域内两组、域外完整固定分区、源坐标/身份、分母和适用限制。

## 文件分工

- `inputs/`：四份完整原输入及完整人工开发判断。全部元数据保留，原确认环不改。自动数值核心不读取人工文件，辅助配置和语义标签与该文件有绑定测试。
- `config.json`：新实验前固定的局部域、目标、参数、预算及控制。不是正式研究合同。
- `src/core.py`：复用坐标含义的独立距离/分区重建、有限二组枚举、全部并列、周期中位位置；不形成新环。
- `src/run_domains.py`：60基础分区、45开发探针、41局部域；人审辅助仅在自动候选/结果形成后计算。
- `src/diagnostics.py`：真实合并历史、去同人约束消融、unb四层输出、全部人审相容成员范围。
- `src/controls.py`：输入打乱、worker改名、微扰、接缝、并列、同人多点及局部域反例。
- `results/summary/`：建议先看的完整成员变动、来源标量核对与总体汇总。
- `results/domains/node_lookup.json`：账本索引到原记录、worker、处理后/源角对及坐标的映射。账本所有节点都保留，未按坐标去重。
- `results/diagnostics/unb_target_layers.json`：五阈值下底部几何身份、原对关联、上部几何分组、人工语义与未知；没有唯一上端选择。
- `logs/`：测试与重放，以及已更正的失败/中断记录。不要把开发版日志当最终数值。
- `EVIDENCE_VIEWER_ZH.html`：离线打开，查看政策备选及全名单、上/下散点与变动。不连新环、不显示原图或GT；不是视觉审核完成证明。

## 结论边界

自动紧凑性政策未恢复rpc开发三点；人审辅助能在部分域/阈值恢复，但会拆开其他未审关系。9人底部组不等于9人同一上部目标。所有“数值唯一”都只是规定成本下唯一，非语义认证。

完整原`candidates.json`、原75行全部审查及原仓库测试未全栈复现。已读取关键源代码、相关诊断、完整人工文件并核对固定输入。见`ACCESS_AND_FAILURES.json`和`VERIFICATION.json`。
