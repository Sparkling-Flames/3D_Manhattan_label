# 十图人员子类便携核查包

这是已完成的有限十图补充核查包装，不增加研究范围。入口为REPORT_ZH.md；已完成数据在results/。

## 自包含内容

inputs/footprints_240.json只含十图共240份正式足迹、匿名人员/作答编号、资格状态、原环状态及必要图片元数据；坐标不变。原Q评分矩阵为精确副本，冻结标签为192行楼外名单摘录。两个案例只保留所需锚点数值。不含原图、身份映射、评论或20份历史额外几何。排除清单仅保留匿名编号与原资格状态。

完整上游输入blob为5a174746730bb70e405680a3748663caf56dd51f，本包足迹文件是字段筛选摘录，不冒充上游完整文件。SOURCE_MANIFEST.json记录源身份、摘录方式和所有输入SHA256；MANIFEST.sha256.json绑定全部交付文件。

## 环境

Python 3.10或更新版本，NumPy、Shapely；不需要SciPy、scikit-learn、网络、原仓库或其他交付包。核查环境为Python3.12.14、NumPy2.3.5、Shapely2.1.2。requirements.txt给出兼容主版本范围；跨版本数值应重新验证。可在自己的环境按常规方式安装这两个依赖。

## 复算

在此目录运行：

```bash
python check_panel.py --out /path/to/NEW_result
python verify_reproduction.py /path/to/NEW_result
```

输出目录必须不存在，脚本拒绝覆盖。脚本先核验输入散列，独立重算楼外中位数名单并与冻结标签核对，再计算十图×两类×k4/k6×两票规。包括独立及完全不重叠二组的同k期望差，输出80行形状量、20行原始分歧；同包两例36项锚点须相符。verify_reproduction.py对照本包results/校验9个结果文件；数值容差1e-12，非数值字段须相同。

logs/clean_reproduction.json记录已在新建解压目录复算的结果。报告中的k4是历史核查锚点，新增重点是原始分歧、k6和同k抽组方式对照；不扩到T/S/B、参考质量真值、额外人员或44/17全量面板。
