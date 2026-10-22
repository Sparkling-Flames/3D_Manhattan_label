# HOHONET组合机制研究，2026-10-15

推荐：B8L2主研究指数；A10/旧WQ历史对照；C8等锚点组合形状敏感性。未修改正式默认评分、参考或资格。

先读REPORT_ZH.md与MATHEMATICAL_NOTES.md。用户原始PRO_PROMPT、30份JSON回执、manifest和全部原话在inputs/handoff/，原字节保留。题号必须与record_id一起读取。

## 复算

```bash
python -m pip install -r requirements.txt
OPENBLAS_NUM_THREADS=1 python run_study.py --output results_replay
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider tests
python plot_results.py
python build_evidence.py
```

第一步计算无需网络。35项测试核对发布results目录；清洁目录复算的逐文件比较结果另存REPRODUCTION.json。Python/库版本保存在ENVIRONMENT.json。不同环境允许有限浮点差异，不承诺跨版本字节相等。

单例CLI：创建JSON `{"I":0.9,"Sb":1,"D":3,"Hm":0.05,"Hc":0.02,"reference_id":"fixed_ref"}`，运行 `python score_one.py input.json --model B8L2`。分项须先由冻结实现得到；完整缺项直接报错，不作参考选择或补零。

## 输出含义

SCORES_1145.csv保留所有原绑定、条件、留出和暂缓字段；数值可算不代表正式合资格。GEOMETRY_PARITY_30.csv是本轮重测，不是全库几何重测。PHYSICAL_CONTROLS.csv是72个确定几何控制，不是真人样本。SCALAR_FACTORIAL_MECHANISMS.csv是潜在损失的数学控制，不表示每个标量组合都是可实现的物理布局。

人工评价没有转成等距分数目标。首揭示时评论全文未记录，保持缺失，不用最终评论回填。REVEAL_TRANSITIONS.csv只是两个已记录快照，不是推测的心理因果过程。

FUSION_*只对保存的终点重评分；未重新选人或融合。WORKER_*使用既有条件中心化和相对分组规则，不是重新训练正式多轴人员类型。外层单调变换只作敏感性，未采用。

原图没有重新打包，本轮没有RGB视觉裁决。证据HTML显示已供应三维几何和原始反馈，不能因此宣称新人工复审完成。

最终交付核验见DELIVERY_RECEIPT.json：35项测试；36个机器结果及11张图在同环境独立目录复算一致。BROWSER_CHECK.json记录精确HTML内容经Chromium逐卡检查30份的俯视／三维和分数展开；运行环境禁止file://导航，因此检查用set_content载入原样HTML，不宣称本轮做了RGB复核。
