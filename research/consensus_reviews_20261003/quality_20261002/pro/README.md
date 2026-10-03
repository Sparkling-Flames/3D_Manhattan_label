# 全景 layout 质量衡量：独立摘录与模型实验

先读 REPORT_zh.md。固定仓库提交：bba3dc7c9a79b8342ecb4ce2487affe41886eb56。

本包不是完整研究快照，也不是原仓库验证器的替代物。容器下载失败，保留 network_attempt.txt。GitHub 文本读取用于核查源码、报告和数值；部分坐标转录到本地进行独立计算，没有下载、运行完整195作答实验或74个既有合成实验。

## 执行

```sh
python -m pip install -r requirements.txt
python reproduce.py
```

执行环境与输入SHA256见 results/environment.json。只需要 NumPy、SciPy、Shapely、pandas、matplotlib；不需要照片或原始导出。

## 输入与范围

inputs/current_numeric_subset.json 保留取得的一张图9份坐标摘录和1份参考。本次严格数值对照只使用能与当前CSV共同字段核对的6份：R03286、R03288、R03281、R03287、R03284、R03282。其余3份不进入报告分母。来源为连接器文本，不是字节一致的原文件复制。选样由传输可得性决定，没有代表性。

输入人员别名仅保留摘录来源；R03288在坐标摘录和另读CSV中的人员别名不一致，因此本轮不按人员身份合并，不进行人员排名或模型。此处不能据此裁决原数据身份，应由完整源绑定核验。

6份作答均保留已存坐标和环序，1份原始GT环未人工确认；既有quality gate未更改。6份BEV可比较，5份列式墙带可比较。R03288相机在所声明足迹外，仅列式表示失败，不自动认定人员错误。

results/source_summary_comparison.csv核对35个可用共同数值字段，不是全部字段或全部数据核验。results/checks.json记录8项针对本实验的计算检查，不是原仓库测试。

inputs/controlled_inputs.json有17组独立构造/衍生对照：7种同墙共线细分、相反斜顶、上下误差耦合、2种深度的半像素扰动、6种真实几何共线细分。它们不是17个独立真实样本，也不是仓库17组改序实验。真实衍生记录是反例用计算副本，不回写原标注。

## 字段身份，必须区分

- current_model_volume_iou、current_height_*：复现本轮核对的当前源码定义，采用周长加权平均墙高。
- vertex_ls_*：本研究另做的角点等权拟合替代方案，**不是当前源码**；显示其节点密度缺陷，不能用来指控当前算法。
- arclength_ls_*：另一探索性角度拟合，不是已推荐主方法。
- wall_height_rmse_h：本研究新增的固定坐标最近边界配准诊断，**不是当前仓库已经实现的完整墙面距离**。
- top_curve_rmse_px、bottom_curve_rmse_px：当前声明列式代理下的投影边界差，不是照片可见性裁决或角点身份RMSE。

报告不含新人员类型、共识权重、显著性结论或GT改判。复算不应改写输入或源仓库。
