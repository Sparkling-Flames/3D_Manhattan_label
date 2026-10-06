# 九图结构政策比较

完整比较：9图、150份作答、800个原始点对，5/9/12°绑定距离，5项政策。输入、票权、完整人员池、源环和中心算法固定。此包只研究结构信息的增量，不重做全部四路线108基线。

## 一条复算命令

在本目录，安装 requirements.txt 所列常规科学计算依赖后：

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python reproduce.py --out NEW_results
```

输出目录必须不存在；不访问网络、桌面、GT或外部仓库。Numba 是速度优化，不改变算法；无Numba也可运行。`results/`为已验证执行，`REPORT_ZH.md`为结论。

## 目录

- `run_study.py`：原型一致性检查、所有自动候选生成、冻结后人工关系记账
- `source_adapter.py`：明确复制权威基线的距离算式和 first-argmin medoid 中心规则；不更改上游源文件
- `check_study.py`：独立向量角度、完整成员/票权/中心/路径审计与7个决定性控制
- `vendor/`：原Pro代码及既有事件域代码的字节不变副本，参见 `SOURCE_PROVENANCE.json`
- `inputs/inputs.json`：全部150份原始有效作答，不含GT
- `inputs/paired_baseline_compact.json`：原108基线的27个绑定状态的全部分组成员与中心，含完整源基线文件哈希
- `inputs/human_review.json`：已有曝光的人审关系，自动结果保存后才解析评价
- `results/*/pair_*.json`：全部组、中心、达票标记、原始环序映射、新连接与全部成员增删
- `results/*/*evidence.jsonl.gz`：逐候选路径、外锚、每边界数值证书与失败原因
- `results/*/*source_paths.jsonl.gz`：每条路径的原记录、源索引、全部内部点
- `results/known_unknown_changes.json`：已审与未审变化严格分开
- `results/review_dossiers.json`：最小人工问题及可供本地大图叠加的点/路径数据

没有新的人审约束选择，没有加票、删原点、强制四对、最低8点或按GT挑门槛。5/9/12均未校准；9°不是本次结果选出的最优值。五困难图为定向选出，另外几图亦已有曝光，不是盲测。
