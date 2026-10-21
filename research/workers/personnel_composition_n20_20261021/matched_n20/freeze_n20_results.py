"""Freeze completed whole-building checkpoint shards, with no mutable files.

The zip contains the already verified rows, receipts, code and source hashes.
Later calls only package newly completed buildings and never rewrite a batch.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,json,os,zipfile
from pathlib import Path
from discover_n20_abc import HERE,read_csv,save_json,sha

def freeze(condition,selected=None):
    base=HERE/('checkpointed_'+condition);plan=read_csv(base/'CHECKPOINT_PLAN.csv')
    ready=base/'ready';ready.mkdir(exist_ok=True)
    sealed=set();committed=list(ready.glob('BATCH_*_ZIP_RECEIPT.json'))
    # A manifest alone is not a committed batch: interruption during ZIP
    # creation must remain recoverable and cannot silently seal its rows.
    for p in committed:sealed.update(json.loads(p.read_text())['buildings'])
    groups=collections.defaultdict(list)
    for r in plan:groups[r['building']].append(r)
    complete=[b for b,rs in sorted(groups.items()) if b not in sealed and all((base/'shards'/(r['part']+'_RECEIPT.json')).exists() for r in rs)]
    if selected:complete=[b for b in complete if b in selected]
    if not complete:print(json.dumps({'new_complete_buildings':0}));return
    parts=[r for b in complete for r in groups[b]];events=0;ids=set();files=[];fail=0;info=[]
    for r in parts:
        rp=base/'shards'/(r['part']+'_RECEIPT.json');rec=json.loads(rp.read_text())
        path=HERE/rec['output']['path'];assert sha(path)==rec['output']['sha256']
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as f:
            reader=csv.reader(f);header=next(reader);assert len(header)==697
            index=header.index('event_id');keys=[]
            for row in reader:assert len(row)==697;keys.append(row[index])
        assert len(keys)==rec['events']==int(r['events'])
        wanted=[x['event_id'] for x in read_csv(HERE/r['input_path'])];assert keys==wanted
        assert not ids.intersection(keys);ids.update(keys)
        events+=len(keys);fail+=rec['events']-rec['all_complete'];files.extend([path,rp])
        info.append(dict(part=r['part'],building=r['building'],events=len(keys),all_complete=rec['all_complete'],columns=697,sha256=sha(path)))
    number=1+max([int(p.name.split('_')[1]) for p in committed],default=0);tag=f'BATCH_{number:03d}'
    note=ready/(tag+'_ZH.md')
    note.write_text(f'# {condition} n20 匹配对照结果分批保存 {number}\n\n本批封存 {len(complete)} 栋建筑、{len(parts)} 个图片池、{events:,} 个完整事件记录，其中 {events-fail:,} 个三队终点完整，{fail:,} 个含原生失败。全部失败留在表中，缺失不置零。\n\n建筑：'+', '.join(complete)+'。\n\n每个事件表保留 697 个字段：三个实际团队、成员交集和替换块、类别人数向量、n 与真实 m、质量各分项、几何距离、效率来源和失败状态。每片已读回验证行数、列宽、唯一事件 ID，并与冻结设计的相应主键按序完全一致。\n\nA/B/C 是实际团队对照臂，与人员类别数量无关。本批是各方法预登记有限成员集合面板内的全部合格对照；不代表全人口所有成员集合穷举。后续仍按相同冻结设计补齐其余建筑，不根据本批结果改变选择规则。总体统计待全部建筑完成后统一汇总，建筑间支持数量不均，不能以本批事件数直接充当独立样本量。\n\n本包无新增融合或评分；结果来自既有终点缓存。相关终点输入哈希见包内 INDEX_RECEIPT_SNAPSHOT.json，精确设计另有冻结包。\n',encoding='utf-8')
    index_snapshot=ready/(tag+'_INDEX_RECEIPT_SNAPSHOT.json');index_snapshot.write_text((base/'INDEX_RECEIPT.json').read_text())
    files.extend([note,index_snapshot,HERE/'event_kernel.py',HERE/'evaluate_n20_checkpointed.py',HERE/'evaluate_n20_abc.py',HERE/'discover_n20_abc.py',HERE/'KERNEL_EQUIVALENCE_CHECK.json',HERE/'atomic_checkpoint_io.py'])
    files.extend([base/'CHECKPOINT_PLAN.csv',base/'PLAN_RECEIPT.json'])
    manifest=dict(condition=condition,batch=tag,buildings=complete,pools=len(parts),events=events,all_complete=events-fail,
       immutable=True,all_expected_ids_for_selected_buildings_verified=True,part_results=info,
       files=[dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=sha(p)) for p in files])
    m=ready/(tag+'_MANIFEST.json');save_json(m,manifest);files.append(m)
    target=ready/f'HOHONET_n20_{condition}_匹配对照结果_第{number:03d}批_{events}事件.zip'
    pending=target.with_suffix('.zip.pending')
    with zipfile.ZipFile(pending,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in files:z.write(p,str(p.relative_to(HERE)))
    with zipfile.ZipFile(pending) as z:
        assert z.testzip() is None
        import hashlib
        for p in files:assert hashlib.sha256(z.read(str(p.relative_to(HERE)))).hexdigest()==sha(p)
    os.replace(pending,target)
    receipt=dict(path=str(target),bytes=target.stat().st_size,sha256=sha(target),batch=tag,events=events,buildings=complete)
    save_json(ready/(tag+'_ZIP_RECEIPT.json'),receipt);print(json.dumps(receipt,ensure_ascii=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--condition',required=True);p.add_argument('--buildings',nargs='*');a=p.parse_args();freeze(a.condition,a.buildings)
