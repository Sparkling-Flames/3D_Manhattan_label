# 本轮严格 ABC 替换的机制案例

本目录使用主比较选出的明确事件，重放少量冻结融合状态以保存原答、对应、票数和连接。统计支持来自完整事件表；案例解释局部机制，不充当全库效果估计。

## 接口

```bash
python exchange_research_20261025/cases/fetch_selected_originals.py --image IMAGE_CODE
python exchange_research_20261025/cases/build_exchange_cases.py --event-id EVENT_ID
```

`--events` 可指定阶段事件表，`--native` 可指定端点目录；默认读取 `design/screen/EVENTS_EXACT.csv.gz` 和 `native/endpoints/<pool>.json.gz`。每个事件的 A、B、C 都由原记录中精确成员重放，已有 B8L2、D10、2D IoU、3D 代理在可评分处核对到 1e-7，不改门槛、匹配规则、环序、GT 或标注坐标。

## 每个事件的证据

- `CASE_GEOMETRY.json.gz`：精确事件、输入池、三队端点、三队完整融合状态。
- `ABC_SCALARS.csv`、`PAIR_DELTAS.csv`：实际 ABC 标量与 B−A、C−A、C−B。
- `BLOCK_MEMBERS.csv`：D/X/Y/Z 精确成员。
- `VOTES.csv`、`LOCAL_VOTE_CHANGES.csv`：全部对应组、选留状态、阈值和各块贡献。
- `RAW_REFERENCE_PAIRS.csv`、`RAW_BLOCK_SUPPORT.csv`：各成员原答与参考的角点后验诊断。
- `GROUP_LINKS.csv`、`COMMON_OBSERVATION_REGROUPING.csv`：共同观察跨队的分组变化。共同 D 相同不代表其观察在三次融合中必然被分到相同组。
- `REPLAY_RECEIPT.json`：端点核对与失败情况。
- `ABC_ERP_BEV_VOTES.png`、`ABC_3D.png`：真实原图、原答与融合图。

参考角点一一分配仅用于输出后的诊断。它不参与冻结投票，不等于已经裁定每一处新增结构必要或错误。记录耗时来自既有记录，不是本轮计时生产实验。

`interface_check/` 是代码接口小样，未被选为最终主文结果；交付时可省略其重复几何。最终采用事件在 `CASE_SELECTION.csv` 和另附案例说明中登记。原图仅按 GitHub Release 索引获取所选 PNG，保存 CRC、大小、SHA-256 与范围下载回执，未下载原图全集。
