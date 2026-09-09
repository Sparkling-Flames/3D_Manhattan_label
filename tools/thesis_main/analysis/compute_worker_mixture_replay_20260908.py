"""楼外训练人员倾向的真实响应组合枚举；仅C1 Manual探索。"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
import sys
import time
from collections import Counter, defaultdict
from contextlib import ExitStack
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.compute_building_convergence_evidence_20260908 import audit_inputs, META, CACHE, js, finite
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition, fixed_distribution

OUTPUT='analysis_results/worker_mixture_replay_20260908_v1/core'
PROFILES='analysis_results/worker_evidence_strata_20260908_v1/worker_profiles_all_folds.csv.gz'
METHODS=['A_only','balanced_AB','B_only','random_AB_pool']
MEASURES=['pairwise_distance_mean','pairwise_distance_max','cluster_count','supported_historical_cluster_count',
          'singleton_response_fraction','training_entropy','historical_largest_share','distribution_tv',
          'validation_outside_fraction','validation_ambiguous_fraction','unique_indicator','non_unique_indicator','truncated_indicator']


def profile_group(row,building):
    if row is None:return 'unknown'
    if row['fold']!=building or building in json.loads(row['training_buildings']):
        raise ValueError('target_building_training_leakage')
    if row['fit_status']!='usable':return 'unknown'
    return {'high':'A','low':'B'}.get(row['label'],'unknown')


def enumerate_combinations(a,b,n):
    if len(set(a+b))!=len(a+b):raise ValueError('duplicate_or_overlapping_people')
    aset=set(a)
    return [(list(ids),'A_only' if all(x in aset for x in ids) else 'B_only' if all(x not in aset for x in ids)
             else 'balanced_AB' if sum(x in aset for x in ids)==n//2 else 'other_AB') for ids in combinations(a+b,n)]


def evaluate_combination(matrix,history,validation):
    if len(set(history))!=len(history) or set(history)&set(validation):raise ValueError('training_validation_overlap_or_duplicate')
    if len(history)<2:raise ValueError('insufficient_support')
    if len(validation)<2:
        return dict(partition_status='validation_lt2',candidate_partition_count='',enumeration_truncated='',training_clusters_local_json='',
                    **{m:np.nan for m in MEASURES},training_cluster_support_json='',validation_cluster_support_json='',
                    validation_compatible_cluster_ids_json='',observed_historical_cluster_count=np.nan)
    d=matrix[np.ix_(history,history)]
    part=partition(d,6.)
    distances=d[np.triu_indices(len(history),1)]
    row=dict(partition_status=part['status'],candidate_partition_count=part['candidate_partition_count'],
             enumeration_truncated=part['enumeration_truncated'],training_clusters_local_json=js(part['clusters']),
             pairwise_distance_mean=float(distances.mean()),pairwise_distance_max=float(distances.max()))
    row.update({m:np.nan for m in MEASURES if m not in row})
    for state in ['unique','non_unique','truncated']:row[state+'_indicator']=int(part['status']==state)
    row.update(training_cluster_support_json='',validation_cluster_support_json='',validation_compatible_cluster_ids_json='',observed_historical_cluster_count=np.nan)
    if part['status']=='unique':
        r=fixed_distribution(matrix,history,validation,part['clusters'],6.,[len(history)])[0]
        r.pop('k');r.pop('prefix_to_full_history_tv');row.update(r)
        row['cluster_count']=len(part['clusters'])
        row['singleton_response_fraction']=sum(len(g)==1 for g in part['clusters'])/len(history)
    return row


def summarize_methods(rows,measures=MEASURES):
    summary=[];paired=[]
    for measure in measures:
        info={}
        for method in METHODS:
            selected=rows if method=='random_AB_pool' else [r for r in rows if r['composition']==method]
            values=[float(r[measure]) for r in selected if finite(r.get(measure))]
            info[method]=dict(total_combinations=len(selected),valid_combinations=len(values),
                valid_fraction=len(values)/len(selected) if selected else np.nan,
                mean=float(np.mean(values)) if values else np.nan,
                non_unique_combinations=sum(r.get('partition_status')=='non_unique' for r in selected),
                truncated_combinations=sum(r.get('partition_status')=='truncated' for r in selected),
                ambiguous_combinations=sum(finite(r.get('validation_ambiguous_fraction')) and r['validation_ambiguous_fraction']>0 for r in selected))
            summary.append(dict(method=method,measure=measure,**info[method]))
        paired.append(dict(measure=measure,paired_any_values=all(r['valid_combinations']>0 for r in info.values()),
                           paired_all_combinations_valid=all(r['total_combinations']>0 and r['total_combinations']==r['valid_combinations'] for r in info.values()),
                           method_support_json=js({m:{k:r[k] for k in ['total_combinations','valid_combinations']} for m,r in info.items()})))
    return summary,paired


def run(root,out):
    out.mkdir(parents=True,exist_ok=True);start=time.time();counts=Counter()
    with (out/'run.log').open('w',encoding='utf-8') as log, ExitStack() as stack:
        def progress(s):
            message=f'{time.time()-start:.1f}s {s}';print(message,flush=True);log.write(message+'\n');log.flush()
        writers={}
        def emit(name,row):
            if name not in writers:
                f=stack.enter_context(gzip.open(out/name,'wt',encoding='utf-8',newline='',compresslevel=1))
                writers[name]=csv.DictWriter(f,fieldnames=list(row));writers[name].writeheader()
            writers[name].writerow(row);counts[name]+=1
        progress('复核全部原始身份、点状态、历史分组')
        a,status,schedules,qa=audit_inputs(root)
        p=pd.read_csv(root/PROFILES,dtype=str,keep_default_na=False)
        p=p[(p.stage=='C1')&(p.raw_condition=='manual')&(p.metric=='corner_pair_count')&
            (p.reading=='raw_point_count')&(p.representation=='not_applicable')&(p.cohort=='available')&(p.fold!='full')]
        assert not p.duplicated(['fold','worker_id']).any()
        target=a[(a.stage=='C1')&(a.raw_condition=='manual')]
        profiles={(r['fold'],r['worker_id']):r for r in p.to_dict('records')}
        roster=sorted(a.worker_id.unique(),key=int);profile_rows=[];labels={}
        for b in sorted(target.building_id.unique()):
            # 本次两类只能在同一训练连接分量参照下比较。
            pp=p[p.fold==b];assert len(pp) and pp.component.nunique()==1
            for w in roster:
                r=profiles.get((b,w));label=profile_group(r,b);labels[b,w]=label
                profile_rows.append(dict(target_building=b,worker_id=w,group=label,
                    source_label=r['label'] if r else 'missing_profile',fit_id=r['fit_id'] if r else '',
                    component=r['component'] if r else '',training_buildings=r['training_buildings'] if r else '[]',
                    effect=r['effect'] if r else '',lower=r['lower'] if r else '',upper=r['upper'] if r else '',
                    informative_buildings=r['informative_buildings'] if r else '',
                    bootstrap_valid_fraction=r['bootstrap_valid_fraction'] if r else '',
                    fit_status=r['fit_status'] if r else 'missing_profile'))
        pd.DataFrame(profile_rows).to_csv(out/'fold_worker_profiles.csv',index=False)
        coverage=a.merge(status[['canonical_annotation_id','status']],on='canonical_annotation_id',validate='one_to_one')
        coverage['target_c1_manual']=(coverage.stage=='C1')&(coverage.raw_condition=='manual')
        coverage['fold_group']=[labels.get((r.building_id,r.worker_id),'not_target') if r.target_c1_manual else 'not_target' for r in coverage.itertuples()]
        coverage.to_csv(out/'coverage.csv.gz',index=False)
        good=set(status.loc[status.status=='computable_point_pattern','canonical_annotation_id'])
        schedules_by=defaultdict(list)
        for s in schedules:schedules_by[s['building_id']].append(s)
        pairs=pd.read_csv(root/CACHE/'pairwise_point_distances.csv.gz')
        pairgroups={c:g for c,g in pairs.groupby('context_key')}
        feasibility=Counter();combo_states=Counter()
        for ordinal,(context,frame) in enumerate(target.groupby('context_key',sort=True)):
            meta={k:frame.iloc[0][k] for k in META};b=meta['building_id']
            workers=dict(zip(frame.worker_id,frame.canonical_annotation_id));idworker={v:k for k,v in workers.items()}
            ids=[x for x in frame.canonical_annotation_id if x in good];pos={x:i for i,x in enumerate(ids)}
            matrix=np.full((len(ids),len(ids)),np.nan);np.fill_diagonal(matrix,0)
            if context in pairgroups:
                for r in pairgroups[context].itertuples():
                    i,j=pos[r.left_canonical],pos[r.right_canonical];assert np.isnan(matrix[i,j])
                    matrix[i,j]=matrix[j,i]=r.ospa30
            assert np.isfinite(matrix).all()
            for s in schedules_by[b]:
                rawh=[workers[w] for w in json.loads(s['history_worker_ids_json']) if w in workers]
                rawv=[workers[w] for w in json.loads(s['validation_worker_ids_json']) if w in workers]
                h=[x for x in rawh if x in good];v=[x for x in rawv if x in good]
                groups={g:[x for x in h if labels[b,idworker[x]]==g] for g in ['A','B','unknown']}
                for n in [2,4]:
                    base=meta|dict(split_id=s['split_id'],replicate=int(s['replicate']),scheme=s['scheme'],n=n,config='ospa30_t6')
                    combos=enumerate_combinations(groups['A'],groups['B'],n)
                    numbers=Counter(c for _,c in combos)
                    common=all(numbers[m]>0 for m in METHODS[:-1]) and len(v)>=2
                    support=base|dict(history_raw_n=len(rawh),validation_raw_n=len(rawv),history_n=len(h),validation_n=len(v),
                        A_n=len(groups['A']),B_n=len(groups['B']),unknown_n=len(groups['unknown']),
                        A_raw_n=sum(labels[b,idworker[x]]=='A' for x in rawh),B_raw_n=sum(labels[b,idworker[x]]=='B' for x in rawh),
                        unknown_raw_n=sum(labels[b,idworker[x]]=='unknown' for x in rawh),
                        history_canonical_ids_json=js(h),validation_canonical_ids_json=js(v),
                        A_ids_json=js(groups['A']),B_ids_json=js(groups['B']),unknown_ids_json=js(groups['unknown']),
                        A_only_combinations=numbers['A_only'],balanced_AB_combinations=numbers['balanced_AB'],B_only_combinations=numbers['B_only'],
                        random_AB_pool_combinations=len(combos),common_count_support=common,
                        validation_supported=len(v)>=2,status='validation_lt2' if len(v)<2 else 'no_AB_pool_combination' if not combos else 'common_count_support' if common else 'partial_method_support')
                    emit('combination_support.csv.gz',support)
                    feasibility[s['scheme'],n,'common_count_support' if common else support['status']]+=1
                    evaluated=[]
                    for ci,(combo,composition) in enumerate(combos):
                        r=evaluate_combination(matrix,[pos[x] for x in combo],[pos[x] for x in v])
                        row=base|dict(combo_id=f'{context}|{s["split_id"]}|{n}|{ci}',composition=composition,
                            canonical_ids_json=js(combo),worker_ids_json=js([idworker[x] for x in combo]),
                            groups_json=js([labels[b,idworker[x]] for x in combo]),validation_canonical_ids_json=js(v))|r
                        emit('combinations.csv.gz',row);evaluated.append(row);combo_states[r['partition_status']]+=1
                    summary,paired=summarize_methods(evaluated)
                    for r in summary:emit('method_summary.csv.gz',base|r)
                    for r in paired:emit('paired_support.csv.gz',base|r)
            if ordinal%10==0:progress(f'完成 {ordinal+1}/{target.context_key.nunique()} context，组合 {counts["combinations.csv.gz"]}')
        qa.update(status='passed',output_rows=dict(counts),profile_rows=len(profile_rows),target_contexts=target.context_key.nunique(),
            target_buildings=target.building_id.nunique(),target_responses=len(target),config='ospa30_t6',n=[2,4],
            combination_partition_states=dict(combo_states),feasibility={str(k):v for k,v in feasibility.items()},
            enumeration='all distinct subsets, no Monte Carlo',unknown_in_random_pool=False,
            target_building_excluded_from_profiles=True,new_participant_responses=False,protocol_changed=False)
        progress('全部计算完成')
    (out/'RUN_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    return qa


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
    args=p.parse_args();run(args.root,args.out or args.root/OUTPUT)
