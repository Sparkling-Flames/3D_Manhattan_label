"""Read-only evaluation of frozen v3 matched events, with complete endpoint rows.

One immutable shard per registered panel. Incomplete endpoint panels wait for
the next invocation; no row is silently dropped from the final event universe.
"""
from __future__ import annotations
import argparse,collections,csv,gzip,io,json,math,os,sys,time
from pathlib import Path
import numpy as np
import pandas as pd
from multin_design import HERE,ROOT,OLD,CONT,gs,h,write_csv,sha
sys.path.insert(0,str(CONT/'n20_abc'))
from event_kernel import evaluate_one

def read_csv(p):
    with gzip.open(p,'rt',encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def load_pool(pid,needed=None):
    rows={}
    for p in sorted((HERE/'runtime').glob(f'*/{pid}.json.gz')):
        if not (HERE/'batches'/p.parent.name/'COMPLETION.json').exists():continue
        for r in gs.read(p)['teams']:
            if needed is None or r['team_key'] in needed:
                if r['team_key'] in rows:
                    prior=rows[r['team_key']]
                    if (prior.get('B8L2'),prior.get('D10'),prior.get('nodes'))!=(r.get('B8L2'),r.get('D10'),r.get('nodes')):raise ValueError('conflicting duplicate endpoint')
                rows[r['team_key']]=r
    return rows

def write_event_shard(path,rows,expected):
    fields=list(dict.fromkeys(k for r in rows for k in r));tmp=path.with_name(path.name+'.tmp');path.parent.mkdir(parents=True,exist_ok=True)
    # Each immutable panel/pool is bounded. Compress a complete byte buffer so
    # publication is independent of streaming gzip finalization in this runtime.
    with io.StringIO(newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow(gs.clean(r))
        packed=gzip.compress(f.getvalue().encode('utf-8-sig'),compresslevel=5,mtime=0)
    with open(tmp,'wb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
    seen=set()
    with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f);head=next(r);ii=head.index('event_id')
        for row in r:
            if len(row)!=len(head) or row[ii] in seen:raise ValueError('ragged or repeated event')
            seen.add(row[ii])
    if seen!=expected:raise ValueError(('wrong_event_key_set',len(seen),len(expected)))
    tmp.replace(path)
    return dict(path=str(path.relative_to(HERE)),rows=len(rows),fields=len(fields),sha256=sha(path),bytes=path.stat().st_size)

def run(kind):
    source=HERE/'matched'/dict(panel='PANEL_MATCHED_EVENTS.csv.gz',large='LARGE_BLOCK_EVENTS.csv.gz',pure='PURE_BLOCK_MATCHED_EVENTS.csv.gz')[kind]
    requests=read_csv(source);by=collections.defaultdict(list)
    for r in requests:by[r['pool_id']].append(r)
    _,_,sg,corner=gs.setup_engine();histories=pd.read_csv(OLD/'multivariate/continuous_features_lobo.csv.gz')
    hist={(r.condition,r.heldout_building,r.worker_id):r for r in histories.itertuples()}
    feature_table=pd.read_csv(HERE.parent/'taxonomy/CONTINUOUS_FEATURES_LOBO.csv.gz')
    structure={(r.condition,r.heldout_building,r.worker_id):r for r in feature_table.itertuples()}
    label_table=pd.read_csv(HERE.parent/'taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz')
    selected={(r.method,r.condition,r.heldout_building):(r.selected_family,r.coarse_k,r.fine_k) for r in label_table.itertuples()}
    behavior_features=['turn_history','short_history','redundancy_history','area_history','height_history','simple_turn_history','complex_turn_history','complex_short_history']
    ledger=[];pending=[];new_events=0;started=time.monotonic()
    for pid,req in sorted(by.items()):
        need={r['team_'+a] for r in req for a in 'ABC'};teams=load_pool(pid,need);groups=collections.defaultdict(list)
        for r in req:groups[r['panel_id']].append(r)
        pairs={};signatures={}
        for panel,rr in sorted(groups.items()):
            key=h('result-panel',kind,panel)[:20];path=HERE/'matched/results'/kind/(key+'.csv.gz');rp=path.with_suffix('.json')
            if path.exists() and rp.exists():
                receipt=gs.read(rp)
                if receipt['request_digest']!=gs.digest(rr):raise ValueError('changed_frozen_event_design')
                ledger.append(receipt);continue
            kk={r['team_'+a] for r in rr for a in 'ABC'}
            if not kk<=teams.keys():pending.append(dict(panel_id=panel,events=len(rr),needed_endpoints=len(kk),missing_endpoints=len(kk-teams.keys())));continue
            result=[]
            for request in rr:
                r=evaluate_one(request,teams,pairs,signatures,hist,sg,corner,request['condition'])
                info=selected.get((r['method_id'],r['condition'],r['building']))
                r['fold_selected_family'],r['fold_coarse_k'],r['fold_fine_k']=info if info else ('legacy_method',None,None)
                for block,col in [('X','outgoing_block_X'),('Y','same_count_block_Y'),('Z','changed_count_block_Z')]:
                    workers=r[col].split('|')
                    for feature in behavior_features:
                        values=[]
                        support_flag='context_supported' if feature.startswith(('simple_','complex_')) else 'base_supported'
                        for w in workers:
                            item=structure.get((r['condition'],r['building'],w))
                            v=getattr(item,feature,np.nan) if item is not None and getattr(item,support_flag,False) else np.nan
                            values.append(v)
                        r[block+'_'+feature+'_known_n']=int(np.isfinite(values).sum())
                        r[block+'_'+feature]=float(np.mean(values)) if np.isfinite(values).all() else None
                for prefix,left,right in [('same','X','Y'),('cross','X','Z'),('net','Y','Z')]:
                    for feature in behavior_features:
                        a,b=r[left+'_'+feature],r[right+'_'+feature]
                        r[prefix+'_'+feature+'_change']=b-a if a is not None and b is not None else None
                r['recorded_time_single_source']=all('|' not in str(teams[r['team_'+a]].get('time_source_kinds','unknown')) and teams[r['team_'+a]].get('source_time_known_n')==r['n'] for a in 'ABC')
                for prefix in ['same','cross','net']:
                    v=r.get(prefix+'_source_log_time_ratio');r[prefix+'_recorded_time_pct']=100*math.expm1(v) if v is not None and r['recorded_time_single_source'] else None
                    r[prefix+'_abs_log_time']=abs(v) if v is not None and r['recorded_time_single_source'] else None
                sv,cv=r['same_abs_log_time'],r['cross_abs_log_time'];r['time_variation_advantage']=cv-sv if sv is not None and cv is not None else None
                for metric in ['floor_jaccard_difference','mean_height_prism_pair_difference','structure_bound_cyclic_deg','centroid_distance_h','floor_area_abs_log_ratio','node_count_difference']:
                    a,b=r.get('within_'+metric),r.get('cross_'+metric);ok=r['all_complete'] and a is not None and b is not None
                    r['common_geometry_within_'+metric]=a if ok else None;r['common_geometry_cross_'+metric]=b if ok else None
                    r['common_geometry_advantage_'+metric]=b-a if ok else None
                result.append(r)
            check=write_event_shard(path,result,{r['event_id'] for r in rr});check.update(kind=kind,panel_id=panel,pool_id=pid,condition=rr[0]['condition'],building=rr[0]['building'],image=rr[0]['image'],n=int(rr[0]['n']),request_digest=gs.digest(rr),native_calls=0,all_complete=sum(r['all_complete'] for r in result),all_scored=sum(r['all_scored'] for r in result))
            gs.save(rp,check);ledger.append(check);new_events+=len(rr)
        print(json.dumps(dict(kind=kind,pool_id=pid,completed_events=sum(r['rows'] for r in ledger),pending_panels=len(pending),elapsed=time.monotonic()-started)),flush=True)
    write_csv(HERE/'matched'/f'{kind.upper()}_RESULT_SHARDS.csv',pd.DataFrame(ledger));write_csv(HERE/'matched'/f'{kind.upper()}_PENDING_PANELS.csv',pd.DataFrame(pending))
    receipt=dict(kind=kind,status='complete' if not pending else 'partial_checkpoint',registered_events=len(requests),completed_events=sum(r['rows'] for r in ledger),new_events_this_invocation=new_events,pending_events=sum(r['events'] for r in pending),pending_panels=len(pending),native_calls=0,event_source_sha256=sha(source),seconds=time.monotonic()-started)
    gs.save(HERE/'matched'/f'{kind.upper()}_RESULT_RECEIPT.json',receipt);print(json.dumps(receipt),flush=True)

PRIMARY=['common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage','within_joint_stable_main','cross_joint_stable_main','stable_advantage','within_joint_stable_D10_main','cross_joint_stable_D10_main','stable_D10_advantage','same_loss_gt5','cross_loss_gt5','same_loss_gt10','cross_loss_gt10','B_failure','C_failure','net_failure_difference','within_floor_jaccard_difference','cross_floor_jaccard_difference','within_mean_height_prism_pair_difference','cross_mean_height_prism_pair_difference','within_structure_bound_cyclic_deg','cross_structure_bound_cyclic_deg','within_centroid_distance_h','cross_centroid_distance_h','same_abs_log_time','cross_abs_log_time','time_variation_advantage']
COMMON_GEOMETRY=['floor_jaccard_difference','mean_height_prism_pair_difference','structure_bound_cyclic_deg','centroid_distance_h','floor_area_abs_log_ratio','node_count_difference']
PRIMARY += ['common_geometry_'+side+'_'+metric for metric in COMMON_GEOMETRY for side in ['within','cross','advantage']]
EXPRESSION_FEATURES=['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
EXPRESSION_FIELDS=[arm+'_'+metric for metric in EXPRESSION_FEATURES for arm in 'ABC'] + [side+'_'+metric for metric in EXPRESSION_FEATURES for side in ['same','cross','net']] + ['common_expression_'+side+'_'+metric for metric in EXPRESSION_FEATURES for side in ['within_abs','cross_abs','advantage']]
PRIMARY += ['common_expression_'+side+'_'+metric for metric in EXPRESSION_FEATURES for side in ['within_abs','cross_abs','advantage']]

def load_expression():
    out={}
    for p in sorted((HERE.parent/'response/geometry_batches').glob('*_EXPRESSION.csv.gz')):
        d=pd.read_csv(p)
        for r in d.itertuples():out[r.team_key]={f:float(getattr(r,f)) if np.isfinite(getattr(r,f)) else None for f in EXPRESSION_FEATURES}
    return out

def expression_row(r,expression):
    for arm in 'ABC':
        values=expression[r['team_'+arm]]
        for metric in EXPRESSION_FEATURES:r[arm+'_'+metric]=values[metric]
    complete=str(r.get('all_complete')).lower()=='true'
    for metric in EXPRESSION_FEATURES:
        for prefix,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:
            av,bv=r[a+'_'+metric],r[b+'_'+metric];r[prefix+'_'+metric]=bv-av if av is not None and bv is not None else None
        s,c=r['same_'+metric],r['cross_'+metric];ok=complete and s is not None and c is not None
        r['common_expression_within_abs_'+metric]=abs(s) if ok else None;r['common_expression_cross_abs_'+metric]=abs(c) if ok else None;r['common_expression_advantage_'+metric]=abs(c)-abs(s) if ok else None
    return r

def expression_frame(d,expression):
    # Vector form of expression_row; all values are endpoint-derived, without
    # re-evaluating native fusion or changing any previously saved event.
    for arm in 'ABC':
        for metric in EXPRESSION_FEATURES:d[arm+'_'+metric]=d['team_'+arm].map(lambda k:expression[k][metric])
    for metric in EXPRESSION_FEATURES:
        for prefix,a,b in [('same','A','B'),('cross','A','C'),('net','B','C')]:d[prefix+'_'+metric]=d[b+'_'+metric]-d[a+'_'+metric]
        s,c=d['same_'+metric],d['cross_'+metric];ok=d.all_complete & s.notna() & c.notna()
        d['common_expression_within_abs_'+metric]=s.abs().where(ok);d['common_expression_cross_abs_'+metric]=c.abs().where(ok);d['common_expression_advantage_'+metric]=(c.abs()-s.abs()).where(ok)
    return d

class SummarySink:
    """Bounded, independently readable checkpoints and one complete CSV."""
    def __init__(self,kind):
        self.kind=kind;self.buffer=[];self.parts=[];self.total=0;self.primary=[]
        self.fields=['method_id','tier','condition','source_domain','design_scope','sensitivity','summary_view','m_AB','n','difficulty','events','panels','pools','images','buildings','all_complete_events','all_scored_events','metric','mean','valid_events','valid_buildings','positive_buildings','negative_buildings','lo95','hi95']
    def add(self,row):
        self.buffer.append(row);self.total+=1
        if row['metric'] in PRIMARY:self.primary.append(row)
        if len(self.buffer)>=20000:self.flush()
    def flush(self):
        if not self.buffer:return
        path=HERE/'matched/summary_parts'/f'{self.kind}_{len(self.parts)+1:04d}.csv.gz';path.parent.mkdir(exist_ok=True)
        data=pd.DataFrame(self.buffer).reindex(columns=self.fields).to_csv(index=False).encode('utf-8-sig')
        packed=gzip.compress(data,compresslevel=5,mtime=0);tmp=path.with_name(path.name+'.tmp')
        with open(tmp,'wb') as f:f.write(packed);f.flush();os.fsync(f.fileno())
        count=0
        with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
            r=csv.reader(f);head=next(r)
            for row in r:
                if len(row)!=len(head):raise ValueError('ragged summary checkpoint')
                count+=1
        if count!=len(self.buffer):raise ValueError('truncated summary checkpoint')
        tmp.replace(path);self.parts.append(dict(path=str(path.relative_to(HERE)),rows=count,sha256=sha(path)));self.buffer=[]
        write_csv(HERE/'matched'/f'{self.kind.upper()}_SUMMARY_PARTS.csv',pd.DataFrame(self.parts))
    def finish(self):
        self.flush();path=HERE/'matched'/f'{self.kind.upper()}_ALL_COMPONENT_SUMMARY.csv.gz';tmp=path.with_name(path.name+'.tmp')
        # Concatenated complete gzip members are standard gzip. Strip the CSV
        # header from later parts, then write/fsync each bounded compressed part.
        with open(tmp,'wb') as target:
            for i,part in enumerate(self.parts):
                data=gzip.decompress((HERE/part['path']).read_bytes())
                if i:data=data.partition(b'\n')[2]
                target.write(gzip.compress(data,compresslevel=5,mtime=0));target.flush();os.fsync(target.fileno())
        count=0
        with gzip.open(tmp,'rt',encoding='utf-8-sig',newline='') as f:
            r=csv.reader(f);head=next(r)
            for row in r:
                if len(row)!=len(head):raise ValueError('ragged combined summary')
                count+=1
        if count!=self.total:raise ValueError('incomplete combined summary')
        tmp.replace(path);write_csv(HERE/'matched'/f'{self.kind.upper()}_PRIMARY_SUMMARY.csv',pd.DataFrame(self.primary).reindex(columns=self.fields))
        gs.save(path.with_suffix('.json'),dict(rows=count,columns=len(self.fields),parts=len(self.parts),sha256=sha(path),bytes=path.stat().st_size))

def harmonize_row(r):
    # Initial immutable panel checkpoints predate these arithmetic views.
    # Add the views on export without changing any saved event or endpoint.
    if 'common_geometry_within_floor_jaccard_difference' in r:return r
    complete=str(r.get('all_complete')).lower()=='true'
    for metric in COMMON_GEOMETRY:
        a,b=r.get('within_'+metric),r.get('cross_'+metric)
        a=float(a) if a not in [None,''] else None;b=float(b) if b not in [None,''] else None
        ok=complete and a is not None and b is not None
        r['common_geometry_within_'+metric]=a if ok else None;r['common_geometry_cross_'+metric]=b if ok else None;r['common_geometry_advantage_'+metric]=b-a if ok else None
    return r

def export_events(kind,condition=None,expression=None):
    """Publish any complete condition immediately, independently of summaries."""
    files=pd.read_csv(HERE/'matched'/f'{kind.upper()}_RESULT_SHARDS.csv')
    if condition is not None:files=files[files.condition.eq(condition)]
    source=HERE/'matched'/dict(panel='PANEL_MATCHED_EVENTS.csv.gz',large='LARGE_BLOCK_EVENTS.csv.gz',pure='PURE_BLOCK_MATCHED_EVENTS.csv.gz')[kind]
    request=pd.read_csv(source,usecols=['event_id','condition'],dtype={'event_id':str})
    expression=load_expression() if expression is None else expression
    source_sha=sha(source)
    from consolidate_deliverables import GzipCsv
    for cond,gg in files.groupby('condition'):
        expected=set(request.loc[request.condition.eq(cond),'event_id'])
        if int(gg.rows.sum())!=len(expected):raise RuntimeError(('condition has pending requested events',kind,cond,int(gg.rows.sum()),len(expected)))
        cols=[];allkeys=set()
        for p in gg.path:
            with gzip.open(HERE/p,'rt',encoding='utf-8-sig',newline='') as f:
                cols.extend(c for c in next(csv.reader(f)) if c not in cols)
            for r in read_csv(HERE/p):allkeys.update(r['team_'+a] for a in 'ABC')
        if not allkeys<=expression.keys():raise RuntimeError(('condition awaits expression',kind,cond,len(allkeys-expression.keys())))
        expression_digest=gs.digest({k:expression[k] for k in sorted(allkeys)})
        path=HERE/'matched'/f'{kind.upper()}_{cond.upper()}_COMPLETE_EVENTS.csv.gz';rp=path.with_suffix('.json')
        if path.exists() and rp.exists():
            prior=gs.read(rp)
            if prior.get('request_sha256')==source_sha and prior.get('expression_digest')==expression_digest and prior['rows']==len(expected) and prior['sha256']==sha(path):
                print(json.dumps(dict(event_export='already_complete',kind=kind,condition=cond,rows=prior['rows'])),flush=True);continue
        cols += [f'common_geometry_{side}_{metric}' for metric in COMMON_GEOMETRY for side in ['within','cross','advantage'] if f'common_geometry_{side}_{metric}' not in cols]
        cols += [c for c in EXPRESSION_FIELDS if c not in cols]
        seen=set();writer=GzipCsv(path,cols,key='event_id')
        for p in gg.path:
            for r in read_csv(HERE/p):
                if r['event_id'] in seen:raise ValueError('duplicate event across panel shards')
                seen.add(r['event_id']);writer.add(expression_row(harmonize_row(r),expression))
        if seen!=expected:raise ValueError('condition event request/result keys differ')
        receipt=writer.finish(expected);receipt.update(source_panel_shards=len(gg),request_sha256=source_sha,expression_digest=expression_digest)
        gs.save(rp,receipt);print(json.dumps(dict(event_export='complete',kind=kind,condition=cond,**receipt)),flush=True)

def summaries(kind):
    index=HERE/'matched'/f'{kind.upper()}_RESULT_SHARDS.csv';files=pd.read_csv(index);sources=[];pool_rows=[];support=[];fields=None;expression=load_expression()
    grouping=['method_id','tier','condition','source_domain','design_scope','m_AB','n','difficulty','building','image','pool_id','panel_id']
    complete=gs.read(HERE/'matched'/f'{kind.upper()}_RESULT_RECEIPT.json')
    if complete['status']!='complete':raise ValueError('refuse final summary with missing events')
    # All numeric components are summarized, but wide complete per-event rows
    # remain in separately retrievable immutable panel shards.
    for entry in files.to_dict('records'):
        p=HERE/entry['path'];d=pd.read_csv(p,low_memory=False);sources.append(p)
        needed=set(d.team_A)|set(d.team_B)|set(d.team_C)
        if not needed<=expression.keys():raise RuntimeError(('wait_for_expression_derivatives',kind,entry['panel_id'],len(needed-expression.keys())))
        d=expression_frame(d,expression)
        for metric in COMMON_GEOMETRY:
            if 'common_geometry_within_'+metric not in d:
                a,b=d['within_'+metric],d['cross_'+metric];ok=d.all_complete & a.notna() & b.notna()
                d['common_geometry_within_'+metric]=a.where(ok);d['common_geometry_cross_'+metric]=b.where(ok);d['common_geometry_advantage_'+metric]=(b-a).where(ok)
        cols=[c for c in d if pd.api.types.is_numeric_dtype(d[c]) and (c.startswith(('within_','same_','cross_','net_','common_quality_','common_geometry_','common_expression_')) or c in ['A_failure','B_failure','C_failure','stable_advantage','stable_D10_advantage','abs_Q_change_advantage','time_variation_advantage'])]
        cols=[c for c in cols if c not in grouping and c not in ['within_parent_fine_change','same_source_counts'] and not c.startswith('cross_parent')]
        fields=sorted(set(fields or [])|set(cols))
        for sensitivity,dd in [('unmatched_total_effect',d),('same_source_count',d[d.same_source_counts]),('source_history_Q5_matched',d[d.source_and_historyQ5_matched])]:
            if not len(dd):continue
            gg=dd.groupby(grouping,dropna=False)
            vals=gg[cols].mean().reset_index();vals['sensitivity']=sensitivity;pool_rows.append(vals)
            ss=gg.agg(events=('event_id','size'),all_complete=('all_complete','sum'),all_scored=('all_scored','sum'),distinct_A=('team_A','nunique'),distinct_B=('team_B','nunique'),distinct_C=('team_C','nunique'),net_m_mean=('m_BC','mean')).join(gg[cols].count().add_prefix('valid__')).reset_index();ss['sensitivity']=sensitivity;support.append(ss)
    values=pd.concat(pool_rows,ignore_index=True);s=pd.concat(support,ignore_index=True);write_csv(HERE/'matched'/f'{kind.upper()}_PANEL_METRICS.csv.gz',values);write_csv(HERE/'matched'/f'{kind.upper()}_PANEL_SUPPORT.csv.gz',s)
    base=['method_id','tier','condition','source_domain','design_scope','sensitivity']
    sink=SummarySink(kind);buildings=[]
    for variant,extra in [('overall',[]),('by_m',['m_AB']),('by_n',['n']),('by_n_m',['n','m_AB']),('by_difficulty',['difficulty']),('by_difficulty_m',['difficulty','m_AB'])]:
        keys=base+extra
        # Equal panels, pools, images and buildings within each named scope.
        im=values.groupby(keys+['building','image','pool_id'],dropna=False)[fields].mean().groupby(level=keys+['building','image'],dropna=False).mean()
        b=im.groupby(level=keys+['building'],dropna=False).mean().reset_index();b['summary_view']=variant;buildings.append(b)
        for kk,g in b.groupby(keys,dropna=False):
            meta=dict(zip(keys,kk));mask=np.ones(len(s),bool)
            for key,v in meta.items():mask &= s[key].eq(v).to_numpy()
            ss=s[mask];den=dict(events=int(ss.events.sum()),panels=ss.panel_id.nunique(),pools=ss.pool_id.nunique(),images=ss.image.nunique(),buildings=ss.building.nunique(),all_complete_events=int(ss.all_complete.sum()),all_scored_events=int(ss.all_scored.sum()))
            for metric in fields:
                z=g[metric].dropna().to_numpy(float);lo=hi=None
                if len(z)>=3 and metric in PRIMARY:
                    rng=np.random.default_rng(2026102187);bt=z[rng.integers(len(z),size=(2000,len(z)))].mean(axis=1);lo,hi=np.quantile(bt,[.025,.975])
                vcol='valid__'+metric;valid_events=int(ss[vcol].fillna(0).sum()) if vcol in ss else 0
                sink.add(dict(meta,summary_view=variant,**den,metric=metric,mean=float(z.mean()) if len(z) else None,valid_events=valid_events,valid_buildings=len(z),positive_buildings=int((z>0).sum()),negative_buildings=int((z<0).sum()),lo95=lo,hi95=hi))
        sink.flush()
    sink.finish();write_csv(HERE/'matched'/f'{kind.upper()}_BUILDING_METRICS.csv.gz',pd.concat(buildings,ignore_index=True))
    export_events(kind,expression=expression)
    print(json.dumps(dict(kind=kind,events=complete['completed_events'],summary_rows=sink.total,primary_rows=len(sink.primary),metrics=len(fields))),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','summary','export']);p.add_argument('--kind',choices=['panel','large','pure'],default='panel');p.add_argument('--condition',choices=['manual','semi']);a=p.parse_args()
    if a.action=='run':run(a.kind)
    elif a.action=='summary':summaries(a.kind)
    else:export_events(a.kind,a.condition)
