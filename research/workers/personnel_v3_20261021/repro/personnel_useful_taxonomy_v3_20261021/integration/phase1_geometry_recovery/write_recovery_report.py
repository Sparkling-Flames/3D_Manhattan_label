#!/usr/bin/env python3
"""Write a compact handoff around the completed, directly downloadable table."""
import csv, hashlib, json, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def main():
    r=json.loads((HERE/'RECOVERY_RECEIPT.json').read_text());assert r['stage']=='complete'
    assert r['rows']==291904 and r['abc_referenced_recovered']==38789 and r['missing_total']==0
    status='\n'.join(f'| {k} | {v:,} |' for k,v in sorted(r['native_status_counts'].items()))
    text=f'''# Phase 1 完整团队几何恢复：291,904 个原生终点

**完整恢复 291,904／291,904 个团队键，覆盖修复后全部 12,953 条 ABC 事件引用的 38,789／38,789 个不同团队。缺失为0。** 本次只读取旧阶段已经保存的几何，不进行融合、不评分、不改变人员标签，也不计入 v3 新计算团队数。

可直接取得的完整表：[{r['output']}]({r['output']})，**{r['rows']:,} 行 × {r['fields']} 列，{r['bytes']:,} 字节**。SHA256：`{r['sha256']}`。

## 1. 覆盖与来源

恢复目标严格以旧 `composition/TEAMS_SCALARS.csv.gz` 的全部键为准，该文件为291,904行、97列，SHA256为`{r['scalar_sha256']}`。ABC子集以完整修复包的 `event_repair/ABC_ENDPOINTS_REFERENCED.csv.gz` 为准，38,789键全部包含于恢复结果。

几何来自旧 `personnel_global_composition_20261021/composition/runtime/endpoints/` 的 **{r['source_pools']} 个原生池缓存**。每池源路径、字节数、SHA256及恢复行数见 [SOURCE_CACHE_MANIFEST.csv](SOURCE_CACHE_MANIFEST.csv)，逐池全键及ABC覆盖见 [POOL_COVERAGE.csv](POOL_COVERAGE.csv)。若源池存在旧式缺口，代码保留按原 `global_study.existing_cache` 清单读取的回退路径；本次实际采用的源身份以清单为准。

旧阶段部分 per-pool 派生 scalar 分片的压缩尾部问题此前已有记录。本恢复直接使用已验证完整的97列总表建立临时磁盘元数据索引，没有重新研究该问题，也没有依赖这些派生分片。源表与原生缓存均未修改；临时索引在完成后删除。

## 2. 11列接口，与本轮和n20几何表一致

| 字段 | 含义 |
|---|---|
| `team_key` | 既有池ID与排序成员集合摘要；与原始标量表一一对应 |
| `pool_id` | 图片、条件和冻结参考池 |
| `member_workers` | 竖线分隔的精确成员 |
| `k` | 团队人数 |
| `score_status` | 原生质量／失败状态，不是本次新评分 |
| `complete_evaluable` | 原生是否完整可评价；未知不补0 |
| `geometry_json` | 原生candidate的完整JSON，保留points、footprint、feature_ids、环序及状态；原生空值仍为空 |
| `node_supports` | 竖线分隔的选中节点支持人数，顺序沿用原状态 |
| `minimum_support` | 冻结融合实际支持门槛 |
| `reference_id` | 冻结参考绑定 |
| `reference_version` | 冻结参考版本 |

机器可读字段说明见 [GEOMETRY_FIELD_DICTIONARY.csv](GEOMETRY_FIELD_DICTIONARY.csv)。

使用示例：

```python
import json
import pandas as pd

geometry = pd.read_csv("{r['output']}")
scalars = pd.read_csv("TEAMS_SCALARS.csv.gz")
assert geometry.team_key.is_unique and scalars.team_key.is_unique
assert set(geometry.team_key) == set(scalars.team_key)
# 仅按team_key合并，重复的人员、参考、人数列用于核对。
joined = scalars.merge(geometry[["team_key", "geometry_json"]], on="team_key", validate="one_to_one")
candidate = json.loads(joined.iloc[0].geometry_json)
```

`geometry_json` 在CSV中是一个正确转义的JSON字符串。不要按逗号手工拆行。大表可使用 `chunksize=5000` 流式读取。

## 3. 失败状态完整保留

全键恢复不意味着所有团队都产生有效闭合多边形。原生状态分母原样保留：

| 原生状态 | 团队数 |
|---|---:|
{status}

其中 geometry为原生JSON null的行有{r['native_null_geometry_rows']:,}行；geometry没有可用points的行有{r['native_geometry_without_points_rows']:,}行。它们是原始融合／几何失败或延后状态，**不是恢复缺失**。`MISSING_KEYS.csv` 仅有表头，表示没有遗失团队键；不要把失败行筛掉后称为全覆盖。

## 4. 分批保存、完整性和资源

恢复按源池逐一读取，任何时刻只持有一个原生池和最多5,000行导出缓存。每个分片先在内存完成 `gzip.compress`，验证解压内容，再通过原子替换及fsync保存。共保存 **{r['standalone_shards']} 个可独立读取的CSV.gz分片**，每份都有自己的表头、CRC与EOF；索引见 [GEOMETRY_SHARD_INDEX.csv](GEOMETRY_SHARD_INDEX.csv)。

最终单表由 **{r['gzip_members']} 个完整gzip member** 组成，只有第一个member保留CSV表头和BOM，因此标准Python gzip、Pandas和常规gzip解压器读到的是一个正常CSV。每个member的精确字节范围见 [GZIP_MEMBER_INDEX.csv](GZIP_MEMBER_INDEX.csv)。这不是仅发布批次索引：完整单表已经实际生成并可单独下载。

发布前重新读到最终gzip的EOF，逐一核对291,904个键唯一、无额外键、与完整scalar全集相等、ABC引用无缺口。人员、人数、参考、节点票数、支持门槛、状态与完整scalar逐字段核对；原生Q、D10与原scalar核对但没有调用评分函数。geometry经JSON序列化后与原生对象精确相等，未做几何修复或重新对齐。

本次峰值RSS为 **{r['peak_rss_kib']/1024:.1f} MiB**，本次完成运行约 **{r['elapsed_seconds']:.1f}秒**，不含先前已保存分片的初次导出时间。完整记录见 [RECOVERY_RECEIPT.json](RECOVERY_RECEIPT.json)。

## 5. 复现与交付组成

在仓库相同相对目录下运行：

```bash
python research/workers/personnel_useful_taxonomy_v3_20261021/integration/phase1_geometry_recovery/recover_geometry.py
python research/workers/personnel_useful_taxonomy_v3_20261021/integration/phase1_geometry_recovery/write_recovery_report.py
```

`recover_geometry.py` 不导入融合或评分引擎。中断后会读取已保存的完整分片并跳过已有键；不会接受不完整的gzip分片作为完成结果。

交付分为完整geometry单表，以及 `HOHONET_phase1_geometry_恢复代码与索引_20261021.zip` 小包。小包包含代码、报告、字段和校验索引，**不重复嵌入完整geometry表或原生大缓存**。源scalar和完整事件由总交付分别提供；本恢复只补回之前未以可下载形式发布的逐团队几何。
'''
    (HERE/'README_ZH.md').write_text(text,encoding='utf-8')
    names=['README_ZH.md','recover_geometry.py','write_recovery_report.py','RECOVERY_RECEIPT.json',
        'GEOMETRY_FIELD_DICTIONARY.csv','GEOMETRY_SHARD_INDEX.csv','GZIP_MEMBER_INDEX.csv','POOL_COVERAGE.csv',
        'SOURCE_CACHE_MANIFEST.csv','MISSING_KEYS.csv']
    mainfile=HERE/r['output'];manifest=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p),role='complete_geometry_table' if p==mainfile else 'recovery_metadata') for p in [mainfile]+[HERE/n for n in names]]
    with (HERE/'DELIVERY_MANIFEST.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['path','bytes','sha256','role']);w.writeheader();w.writerows(manifest)
    names.append('DELIVERY_MANIFEST.csv')
    archive=HERE/'HOHONET_phase1_geometry_恢复代码与索引_20261021.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(HERE/name,name)
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    out=dict(full_geometry_file=mainfile.name,full_geometry_bytes=mainfile.stat().st_size,full_geometry_sha256=sha(mainfile),
        metadata_package=archive.name,metadata_package_bytes=archive.stat().st_size,metadata_package_sha256=sha(archive),
        standalone_report='README_ZH.md',rows=r['rows'],abc_keys=r['abc_referenced_recovered'],missing=0,new_fusion_calls=0,new_score_calls=0)
    (HERE/'DELIVERY_RECEIPT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False))

if __name__=='__main__':main()
