"""Package existing complete events as lossless relational research tables.

This is a delivery projection, not a new experiment. Every input row and every
event change/ratio/risk field is retained. Repeated endpoint measurements are
linked to ENDPOINT_SCALARS by the existing canonical team key. Full category
vectors link to ENDPOINT_CLASS_VECTORS, never reconstructed from class IDs
pooled across folds. Exact member differences are taken from registered orders.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, itertools, json, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
SCALARS = WORK/'results/ENDPOINT_SCALARS.csv.gz'
ORDERS = WORK/'composition/EXACT_ORDER_DESIGN.csv.gz'
VECTORS = WORK/'composition/ENDPOINT_CLASS_VECTORS.csv.gz'
SPECS = {
    'natural_adjacent': dict(
        source='difficulty/final24/NATURAL_ADJACENT_TRANSITIONS.csv.gz',
        output='NATURAL_ADJACENT_TRANSITIONS_LINKED.csv.gz',
        before=dict(arm='previous',key='team_key_previous',path='path_id',k='k_previous'),
        after=dict(arm='current',key='team_key',path='path_id',k='k'),
        direction='current minus previous; adjacent prefixes within the same order'),
    'natural_intervals': dict(
        source='difficulty/final24/NATURAL_PAIRED_PATH_INTERVALS.csv.gz',
        output='NATURAL_PAIRED_PATH_INTERVALS_LINKED.csv.gz',
        before=dict(arm='from',key='team_key_from',path='path_id',k='k_from'),
        after=dict(arm='to',key='team_key_to',path='path_id',k='k_to'),
        direction='to minus from; the original registered path interval'),
    'policy_paired': dict(
        source='composition/final/POLICY_PAIRED_PREFIX_EVENTS.csv.gz',
        output='POLICY_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',
        before=dict(arm='natural',key='natural_team_key',path='base_path_id',k='k'),
        after=dict(arm='priority',key='priority_team_key',path='path_id',k='k'),
        direction='priority minus its exact paired natural prefix',expected_rows=229050),
    'policy_direct': dict(
        source='composition/final/POLICY_DIRECT_PAIRED_PREFIX_EVENTS.csv.gz',
        output='POLICY_DIRECT_PAIRED_PREFIX_EVENTS_LINKED.csv.gz',
        before=dict(arm='comparison',key='comparison_team_key',path='comparison_path_id',k='k'),
        after=dict(arm='focal',key='focal_team_key',path='path_id',k='k'),
        direction='focal priority role minus comparison priority role at the same base path and n',expected_rows=112520)
}

# Keep these endpoint values in place so Q, time and failure remain directly
# readable. All other directly recoverable scalar values are represented once
# in the endpoint table. Unknown/unmapped derived endpoint fields stay intact.
READABLE_ENDPOINT_FIELDS = {
    'B8L2','D10','nodes','source_time_total_seconds','target_time_total_seconds',
    'score_available','score_unavailable','score_failure_nonpolicy',
    'incomplete_nonpolicy','complete_evaluable','complete_floor_evaluable',
    'policy_deferred','sorting_deferred','geometry_unavailable','geometry_available',
    'below_four','below_four_flag','connection_unavailable','connection_available',
    'score_status','geometry_status','minimum_support','selected_support_min',
    'selected_node_support_min','selected_node_support_mean','node_supports',
    'team_key','k','path_id','pool_id','member_workers','member_object_ids'
}
ALIASES = {'floor_turn5':'floor_turn5_n'}
ADDED_COLUMNS = ['source_row_1based','members_added','members_removed',
                 'members_added_n','members_removed_n','members_shared_n']


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def stat_signature(path):
    s=Path(path).stat();return dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns)


def atomic_json(path,obj):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    with temp.open('w') as f:
        json.dump(obj,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    temp.replace(path)


def atomic_csv(path, rows, fields=None):
    path=Path(path);temp=path.with_name(path.name+'.tmp')
    if fields is None:fields=list(rows[0]) if rows else []
    with temp.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    temp.replace(path)


def header(path):
    op=gzip.open if str(path).endswith('.gz') else open
    with op(path,'rt',encoding='utf-8-sig',newline='') as f:return next(csv.reader(f))


def read_orders():
    out={}
    with gzip.open(ORDERS,'rt',encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            workers=tuple(r['worker_order'].split('|'))
            assert len(workers)==int(r['pool_n']) and len(set(workers))==len(workers)
            assert r['path_id'] not in out
            out[r['path_id']]=(r['pool_id'],workers)
    return out


def canonical_key(pid,workers):
    raw=json.dumps(sorted(workers),sort_keys=True,separators=(',',':')).encode()
    return pid+'__'+hashlib.sha256(raw).hexdigest()[:20]


def column_plan(name,spec,columns,endpoint_fields):
    plan=[];keep=[]
    for pos,c in enumerate(columns):
        p=dict(dataset=name,input_position=pos+1,event_column=c,action='keep',
               arm='',endpoint_key_column='',endpoint_column='',restore_expression='',
               reason='event identity, metadata, or previously computed change/ratio/risk')
        for side in ('before','after'):
            arm=spec[side]['arm'];suffix='_'+arm
            if not c.endswith(suffix):continue
            base=c[:-len(suffix)];endpoint=ALIASES.get(base,base)
            p.update(arm=arm,endpoint_key_column=spec[side]['key'])
            if endpoint in endpoint_fields:
                p.update(endpoint_column=endpoint,restore_expression=f'ENDPOINT_SCALARS[{spec[side]["key"]}].{endpoint}')
                if base not in READABLE_ENDPOINT_FIELDS:
                    p.update(action='link_endpoint',reason='repeated raw endpoint measurement; event change retained')
                else:p['reason']='retain Q/D10, nodes, time, identity or failure/support state for direct reading'
            else:
                p['reason']='retain original derived/state field: no direct endpoint-column replacement'
            break
        if p['action']=='keep':keep.append(pos)
        plan.append(p)
    # No unsuffixed event field may be removed; all source deltas are untouched.
    assert all(p['action']=='keep' for p in plan if not p['arm'])
    return keep,plan


def relation_rows(name,spec):
    rows=[]
    for side in ('before','after'):
        a=spec[side]
        rows.append(dict(dataset=name,linked_file=spec['output'],side=side,arm=a['arm'],
            event_team_key_column=a['key'],endpoint_table='../results/ENDPOINT_SCALARS.csv.gz',
            endpoint_join_key='team_key',endpoint_join_cardinality='many events to one exact member set',
            event_path_column=a['path'],event_k_column=a['k'],
            prefix_table='../results/PREFIX_RESULTS.csv.gz',prefix_join_keys='path_id|k',
            order_table='../composition/EXACT_ORDER_DESIGN.csv.gz',order_join_key='path_id',
            member_rule='first k entries of worker_order; full set also in ENDPOINT_SCALARS.member_workers',
            class_vector_table='../composition/ENDPOINT_CLASS_VECTORS.csv.gz',class_vector_join_key='team_key',
            class_axes_table='../composition/CLASS_VECTOR_AXES_BY_POOL.csv',
            class_scope='local held-out-building fold; preserve UNKNOWN counts and do not pool class IDs across folds',
            delta_direction=spec['direction']))
    return rows


def compact_one(name,spec,orders,endpoint_fields,chunk_size):
    source=WORK/spec['source'];target=HERE/spec['output']
    before=stat_signature(source);source_sha=digest(source)
    fields=header(source);indices,plan=column_plan(name,spec,fields,endpoint_fields)
    kept=[fields[i] for i in indices];assert not set(ADDED_COLUMNS)&set(kept)
    ix={v:i for i,v in enumerate(fields)}
    cols=kept+ADDED_COLUMNS
    tmp=target.with_name(target.name+'.tmp')
    source_rows=output_rows=0;read_blocks=0
    with gzip.open(source,'rt',encoding='utf-8-sig',newline='') as f, \
         gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=6) as h:
        reader=csv.reader(f);assert next(reader)==fields
        writer=csv.writer(h);writer.writerow(cols)
        while True:
            block=list(itertools.islice(reader,chunk_size))
            if not block:break
            read_blocks+=1
            for row in block:
                source_rows+=1;assert len(row)==len(fields)
                sets=[]
                for side in ('before','after'):
                    a=spec[side];pid,order=orders[row[ix[a['path']]]]
                    k=int(float(row[ix[a['k']]]));assert 1<=k<=len(order)
                    members=set(order[:k]);key=row[ix[a['key']]]
                    assert key==canonical_key(pid,members),(name,source_rows,side,key)
                    sets.append(members)
                added=sets[1]-sets[0];removed=sets[0]-sets[1];shared=len(sets[0]&sets[1])
                if 'actual_m' in ix:
                    assert len(added)==len(removed)==int(float(row[ix['actual_m']]))
                if 'shared_n' in ix:assert shared==int(float(row[ix['shared_n']]))
                if name.startswith('natural_'):assert not removed
                writer.writerow([row[i] for i in indices]+[source_rows,'|'.join(sorted(added)),
                    '|'.join(sorted(removed)),len(added),len(removed),shared])
                output_rows+=1
    assert before==stat_signature(source),'Source changed during packaging'
    assert output_rows==source_rows
    if 'expected_rows' in spec:assert output_rows==spec['expected_rows']
    # A separate bounded-memory reread confirms every numbered source row was
    # physically written, without repeating scientific analysis.
    reread=0
    with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
        reader=csv.reader(f);assert next(reader)==cols
        row_idx=cols.index('source_row_1based')
        for row in reader:
            reread+=1;assert len(row)==len(cols) and int(row[row_idx])==reread
    assert reread==source_rows
    tmp.replace(target)
    atomic_csv(HERE/(name+'_COLUMN_MAP.csv'),plan)
    receipt=dict(dataset=name,stage='complete_relational_delivery',source=spec['source'],output=target.name,
        input_rows=source_rows,output_rows=output_rows,reread_rows=reread,
        input_columns=len(fields),retained_source_columns=len(kept),linked_endpoint_columns=len(fields)-len(kept),
        added_relation_columns=ADDED_COLUMNS,output_columns=len(cols),input_bytes=before['bytes'],
        output_bytes=target.stat().st_size,source_sha256=source_sha,output_sha256=digest(target),
        chunk_rows=chunk_size,chunks_read=read_blocks,all_rows_retained=True,all_event_changes_retained=True,
        original_values='Kept fields copied as original strings; no value imputation, rounding, rescoring or event filtering.',
        member_differences='Exact registered prefix sets; canonical team keys checked; added/removed are after minus before and before minus after.',
        endpoint_join='ENDPOINT_SCALARS.csv.gz team_key',class_vector_join='ENDPOINT_CLASS_VECTORS.csv.gz team_key',
        code_sha256=digest(Path(__file__)),fusion_calls=0,quality_scores_recomputed=0)
    atomic_json(HERE/(name+'_DELIVERY_RECEIPT.json'),receipt)
    print(json.dumps({k:receipt[k] for k in ['dataset','input_rows','output_rows','input_columns','output_columns','input_bytes','output_bytes']},ensure_ascii=False),flush=True)
    return receipt


def write_index():
    receipts=[];columns=[];relations=[]
    for name,spec in SPECS.items():
        p=HERE/(name+'_DELIVERY_RECEIPT.json')
        if not p.exists():continue
        r=json.loads(p.read_text());receipts.append(r);relations+=relation_rows(name,spec)
        with (HERE/(name+'_COLUMN_MAP.csv')).open(encoding='utf-8-sig',newline='') as f:columns+=list(csv.DictReader(f))
    atomic_csv(HERE/'COLUMN_RETENTION_AND_ENDPOINT_MAP.csv',columns)
    atomic_csv(HERE/'EVENT_RELATION_MAP.csv',relations)
    coverage=[{k:r[k] for k in ['dataset','source','output','input_rows','output_rows','reread_rows','input_columns',
        'retained_source_columns','linked_endpoint_columns','output_columns','input_bytes','output_bytes','source_sha256','output_sha256']} for r in receipts]
    atomic_csv(HERE/'DELIVERY_COVERAGE.csv',coverage)
    text=['# 完整事件的关系式交付','',
        '这些文件是已经完成的自然人数与类别进入顺序实验的完整事件表。只将两端重复的原始测量移到一次保存的端点表，通过精确 `team_key` 关联；未删除事件、失败、负向结果或任何已计算的事件差值。原宽表不改动。','',
        '每个源按5,000行分块处理，输出后重新逐行读取，确认 `source_row_1based` 从1连续到源表末行。新增成员差集按登记顺序的实际前缀取得；两端canonical键与源事件一致。同人数政策比较的差集人数同时与已有actual_m核对。该步骤用于交付关联，不新增融合或质量评价。','',
        '## 实际文件与覆盖','',
        '| 表 | 完整行数 | 原列数 | 保留原列 | 改为端点关联的列 | 输出列数（另含6个关联字段） | 压缩大小 MB |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in receipts:
        text.append(f"| [{r['output']}]({r['output']}) | {r['output_rows']:,} | {r['input_columns']} | {r['retained_source_columns']} | {r['linked_endpoint_columns']} | {r['output_columns']} | {r['output_bytes']/1e6:.2f} |")
    text+=['','## 怎样继续分析','',
        '1. 直接用本表中全部 `*_change`、`*_delta`、`*_ratio`、`*_logratio`、净席位变化和风险字段重聚合；这些值按原字符串保留，没有重算或补缺。两端Q、D10、节点、记录总时间和评分/失败状态也保留，便于直接读。',
        '2. 读取同一交付中的 `results/ENDPOINT_SCALARS.csv.gz`，按关系映射中每端的 `team_key` 左连接。底面、三维、定位、尺度、边界、短边和参考对应等其余原值每个唯一成员集合只保存一次。`COLUMN_RETENTION_AND_ENDPOINT_MAP.csv` 逐列给出保留/关联决定及目标列。',
        '3. 两端完整成员可从端点的 `member_workers` / `member_object_ids` 取得。新增 `members_added` / `members_removed` 直接列出方向上的成员差集；空字符串表示差集确实为空。自然前缀是增加成员，不冒称为等人数替换。',
        '4. 完整类别人数向量按同一 `team_key` 连接 `composition/ENDPOINT_CLASS_VECTORS.csv.gz`，包含结构粗/细类、联合粗/细类及UNKNOWN人数；类别轴由 `CLASS_VECTOR_AXES_BY_POOL.csv` 定义。保留逐池楼外语义，不把不同折的编号当同一类型。已有目标类人数、容量、净席位变化仍在事件中。',
        '5. 路径过程、进入者与来源用 `path_id` 和 `k` 关联 `results/PREFIX_RESULTS.csv.gz`；精确无放回顺序、抽样权重、角色和楼外来源用 `path_id` 关联 `composition/EXACT_ORDER_DESIGN.csv.gz`。端点重复使用不增加独立成员集合数。','',
        '## 方向与文件身份','',
        '- 自然相邻：current − previous；当前键为 `team_key`，前端键为 `team_key_previous`。',
        '- 自然区间：to − from；区间原名、人数与路径保持原样。',
        '- 政策对自然：priority − natural；自然使用 `base_path_id`，政策使用 `path_id`，人数相同。',
        '- 角色直接对照：focal − comparison；两个角色使用同一 `base_path_id` 与人数，原角色重叠、实际m、全部类别向量席位变化都保留。','',
        '`source_row_1based` 是原CSV数据行号（不含表头），可定位历史宽表，不是新的抽样权重。表中空值、失败和n2排序延期沿用原分析。未直接出现在端点表的自然派生量，例如参考转折差和一些状态旗标，仍保留两端原值，避免信息损失。','',
        '## 清单与复现','',
        '- [DELIVERY_COVERAGE.csv](DELIVERY_COVERAGE.csv)：源/目标行数、实际字节和SHA。',
        '- [COLUMN_RETENTION_AND_ENDPOINT_MAP.csv](COLUMN_RETENTION_AND_ENDPOINT_MAP.csv)：全部原列的决定与恢复字段。',
        '- [EVENT_RELATION_MAP.csv](EVENT_RELATION_MAP.csv)：每种事件各端的端点、前缀、顺序及类别向量关联。',
        '- [build_linked_event_tables.py](build_linked_event_tables.py)：实际整理代码；逐源回执保留独立阶段。','',
        '在完整本轮目录下运行：','',
        '```bash','python population_work/compact_events/build_linked_event_tables.py','```','',
        '可用 `--datasets natural_adjacent natural_intervals policy_paired policy_direct` 选定一部分，完成一表即保存并刷新索引。本目录依赖上面明确列出的端点、前缀、顺序与类别向量；它不通过省略这些依赖来冒称单文件自足。']
    p=HERE/'README.md';tmp=p.with_name(p.name+'.tmp');tmp.write_text('\n'.join(text),encoding='utf-8');tmp.replace(p)
    manifest=[]
    for p in sorted(HERE.iterdir()):
        if p.is_file() and p.name!='FILE_MANIFEST.csv' and not p.name.endswith('.tmp'):
            manifest.append(dict(file=p.name,bytes=p.stat().st_size,sha256=digest(p)))
    atomic_csv(HERE/'FILE_MANIFEST.csv',manifest)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--datasets',nargs='+',choices=list(SPECS),default=list(SPECS));ap.add_argument('--chunk-rows',type=int,default=5000)
    args=ap.parse_args();HERE.mkdir(parents=True,exist_ok=True)
    endpoint_fields=set(header(SCALARS));orders=read_orders()
    for name in args.datasets:
        compact_one(name,SPECS[name],orders,endpoint_fields,args.chunk_rows)
        write_index()


if __name__=='__main__':main()
