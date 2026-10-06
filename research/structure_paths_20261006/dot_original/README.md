# 局部结构对应独立复审与新增实验

先读 REVIEW_ZH.md。最新本地工作树包未取得，本包不验收137图、e9z或五张困难图。

## 目录

- reproduction：原新交付的22测试、两次200工件重放、独立计数与构造核验；含一次完整结果
- source_audit：最新意图、旧输入绑定及缺失材料说明
- interpretation：范围与共享x点对路径反例、方向检查、科学解释
- event_exploration：分段不敏感的事件窗口原型、14测试、完整一次结果和第二次重放哈希
- probe_source_subset：仅供新增实验调用的原交付源码/输入子集，文件未修改；不是完整原交付，不能从其README误认为原全套结果也在此目录
- PROVENANCE.json：来源、版本和子集原始文件哈希
- MANIFEST_SHA256.json：最终包全部其他文件的哈希

## 运行新增事件窗口实验

需要Python、NumPy、SciPy、Shapely、pytest；Numba可加速。具体已测版本见reproduction/checks/environment.json。

从本包根目录（Linux/macOS shell示例）：

```
export STRUCTURE_SOURCE="$(pwd)/probe_source_subset"
export PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
python -m pytest -p no:cacheprovider event_exploration/test_event_search.py -q
python event_exploration/run_exploration.py --out NEW_event_results
python interpretation/targeted_probes.py --delivery probe_source_subset --out NEW_probe_results
```

Windows中将STRUCTURE_SOURCE设置为probe_source_subset的绝对路径后运行相同Python命令。输出目录须使用新路径。所有细分均为同一观察的合成变换，不新增人员或投票。

## 复算原云端完整流水线

需要另外解压已有 structure_paths_20261006_delivery.zip（SHA256见PROVENANCE）。将完整目录作为第一个参数；本包的probe_source_subset不够运行原完整流水线。

```
bash reproduction/scripts/run_reproduction.sh /absolute/path/to/structure_paths_20261006 /absolute/path/to/NEW_results /absolute/path/to/NEW_evidence
```

全部科学数值与原交付一致；发布包与重放的两个字节差异是清单顺序及摘要，不是数值差。各分项报告保留失败、未执行、开发追加和证据限制。
