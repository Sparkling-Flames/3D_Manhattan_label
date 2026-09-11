"""四类人员信息的探索；只写分析工件，不改变正式人员资格或原始记录。"""
from pathlib import Path
from itertools import combinations
from collections import Counter
from functools import lru_cache
from urllib.parse import urlparse
import argparse
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from scipy.stats import spearmanr

from tools.thesis_main.analysis import worker_rule_triad_20260910 as triad
from tools.thesis_main.analysis import worker_reference_feasibility_20260909 as ref
from tools.thesis_main.analysis import worker_behavior_time_20260910 as timing
from tools.thesis_main.analysis import prescreen_scope_adjudication as scope_parser
from tools.thesis_main.analysis import validate_worker_reuse_20260909 as reuse
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import informative, predict_peers, sufficient, solve

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'analysis_results/worker_four_block_exploration_20260910_v1'
P1 = ROOT/'analysis_results/prescreen_closeout_final_gold_v2_20260701'
BLOCKS = {'Q': ['quality'], 'T': ['time'],
          'S': ['scope_reject', 'scope_accept'], 'B': ['edit', 'benefit']}
COMBOS = [c for n in range(1,5) for c in combinations(BLOCKS, n)]
SEED = 20260910
MIN_ROWS, MIN_BUILDINGS = 6, 3
KEY = ['canonical_annotation_id','worker_id','image_id','building_id','context_key','current20_member']


def scope_axis(final, worker):
    if final not in ('in_scope','oos') or worker not in ('in_scope','oos'):
        return None, None
    return ('scope_reject' if final == 'in_scope' else 'scope_accept', float(final != worker))


def cluster_blocks(p, blocks, median=False):
    """每个信息块总权重相同；单人类拒绝，不能事后合并凑人数。"""
    if len(p) < 4:
        return np.zeros(len(p), int), 'insufficient_workers'
    if median:
        labels = (p.quality.to_numpy() > p.quality.median()).astype(int)+1
    else:
        parts=[]
        for block in blocks:
            x=p[BLOCKS[block]].to_numpy(float)
            scale=x.std(axis=0)
            if not np.isfinite(x).all() or np.any(scale < 1e-10):
                return np.zeros(len(p), int), 'constant_or_missing_axis'
            parts.append((x-x.mean(axis=0))/scale/np.sqrt(x.shape[1]))
        labels=cut_tree(linkage(np.concatenate(parts,axis=1),method='ward'),n_clusters=2).ravel()+1
        first=BLOCKS[blocks[0]][0]
        means=p.assign(label=labels).groupby('label')[first].mean()
        if means.loc[1] > means.loc[2]: labels=3-labels
    if len(set(labels)) < 2 or min(np.bincount(labels)[1:]) < 2:
        return np.zeros(len(p), int), 'singleton_rejected'
    return labels, 'usable'


def axis_profiles(data):
    return fit_axis_cache(prepare_axis_cache(data),set(data.building_id))


def prepare_axis_cache(data):
    return {axis:sufficient(informative(g)) for axis,g in data.groupby('axis') if not informative(g).empty}


def fit_axis_cache(cache, buildings, min_rows=MIN_ROWS, min_buildings=MIN_BUILDINGS):
    pieces=[]
    for axis,s in cache.items():
        weights=np.array([float(b in buildings) for b in s['buildings']])
        rows=weights@s['support']; nbuild=weights@(s['support']>0)
        present=rows>0
        if present.sum()<2:continue
        local=dict(s,workers=np.asarray(s['workers'])[present].tolist(),A=s['A'][:,present][:,:,present],
                   rhs=s['rhs'][:,present],support=s['support'][:,present])
        effect,status,_=solve(local,weights)
        if status!='usable':continue
        eligible=(rows[present]>=min_rows)&(nbuild[present]>=min_buildings)
        pieces.append(pd.DataFrame({axis:effect[eligible]},index=pd.Index(np.asarray(local['workers'])[eligible],name='worker_id')))
    return pd.concat(pieces,axis=1).reset_index() if pieces else pd.DataFrame(columns=['worker_id'])


def classify_training(data, buildings, blocks, common=False, median=False):
    train=data[data.building_id.isin(buildings)]
    p=axis_profiles(train)
    required=[a for b in (BLOCKS if common else blocks) for a in BLOCKS[b]]
    if not set(required)<=set(p): return pd.DataFrame(columns=['worker_id','label','status'])
    p=p.dropna(subset=required).copy()
    labels,status=cluster_blocks(p,blocks,median)
    return p.assign(label=labels,status=status)


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    plan=dict(blocks=BLOCKS,combinations=[''.join(c) for c in COMBOS],classes=2,
        additional_baseline='Q_median2',cohorts=['all26','current20'],
        primary='ospa30; all allowed references; natural and synthetic Semi separately described',
        sensitivity=['ospa60','without_synthetic','reviewed_quality_only','scope_all_historical'],
        training_minimum=dict(responses=MIN_ROWS,buildings=MIN_BUILDINGS),
        weighting='each block unit total standardized squared distance; not each raw axis equal',
        fit='task-adjusted effects independently per axis; target building excluded from every block',
        fairness='all methods use same training-qualified workers for common-panel predictions; native coverage separately reported',
        half_repeats=100,seed=SEED,
        half_support_sensitivity='Primary keeps 6 responses/3 buildings; supplementary halves use 3 responses/2 buildings because scope OOS has only 9 images; never substitutes for primary support',
        replay='all prespecified methods; q=.95 and OSPA30<=6; point count hard constraint; 200 without-replacement orders; future>=5',
        exploratory_only=True,not_new_worker_validation=True,not_chosen_by_convergence=True,
        protocol='No formal eligibility/routing/assignment/contract change')
    (OUT/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf8')
    triad.OUT=OUT
    manual,semi=triad.prepare()  # 重新核对有效点、初始化、参考和原始时间来源。
    pairs=pd.read_csv(reuse.GEOMETRY/'pairwise_q.csv.gz')
    pairs.to_csv(OUT/'pairs.csv.gz',index=False)
    a=pd.read_csv(ref.BASE/'annotations.csv.gz',dtype=str).fillna('')
    a['current20_member']=a.current20_member.eq('True')|a.current20_member.eq('true')
    assert a.groupby('worker_id').current20_member.nunique().max()==1
    # Scope直接回到原始导出读取，不将旧统计表视为新观测。
    manifest=pd.read_csv(P1/'raw_inputs/raw_input_snapshot_manifest.csv')
    original_by_snapshot={str(Path(r.snapshot_path)).replace('\\','/'):r.source_path for r in manifest.itertuples()
                          if r.source_kind=='raw_label_studio_export'}
    gold={str(r['task_id']):r for r in ref.jsonlines(P1/'final_gold_records_v2_p1_closeout_corrected.jsonl')}
    gold_by_base={r['base_task_id']:r for r in gold.values()}
    assert len(gold_by_base)==len(gold)
    raw_gold_path=ROOT/'export_label/人工精标/project-20-at-2026-03-27-14-57-e66c6481.json'
    raw_gold=json.loads(raw_gold_path.read_text(encoding='utf-8-sig'))
    raw_gold_index={Path(urlparse(t['data']['image']).path).stem:t for t in raw_gold}
    assert len(raw_gold_index)==len(raw_gold)
    gold_changes=[]
    for image,g in gold_by_base.items():
        anns=[a for a in raw_gold_index[image]['annotations'] if not a.get('was_cancelled')]
        assert len(anns)==1
        original_scope=scope_parser._worker_scope(anns[0])[1]
        if original_scope!=g['final_scope_binary']:gold_changes.append((g['task_id'],original_scope,g['final_scope_binary']))
    assert gold_changes==[('696','in_scope','oos')]
    correction=json.loads((P1/'prescreen_final_gold_v2_correction_audit.json').read_text(encoding='utf-8-sig'))
    assert any(r['task_id']=='696' and r['new_final_scope_binary']=='oos' for r in correction['corrections'])
    ledger={r['image_id']:r for r in ref.jsonlines(reuse.REFERENCE)}
    old_scope=pd.read_csv(P1/'prescreen_scope_response_audit.csv',dtype=str)
    old_index=old_scope.set_index(['project_id','task_id','annotator_id'])
    raw_sources={}; scope_rows=[]; source_checks=[]
    for source,g in a[a.stage=='P1'].groupby('raw_export_path'):
        original=ROOT/original_by_snapshot[source]
        raw=json.loads(original.read_text(encoding='utf-8-sig'))
        snapshot=json.loads((ROOT/source).read_text(encoding='utf-8-sig'))
        assert raw==snapshot, 'P1 live/snapshot mismatch: '+str(original)
        raw_sources[source]={str(t['id']):t for t in raw}
        source_checks.append(dict(source=str(original.relative_to(ROOT)),records=len(g),snapshot_equal=True))
        for r in g.to_dict('records'):
            task=raw_sources[source][r['runtime_task_id']]
            anns=[x for x in task['annotations'] if str(x['id'])==r['raw_annotation_id']]
            assert len(anns)==1
            ann=anns[0]; owner=ann.get('completed_by')
            assert str(owner.get('id') if isinstance(owner,dict) else owner)==r['worker_id']
            raw_label, worker, _=scope_parser._worker_scope(ann)
            prev=old_index.loc[(r['project_id'],r['runtime_task_id'],r['worker_id'])]
            assert worker==prev.worker_scope_normalized and raw_label==prev.worker_scope_raw
            if r['raw_condition']=='semi':continue
            gold_record=gold_by_base.get(r['image_id'])
            assert gold_record and gold_record['scope_gold_ready']
            final=gold_record['final_scope_binary']
            assert final==scope_parser._scope_binary(prev.task_final_scope)
            lr=ledger.get(r['image_id'],{})
            # 后来出现明确争议时不默认为旧裁定仍适用于规则评价。
            hold=lr.get('hold_reason','')
            later_hold=hold if hold and hold!='historical_review_reference_not_geometry_ready' else ''
            axis,value=scope_axis(final,worker)
            scope_rows.append(dict(**{k:r[k] for k in KEY},raw_export=str(original.relative_to(ROOT)),
                raw_annotation_id=r['raw_annotation_id'],raw_scope=raw_label,worker_scope=worker,
                final_scope=final,final_scope_alias=gold_record['final_scope_alias'],
                final_task_id=gold_record['task_id'],scope_source=gold_record['scope_source'],
                later_hold=later_hold,axis=axis,value=value,condition=r['raw_condition']))
    scope=pd.DataFrame(scope_rows)
    assert not scope.duplicated(['image_id','worker_id']).any()
    scope['context_key']='scope|'+scope.image_id
    scope.to_csv(OUT/'scope_responses.csv',index=False)
    source_checks.append(dict(final_gold=str((P1/'final_gold_records_v2_p1_closeout_corrected.jsonl').relative_to(ROOT)),
                             original_gold_export=str(raw_gold_path.relative_to(ROOT)),raw_gold_scope_checks=len(gold),
                             contract_correction='task696 changed to oos_insufficient; task564 geometry-only',
                             scope_records=len(scope),later_hold_rows=int(scope.later_hold.ne('').sum())))
    (OUT/'SCOPE_SOURCE_AUDIT.json').write_text(json.dumps(source_checks,ensure_ascii=False,indent=2),encoding='utf8')
    time=pd.read_csv(ref.BASE/'facts/active_time_context.csv.gz',dtype={'worker_id':str,'project_id':str,'runtime_task_id':str})
    m=manual.merge(time,on='canonical_annotation_id',suffixes=('','_timing'),validate='one_to_one')
    assert m.worker_id.equals(m.worker_id_timing)
    shifted=timing.adjusted_time_keys()
    m['time_ok']=timing.clean_time(m)&pd.Series([(p,t,w) not in shifted for p,t,w in zip(m.project_id,m.runtime_task_id,m.worker_id)],index=m.index)
    m['time']=np.where(m.time_ok,np.log1p(m.active_time_seconds),np.nan)
    m.to_csv(OUT/'manual_with_time.csv.gz',index=False)
    for variant,metric in [('primary','ospa30'),('ospa60','ospa60'),('without_synthetic','ospa30'),
                           ('reviewed_quality_only','ospa30'),('scope_all_historical','ospa30')]:
        parts=[]
        def add(d,axis,column):
            z=d[KEY+[column]].rename(columns={column:'value'}).copy();z['axis']=axis
            parts.append(z[np.isfinite(z.value)])
        q=m[m.reference_allowed]
        if variant=='reviewed_quality_only':q=q[q.reference_basis=='reviewed_reference']
        add(q,'quality',metric)
        add(m,'time','time')
        sc=scope if variant=='scope_all_historical' else scope[scope.later_hold.eq('')]
        parts.append(sc[KEY+['axis','value']].dropna(subset=['axis','value']))
        s=semi if variant!='without_synthetic' else semi[semi.source_group!='trap_synthetic_disjoint_source']
        s=s[s.calculation_included&~s.imputed_point]
        # B同时保留修改量和净改善；任务内净改善等价于最终偏差的反方向，不能声称是独立能力。
        add(s,'edit','edit_'+metric)
        add(s,'benefit','gain_'+metric)
        d=pd.concat(parts,ignore_index=True)
        assert not d.duplicated(['axis','context_key','worker_id']).any()
        d.to_csv(OUT/f'axes_{variant}.csv.gz',index=False)
    print('prepared',len(manual),len(semi),len(scope),flush=True)


def model_profiles(p, combo, common):
    required=[a for b in (BLOCKS if common else combo) for a in BLOCKS[b]]
    return p.dropna(subset=required).copy() if set(required)<=set(p) else p.iloc[:0].copy()


def screen(variants=None):
    all_full=[];all_fold=[];all_half=[];all_pred=[];all_coverage=[]
    for variant in (variants or ['primary','ospa60','without_synthetic','reviewed_quality_only','scope_all_historical']):
        data=pd.read_csv(OUT/f'axes_{variant}.csv.gz',dtype={'worker_id':str})
        for cohort in ['all26','current20']:
            d=data if cohort=='all26' else data[data.current20_member]
            buildings=set(d.building_id.unique());cache=prepare_axis_cache(d);p=fit_axis_cache(cache,buildings)
            configs=[(''.join(c),c,False) for c in COMBOS]+[('Q_median2',('Q',),True)]
            for panel in ['native','common']:
                for name,combo,median in configs:
                    z=model_profiles(p,combo,panel=='common')
                    labels,status=cluster_blocks(z,combo,median)
                    meta=dict(variant=variant,cohort=cohort,panel=panel,model=name)
                    all_full.append(z.assign(**meta,label=labels,status=status))
                    all_coverage.append(dict(**meta,workers=len(z),status=status,group_sizes='|'.join(map(str,np.bincount(labels)[1:])) if status=='usable' else ''))
            for building in sorted(buildings):
                train=d[d.building_id!=building];p=fit_axis_cache(cache,buildings-{building})
                for panel in ['native','common']:
                    # 完整15组合的公平比较在common；native同时检查各自实际覆盖。
                    for name,combo,median in configs:
                        z=model_profiles(p,combo,panel=='common')
                        labels,status=cluster_blocks(z,combo,median)
                        meta=dict(variant=variant,cohort=cohort,panel=panel,model=name,heldout_building=building)
                        z=z.assign(**meta,label=labels,status=status,training_buildings='|'.join(sorted(set(train.building_id))))
                        all_fold.append(z)
                        if z.empty:continue
                        for axis,test in d[d.building_id==building].groupby('axis'):
                            if axis not in z:continue
                            profile=z[['worker_id','label',axis]].dropna().rename(columns={axis:'effect'})
                            profile['layer_value']=profile.groupby('label').effect.transform('mean') if status=='usable' else 0.
                            pred=predict_peers(test,profile.assign(component='0',fit_status='usable'))
                            all_pred.append(pred.assign(**meta,classification_status=status))
            rng=np.random.default_rng(SEED)
            for rep in range(100):
                left=set(rng.permutation(sorted(buildings))[:len(buildings)//2])
                for support,min_rows,min_buildings in [('full_requirement',6,3),('half_diagnostic',3,2)]:
                    a=fit_axis_cache(cache,left,min_rows,min_buildings);b=fit_axis_cache(cache,buildings-left,min_rows,min_buildings)
                    for panel in ['native','common']:
                        for name,combo,median in configs:
                            x=model_profiles(a,combo,panel=='common');y=model_profiles(b,combo,panel=='common')
                            la,sa=cluster_blocks(x,combo,median);lb,sb=cluster_blocks(y,combo,median)
                            match=x.assign(label=la).merge(y.assign(label=lb),on='worker_id',suffixes=('_a','_b'))
                            ok=sa==sb=='usable' and len(match)>=4
                            row=dict(variant=variant,cohort=cohort,panel=panel,model=name,repeat=rep,workers=len(match),half_support=support,
                                     left_status=sa,right_status=sb,status='usable' if ok else 'unavailable',
                                     ari=reuse.adjusted_rand(match.label_a,match.label_b) if ok else np.nan)
                            all_half.append(row)
            print('screened',variant,cohort,flush=True)
    for name,items in [('members',all_full),('fold_members',all_fold),('predictions',all_pred)]:
        pd.concat(items,ignore_index=True).to_csv(OUT/(name+('.csv.gz' if name!='members' else '.csv')),index=False)
    pd.DataFrame(all_half).to_csv(OUT/'half_stability.csv',index=False)
    pd.DataFrame(all_coverage).to_csv(OUT/'coverage.csv',index=False)
    summarize()


def summarize():
    pred=pd.read_csv(OUT/'predictions.csv.gz',dtype={'worker_id':str})
    keys=['variant','cohort','panel','model','axis'];rows=[]
    for key,g in pred.groupby(keys):
        bm=g.groupby('building_id')[['baseline_sqerr','layer_sqerr','continuous_sqerr']].mean()
        base=bm.baseline_sqerr.mean()
        rows.append(dict(zip(keys,key),rows=len(g),workers=g.worker_id.nunique(),images=g.image_id.nunique(),buildings=len(bm),
            group_gain=1-bm.layer_sqerr.mean()/base if base>1e-20 else np.nan,
            continuous_gain=1-bm.continuous_sqerr.mean()/base if base>1e-20 else np.nan,
            abstention_rows=int(g.classification_status.ne('usable').sum())))
    pd.DataFrame(rows).to_csv(OUT/'validation.csv',index=False)
    half=pd.read_csv(OUT/'half_stability.csv')
    h=half.groupby(keys[:-1]+['half_support']).agg(attempts=('repeat','size'),valid=('ari','count'),ari_median=('ari','median'),shared_workers_median=('workers','median')).reset_index()
    h.to_csv(OUT/'stability_summary.csv',index=False)
    # common比较不允许某种方法偷偷删掉难预测的响应。
    for key,g in pred[pred.panel=='common'].groupby(['variant','cohort','axis','heldout_building']):
        sets=g.groupby('model').canonical_annotation_id.apply(lambda x:frozenset(x))
        assert sets.nunique()==1,(key,'unequal_common_test_rows')
    (OUT/'SCREEN_QA.json').write_text(json.dumps(dict(common_test_rows_identical=True,
        prediction_rows=len(pred),half_comparisons=len(half),configurations=len(rows)),indent=2),encoding='utf8')


def graph_partition_bits(neighbors, mask, invalid):
    """相同阈值图的快捷计算；非完全连通分量仍交给原v5枚举器。"""
    from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import _partition_graph
    if mask & invalid:return None
    remaining=mask;groups=[];complete=True
    while remaining:
        seed=remaining&-remaining;component=0;front=seed
        while front:
            bit=front&-front;front^=bit;component|=bit
            front|=(int(neighbors[bit.bit_length()-1])&mask&~component)
        remaining&=~component;groups.append(component)
        bits=component
        while bits:
            bit=bits&-bits;bits^=bit
            if (int(neighbors[bit.bit_length()-1])&component)!=(component^bit):complete=False
    if complete:return tuple(groups)
    ix=[i for i in range(len(neighbors)) if mask&(1<<i)]
    edges=tuple((i,j) for i,x in enumerate(ix) for j,y in enumerate(ix) if i<j and int(neighbors[x])&(1<<y))
    groups,count,truncated=_partition_graph(len(ix),edges)
    return tuple(sum(1<<ix[i] for i in g) for g in groups) if count==1 and not truncated else None


def compare_bits(left,right):
    # 0=稳定，1=未知，2=明确变化；max实现与原stage_tail相同的优先级。
    if left is None or right is None or not any(g.bit_count()>=2 for g in left):return 1
    common=0
    for g in left:common|=g
    k=common.bit_count();j=sum(g.bit_count() for g in right)
    choose2=lambda n:n*(n-1)//2
    inside=[(g&common).bit_count() for g in right]
    before=sum(choose2(g.bit_count()) for g in left)
    after=sum(choose2(v) for v in inside)
    both=sum(choose2((a&b).bit_count()) for a in left for b in right)
    membership=(before+after-2*both)/choose2(k) if k>1 else 0.
    shares=.5*sum(abs(v/k-g.bit_count()/j) for g,v in zip(right,inside))
    promotion=any(v<2<=g.bit_count() for g,v in zip(right,inside))
    return 2 if membership>.1+1e-12 or shares>.1+1e-12 or promotion else 0


def replay():
    from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import ORDERS
    frame=pd.read_csv(OUT/'manual.csv.gz',dtype={'worker_id':str})
    pairs=pd.read_csv(OUT/'pairs.csv.gz')
    members=pd.read_csv(OUT/'fold_members.csv.gz',dtype={'worker_id':str})
    members=members[members.variant.eq('primary')&((members.panel=='common')|((members.panel=='native')&members.model.eq('Q_median2')))]
    orders=[[str(w) for w in json.loads(line)['worker_ids']] for line in ORDERS.read_text(encoding='utf8').splitlines()]
    assert len(orders)==200
    curves=[];coverage=[]
    for image,original in frame.groupby('image_id'):
        original=original.sort_values('canonical_annotation_id').reset_index(drop=True)
        if len(original)<7:continue
        ids=set(original.canonical_annotation_id)
        ip=pairs[pairs.image_id.eq(image)&pairs.left_canonical.isin(ids)&pairs.right_canonical.isin(ids)]
        matrices=reuse.image_matrices(original,ip)
        positions=dict(zip(original.worker_id,original.index))
        building=original.building_id.iloc[0]
        counts=original.effective_point_count.to_numpy()
        neighbors={};invalid={}
        for config,key,threshold in [('q95','q',.05),('ospa30_t6','ospa30',6.)]:
            edges=(matrices[key]<=threshold+1e-12)&(counts[:,None]==counts[None,:]);np.fill_diagonal(edges,False)
            neighbors[config]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in edges]
            invalid[config]=sum(1<<int(i) for i in np.flatnonzero(~original.q_geometry_valid.to_numpy())) if config=='q95' else 0
        @lru_cache(maxsize=None)
        def part(config,mask):
            return graph_partition_bits(neighbors[config],mask,invalid[config])
        @lru_cache(maxsize=None)
        def compare(config,left,right):
            return compare_bits(part(config,left),part(config,right))
        @lru_cache(maxsize=None)
        def evaluate(people,second,mix):
            people,second=set(people),set(second)
            n=2*min(len(people),len(second)) if mix else len(people)
            horizons=sorted({h for h in (7,8,10,13,n) if 7<=h<=n})
            agg={}
            for order in orders:
                a=[positions[w] for w in order if w in people]
                if mix:
                    b=[positions[w] for w in order if w in second]
                    if order.index(next(w for w in order if w in people))>order.index(next(w for w in order if w in second)):a,b=b,a
                    seq=[v for pair in zip(a,b) for v in pair]
                else:seq=a
                assert len(seq)==n and len(set(seq))==n
                masks={};mask=0
                for k,pos in enumerate(seq,1):mask|=1<<pos;masks[k]=mask
                for config in ('q95','ospa30_t6'):
                    for h in horizons:
                        anchors=[]
                        for k in range(1,h-4):
                            state=0
                            for j in range(k+1,h+1):
                                state=max(state,compare(config,masks[k],masks[j]))
                                if state==2:break
                            anchors.append(state)
                        tail=np.maximum.accumulate(anchors[::-1])[::-1]
                        for k,code in enumerate(tail,1):
                            state=['stable','unknown','changing'][code]
                            c=agg.setdefault((config,h,k),Counter());c[state]+=1
                            if state=='stable':c['multi' if sum(g.bit_count()>=2 for g in part(config,masks[k]))>=2 else 'single']+=1
            return [(config,h,k,dict(c)) for (config,h,k),c in agg.items()]
        grouped={key:g for key,g in members[members.heldout_building.eq(building)].groupby(['cohort','panel','model'])}
        expected=[(c,'common',m) for c in ['all26','current20'] for m in [''.join(x) for x in COMBOS]+['Q_median2']]
        expected += [(c,'native','Q_median2') for c in ['all26','current20']]
        for cohort,panel,model in expected:
            trained=grouped.get((cohort,panel,model))
            if trained is None or trained.empty:
                for arm in ('G1','G2','MIX','ALL'):coverage.append(dict(image_id=image,building_id=building,cohort=cohort,panel=panel,model=model,arm=arm,n=0,status='no_training_support'))
                continue
            assert all(building not in v.split('|') for v in trained.training_buildings)
            available=set(reuse.cohort(original,cohort).worker_id)&set(trained.worker_id)
            label=trained.set_index('worker_id').label.to_dict()
            groups={str(i):{w for w in available if label[w]==i} for i in (1,2)}
            arms=[('ALL',available,set(),False)]
            if trained.status.eq('usable').all():
                arms += [('G1',groups['1'],set(),False),('G2',groups['2'],set(),False),('MIX',groups['1'],groups['2'],True)]
            else:
                for arm in ('G1','G2','MIX'):coverage.append(dict(image_id=image,building_id=building,cohort=cohort,panel=panel,model=model,arm=arm,n=0,status='classification_rejected'))
            for arm,people,second,mix in arms:
                n=2*min(len(people),len(second)) if mix else len(people)
                meta=dict(image_id=image,building_id=building,cohort=cohort,panel=panel,model=model,arm=arm)
                coverage.append(dict(**meta,n=n,status='available' if n>=7 else 'insufficient_people'))
                if n<7:continue
                for config,h,k,c in evaluate(tuple(sorted(people)),tuple(sorted(second)),mix):
                    assert c.get('stable',0)+c.get('changing',0)+c.get('unknown',0)==200
                    curves.append(dict(**meta,config=config,horizon=h,k=k,lower=c.get('stable',0)/200,
                        upper=(c.get('stable',0)+c.get('unknown',0))/200,unknown=c.get('unknown',0),
                        stable_single=c.get('single',0),stable_multi=c.get('multi',0)))
        print('replay',image,len(curves),flush=True)
    pd.DataFrame(curves).to_csv(OUT/'stage_curves.csv.gz',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'stage_support.csv',index=False)
    replay_summary()


def replay_summary(target_filter='all'):
    d=pd.read_csv(OUT/'stage_curves.csv.gz');rows=[]
    suffix=''
    if target_filter=='reference_allowed':
        m=pd.read_csv(OUT/'manual.csv.gz');d=d[d.image_id.isin(m[m.reference_allowed].image_id)]
        suffix='_reference_allowed'
    elif target_filter=='scope_confirmed_in':
        s=pd.read_csv(OUT/'scope_responses.csv').fillna('')
        d=d[d.image_id.isin(s[s.final_scope.eq('in_scope')&s.later_hold.eq('')].image_id)]
        suffix='_scope_confirmed_in'
    elif target_filter!='all':raise ValueError(target_filter)
    keys=['cohort','panel','model','config','horizon','k']
    # 单组对照和四臂共同图比较分开，不将各自不同的图片汇总硬比。
    for key,g in d[d.k>=2].groupby(keys):
        for arms in [('G1','ALL'),('G2','ALL'),('MIX','ALL'),('G1','G2','MIX','ALL')]:
            for bound in ('lower','upper'):
                wide=g.pivot(index=['image_id','building_id'],columns='arm',values=bound).reindex(columns=arms).dropna()
                if wide.empty:continue
                means=wide.groupby('building_id').mean().mean()
                rows.append(dict(zip(keys,key),comparison='|'.join(arms),bound=bound,images=len(wide),buildings=wide.index.get_level_values('building_id').nunique(),**means.to_dict()))
    pd.DataFrame(rows).to_csv(OUT/f'stage_matched_summary{suffix}.csv',index=False)
    paired=[]
    for (cohort,config,h,k),g in d[(d.panel=='common')&d.horizon.isin([7,8,10,13])&(d.k==d.horizon-5)].groupby(['cohort','config','horizon','k']):
        for bound in ('lower','upper'):
            wide=g.pivot(index=['image_id','building_id'],columns=['model','arm'],values=bound)
            for model in [''.join(c) for c in COMBOS]:
                columns=[(m,a) for m in ['Q_median2',model] for a in ('G1','G2','ALL')]
                z=wide.reindex(columns=pd.MultiIndex.from_tuples(columns)).dropna()
                if z.empty:continue
                means=z.groupby('building_id').mean().mean()
                row=dict(cohort=cohort,config=config,horizon=h,k=k,bound=bound,model=model,images=len(z),buildings=z.index.get_level_values('building_id').nunique())
                for m in ['Q_median2',model]:
                    for a in ('G1','G2','ALL'):row[('quality_baseline' if m=='Q_median2' else 'candidate')+'_'+a]=means[(m,a)]
                paired.append(row)
    pd.DataFrame(paired).to_csv(OUT/f'cross_method_stage_comparison{suffix}.csv',index=False)


def stage_subsets():
    for subset in ['all','reference_allowed','scope_confirmed_in']:replay_summary(subset)
    stage_onsets()


def stage_onsets():
    d=pd.read_csv(OUT/'stage_curves.csv.gz');rows=[]
    keys=['image_id','building_id','cohort','panel','model','arm','config','horizon']
    for key,g in d[d.k>=2].groupby(keys):
        g=g.sort_values('k')
        assert (np.diff(g.lower)>=-1e-12).all() and (np.diff(g.upper)>=-1e-12).all()
        possible=g.loc[g.upper>=.8-1e-12,'k'];confirmed=g.loc[g.lower>=.8-1e-12,'k']
        rows.append(dict(zip(keys,key),earliest_possible=int(possible.iloc[0]) if len(possible) else None,
            earliest_confirmed=int(confirmed.iloc[0]) if len(confirmed) else None,
            status='confirmed_in_observed_range' if len(confirmed) else 'not_reached_in_observed_range' if not len(possible) else 'undetermined'))
    pd.DataFrame(rows).to_csv(OUT/'stage_onsets.csv',index=False)


def stage_quality():
    """代表标注只依组内距离选取；参考仅用于事后评价，不参与选择。"""
    from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import ORDERS
    curves=pd.read_csv(OUT/'stage_curves.csv.gz')
    keys=['image_id','building_id','cohort','panel','model','arm','horizon']
    scenarios=curves[keys].drop_duplicates()
    members=pd.read_csv(OUT/'fold_members.csv.gz',dtype={'worker_id':str})
    members=members[members.variant.eq('primary')]
    frame=pd.read_csv(OUT/'manual.csv.gz',dtype={'worker_id':str});pairs=pd.read_csv(OUT/'pairs.csv.gz')
    orders=[[str(w) for w in json.loads(line)['worker_ids']] for line in ORDERS.read_text(encoding='utf8').splitlines()]
    rows=[]
    for image,sc in scenarios.groupby('image_id'):
        original=frame[frame.image_id.eq(image)].sort_values('canonical_annotation_id').reset_index(drop=True)
        ids=set(original.canonical_annotation_id)
        matrix=reuse.image_matrices(original,pairs[pairs.image_id.eq(image)&pairs.left_canonical.isin(ids)&pairs.right_canonical.isin(ids)])['ospa30']
        positions=dict(zip(original.worker_id,original.index));allowed=original.reference_allowed.all()
        @lru_cache(maxsize=None)
        def score(first,second,mix,h):
            if not allowed:return np.nan
            first,second=set(first),set(second);subsets=[]
            for order in orders:
                a=[positions[w] for w in order if w in first]
                if mix:
                    b=[positions[w] for w in order if w in second]
                    if order.index(next(w for w in order if w in first))>order.index(next(w for w in order if w in second)):a,b=b,a
                    seq=[v for pair in zip(a,b) for v in pair]
                else:seq=a
                subsets.append(seq[:h])
            values,_=reuse.medoid_reference(original.ospa30.to_numpy(),matrix,np.asarray(subsets,int))
            return float(values.mean())
        for (cohort,panel,model),g in sc.groupby(['cohort','panel','model']):
            trained=members[members.cohort.eq(cohort)&members.panel.eq(panel)&members.model.eq(model)&members.heldout_building.eq(original.building_id.iloc[0])]
            available=set(original.worker_id)&set(trained.worker_id);labels=trained.set_index('worker_id').label.to_dict()
            a={w for w in available if labels[w]==1};b={w for w in available if labels[w]==2}
            for r in g.to_dict('records'):
                first,second,mix=(available,set(),False) if r['arm']=='ALL' else (a,set(),False) if r['arm']=='G1' else (b,set(),False) if r['arm']=='G2' else (a,b,True)
                rows.append(dict(r,reference_allowed=bool(allowed),medoid_reference_error=score(tuple(sorted(first)),tuple(sorted(second)),mix,r['horizon'])))
    pd.DataFrame(rows).to_csv(OUT/'stage_quality.csv',index=False)


def diagnostics():
    pred=pd.read_csv(OUT/'predictions.csv.gz',dtype={'worker_id':str})
    pred=pred[pred.variant.eq('primary')&pred.panel.eq('common')]
    rows=[]
    for (cohort,axis),g in pred.groupby(['cohort','axis']):
        baseline=g[g.model=='Q_median2'].groupby('building_id')[['baseline_sqerr','layer_sqerr']].mean()
        n=len(baseline);weights=np.random.default_rng(SEED).multinomial(n,np.full(n,1/n),size=1000)
        denom=weights@baseline.baseline_sqerr.to_numpy();valid=denom>1e-15
        for model,z in g.groupby('model'):
            bm=z.groupby('building_id').layer_sqerr.mean().reindex(baseline.index)
            assert not bm.isna().any()
            gain=1-(weights[valid]@bm.to_numpy())/denom[valid]
            delta=(weights[valid]@(baseline.layer_sqerr.to_numpy()-bm.to_numpy()))/denom[valid]
            rows.append(dict(cohort=cohort,axis=axis,model=model,buildings=n,replicates=len(gain),
                gain_lower=float(np.quantile(gain,.025)),gain_upper=float(np.quantile(gain,.975)),
                extra_over_Qmedian_lower=float(np.quantile(delta,.025)),extra_over_Qmedian_upper=float(np.quantile(delta,.975))))
    pd.DataFrame(rows).to_csv(OUT/'conditional_building_intervals.csv',index=False)
    members=pd.read_csv(OUT/'members.csv',dtype={'worker_id':str})
    members=members[members.variant.eq('primary')&members.panel.eq('common')&members.status.eq('usable')]
    scopes=pd.read_csv(OUT/'scope_responses.csv',dtype={'worker_id':str}).fillna('')
    scopes=scopes[scopes.later_hold.eq('')]
    semi=pd.read_csv(OUT/'semi.csv.gz',dtype={'worker_id':str})
    rows=[]
    for (cohort,model,label),g in members.groupby(['cohort','model','label']):
        row=dict(cohort=cohort,model=model,label=label,n=len(g),worker_ids='|'.join(sorted(g.worker_id,key=int)))
        for axis in [a for b in BLOCKS.values() for a in b]:row[axis+'_effect_mean']=g[axis].mean()
        sc=scopes[scopes.worker_id.isin(g.worker_id)]
        for final in ('in_scope','oos'):
            x=sc[sc.final_scope.eq(final)]
            row[final+'_error_person_mean']=x.groupby('worker_id').value.mean().mean()
            row[final+'_responses']=len(x)
        s=semi[semi.worker_id.isin(g.worker_id)]
        for source,z in s.groupby('source_group'):
            row[source+'_unchanged_person_mean']=z.assign(unchanged=np.isclose(z.edit_ospa30,0,atol=1e-8)).groupby('worker_id').unchanged.mean().mean()
            row[source+'_gain_person_median_mean']=z.groupby('worker_id').gain_ospa30.median().mean()
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT/'group_explanations.csv',index=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','screen','summarize','replay','replay_summary','stage_subsets','stage_onsets','stage_quality','diagnostics'])
    args=parser.parse_args()
    globals()[args.action]()
