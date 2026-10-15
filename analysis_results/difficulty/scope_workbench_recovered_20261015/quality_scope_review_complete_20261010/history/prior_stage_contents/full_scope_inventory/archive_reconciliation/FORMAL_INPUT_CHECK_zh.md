# 审核包与当前正式输入核验

2026-10-10；核验基线为 `fae48e69aa4ae879b8268c34afb8f8221ee53022`。

## 实际读到的内容

仓库中的 `analysis_results/审核资料_原清单与最终入口_20261010.zip` 为12,939,203字节，SHA256为 `7f752b62e303f126ecd05a09b1db001ea70e7bb59ac506bac7d1c154b3b788bb`。143个ZIP成员CRC全通过。逐项索引列出的123份文件均非空，实际大小与索引相符。此处验证的是已提交的包，不冒称再次读取用户电脑原长路径。

正式输入的59,485,508字节 preprocessed_source.json 与108,396,834字节 comments.json 已实际物化，并逐份SHA256匹配同一提交中的LFS指针。

## 正式加载结果

实际调用 `load_current_bundle()` 与 `load_current_input()`，两者结果相同；当前14条增量已应用。3441个对象、3152份人员作答、3312个可用配对坐标对象、1309个确认环、259张研究图和2张参考专用图。14条中3条改变初始环邻接、11条保留初始环。原始作答、GT及资格的不变性由针对性测试核验。

评论源仍有32462处出现记录及1处未解析出现记录，后者由正式loader明确保留，不能宣称全部人工来源均已解决。此次没有重算任何质量分数，也没有把旧评论快照替代正式输入。

运行 `tests/test_quality_review_input_20261010.py` 和 `tests/test_consolidate_research_input.py`：9项通过，日志见 formal_tests.log。这是针对性一致性与拒绝损坏输入检查，不是全仓测试或质量方法有效性证明。

## 历史GT层补齐

先前清单中28张当前选定GT与历史原GT不同的图片，现已从同一份经哈希核验的正式基线中恢复两套坐标，见 restored_historical_reference_coordinates.json。原GT和当前选定GT的对象ID均精确匹配。这解决了此前历史坐标未物化的问题，不意味着已确定每条旧评论当时看的是哪一版GT；不修改当前参考。该补充数据尚未重新发布到在线工作台。

## 复核方法

在已物化LFS数据及安装仓库研究依赖的环境中运行：

```
python check_formal_input.py --repo /path/to/repository --archive /path/to/审核资料_原清单与最终入口_20261010.zip --output /tmp/formal_input_verification.json
```

脚本仅读取输入并向指定位置输出核验结果；不更新正式输入、不重新计分。保存的验证JSON冻结本次源版本，后续重跑会记录重跑仓库HEAD。

新增历史评论、传播上下文和来源恢复见同目录 REPORT_zh.md。清单保持阶段性，等待用户随后提供的新图片批次；这些历史线索没有被自动升级为新范围裁决。
