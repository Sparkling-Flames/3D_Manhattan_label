"""Complete-order context for five previously selected mechanism cases.

Reads finished prefix results only. Natural all-order distributions and exact
paired policy comparisons have separate arms and denominators. Reference-node
presence is the saved geometry diagnostic, not identity-group/vote continuity.
No fusion, scoring, classification or selective order removal is performed.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, math, os
from pathlib import Path
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
WORK = Path(os.environ.get('HOHONET_POPULATION_WORKSPACE', '/workspace/scratch/fe955c3c772c'))/'population_work'
IMAGES = ['UwV83HsGsw3-12','pa4otMbVnkk-09','UwV83HsGsw3-09','uNb9QFRL6hY-60','B6ByNegPMKs-33']
KEY_CORNERS = {'UwV83HsGsw3-12':[4], 'uNb9QFRL6hY-60':[8],
    'UwV83HsGsw3-09':[3,4,5,6], 'pa4otMbVnkk-09':[1,2,3,4],
    'B6ByNegPMKs-33':[1,2,3,4]}
METRICS = ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
    'omission','extension','nodes','height_mean_h','height_sd_h','floor_area_camera_h2',
    'floor_turn5_n','floor_redundant5_n','source_time_total_seconds','target_time_total_seconds',
    'ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9',
    'ref_top_pair_mean_deg','ref_bottom_pair_mean_deg']
IDENTITY_COLUMNS = ['pool_id','image','image_id','building','condition','layer','difficulty','pool_n',
    'path_id','base_path_id','replicate','policy','k','team_key','sample_kind','generation',
    'target_class','method','tier','target_capacity','target_present_n','entrant_worker',
    'member_workers','member_object_ids','minimum_support','reference_id','reference_version','reference_nodes',
    'complete_evaluable','geometry_available','endpoint_origin','score_status','source_time_known_n',
    'target_time_known_n','source_time_known_sum_seconds','time_source_kinds',
    'ref_matched_nodes_5','ref_matched_nodes_9','ref_matched_edges_5','ref_matched_edges_9']
POLICY_ZH = {'natural_random':'自然随机', 'structure_moreturn_first':'较多转折类优先',
    'structure_dominant_first':'历史常规结构类优先','joint_highq_first':'联合较高历史Q类优先',
    'joint_fast_first':'联合较快类优先'}


def atomic(p, raw):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp')
    with tmp.open('wb') as h:h.write(raw);h.flush();os.fsync(h.fileno())
    tmp.replace(p)


def save_csv(p,d):
    raw=d.to_csv(index=False).encode('utf-8-sig')
    atomic(p,gzip.compress(raw,mtime=0) if str(p).endswith('.gz') else raw)


def save_json(p,d):
    atomic(p,json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False).encode())


def truth(v):
    return str(v).lower() in ('true','1','1.0')


def number(v):
    try:
        value=float(v)
        return value if math.isfinite(value) else np.nan
    except (TypeError,ValueError):
        return np.nan


def parse_matched(v, recall):
    """None is unknown; an empty set with finite zero recall is observed zero."""
    if not math.isfinite(number(recall)):
        return None
    if isinstance(v,(list,tuple)):
        return {int(x) for x in v}
    s=str(v).strip()
    if s not in ('','nan','None','null','<NA>'):
        if s.startswith('['):return {int(x) for x in json.loads(s)}
        return {int(float(x)) for x in s.split('|') if x.strip()}
    return set()


def stats(values):
    x=np.asarray([number(a) for a in values],float);x=x[np.isfinite(x)]
    if not len(x):return dict(n=0,mean=np.nan,sd=np.nan,p10=np.nan,p50=np.nan,p90=np.nan,min=np.nan,max=np.nan)
    return dict(n=int(len(x)),mean=float(x.mean()),sd=float(x.std(ddof=1)) if len(x)>1 else np.nan,
        p10=float(np.quantile(x,.1)),p50=float(np.quantile(x,.5)),p90=float(np.quantile(x,.9)),
        min=float(x.min()),max=float(x.max()))


def node_diagnostics(row, nref):
    out={}
    for t in (5,9):
        matched=parse_matched(row.get(f'ref_matched_nodes_{t}'),row.get(f'ref_node_recall_{t}'))
        if matched is not None:
            assert matched<=set(range(nref)), (row['image'],row['k'],t,matched,nref)
            assert abs(len(matched)/nref-number(row.get(f'ref_node_recall_{t}')))<1e-9, \
                ('saved match-list / recall inconsistency',row['image'],row['team_key'],t)
        out[f'ref_diag_known_{t}']=matched is not None
        for j in range(nref):out[f'R{j+1}_present_{t}']=float(j in matched) if matched is not None else np.nan
    return out


def summarize_arm(g, arm, policy, meta, nref):
    q=stats(g.B8L2)
    row=dict(meta,comparison_policy=policy,arm=arm,k=int(g.k.iloc[0]),
        attempted_paths=len(g),unique_teams=g.team_key.nunique(),
        scorable_paths=q['n'],scorable_unique_teams=g.loc[g.B8L2.notna(),'team_key'].nunique(),
        failure_nonpolicy_n=int(g.failure_nonpolicy.sum()),
        incomplete_nonpolicy_n=int(g.incomplete_nonpolicy.sum()),
        policy_deferred_n=int(g.policy_deferred.sum()),
        failure_nonpolicy_rate=float(g.failure_nonpolicy.mean()),
        incomplete_nonpolicy_rate=float(g.incomplete_nonpolicy.mean()),
        nonpolicy_attempts=int((~g.policy_deferred).sum()))
    row['failure_rate_nonpolicy_attempts']=row['failure_nonpolicy_n']/row['nonpolicy_attempts'] if row['nonpolicy_attempts'] else np.nan
    for m in METRICS:
        for key,value in stats(g[m]).items():row[m+'_'+key]=value
    row['variance_estimable_from_distinct_scorable_teams']=row['scorable_unique_teams']>=2
    row['at_full_pool']=row['k']==meta['pool_n']
    row['fixed_endpoint_reason']='full_actual_pool' if row['at_full_pool'] else ('one_observed_set' if row['unique_teams']==1 else 'multiple_sets')
    nodes=[]
    for t in (5,9):
        for j in range(nref):
            s=g[f'R{j+1}_present_{t}'];valid=int(s.notna().sum());present=int(s.fillna(0).sum())
            nodes.append(dict(meta,comparison_policy=policy,arm=arm,k=int(g.k.iloc[0]),
                angle_threshold_deg=t,reference_corner_1based=j+1,stored_reference_index_0based=j,
                focal_corner=(j+1 in KEY_CORNERS[meta['image']]),attempted_paths=len(g),
                geometry_diagnostic_paths=valid,unknown_geometry_paths=len(g)-valid,
                present_paths=present,absent_paths=valid-present,
                present_rate_given_diagnostic=present/valid if valid else np.nan,
                presence_lower_bound_all_attempts=present/len(g),
                presence_upper_bound_all_attempts=(present+len(g)-valid)/len(g),
                failure_nonpolicy_n=row['failure_nonpolicy_n'],policy_deferred_n=row['policy_deferred_n'],
                diagnostic='saved output-pair Hungarian match, not identity-group correspondence'))
            if len(KEY_CORNERS[meta['image']])==1 and j+1==KEY_CORNERS[meta['image']][0]:
                row[f'key_R{j+1}_present_{t}_n']=present
                row[f'key_R{j+1}_diagnostic_{t}_n']=valid
                row[f'key_R{j+1}_present_{t}_rate']=present/valid if valid else np.nan
    return row,nodes


def read_finished(results, completion, orders):
    if not results.exists() or not completion.exists():
        raise SystemExit('Final PREFIX_RESULTS.csv.gz / COMPLETION.json not yet available; no partial case context emitted.')
    comp=json.loads(completion.read_text())
    assert comp.get('missing')==0
    assert comp['paths']==len(orders)
    assert comp['prefix_rows']==int(orders.pool_n.sum())
    before=results.stat();parts=[];total=0
    wanted=set(IDENTITY_COLUMNS+METRICS)
    for chunk in pd.read_csv(results,chunksize=10000,usecols=lambda c:c in wanted,
                            keep_default_na=False,low_memory=False):
        total+=len(chunk)
        q=chunk[chunk.image.isin(IMAGES)&chunk.condition.eq('manual')].copy()
        if len(q):parts.append(q)
    after=results.stat()
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),'Input changed during read'
    assert total==comp['prefix_rows'],(total,comp['prefix_rows'])
    d=pd.concat(parts,ignore_index=True)
    selected=orders[orders.image.isin(IMAGES)&orders.condition.eq('manual')]
    assert len(d)==int(selected.pool_n.sum())
    assert not d.duplicated(['path_id','k']).any()
    counts=d.groupby('path_id').k.agg(['size','min','max'])
    for r in selected.itertuples():
        c=counts.loc[r.path_id];assert (c['size'],c['min'],c['max'])==(r.pool_n,1,r.pool_n)
    return d,selected,comp,dict(bytes=after.st_size,mtime_ns=after.st_mtime_ns,rows=total)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--results',type=Path,default=WORK/'results/PREFIX_RESULTS.csv.gz')
    parser.add_argument('--completion',type=Path,default=WORK/'results/COMPLETION.json')
    parser.add_argument('--orders',type=Path,default=WORK/'composition/EXACT_ORDER_DESIGN.csv.gz')
    parser.add_argument('--out',type=Path,default=OUT/'final_context')
    args=parser.parse_args();out=args.out
    orders=pd.read_csv(args.orders,keep_default_na=False)
    d,selected,completion,source_stat=read_finished(args.results,args.completion,orders)
    dims=pd.read_csv(OUT/'CASE_DIFFICULTY_SCOPE.csv').set_index('image')
    refs,coordinates={},[]
    for image in IMAGES:
        obj=json.load(gzip.open(OUT/image/'CASE_GEOMETRY.json.gz','rt'));ref=obj['pool']['reference']
        refs[image]=dict(n=len(ref['points_1024x512'])//2,id=obj['pool']['meta']['reference_id'],
            version=obj['pool']['meta']['reference_version'],pool_id=obj['pool']['pool_id'])
        for j,pair in enumerate(np.array(ref['points_1024x512']).reshape(-1,2,2)):
            coordinates.append(dict(image=image,condition='manual',pool_id=obj['pool']['pool_id'],
                reference_id=refs[image]['id'],reference_version=refs[image]['version'],
                reference_corner_1based=j+1,stored_reference_index_0based=j,
                x_top_px=pair[0,0],y_top_px=pair[0,1],x_bottom_px=pair[1,0],y_bottom_px=pair[1,1],
                focal_corner=j+1 in KEY_CORNERS[image]))
    for m in METRICS:
        if m not in d:d[m]=np.nan
        d[m]=pd.to_numeric(d[m],errors='coerce').replace([np.inf,-np.inf],np.nan)
    d['policy_deferred']=d.k.eq(2)
    d['failure_nonpolicy']=d.B8L2.isna()&~d.policy_deferred
    d['incomplete_nonpolicy']=~d.complete_evaluable.map(truth)&~d.policy_deferred
    extra=[]
    for row in d.to_dict('records'):
        rr=refs[row['image']]
        assert row['reference_id']==rr['id'] and row['reference_version']==rr['version']
        extra.append(node_diagnostics(row,rr['n']))
    d=pd.concat([d.reset_index(drop=True),pd.DataFrame(extra)],axis=1)
    # Matched lists are serialized zero-based reference positions. They do not
    # identify frozen identity groups, whose node IDs may change between teams.
    arms,reference_curves,events,effects=[],[],[],[]
    for image in IMAGES:
        im=d[d.image.eq(image)];od=selected[selected.image.eq(image)];nr=refs[image]['n']
        meta=dict(image=image,condition='manual',building=od.building.iloc[0],pool_id=refs[image]['pool_id'],
            pool_n=int(od.pool_n.iloc[0]),difficulty=dims.loc[image,'difficulty_coarse'],
            structure_opportunity=dims.loc[image,'structure_opportunity'],
            reference_id=refs[image]['id'],reference_version=refs[image]['version'])
        natural=im[im.policy.eq('natural_random')]
        assert natural.path_id.nunique()==24
        for k,g in natural.groupby('k'):
            row,node=summarize_arm(g,'natural_all24','natural_random',meta,nr)
            arms.append(row);reference_curves.extend(node)
        for policy,pp in im[~im.policy.eq('natural_random')].groupby('policy'):
            po=od[od.policy.eq(policy)].set_index('path_id');assert len(po)==8
            for field in ('target_class','method','tier','target_capacity','target_members'):
                assert po[field].nunique(dropna=False)==1, (image,policy,field)
            target_meta={k:po[k].iloc[0] for k in ['target_class','method','tier','target_capacity']}
            target=set(po.target_members.iloc[0].split('|'))
            for k,pg in pp.groupby('k'):
                base=natural[natural.k.eq(k)].set_index('path_id')
                ng=base.loc[pg.base_path_id.tolist()].copy().reset_index()
                assert len(pg)==len(ng)==8
                paired=[]
                for pr in pg.to_dict('records'):
                    na=base.loc[pr['base_path_id']]
                    a=set(na.member_workers.split('|'));b=set(pr['member_workers'].split('|'))
                    event=dict(meta,**target_meta,policy=policy,k=int(k),path_id=pr['path_id'],base_path_id=pr['base_path_id'],
                        natural_team_key=na.team_key,priority_team_key=pr['team_key'],
                        natural_members=na.member_workers,priority_members=pr['member_workers'],
                        actual_m=len(b-a),shared_n=len(a&b),
                        natural_target_n=len(a&target),priority_target_n=len(b&target),
                        target_seat_change=len(b&target)-len(a&target),
                        natural_failure_nonpolicy=bool(na.failure_nonpolicy),priority_failure_nonpolicy=bool(pr['failure_nonpolicy']),
                        natural_incomplete_nonpolicy=bool(na.incomplete_nonpolicy),priority_incomplete_nonpolicy=bool(pr['incomplete_nonpolicy']),
                        policy_deferred=bool(pr['policy_deferred']))
                    for m in METRICS:
                        event[m+'_natural']=na[m];event[m+'_priority']=pr[m]
                        event[m+'_delta']=pr[m]-na[m]
                    for side,rr in [('natural',na),('priority',pr)]:
                        event['source_time_known_n_'+side]=rr.get('source_time_known_n')
                        event['time_source_kinds_'+side]=rr.get('time_source_kinds')
                    time_base=number(na.source_time_total_seconds)
                    time_priority=number(pr['source_time_total_seconds'])
                    event['source_time_relative_delta_pct']=100*(time_priority-time_base)/time_base \
                        if math.isfinite(time_base) and time_base>0 and math.isfinite(time_priority) else np.nan
                    for t in (5,9):
                        event[f'ref_matched_nodes_{t}_natural']=na.get(f'ref_matched_nodes_{t}')
                        event[f'ref_matched_nodes_{t}_priority']=pr.get(f'ref_matched_nodes_{t}')
                        for corner in KEY_CORNERS[image]:
                            f=f'R{corner}_present_{t}'
                            event[f+'_natural']=na[f];event[f+'_priority']=pr[f]
                            event[f+'_delta']=pr[f]-na[f]
                    if k==meta['pool_n']:
                        assert a==b and event['actual_m']==0
                        if pd.notna(event['B8L2_delta']):assert abs(event['B8L2_delta'])<1e-10
                    events.append(event);paired.append(event)
                p=pd.DataFrame(paired)
                summaries={}
                for arm,g in [('paired_natural8',ng),('priority8',pg)]:
                    row,node=summarize_arm(g,arm,policy,dict(meta,**target_meta),nr)
                    arms.append(row);reference_curves.extend(node);summaries[arm]=row
                er=dict(meta,**target_meta,policy=policy,k=int(k),paired_paths=len(p),
                    distinct_natural_teams=ng.team_key.nunique(),distinct_priority_teams=pg.team_key.nunique(),
                    actual_m_mean=p.actual_m.mean(),actual_m_max=p.actual_m.max(),
                    target_seat_change_mean=p.target_seat_change.mean(),
                    paired_Q=int(p.B8L2_delta.notna().sum()),
                    Q_up_n=int(p.B8L2_delta.gt(0).sum()),Q_down_n=int(p.B8L2_delta.lt(0).sum()),
                    Q_gain_gt5_n=int(p.B8L2_delta.gt(5).sum()),Q_loss_gt5_n=int(p.B8L2_delta.lt(-5).sum()),
                    natural_failure_n=int(p.natural_failure_nonpolicy.sum()),priority_failure_n=int(p.priority_failure_nonpolicy.sum()),
                    natural_incomplete_n=int(p.natural_incomplete_nonpolicy.sum()),priority_incomplete_n=int(p.priority_incomplete_nonpolicy.sum()))
                for side,arm in [('natural','paired_natural8'),('priority','priority8')]:
                    for name in ['B8L2_mean','B8L2_p10','B8L2_sd','nodes_mean','failure_nonpolicy_rate']:
                        er[side+'_'+name]=summaries[arm][name]
                for m in METRICS:
                    ss=stats(p[m+'_delta'])
                    for name in ('n','mean','p10','p50','p90','sd'):er[m+'_paired_delta_'+name]=ss[name]
                er['Q_p10_difference']=er['priority_B8L2_p10']-er['natural_B8L2_p10']
                er['Q_mean_difference_of_available_arms']=er['priority_B8L2_mean']-er['natural_B8L2_mean']
                er['Q_up_fraction_given_pair']=er['Q_up_n']/er['paired_Q'] if er['paired_Q'] else np.nan
                tt=stats(p.source_time_relative_delta_pct)
                for name in ('n','mean','p10','p50','p90','sd'):
                    er['source_time_relative_delta_pct_'+name]=tt[name]
                time_good=p.source_time_relative_delta_pct.notna()
                er['source_time_ratio_of_paired_sums_pct']=100*p.loc[time_good,'source_time_total_seconds_delta'].sum()/p.loc[time_good,'source_time_total_seconds_natural'].sum() if time_good.any() else np.nan
                for t in (5,9):
                    for corner in KEY_CORNERS[image]:
                        f=f'R{corner}_present_{t}'
                        for side in ('natural','priority'):
                            vals=p[f+'_'+side]
                            er[f+'_'+side+'_n']=int(vals.notna().sum())
                            er[f+'_'+side+'_rate']=vals.mean()
                        er[f+'_paired_delta_n']=int(p[f+'_delta'].notna().sum())
                        er[f+'_paired_delta_mean']=p[f+'_delta'].mean()
                effects.append(er)
    curves=pd.DataFrame(arms);effects=pd.DataFrame(effects);node_curves=pd.DataFrame(reference_curves)
    save_csv(out/'CASE_FULL_PREFIX_ROWS.csv.gz',d)
    save_csv(out/'CASE_CURVES_BY_POLICY_K.csv',curves)
    save_csv(out/'CASE_REFERENCE_NODE_CURVES.csv',node_curves)
    save_csv(out/'CASE_POLICY_PAIRED_EVENTS.csv.gz',pd.DataFrame(events))
    save_csv(out/'CASE_POLICY_EFFECTS_BY_K.csv',effects)
    save_csv(out/'CASE_REFERENCE_INDEX.csv',pd.DataFrame(coordinates))
    save_csv(out/'CASE_EXACT_ORDERS.csv.gz',selected)
    # Fixed k and pool-relative checkpoints; duplicates intentionally retain
    # both landmark names without being pooled as independent observations.
    focal=[]
    for (image,policy),g in effects.groupby(['image','policy']):
        n=int(g.pool_n.iloc[0]);sel={f'k{k}':k for k in (3,4,5,6,8,9,10,11,20) if k<=n}
        sel.update(quarter_pool=max(3,math.ceil(n/4)),half_pool=math.ceil(n/2),threequarter_pool=math.ceil(3*n/4),full_pool=n)
        for name,k in sel.items():
            row=g[g.k.eq(k)].iloc[0].to_dict();row['landmark']=name;focal.append(row)
    focal=pd.DataFrame(focal);save_csv(out/'CASE_FOCAL_POLICY_COMPARISON.csv',focal)
    write_report(out,curves,effects,source_stat)
    plot_curves(out,curves,node_curves)
    receipt=dict(status='complete_registered_order_context_for_five_exploratory_cases',
        global_completion=completion,input_prefix_file=str(args.results),input_prefix_stat=source_stat,
        selected_images=IMAGES,condition='manual',selected_pools=5,
        case_paths=int(selected.path_id.nunique()),case_prefix_rows=len(d),
        case_unique_endpoints=int(d.team_key.nunique()),policy_paired_events=len(events),
        policy_k_rows=len(effects),reference_node_curve_rows=len(node_curves),
        natural_orders_per_case=24,paired_orders_per_case_policy=8,
        dispersion_contract='Sample standard deviation ddof=1, same convention as the main natural curve tables; n=1 undefined.',
        ref_index_contract={'UwV83HsGsw3-12_R4':3,'uNb9QFRL6hY-60_R8':7},
        geometry_identity_note='Saved output-pair Hungarian matching, distinct from historical frozen group IDs and votes.',
        native_fusion_calls=0,quality_scores_recomputed=0,
        orders_sha256=hashlib.sha256(args.orders.read_bytes()).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    save_json(out/'CASE_BACKGROUND_RECEIPT.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','case_paths','case_prefix_rows','case_unique_endpoints','policy_paired_events')},ensure_ascii=False),flush=True)


def fmt(v, digits=2):
    return '未知' if pd.isna(v) else f'{float(v):.{digits}f}'


def pct(v):
    return '未知' if pd.isna(v) else f'{100*float(v):.1f}%'


def write_report(out,curves,effects,source_stat):
    lines=['# 五个机制案例的完整顺序背景','',
        '本表在整批注册前缀结果完成后生成。机制案例仍是旧四条自然顺序中选出的探索案例；这里补入每图24条自然顺序和各政策8条精确配对顺序，不重新选择案例。',
        '',
        '自然24条描述该人员池的平均过程。政策的净变化只对比它自身对应的8条自然顺序；不把政策8条与自然24条的差直接当配对效应。每条顺序保留其抽样权重，重复终点只在计算时去重。标准差统一使用样本标准差（ddof=1），与主自然曲线表一致。',
        '',
        'R4／R8等存在率来自已存输出几何与参考点对的Hungarian对应。`ref_matched_nodes_5/9` 使用0基角号，因此Uw-12的R4查询索引3，uNb-60的R8查询索引7。它不是投票组身份的跨顺序跟踪，也不自动证明真实结构语义。匹配未知保留未知；n2延期与其他不可评分分别记录。',
        '',
        '## 自然24条：固定人数的分布','',
        '| 图 | n | Q均值 | Q P10 | Q标准差 | 可评分/路径 | 非策略失败 | 平均节点 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    nat=curves[curves.arm.eq('natural_all24')]
    for image in IMAGES:
        g=nat[nat.image.eq(image)];n=int(g.pool_n.iloc[0])
        for k in sorted(set([3,6,10,math.ceil(n/2),20,n])):
            if k>n:continue
            r=g[g.k.eq(k)].iloc[0]
            lines.append(f'| {image} | {k} | {fmt(r.B8L2_mean)} | {fmt(r.B8L2_p10)} | {fmt(r.B8L2_sd)} | {int(r.scorable_paths)}/{int(r.attempted_paths)} | {int(r.failure_nonpolicy_n)} | {fmt(r.nodes_mean)} |')
    lines+=['','## 两个关键局部：较多转折类优先的配对效果','',
        '下表使用各政策与其自然基线的8对顺序；“改善”分母为两端均有Q的路径。存在率分母为该端可取得几何匹配诊断的路径，完整分母见CSV。P10差是两端分布分位数之差，不是逐对差的P10。','',
        '| 图/局部 | n | 自然8 Q | 优先8 Q | 配对ΔQ | 改善/可比 | Q P10差 | 5°存在率：自然→优先 | 9°存在率：自然→优先 | 失败：自然→优先 |',
        '|---|---:|---:|---:|---:|---:|---:|---|---|---|']
    for image,corner in [('UwV83HsGsw3-12',4),('uNb9QFRL6hY-60',8)]:
        g=effects[effects.image.eq(image)&effects.policy.eq('structure_moreturn_first')]
        n=int(g.pool_n.iloc[0])
        ks=sorted(set([3,4,5,6,8,9,10,11,math.ceil(n/2),20,n]))
        for k in ks:
            if k>n:continue
            r=g[g.k.eq(k)].iloc[0]
            rates=[]
            for t in (5,9):
                rates.append('→'.join(pct(r[f'R{corner}_present_{t}_{s}_rate']) for s in ('natural','priority')))
            lines.append(f'| {image}/R{corner} | {k} | {fmt(r.natural_B8L2_mean)} | {fmt(r.priority_B8L2_mean)} | {fmt(r.B8L2_paired_delta_mean)} | {int(r.Q_up_n)}/{int(r.paired_Q)} | {fmt(r.Q_p10_difference)} | {rates[0]} | {rates[1]} | {int(r.natural_failure_n)}→{int(r.priority_failure_n)} |')
    lines+=['','## 所有登记政策都保留','',
        '四种政策为较多转折类优先、历史常规结构类优先、联合较高历史Q类优先、联合较快类优先。源类、目标类及其容量由目标建筑之外的历史指定。本目录保留各图每一个人数的全部结果，不只保留有利政策或人数。','',
        '| 图 | 政策 | n | 配对ΔQ | Q P10差 | 改善/可比 | 损失超过5分 | 平均实际换人数 |',
        '|---|---|---:|---:|---:|---:|---:|---:|']
    for image in IMAGES:
        g=effects[effects.image.eq(image)];n=int(g.pool_n.iloc[0])
        for policy,pg in g.groupby('policy'):
            for k in (6,math.ceil(n/2),20):
                if k>n:continue
                r=pg[pg.k.eq(k)].iloc[0]
                lines.append(f'| {image} | {POLICY_ZH.get(policy,policy)} | {k} | {fmt(r.B8L2_paired_delta_mean)} | {fmt(r.Q_p10_difference)} | {int(r.Q_up_n)}/{int(r.paired_Q)} | {int(r.Q_loss_gt5_n)} | {fmt(r.actual_m_mean,1)} |')
    lines+=interpretation(curves,effects)
    lines+=['','## 完整顺序曲线图','',
        '![五案的自然24条曲线；阴影为可评分路径的P10至P90](NATURAL_CASE_CURVES.png)','',
        '![同一终池的8对顺序；左为Q，右为关键参考角5度存在率](LOCAL_OPPORTUNITY_POLICY_CURVES.png)','',
        '局部角存在率图只使用有几何诊断的路径，失败分母另见各表。未知匹配不能计作缺失，已知零命中仍计入缺失。政策图的自然线是相应8条配对自然路径；它与上图自然24条的均值可以不同。','',
        '## 文件与适用范围','',
        '- `CASE_CURVES_BY_POLICY_K.csv`：自然24、政策8及其配对自然8分别的逐人数分布，含分项、时间、失败、节点数及各自分母。',
        '- `CASE_REFERENCE_NODE_CURVES.csv`：每个参考角、5°／9°、每个人数及每个比较臂的出现率，保留未知数；所有参考角都保存。',
        '- `CASE_POLICY_EFFECTS_BY_K.csv`：精确配对8条的净变化、方向比例、失败和关键角出现率；自然24仅另作背景。',
        '- `CASE_POLICY_PAIRED_EVENTS.csv.gz`：各顺序前缀的实际两队成员、端点、真实替换量、类别席位变化及分项差。',
        '- `CASE_FULL_PREFIX_ROWS.csv.gz`、`CASE_EXACT_ORDERS.csv.gz`：完整五案前缀与精确顺序输入切片。',
        '- `CASE_REFERENCE_INDEX.csv`：明确1基图示编号、0基保存索引与不变参考坐标。',
        '- `CASE_BACKGROUND_RECEIPT.json`：输入完整性、实际覆盖与代码身份。','',
        '全员人数处所有顺序具有同一实际成员集合，因此输出一致、方差为零是确定性终点的性质，不用它证明分类有效。某类全部先进入后也可能暂时只有一个团队集合；表中同时给出独立端点数及可估计成员波动标识。','',
        '本目录只给五张探索机制图的完整注册顺序背景，不替代全体图片／建筑的总体推断。原机制的原答、票数、门槛、对应及原图仍由上一级案例目录保存。']
    atomic(out/'CASE_CURVE_BACKGROUND.md','\n'.join(lines).encode())


def interpretation(curves,effects):
    """Evidence-linked interpretation; all new numeric claims come from tables."""
    def nat(im,k):
        return curves[curves.image.eq(im)&curves.arm.eq('natural_all24')&curves.k.eq(k)].iloc[0]
    def eff(im,p,k):
        return effects[effects.image.eq(im)&effects.policy.eq(p)&effects.k.eq(k)].iloc[0]
    uw='UwV83HsGsw3-12';un='uNb9QFRL6hY-60';pa='pa4otMbVnkk-09';low='UwV83HsGsw3-09';b6='B6ByNegPMKs-33'
    u3=eff(uw,'structure_moreturn_first',3);u6=eff(uw,'structure_moreturn_first',6);u20=eff(uw,'structure_moreturn_first',20)
    d10=eff(un,'structure_dominant_first',10);d17=eff(un,'structure_dominant_first',17)
    m6=eff(un,'structure_moreturn_first',6);m10=eff(un,'structure_moreturn_first',10)
    q6=eff(un,'joint_highq_first',6);uwq6=eff(uw,'joint_highq_first',6)
    fast6=eff(pa,'joint_fast_first',6);a=nat(b6,10);b=nat(b6,20)
    out=['','## 由完整顺序得出的具体判断','',
        '### 1. Uw-12：较多转折类能加快这个入口回折形成多数','',
        '原答支持表显示，入口R4得到较多转折类6/6人、常规类11/22人支持。这个局部的支持比例与历史类别一致；不是只因为六角比五角“更多”。旧精确路径说明同一个位置如何在票数1/2、2/2、2/3、3/3时反复入选与失选。',
        f'完整配对结果也支持这一解释：较多转折类优先在n3的Q净增{fmt(u3.B8L2_paired_delta_mean)}分，{int(u3.Q_up_n)}/{int(u3.paired_Q)}对改善，R4的5°存在率由{pct(u3.R4_present_5_natural_rate)}到{pct(u3.R4_present_5_priority_rate)}；n6仍净增{fmt(u6.B8L2_paired_delta_mean)}分，{int(u6.Q_up_n)}/{int(u6.paired_Q)}对改善。n3的D10净增{fmt(u3.D10_paired_delta_mean)}分、三维代理净增{fmt(u3.IoU3D100_paired_delta_mean)}分，底边误差减少{fmt(-u3.S_bottom_deg_paired_delta_mean,3)}°，变化不仅见于Q。',
        f'作用主要在前段：到n20，净Q为{fmt(u20.B8L2_paired_delta_mean)}分，接近零；全员28人时两种顺序必然合流。n6较多转折类六人已全进入，政策侧只有{int(u6.distinct_priority_teams)}个实际成员集合；其8次配对比较反映对8个自然背景的差异，不能解释为8种不同六人政策队。',
        '',
        '### 2. uNb-60：同一结构类在玻璃侧机会上的作用反向，常规类更有用','',
        '此图R8是既有参考采用的玻璃淋浴邻接折点，语义与入口实墙回折不同。原答支持为较多转折类2/12、常规类9/17、简化类0/4。类别“通常较多转折”保留其历史解释，但并不意味着它更常表达这个具体位置。',
        f'较多转折类优先在n10净Q为{fmt(m10.B8L2_paired_delta_mean)}分，R8出现率从自然配对组{pct(m10.R8_present_5_natural_rate)}变成{pct(m10.R8_present_5_priority_rate)}。相反，常规类优先在n10净增{fmt(d10.B8L2_paired_delta_mean)}分，Q P10提高{fmt(d10.Q_p10_difference)}分，R8出现率变为{pct(d10.R8_present_5_priority_rate)}；n17净增{fmt(d17.B8L2_paired_delta_mean)}分，{int(d17.Q_up_n)}/{int(d17.paired_Q)}对改善。n17常规类全部17人组成同一个政策端点，因此这里的8/8是8个不同自然对照都较低，不是8个独立纯类团队。',
        f'n10常规优先的D10提高{fmt(d10.D10_paired_delta_mean)}分，底边误差减少{fmt(-d10.S_bottom_deg_paired_delta_mean,3)}°，输出自身方向残差减少{fmt(-d10.dir_paired_delta_mean,3)}°，三维代理提高{fmt(d10.IoU3D100_paired_delta_mean)}分；均高项变化仅{fmt(d10.Hmean_paired_delta_mean,4)}。这与局部折点和边界表达改变相符，不是所有几何维度等幅变化。继续把其余人员加入后，这一优势衰减，全员33人的Q仍为{fmt(nat(un,33).B8L2_mean)}分。',
        f'失败也保留：较多转折优先n6有{int(m6.priority_failure_n)}/8不可评分，两端均可评分的{int(m6.paired_Q)}对净Q为{fmt(m6.B8L2_paired_delta_mean)}分。这个数与两端各自可评分均值之差不同，不能混用。联合较高历史Q优先在n6可产生{fmt(q6.B8L2_paired_delta_mean)}分的改善（{int(q6.Q_up_n)}/{int(q6.paired_Q)}对），但其后也不保证保持R8；不同政策有不同过程用途。',
        '',
        '### 3. 另外三案分别解释定位改善、结构缺失和缩波平台','',
        f'pa4-09始终为四角。自然24条n3→6的Q均值为{fmt(nat(pa,3).B8L2_mean)}→{fmt(nat(pa,6).B8L2_mean)}，到n20为{fmt(nat(pa,20).B8L2_mean)}；原精确路径中的上下边界与底面定位改善可以解释这种早段收益。单看节点数会漏掉它。',
        f'Uw-09的可评分Q到n20仍仅{fmt(nat(low,20).B8L2_mean)}，原答少数转折远低于多数门槛的机制继续成立。扩展到24条后还看到明显失败：n3为{int(nat(low,3).failure_nonpolicy_n)}/24，n6为{int(nat(low,6).failure_nonpolicy_n)}/24，n20为{int(nat(low,20).failure_nonpolicy_n)}/24。可评分Q均值并不含这些失败，不能把它单独当整体可靠性。原四条中选出的可评分路径不能代表这些新增失败背景。',
        f'B6-33的n10→20自然均值为{fmt(a.B8L2_mean)}→{fmt(b.B8L2_mean)}，样本标准差为{fmt(a.B8L2_sd,3)}→{fmt(b.B8L2_sd,3)}，Q P10为{fmt(a.B8L2_p10)}→{fmt(b.B8L2_p10)}。24条支持“均值小幅改善、低尾与波动明显收缩”，替代旧四条均值略降的背景描述；四角一致但共同外扩的具体机制不变。全员Q仍为{fmt(nat(b6,31).B8L2_mean)}，所以缩波不等于消除共同偏差。',
        '',
        '### 4. 时间用途使用实际记录与相同配对范围','',
        f'Uw-12联合较高历史Q类优先在n6净Q为{fmt(uwq6.B8L2_paired_delta_mean)}分，8对完整记录的时间差平均{fmt(uwq6.source_time_total_seconds_paired_delta_mean)}秒，逐对相对差平均{fmt(uwq6.source_time_relative_delta_pct_mean)}%。pa4-09快类优先n6的净Q为{fmt(fast6.B8L2_paired_delta_mean)}分、时间差{fmt(fast6.source_time_total_seconds_paired_delta_mean)}秒、逐对相对差{fmt(fast6.source_time_relative_delta_pct_mean)}%；其质量变化较小而记录时间变化更清楚。',
        '这些是已有标注记录时间之和，不是新测生产工时，也不是把算法预测误差换算成节时。秒差均值、逐对百分比均值、总量之比均在表中区分；基线差异大时它们可以异号。uNb-60较大前缀多有缺失时间，本案不据此声称节时。',
        '',
        '**采用判断：**入口回折与玻璃侧折点给出可接续的正反局部规律：先识别类别在具体结构机会上的支持，再选择进入顺序。自然混合确实能在前段改善定位或补多数，也会在另一些图上收敛到缺结构或共同偏移的平台。五案为总体曲线提供机制解释，不能把任一图的较优政策直接推广为全库选队规则。',
        '']
    return out


def plot_curves(out,curves,node_curves):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    nick={'UwV83HsGsw3-12':'Uw-12 (medium)','pa4otMbVnkk-09':'pa4-09 (simple)',
          'UwV83HsGsw3-09':'Uw-09 (difficult)','uNb9QFRL6hY-60':'uNb-60 (difficult)',
          'B6ByNegPMKs-33':'B6-33 (simple)'}
    fig,axes=plt.subplots(3,2,figsize=(11,10),sharey=True)
    for image,ax in zip(IMAGES,axes.flat):
        g=curves[curves.image.eq(image)&curves.arm.eq('natural_all24')&curves.k.ge(3)].sort_values('k')
        x=g.k.to_numpy(float)
        ax.fill_between(x,g.B8L2_p10.to_numpy(float),g.B8L2_p90.to_numpy(float),color='#9ecae1',alpha=.5,label='P10–P90, scorable')
        ax.plot(x,g.B8L2_mean,color='#08519c',lw=2,label='Mean Q, scorable')
        ax.plot(x,g.B8L2_p10,color='#2171b5',ls=':',lw=1,label='P10, scorable')
        bad=g.failure_nonpolicy_n.gt(0)
        ax.scatter(g.loc[bad,'k'],g.loc[bad,'B8L2_mean'],s=24,color='#c53030',zorder=4,label='At least one failure')
        ax.set_title(f'{nick[image]}; actual pool N={int(g.pool_n.iloc[0])}')
        ax.set(xlabel='Prefix team size n',ylabel='B8L2 Q',ylim=(0,103),xlim=(2,int(g.pool_n.iloc[0])+1))
        ax.grid(alpha=.2)
    axes.flat[-1].axis('off')
    handles,labels=axes.flat[0].get_legend_handles_labels()
    axes.flat[-1].legend(handles,labels,loc='upper left',frameon=False)
    axes.flat[-1].text(0,.56,'24 uniform full-pool orders per image.\nAll five cases are Manual, non-doorway.\nn=2 is deferred by the frozen policy.\n\nFailure denominators are retained in CSV;\nQ summaries use scorable outputs only.\nAt N every order has the same endpoint.',transform=axes.flat[-1].transAxes,va='top',linespacing=1.5)
    fig.suptitle('Natural mixed populations: five mechanism contexts',fontsize=16)
    fig.tight_layout(rect=(0,0,1,.97))
    temp=out/'NATURAL_CASE_CURVES.png.tmp';fig.savefig(temp,format='png',dpi=170);temp.replace(out/'NATURAL_CASE_CURVES.png');plt.close(fig)
    palette={'natural_random':('#222222','Paired natural (8)'),
        'structure_moreturn_first':('#d95f02','More-turn class first'),
        'structure_dominant_first':('#1b9e77','Regular class first'),
        'joint_highq_first':('#7570b3','Joint high-Q class first'),
        'joint_fast_first':('#e7298a','Joint fast class first')}
    fig,axes=plt.subplots(2,2,figsize=(13,8))
    for row,(image,corner) in enumerate([('UwV83HsGsw3-12',4),('uNb9QFRL6hY-60',8)]):
        for policy,(color,label) in palette.items():
            if policy=='natural_random':
                arm='paired_natural8';cmp='structure_moreturn_first'
            else:arm='priority8';cmp=policy
            g=curves[curves.image.eq(image)&curves.arm.eq(arm)&curves.comparison_policy.eq(cmp)&curves.k.ge(3)].sort_values('k')
            ng=node_curves[node_curves.image.eq(image)&node_curves.arm.eq(arm)&node_curves.comparison_policy.eq(cmp)&node_curves.k.ge(3)&node_curves.angle_threshold_deg.eq(5)&node_curves.reference_corner_1based.eq(corner)].sort_values('k')
            axes[row,0].plot(g.k,g.B8L2_mean,color=color,lw=2,label=label)
            axes[row,1].plot(ng.k,ng.present_rate_given_diagnostic,color=color,lw=2,label=label)
        axes[row,0].set(title=f'{nick[image]}: mean Q',ylabel='B8L2 Q',ylim=(20,103))
        axes[row,1].set(title=f'{nick[image]}: R{corner} present within 5°',ylabel='Fraction with geometry diagnosis',ylim=(-.03,1.03))
        for ax in axes[row]:ax.set_xlabel('Prefix team size n');ax.grid(alpha=.2)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False,bbox_to_anchor=(.5,.005))
    fig.suptitle('Same final pool, different entering roles: all four priority policies',fontsize=15)
    fig.tight_layout(rect=(0,.09,1,.96))
    temp=out/'LOCAL_OPPORTUNITY_POLICY_CURVES.png.tmp';fig.savefig(temp,format='png',dpi=170);temp.replace(out/'LOCAL_OPPORTUNITY_POLICY_CURVES.png');plt.close(fig)


if __name__=='__main__':
    main()
