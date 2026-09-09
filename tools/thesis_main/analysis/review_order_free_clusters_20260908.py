"""无序点簇输出回读、成员稳定性、固定支持图与点集示例。"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
from collections import defaultdict
from itertools import combinations
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import BASE,PREVIOUS,OUTPUT,CONFIGS


def labels(clusters):
    result={p:i for i,g in enumerate(clusters) for p in g}
    assert len(result)==sum(map(len,clusters))
    return result


def coassignment_disagreement(left,right,common):
    a,b=labels(left),labels(right)
    if len(common)<2:raise ValueError('insufficient_overlap')
    return sum((a[i]==a[j])!=(b[i]==b[j]) for i,j in combinations(common,2))/math.comb(len(common),2)


def run(root,out):
    def save(name,rows):pd.DataFrame(rows).to_csv(out/name,index=False,float_format='%.12g')
    a=pd.read_csv(root/BASE/'annotations.csv.gz',dtype=str,keep_default_na=False)
    meta=a.drop_duplicates('context_key').set_index('context_key');aid_worker=a.set_index('canonical_annotation_id').worker_id.to_dict()
    interner={x:x for x in a.canonical_annotation_id}
    status=pd.read_csv(out/'response_status.csv.gz',dtype=str)
    assert set(status.canonical_annotation_id)==set(a.canonical_annotation_id)
    good=set(status.loc[status.status=='computable_point_pattern','canonical_annotation_id'])
    context_workers={c:dict(zip(g.worker_id,g.canonical_annotation_id)) for c,g in a[a.canonical_annotation_id.isin(good)].groupby('context_key')}
    schedules={r.split_id:(json.loads(r.history_worker_ids_json),json.loads(r.validation_worker_ids_json)) for r in pd.read_csv(root/PREVIOUS/'census/worker_splits.csv.gz',dtype=str).itertuples()}
    points=pd.read_csv(out/'pairwise_point_distances.csv.gz')
    assert not points.duplicated(['context_key','left_canonical','right_canonical']).any()
    edge={}
    for r in points.itertuples():
        for m in ('ospa30','ospa60','chamfer'):edge[(m,*sorted((r.left_canonical,r.right_canonical)))]=getattr(r,m)
    def distance(m,x,y):return 0. if x==y else edge[(m,*sorted((x,y)))]
    configs={c:(m,t) for c,m,t in CONFIGS}
    definitions={};pair_counts=defaultdict(lambda:[0,0]);case_rows=[]
    full_count=0
    for chunk in pd.read_csv(out/'historical_cluster_definitions.csv.gz',chunksize=15000):
        for r in chunk.itertuples():
            key=(r.context_key,r.split_id,r.config);assert key not in definitions
            h=tuple(interner[x] for x in json.loads(r.historical_canonical_ids_json));v=tuple(interner[x] for x in json.loads(r.validation_canonical_ids_json))
            hw,vw=schedules[r.split_id];mapping=context_workers[r.context_key]
            assert list(h)==[mapping[w] for w in hw if w in mapping]
            assert list(v)==[mapping[w] for w in vw if w in mapping] and not set(h)&set(v)
            assert len(h)==r.history_n and len(v)==r.validation_n
            clusters=tuple(tuple(interner[x] for x in g) for g in json.loads(r.full_clusters_json))
            if r.full_partition_status=='unique':assert set(labels(clusters))==set(h)
            else:assert not clusters
            definitions[key]=(h,v,clusters,r.full_partition_status)
            if clusters:
                lab=labels(clusters)
                for i,j in combinations(sorted(h),2):
                    stat=pair_counts[(r.context_key,r.config,r.scheme,i,j)];stat[0]+=1;stat[1]+=int(lab[i]==lab[j])
            if r.config=='ospa30_t6' and r.scheme=='two_thirds':
                sizes=[len(g) for g in clusters]
                case_rows.append(dict(context_key=r.context_key,split_id=r.split_id,replicate=r.replicate,unique=bool(clusters),
                    supported_groups=sum(n>=2 for n in sizes) if clusters else np.nan,group_count=len(clusters) if clusters else np.nan,
                    history_n=len(h),validation_n=len(v)))
            full_count+=1
    print('完整历史簇身份及成员已回读',full_count,flush=True)
    pr=[dict(context_key=k[0],config=k[1],scheme=k[2],left_canonical=k[3],right_canonical=k[4],
             shared_unique_partition_splits=n,together_splits=s,coassignment_probability=s/n,
             observed_split_pair_disagreement=2*s*(n-s)/(n*(n-1)) if n>=2 else np.nan) for k,(n,s) in pair_counts.items()]
    pairframe=pd.DataFrame(pr);save('membership_pair_repeatability.csv.gz',pr)
    aggregate=pairframe.groupby(['context_key','config','scheme']).agg(observed_worker_pairs=('left_canonical','size'),
        minimum_pair_splits=('shared_unique_partition_splits','min'),maximum_pair_splits=('shared_unique_partition_splits','max'),
        pairs_with_at_least_two_splits=('observed_split_pair_disagreement','count'),
        mean_pair_membership_disagreement=('observed_split_pair_disagreement','mean')).reset_index()
    aggregate=aggregate.merge(meta[['building_id','stage','raw_condition']],on='context_key',validate='many_to_one')
    save('context_membership_repeatability.csv',aggregate)
    prefix_n=0;prefix_sample=[]
    with gzip.open(out/'prefix_membership_stability.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['context_key','split_id','config','scheme','k','prefix_status','full_status','coassignment_disagreement_to_full_history']);writer.writeheader()
        for chunk in pd.read_csv(out/'prefix_reclustering.csv.gz',chunksize=25000):
            for r in chunk.itertuples():
                h,v,c,state=definitions[(r.context_key,r.split_id,r.config)]
                part=json.loads(r.prefix_clusters_json)
                if r.status=='unique':assert set(labels(part))==set(h[:r.k])
                else:assert not part
                value=coassignment_disagreement(part,c,h[:r.k]) if part and c else np.nan
                row=dict(context_key=r.context_key,split_id=r.split_id,config=r.config,scheme=r.scheme,k=r.k,
                         prefix_status=r.status,full_status=state,coassignment_disagreement_to_full_history=value)
                writer.writerow(row);prefix_n+=1
                if r.config=='ospa30_t6' and r.scheme=='two_thirds':prefix_sample.append(row)
    pf=pd.DataFrame(prefix_sample)
    ps=pf.groupby(['context_key','k']).agg(splits=('split_id','size'),comparable_splits=('coassignment_disagreement_to_full_history','count'),
        coassignment_disagreement=('coassignment_disagreement_to_full_history','mean')).reset_index()
    save('context_prefix_membership_summary.csv',ps)
    fixed_n=0;fixed_assignments={};sampled_geometry=0;fixed_rows=[];errors=[]
    for chunk in pd.read_csv(out/'fixed_taxonomy_prefixes.csv.gz',chunksize=25000):
        for r in chunk.itertuples():
            key=(r.context_key,r.split_id,r.config);h,v,c,state=definitions[key];assert state=='unique'
            observed=json.loads(r.validation_compatible_cluster_ids_json)
            if key not in fixed_assignments:
                fixed_assignments[key]=observed
                if r.replicate in (0,199):
                    metric,tau=configs[r.config]
                    expected=[[j for j,g in enumerate(c) if max(distance(metric,x,y) for y in g)<=tau+1e-10] for x in v]
                    assert observed==expected,(key,observed,expected)
                    sampled_geometry+=1
            else:assert observed==fixed_assignments[key]
            counts=[sum(x in set(h[:r.k]) for x in g) for g in c]
            assert json.loads(r.training_cluster_support_json)==counts
            outside=sum(not x for x in observed);ambiguous=sum(len(x)>1 for x in observed)
            assert abs(outside/len(v)-r.validation_outside_fraction)<1e-10
            assert abs(ambiguous/len(v)-r.validation_ambiguous_fraction)<1e-10
            vc=[sum(x==[j] for x in observed) for j in range(len(c))]+[outside]
            assert json.loads(r.validation_cluster_support_json)==vc
            tv=sum(abs(x/r.k-y/len(v)) for x,y in zip(counts+[0],vc))/2 if not ambiguous else np.nan
            if ambiguous:assert pd.isna(r.distribution_tv)
            else:errors.append(abs(tv-r.distribution_tv))
            if r.config=='ospa30_t6' and r.scheme=='two_thirds' and len(h)>=15 and r.k in (3,5,8,10,12,15) and not ambiguous:
                fixed_rows.append(dict(context_key=r.context_key,split_id=r.split_id,k=r.k,distribution_tv=r.distribution_tv,
                    training_entropy=r.training_entropy,validation_outside_fraction=r.validation_outside_fraction,history_n=len(h),validation_n=len(v)))
            fixed_n+=1
    assert max(errors,default=0)<1e-10
    q=json.loads((out/'RUN_QA.json').read_text(encoding='utf-8'))
    assert full_count==q['streams']['historical_cluster_definitions.csv.gz'] and prefix_n==q['streams']['prefix_reclustering.csv.gz'] and fixed_n==q['streams']['fixed_taxonomy_prefixes.csv.gz']
    fixed=pd.DataFrame(fixed_rows);assert fixed.groupby(['context_key','split_id']).k.nunique().eq(6).all()
    init=pd.read_csv(root/PREVIOUS/'initialization_context_index.csv').set_index('context_key').initialization_kind
    for col in ['stage','raw_condition','building_id']:fixed[col]=fixed.context_key.map(meta[col])
    fixed['initialization_kind']=fixed.context_key.map(init)
    fc=fixed.groupby(['context_key','stage','raw_condition','initialization_kind','k']).agg(splits=('split_id','nunique'),
        distribution_tv=('distribution_tv','mean'),entropy=('training_entropy','mean'),validation_outside_fraction=('validation_outside_fraction','mean')).reset_index()
    save('fixed_support_context_curves.csv',fc)
    plots=fc.groupby(['stage','raw_condition','initialization_kind','k']).agg(contexts=('context_key','nunique'),
        min_splits=('splits','min'),max_splits=('splits','max'),distribution_tv=('distribution_tv','mean'),entropy=('entropy','mean')).reset_index()
    save('fixed_support_summary.csv',plots)
    case=pd.DataFrame(case_rows);case['supported_multi']=case.supported_groups.ge(2)
    csummary=case.groupby('context_key').agg(available_splits=('split_id','nunique'),unique_splits=('unique','sum'),
        supported_multi_splits=('supported_multi','sum'),median_group_count=('group_count','median')).reset_index()
    csummary=csummary.merge(aggregate[(aggregate.config=='ospa30_t6')&(aggregate.scheme=='two_thirds')],on='context_key',validate='one_to_one')
    save('case_selection_contexts.csv',csummary)
    sensitivity=pd.read_csv(out/'historical_cluster_definitions.csv.gz',usecols=['context_key','split_id','config','scheme','stage','raw_condition','full_cluster_count'])
    matched=sensitivity[(sensitivity.scheme=='two_thirds')&sensitivity.config.isin(['ospa30_t3','ospa30_t6','ospa30_t12'])].pivot(
        index=['context_key','split_id','stage','raw_condition'],columns='config',values='full_cluster_count').dropna()
    matched_summary=matched.groupby(['context_key','stage','raw_condition']).mean()
    matched_summary['common_unique_splits']=matched.groupby(['context_key','stage','raw_condition']).size()
    save('matched_threshold_context_summary.csv',matched_summary.reset_index())
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    figdir=out/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(13,5.4))
    names={'not_applicable':'Manual','control_natural':'Semi 自然control','trap_natural':'Semi 自然trap','trap_synthetic_disjoint_source':'Semi 合成trap'}
    for kind,g in plots[(plots.stage=='P1')&(plots.raw_condition!='oos')].groupby('initialization_kind'):
        label=f'{names[kind]}（{g.contexts.iloc[0]}单元，{g.min_splits.iloc[0]}–{g.max_splits.iloc[0]}次）'
        axes[0].plot(g.k,g.distribution_tv,'o-',label=label);axes[1].plot(g.k,g.entropy,'o-',label=label)
    for ax in axes:ax.set_xlabel('历史前缀人数');ax.set_xticks([3,5,8,10,12,15]);ax.grid(alpha=.2);ax.set_ylim(bottom=0)
    axes[0].set_ylabel('历史／验证簇分布的 TV 距离');axes[1].set_ylabel('历史簇分布的 Shannon 熵')
    axes[0].legend(fontsize=8);axes[0].set_title('比例是否更接近固定验证组');axes[1].set_title('稳定多簇不要求熵降到零')
    fig.suptitle('无序点集 OSPA式距离：cap=30°、簇阈值=6°；固定完整历史组学到的簇')
    fig.text(.5,.012,'仅保留 h≥15、历史分区唯一且验证无多重归属的相同划分；不是在线前缀学习，也不代表全部图。',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(figdir/'cluster_distribution_curves.png',dpi=180);plt.close(fig)
    # 展示候选只用于核对点集差异，不因示例选择推断全体已形成语义模式。
    eligible=csummary[(csummary.stage=='P1')&(csummary.raw_condition=='manual')&(csummary.supported_multi_splits>0)]
    eligible=eligible.sort_values(['supported_multi_splits','mean_pair_membership_disagreement','context_key'],ascending=[False,True,True]).head(4)
    raw={v['canonical_annotation_id']:v['points_1024x512'] for v in map(json.loads,(root/BASE/'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()) if str(v['selected_canonical_version']).lower()=='true'}
    examples=[]
    for number,r in enumerate(eligible.itertuples(),1):
        selected=case[(case.context_key==r.context_key)&case.supported_multi].sort_values('replicate').iloc[0]
        h,v,c,_=definitions[(r.context_key,selected.split_id,'ospa30_t6')]
        image_id=meta.loc[r.context_key,'image_id'];image_path=root/'data/mp3d_layout/img_v'/f'{image_id}.jpg'
        image=np.asarray(Image.open(image_path).convert('RGB'));top=sorted(c,key=lambda g:(-len(g),tuple(g)))[:3]
        fig,axes=plt.subplots(len(top)+1,1,figsize=(14,3.4*(len(top)+1)))
        for ax in axes:ax.imshow(image,extent=[0,1024,512,0]);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.axis('off')
        axes[0].set_title(f'示例 {number}：{image_id}\n原全景；点集簇不能自动解释为 enclosed / extended',fontsize=11)
        reps=[]
        for ax,g,color in zip(axes[1:],top,['#00c9ff','#ff5070','#ffe343']):
            pick=min(sorted(g),key=lambda x:sum(distance('ospa30',x,y) for y in g))
            pp=np.asarray(raw[pick]);ax.scatter(pp[:,0],pp[:,1],s=70,c=color,edgecolors='black',linewidths=.8)
            ax.set_title(f'历史簇 {len(reps)+1}：{len(g)}/{len(h)} 份；显示代表 W{aid_worker[pick]}，只画原始点，不画连接线',fontsize=11)
            reps.append(dict(canonical=pick,worker=aid_worker[pick],support=len(g)))
        fig.tight_layout();filename=f'point_cluster_case_{number:02d}.png';fig.savefig(figdir/filename,dpi=150);plt.close(fig)
        examples.append(dict(number=number,context_key=r.context_key,split_id=selected.split_id,
            image_source=str(image_path.relative_to(root)),figure='figures/'+filename,
            representatives_json=json.dumps(reps),selection='P1 Manual按有支持多簇次数降序，再成员变动升序；选首个有支持多簇的历史分组，未按验证表现选择',visual_observation='pending'))
    save('visual_examples.csv',examples)
    audit=dict(status='passed',full_training_definitions_identity_checked=full_count,prefix_membership_rows_checked=prefix_n,
        fixed_taxonomy_rows_arithmetic_checked=fixed_n,validation_assignments_geometry_checked=sampled_geometry,
        detailed_geometry_sample='replicate 0 and 199, all configs/contexts',maximum_tv_difference=max(errors,default=0),
        same_validation_assignment_for_all_prefixes=True,raw_points_modified=False,
        membership_repeatability='同一工人对在不同唯一历史分区中的同簇关系变化；只在至少2次共同出现时有比较量，不是总体置信区间',
        prefix_membership_to_full='只用于回顾性诊断；全历史端点机械为0，不能当验证成功',
        visual_examples_rendered=len(examples),visual_examples_reviewed=0)
    (out/'REVIEW_AUDIT.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(audit,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
    a=p.parse_args();run(a.root,a.out or a.root/OUTPUT)
