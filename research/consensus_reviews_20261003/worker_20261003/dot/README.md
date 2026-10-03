# 人员与组合共识独立审核和探索

先读“独立审核与人员组合探索.md”。本包固定到405f3041fdd76977f625d50c558c63dbf342699d，审查新136图A线及24人×10图B线，不用旧Lee小面板替代当前目标。

## 阅读与复现入口

1. worker-audit-validation/REPORT_zh.md：返回包复跑、12测试、独立几何与组合核查，以及不影响当前合法输入的接口问题
2. worker-audit-source-review/REPORT_zh.md、README_PORTABLE.md：完整十图原算法重放、71个固定源文件、23测试、两套依赖栈及警告定位
3. expanded_count_independent_20261003/REPORT_zh.md、README_reproduce.md：A线136图独立全均值复算、固定33图8到20人配对计算及有效计算误差界
4. worker-audit-exploration/REPORT_zh.md、README.md：全十图共同三人替换第四人、背景差异、训练排序与融合贡献、假设22人池和建筑敏感性。正式结果在results_v2与restricted_results，未包含旧版初步结果
5. worker-audit-risk/REPORT_zh.md、README.md：全十图保存几何重复核查、280状态R/B/V分解和参考政策敏感性
6. worker-audit-inference/独立判断与替换实验数学审查.md：平均替换恒等式、合成反例、人员预测分数与排名信号的区别

worker-audit-inputs保留收到的原ZIP和原样提取目录。worker-audit-original保留固定源码、输入、结果与测试依赖。worker-audit-repro是隔离重放输出。没有复制完整原始身份/评论库、安装依赖目录或任何登录凭据。

## 可复现实验

先在隔离Python环境准备各分项requirements中的依赖。保持本包目录结构；建议复制到新的工作目录后执行，以免覆盖保存的核验输出。

```sh
# 返回包原复跑，fresh_return必须不存在
python -B worker-audit-inputs/extracted/worker_consensus_independent_20261003/reproduce.py --out fresh_return --figures

# 独立固定背景替换探索：运行14测试并重算所有结果
python -B worker-audit-exploration/reproduce.py --out fresh_replacement

# A线：完整3438均值与新种子配对核验
python -B expanded_count_independent_20261003/independent_verify.py --all-k

# 独立数学检查
python -B worker-audit-inference/check_inference.py
```

原B线完整重放与23测试的精确命令、旧/新两套依赖环境见worker-audit-source-review/README_PORTABLE.md。风险分解的运行命令见worker-audit-risk/README.md。A线的进一步核对脚本见其README_reproduce.md。

## 解释边界

- 组合、背景、矩阵单元格和双参考版本行不是独立真人样本
- 所有“上/下半”按既有外建筑校准，未改正式人员资格；假设缩小池仅为敏感性分析，不是删除数据
- 相同保存坐标不自动证明身份相同或复制原因；完整原始提交生成链没有独立重连
- 全部枚举消除有限池计算抽样误差，不解决GT是否适用、独立新图片/人员的推广
- A线新置信界只针对固定33图的计算随机性和预定两规则对比，不是人员总体置信区间或最佳人数阈值
- 配对均值只是个人条件贡献差，背景分布另报；IoU均值不能用期望面积比代替
- 质心相关、λ敏感性与GT更接近都不自动证明质量效度
- 未取得原图与完整聊天正文；未完成视觉GT审核、独立外部验证或完整原始源链审核

AUDIT_PACKAGE_HASHES.json列出本交付文件的SHA256与大小。原数据、源码、原报告和本轮独立结果分别保留，没有远程写入。
