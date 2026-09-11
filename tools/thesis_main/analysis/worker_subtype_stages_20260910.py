"""对多组方案逐子类回放；真实人员子集复用计算，不要求其余组够人数。"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import argparse
import json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis import worker_four_block_exploration_20260910 as base
from tools.thesis_main.analysis import worker_group_count_exploration_20260910 as grouping

OUT=base.OUT/'subtype_stage_validation'


def make_evaluator(neighbors, invalid, orders, reference, distances):
    # ponytail: 每图独立有限缓存，覆盖现有26人；更大池需单独测量内存后再扩展。
    @lru_cache(maxsize=120000)
    def part(config,mask):return base.graph_partition_bits(neighbors[config],mask,invalid[config])
    @lru_cache(maxsize=180000)
    def compare(config,a,b):return base.compare_bits(part(config,a),part(config,b))
    @lru_cache(maxsize=None)
    def evaluate(pool,horizons):
        allowed=set(pool);n=len(pool);reps=len(orders)
        assert n>=7 and len(allowed)==n and all(7<=h<=n for h in horizons)
        sequences=[[i for i in order if i in allowed] for order in orders]
        assert all(len(s)==n and len(set(s))==n for s in sequences)
        totals={}
        for seq in sequences:
            masks=[0]
            for i in seq:masks.append(masks[-1]|(1<<int(i)))
            for config in neighbors:
                for h in horizons:
                    anchors=[]
                    for k in range(2,h-4):
                        state=0
                        for j in range(k+1,h+1):
                            state=max(state,compare(config,masks[k],masks[j]))
                            if state==2:break
                        anchors.append(state)
                    tail=np.maximum.accumulate(anchors[::-1])[::-1]
                    for k,state in enumerate(tail,2):
                        c=totals.setdefault((config,h,k),Counter());c[int(state)]+=1
                        if state==0:c['multi' if sum(g.bit_count()>=2 for g in part(config,masks[k]))>=2 else 'single']+=1
        curves=[]
        for (config,h,k),c in totals.items():
            assert c[0]+c[1]+c[2]==reps
            curves.append(dict(config=config,horizon=h,k=k,lower=c[0]/reps,upper=(c[0]+c[1])/reps,
                unknown=c[1],changing=c[2],stable_single=c['single'],stable_multi=c['multi']))
        quality={}
        for h in horizons:
            if not np.isfinite(reference).all():quality[h]=np.nan
            else:
                values,_=base.reuse.medoid_reference(reference,distances,np.asarray([seq[:h] for seq in sequences],int))
                quality[h]=float(values.mean())
        return curves,quality
    return evaluate


def replay():
    from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import ORDERS
    OUT.mkdir(exist_ok=True)
    frame=pd.read_csv(base.OUT/'manual.csv.gz',dtype={'worker_id':str})
    pairs=pd.read_csv(base.OUT/'pairs.csv.gz')
    folds=pd.read_csv(base.OUT/'fold_members.csv.gz',dtype={'worker_id':str})
    folds=folds[folds.variant.eq('primary')&folds.panel.eq('native')&folds.model.ne('Q_median2')]
    full=pd.read_csv(grouping.OUT/'group_counts.csv');maxima=full.groupby(['cohort','model'])['groups'].max().to_dict()
    orders=[[str(w) for w in json.loads(line)['worker_ids']] for line in ORDERS.read_text(encoding='utf8').splitlines()]
    assert len(orders)==200
    scenarios=[];coverage=[];pool_curves=[];pool_quality=[];pool_index=[]
    for image,original in frame.groupby('image_id'):
        original=original.sort_values('canonical_annotation_id').reset_index(drop=True)
        if len(original)<7:continue
        building=original.building_id.iloc[0];positions=dict(zip(original.worker_id,original.index))
        ids=set(original.canonical_annotation_id)
        ip=pairs[pairs.image_id.eq(image)&pairs.left_canonical.isin(ids)&pairs.right_canonical.isin(ids)]
        matrices=base.reuse.image_matrices(original,ip);counts=original.effective_point_count.to_numpy()
        neighbors={};invalid={}
        for config,key,threshold in [('q95','q',.05),('ospa30_t6','ospa30',6.)]:
            edges=(matrices[key]<=threshold+1e-12)&(counts[:,None]==counts[None,:]);np.fill_diagonal(edges,False)
            neighbors[config]=[sum(1<<int(j) for j in np.flatnonzero(row)) for row in edges]
            invalid[config]=sum(1<<int(i) for i in np.flatnonzero(~original.q_geometry_valid.to_numpy())) if config=='q95' else 0
        reference=original.ospa30.to_numpy() if original.reference_allowed.all() else np.full(len(original),np.nan)
        evaluate=make_evaluator(neighbors,invalid,[[positions[w] for w in order if w in positions] for order in orders],reference,matrices['ospa30'])
        pools={};image_scenarios=[]
        def register(people,horizons):
            pool=tuple(sorted(positions[w] for w in people));mask=sum(1<<int(i) for i in pool)
            pools.setdefault(mask,dict(pool=pool,horizons=set(),worker_ids='|'.join(sorted(people,key=int))))['horizons'].update(horizons)
            return mask
        for (cohort,model),trained in folds[folds.heldout_building.eq(building)].groupby(['cohort','model']):
            assert all(building not in s.split('|') for s in trained.training_buildings)
            available=set(original.worker_id)&set(trained.worker_id)
            if cohort=='current20':available&=set(original[original.current20_member].worker_id)
            for ng,labels in grouping.partitions(trained,model,range(2,maxima[(cohort,model)]+1)).items():
                for label in range(1,ng+1):
                    people=available&set(trained.loc[labels==label,'worker_id']);n=len(people)
                    meta=dict(image_id=image,building_id=building,cohort=cohort,model=model,groups=ng,group=label,
                        training_group_n=int((labels==label).sum()),target_group_n=n,available_pool_n=len(available),
                        reference_allowed=bool(original.reference_allowed.all()))
                    coverage.append(dict(**meta,status='can_replay' if n>=7 else 'insufficient_people'))
                    if n<7:continue
                    horizons=sorted({h for h in (7,8,10,13,n) if 7<=h<=n})
                    pool=register(people,horizons);allpool=register(available,horizons)
                    for h in horizons:image_scenarios.append(dict(**meta,horizon=h,pool=pool,baseline_pool=allpool))
        for mask,data in pools.items():
            curves,quality=evaluate(data['pool'],tuple(sorted(data['horizons'])))
            pool_curves.extend(dict(image_id=image,building_id=building,pool=mask,**r) for r in curves)
            pool_quality.extend(dict(image_id=image,pool=mask,horizon=h,reference_error=v) for h,v in quality.items())
            pool_index.append(dict(image_id=image,pool=mask,n=len(data['pool']),worker_ids=data['worker_ids']))
        scenarios.extend(image_scenarios)
        print('subtype replay',image,'unique pools',len(pools),'scenarios',len(image_scenarios),flush=True)
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv.gz',index=False)
    pd.DataFrame(scenarios).to_csv(OUT/'scenarios.csv.gz',index=False)
    pd.DataFrame(pool_curves).to_csv(OUT/'pool_curves.csv.gz',index=False)
    pd.DataFrame(pool_quality).to_csv(OUT/'pool_quality.csv.gz',index=False)
    pd.DataFrame(pool_index).to_csv(OUT/'pool_members.csv.gz',index=False)
    (OUT/'REPLAY_QA.json').write_text(json.dumps(dict(permutations=200,unique_image_pools=len(pool_index),scenarios=len(scenarios),
        coverage_rows=len(coverage),curve_rows=len(pool_curves),target_building_excluded=True,
        singletons_preserved_in_coverage=True,other_groups_not_required=True,raw_data_changed=False),indent=2),encoding='utf8')
    summarize()


def summarize():
    s=pd.read_csv(OUT/'scenarios.csv.gz');curves=pd.read_csv(OUT/'pool_curves.csv.gz');quality=pd.read_csv(OUT/'pool_quality.csv.gz')
    scope=pd.read_csv(base.OUT/'scope_responses.csv').fillna('')
    scope_in=set(scope[scope.final_scope.eq('in_scope')&scope.later_hold.eq('')].image_id)
    assert not curves.duplicated(['image_id','pool','config','horizon','k']).any()
    assert np.allclose(curves.lower*200,curves.stable_single+curves.stable_multi)
    assert np.allclose(curves.upper,curves.lower+curves.unknown/200)
    assert ((curves.k>=2)&(curves.k<=curves.horizon-5)).all()
    fields=['config','k','lower','upper','unknown','changing','stable_single','stable_multi']
    joined=s.merge(curves[['image_id','pool','horizon']+fields],on=['image_id','pool','horizon'],validate='many_to_many')
    baseline=curves.drop(columns='building_id').rename(columns={'pool':'baseline_pool',**{x:'baseline_'+x for x in fields if x not in ['config','k']}})
    joined=joined.merge(baseline,on=['image_id','baseline_pool','config','horizon','k'],validate='many_to_one')
    joined=joined.merge(quality,on=['image_id','pool','horizon'],validate='many_to_one').merge(
        quality.rename(columns={'pool':'baseline_pool','reference_error':'baseline_reference_error'}),on=['image_id','baseline_pool','horizon'],validate='many_to_one')
    assert joined.baseline_lower.notna().all()
    joined['difference_lower']=joined.lower-joined.baseline_upper
    joined['difference_upper']=joined.upper-joined.baseline_lower
    same=joined.pool.eq(joined.baseline_pool);joined.loc[same,['difference_lower','difference_upper']]=0.
    joined['reference_difference']=joined.reference_error-joined.baseline_reference_error
    joined['scope_confirmed_in']=joined.image_id.isin(scope_in)
    joined.to_csv(OUT/'paired_curves.csv.gz',index=False)
    rows=[]
    for key,g in joined.groupby(['cohort','model','groups','group','config','horizon','k']):
        for subset in ['all','reference_allowed','scope_confirmed_in']:
            z=g if subset=='all' else g[g[subset]]
            if z.empty:continue
            numeric=['lower','upper','baseline_lower','baseline_upper','difference_lower','difference_upper','reference_error','baseline_reference_error','reference_difference']
            mean=z.groupby('building_id')[numeric].mean().mean()
            rows.append(dict(zip(['cohort','model','groups','group','config','horizon','k'],key),subset=subset,
                images=z.image_id.nunique(),buildings=z.building_id.nunique(),
                confirmed_images=int(z.lower.ge(.8-1e-12).sum()),undetermined_images=int(((z.lower<.8-1e-12)&(z.upper>=.8-1e-12)).sum()),
                not_reached_images=int(z.upper.lt(.8-1e-12).sum()),baseline_confirmed_images=int(z.baseline_lower.ge(.8-1e-12).sum()),
                target_group_min=int(z.target_group_n.min()),target_group_max=int(z.target_group_n.max()),**mean.to_dict()))
    pd.DataFrame(rows).to_csv(OUT/'subtype_summary.csv',index=False)
    onset=[]
    for key,g in joined.groupby(['image_id','building_id','cohort','model','groups','group','config','horizon']):
        g=g.sort_values('k');assert (np.diff(g.lower)>=-1e-12).all() and (np.diff(g.upper)>=-1e-12).all()
        possible=g[g.upper>=.8-1e-12];confirmed=g[g.lower>=.8-1e-12]
        onset.append(dict(zip(['image_id','building_id','cohort','model','groups','group','config','horizon'],key),
            earliest_possible=int(possible.k.iloc[0]) if len(possible) else None,
            earliest_confirmed=int(confirmed.k.iloc[0]) if len(confirmed) else None,
            status='confirmed' if len(confirmed) else 'undetermined' if len(possible) else 'not_reached_in_observed_range'))
    pd.DataFrame(onset).to_csv(OUT/'subtype_onsets.csv.gz',index=False)
    print('summarized subtype stages',len(joined),len(rows),flush=True)


def named_summary():
    folds=pd.read_csv(base.OUT/'fold_members.csv.gz',dtype={'worker_id':str})
    folds=folds[folds.variant.eq('primary')&folds.panel.eq('native')&folds.model.ne('Q_median2')]
    limits=pd.read_csv(grouping.OUT/'group_counts.csv').groupby(['cohort','model'])['groups'].max().to_dict()
    maps=[]
    for (cohort,model,building),p in folds.groupby(['cohort','model','heldout_building']):
        assert all(building not in s.split('|') for s in p.training_buildings)
        for k,labels in grouping.partitions(p,model,range(2,limits[(cohort,model)]+1)).items():
            for role,label in grouping.named_groups(p,model,labels).items():
                maps.append(dict(cohort=cohort,model=model,building_id=building,groups=k,role=role,group=label if label is not None else 0))
    mapping=pd.DataFrame(maps);assert not mapping.duplicated(['cohort','model','building_id','groups','role']).any()
    mapping.to_csv(OUT/'named_role_map.csv.gz',index=False)
    frame=pd.read_csv(base.OUT/'manual.csv.gz')
    images=frame.groupby(['image_id','building_id']).size().reset_index(name='n');images=images[images.n>=7]
    configurations=pd.read_csv(grouping.OUT/'group_counts.csv')
    formed=set(zip(mapping.cohort,mapping.model,mapping.building_id,mapping.groups))
    availability=[dict(image_id=i.image_id,building_id=i.building_id,cohort=c.cohort,model=c.model,groups=c.groups,
                      classification_available=(c.cohort,c.model,i.building_id,c.groups) in formed)
                  for i in images.itertuples() for c in configurations.itertuples()]
    pd.DataFrame(availability).to_csv(OUT/'classification_availability.csv',index=False)
    keys=['cohort','model','building_id','groups','group']
    paired=pd.read_csv(OUT/'paired_curves.csv.gz').merge(mapping[mapping.group.ne(0)],on=keys,validate='many_to_many')
    assert not paired.duplicated(['image_id','cohort','model','groups','role','config','horizon','k']).any()
    paired.to_csv(OUT/'named_paired_curves.csv.gz',index=False)
    coverage=pd.read_csv(OUT/'coverage.csv.gz').merge(mapping[mapping.group.ne(0)],on=keys,validate='many_to_many')
    coverage.to_csv(OUT/'named_coverage.csv.gz',index=False)
    summary=[];groupcols=['cohort','model','groups','role','config','horizon','k']
    for subset in ['all','reference_allowed','scope_confirmed_in']:
        z=paired if subset=='all' else paired[paired[subset]]
        numeric=['lower','upper','baseline_lower','baseline_upper','difference_lower','difference_upper','reference_error','baseline_reference_error','reference_difference']
        means=z.groupby(groupcols+['building_id'])[numeric].mean().groupby(groupcols).mean()
        z=z.assign(confirmed=z.lower.ge(.8-1e-12),unknown_band=(z.lower<.8-1e-12)&(z.upper>=.8-1e-12),
                   not_reached=z.upper.lt(.8-1e-12),baseline_confirmed=z.baseline_lower.ge(.8-1e-12))
        tally=z.groupby(groupcols).agg(images=('image_id','nunique'),buildings=('building_id','nunique'),
            confirmed_images=('confirmed','sum'),undetermined_images=('unknown_band','sum'),
            not_reached_images=('not_reached','sum'),baseline_confirmed_images=('baseline_confirmed','sum'),
            target_group_min=('target_group_n','min'),target_group_max=('target_group_n','max'))
        summary.append(tally.join(means).reset_index().assign(subset=subset))
    pd.concat(summary,ignore_index=True).to_csv(OUT/'named_subtype_summary.csv',index=False)
    pd.read_csv(OUT/'subtype_onsets.csv.gz').merge(mapping[mapping.group.ne(0)],on=keys,validate='many_to_many').to_csv(OUT/'named_onsets.csv.gz',index=False)
    members=pd.read_csv(base.OUT/'members.csv',dtype={'worker_id':str})
    members=members[members.variant.eq('primary')&members.panel.eq('native')&members.model.ne('Q_median2')]
    rows=[]
    for (cohort,model),p in members.groupby(['cohort','model']):
        for k,labels in grouping.partitions(p,model,range(2,limits[(cohort,model)]+1)).items():
            for role,label in grouping.named_groups(p,model,labels).items():
                z=p.loc[labels==label] if label is not None else p.iloc[:0]
                rows.append(dict(cohort=cohort,model=model,groups=k,role=role,group=label,n=len(z),worker_ids='|'.join(sorted(z.worker_id,key=int))))
    pd.DataFrame(rows).to_csv(OUT/'named_full_profiles.csv',index=False)
    (OUT/'NAMED_QA.json').write_text(json.dumps(dict(role_mapping_unique=True,no_target_outcome_used=True,
        ambiguous_role_assignments=int(mapping.group.eq(0).sum()),named_curve_rows=len(paired),
        repeated_descriptions_not_independent=True),indent=2),encoding='utf8')
    print('named summaries complete',len(paired),flush=True)


def report():
    from tools.thesis_main.analysis.build_worker_four_block_report_20260910 import NAMES
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names={m:n.replace('scope','规则判断').replace('质量自动二分','质量').replace('分组','') for m,n in NAMES.items()}
    names['QTSB']='质量＋时间＋规则＋半自动';names['T']='时间'
    counts=pd.read_csv(grouping.OUT/'group_counts.csv')
    members=json.loads((grouping.OUT/'group_members.json').read_text('utf8'))
    repeat=pd.read_csv(grouping.OUT/'named_repeatability.csv')
    summary=pd.read_csv(OUT/'named_subtype_summary.csv');coverage=pd.read_csv(OUT/'coverage.csv.gz')
    named_full=pd.read_csv(OUT/'named_full_profiles.csv')
    qa=json.loads((OUT/'REPLAY_QA.json').read_text('utf8'))
    examples=[('T',2),('QT',3),('QTSB',3)] # 延续用户讨论的例子，不按本次稳定效果选择。
    named_examples=[('T',2,'time_low','较快组'),('T',2,'time_high','较慢组'),
        ('QT',3,'quality_low','参考偏差最低组'),('QT',3,'time_low','最快组'),('QT',3,'time_high','最慢组'),
        ('QTSB',3,'quality_low','参考偏差最低组'),('QTSB',3,'time_low','最快组'),('QTSB',3,'benefit_high','净改善最高组')]
    order=[''.join(c) for c in base.COMBOS]
    pages=[]
    def p(s):return dict(type='p',text=s)
    def t(headers,rows):return dict(type='table',headers=headers,rows=rows)
    def page(title,*blocks):pages.append(dict(title=title,blocks=list(blocks)))
    def cohort_members(cohort,model,k):return [r for r in members if r['cohort']==cohort and r['model']==model and r['groups']==k]
    def rrow(model,k,role,support):
        r=repeat[repeat.cohort.eq('current20')&repeat.model.eq(model)&repeat.groups.eq(k)&repeat.role.eq(role)&repeat.support.eq(support)]
        assert len(r)==1;return r.iloc[0]
    def nrow(model,k,role):
        z=named_full[named_full.cohort.eq('current20')&named_full.model.eq(model)&named_full.groups.eq(k)&named_full.role.eq(role)]
        assert len(z)==1;return z.iloc[0]
    def srow(model,k,role,h,cohort='current20',config='q95'):
        r=summary[summary.cohort.eq(cohort)&summary.model.eq(model)&summary.groups.eq(k)&summary.role.eq(role)&summary.config.eq(config)&
                  summary.horizon.eq(h)&summary.k.eq(h-5)&summary.subset.eq('reference_allowed')]
        assert len(r)<=1;return r.iloc[0] if len(r) else None
    page('人员分类与具体子类稳定性',
        p('2026年9月10日｜更新探索规则后的历史验证｜不固定组数，不强行均分，不预选最终方案'),
        p('方案一：用单项表现形成候选子类。质量、时间、规则判断、半自动行为各自探索分组及组数。原先按质量中位数切为10／10人的方法仅作历史对照，不作为本版应退回的方案。'),
        p('方案二：用若干表现联合形成候选子类。例如质量＋时间、质量＋半自动、质量＋规则，以及三项、四项组合；每个组合都重新分类，并检查不同组数。'),
        p('本版的判断目标是：能否识别至少一个含义清楚、换图后仍能重复识别的人群子类，其独立标注能进入稳定阶段。人数均匀不算优点；其他子类人数不足，也不否定这个子类。'),
        p('单项方案较容易解释，但可能忽略其他行为差异。联合方案能够刻画更具体的行为，但加入信息和增加组数也可能使名单更不稳定。两者均须用数据验证，不能只看分组是否整齐或哪条曲线更早变平。'),
        p('本轮已经从“人员够不够”推进到逐子类真实回放。结果仍是历史人员池内的探索，不能称为新增人员已验证，也不能证明某类在所有图片上永久收敛。'))
    page('这次实际检查了什么',
        t(['项目','本轮执行内容'],[
            ['指标组合','四个信息块的全部15种非空组合；大项总权重相同。'],
            ['组数','从2组至可分类人数的一半；后续20人探索2—10组，全部范围随资料支持调整。'],
            ['人员范围',f'全部26人与后续20人分开，共{len(counts)}套分类配置；没有各组人数相等的配额。'],
            ['具体子类','每个子类独立检查名单重复性、目标图人数、稳定阶段及代表标注的参考偏差。'],
            ['反复抽取','每图200条全局人员顺序；不同方法下相同人员子集复用计算，不增加独立证据。'],
            ['目标隔离','分类时排除目标楼的质量、时间、scope及半自动记录；目标图仅在分类之后评价。']]),
        p('质量是最终点集与参考的偏差，时间是无辅助有效操作时间，规则目前只覆盖scope适用范围误判，半自动是修改幅度与参考净改善。不能将scope等同所有规则执行，也不能把快慢解释成认真程度。'),
        p('实际运行仍使用Ward算法，探索的是指标组合与组数；没有穷尽其他聚类算法或权重。单人组原样保留，只能提示特殊表现，不能由一个人证明一种人群类型。资料不足的人保持未定。'))
    for cohort,label in [('current20','后续20人'),('all26','全部26人')]:
        rows=[]
        for model in order:
            g=counts[counts.cohort.eq(cohort)&counts.model.eq(model)]
            vals=[g[g.groups.eq(k)].sizes.iloc[0].replace('|','／') for k in [2,3,4,5]]
            rows.append([names[model],str(g.workers.iloc[0]),*vals])
        page(label+'：各组合分了多少人',p('各数字为一组人数。以下展示2—5组，全部探索组数和名单保留在数据附录。包含1人的组照列，不因此删除其他组，也不认定单人类型已成立。'),
             t(['分类指标','人数','2组','3组','4组','5组'],rows),
             p('同一组号只在同一分类办法内按首项指标排序；不同组数、不同目标楼的组1不保证同一批人。这里是全部历史资料下的名单摘要，后面的验证每次重新排除目标楼。'))
    plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'font.size':11})
    fig,ax=plt.subplots(figsize=(8,2.7));colors=['#287C8E','#7197BA','#B3C7D8']
    for y,(model,k) in enumerate([('QT',3),('QTSB',3)]):
        rr=cohort_members('current20',model,k);left=0
        for i,r in enumerate(rr):
            ax.barh(y,r['n'],left=left,color=colors[i],height=.55);ax.text(left+r['n']/2,y,str(r['n']),ha='center',va='center',color='white' if i<2 else '#20252B');left+=r['n']
    ax.set_yticks([0,1],['质量＋时间：三组','四项联合：三组']);ax.invert_yaxis();ax.set_xticks([0,5,10,15,20]);ax.set_xlim(0,20)
    ax.set_xlabel('人数；分配比例不是分类有效性的评分')
    for side in ['top','right']:ax.spines[side].set_visible(False)
    fig.tight_layout();chart=OUT/'三组候选人数.png';fig.savefig(chart,dpi=180,bbox_inches='tight');plt.close(fig)
    page('三组例子：人数与含义分开判断',
        {'type':'figure','path':str(chart),'width':6.35,'caption':'图1  延续此前讨论的两个三组例子，未根据本轮稳定结果选择。4／6／10和8／6／6都不是人数配额。'},
        p('质量＋时间三组：组1为4人，平均参考偏差最低；组2为6人，平均操作最快；组3为10人，平均用时较长、参考偏差较高。这里能描述不同表现，但仍需检验这些人换图后是否保持在同一类。'),
        p('四项联合三组：组1为8人，平均参考偏差较低、净改善较多；组2为6人，平均操作较快、修改较少；组3为6人，平均参考偏差及两种scope误判较高、修改较多。组平均不代表每个人都完全符合。'),
        p('8／6／6接近均分并不支持分类更好。三组人数较少也不自动否定分类；它限制的是当前能观察多长的组内人数过程。'))
    for model,k in examples:
        rr=cohort_members('current20',model,k)
        axes=[a for b in model for a in base.BLOCKS[b]]
        axis_names={'quality':'参考偏差','time':'用时','scope_reject':'误拒可标图','scope_accept':'误收不可标图','edit':'修改幅度','benefit':'净改善'}
        page('候选名单｜'+names[model]+f'，{k}组',
            t(['组别／人数','成员'],[[f"组{r['group']}／{r['n']}人",'、'.join('W'+w for w in r['worker_ids'].split('|'))] for r in rr]),
            t(['所用指标']+[f'组{r["group"]}平均' for r in rr],[[axis_names[a]]+[f'{r["axis_means"][a]:+.3f}' for r in rr] for a in axes]),
            p('数值是考虑任务差异后的人员效应均值，零是模型内的相对中心。用时采用log(1+秒数)，不是表中的数值秒；scope不是绝对正确率，偏差也不是人工逐条确认的规则错误数。只在同一行比较组间表现。'),
            p('这份全量候选名单仅用于说明分出了什么人。验证目标楼时会重新分类，不能拿本表直接声称固定这些成员已经通过全部验证。'))
    rows=[]
    for model,k,role,label in named_examples:
        z=rrow(model,k,role,'primary_6rows_3buildings');n=nrow(model,k,role)
        rows.append([f'{names[model]}／{label}',str(n.n),f'{int(z.available)}/100',
                     f'{int(z.both_at_least_2)}/100',f'{z.jaccard_median:.3f}' if pd.notna(z.jaccard_median) else '资料不足'])
    page('具体子类换图片后，人员是否相似',
        p('将楼分成互不重叠的两批，各自分类，重复100次。每个所选测量方向仍要求至少6份记录、3栋楼。按训练资料中的明确行为对应，例如两边各取平均操作最快的一组，再比较共有人员中的名单。'),
        t(['子类','全量人数','可比较次数','两边均≥2人','名单重合程度'],rows),
        p('名单重合程度＝两边共同成员数／至少在一边属于该组的人数。1表示相同，0表示无共同成员；大组随机选人也容易重合，因此另保留相同组大小随机选人的期望和扣除该期望后的数值，不能单凭原始重合比例判断。'),
        p('四项联合包含的不可标scope图只有9张，不能分成两批各至少6张，所以主要求下无法检验。降低到每半3份、2楼只是补充诊断，不能当作主要求已通过。'))
    rows=[]
    for model,k,role,label in named_examples:
        z=rrow(model,k,role,'diagnostic_3rows_2buildings')
        rows.append([f'{names[model]}／{label}',f'{int(z.available)}/100',
                     f'{z.jaccard_median:.3f}' if pd.notna(z.jaccard_median) else '不可算',
                     f'{z.adjusted_jaccard_median:.3f}' if pd.notna(z.adjusted_jaccard_median) else '不可算'])
    page('较宽松的补充检查',t(['子类','可比较次数','名单重合程度','扣除随机重合后'],rows),
         p('本页每半至少3份记录、2栋楼，单独展示。扣除随机重合后的1表示完全一致，0附近表示接近同样组大小随机选人的水平，负数表示低于这个水平；不是准确率。'),
         p('同一套三分类中，有的组可以较容易再次识别，有的组会明显换人。因此不能只用整套分类的一个分数，代替对具体子类的检查。'),
         p('指标与组数试过很多种；这里的例子延续前面讨论，不能仅根据某个最高数值命名最终人群类型。全部子类的结果均保留。'))
    for h in [8,10,13]:
        rows=[]
        for model,k,role,label in named_examples:
            z=srow(model,k,role,h);n=nrow(model,k,role)
            rows.append([f'{names[model]}／{label}',str(n.n),
                '人数不足' if z is None else f'{int(z.confirmed_images)}/{int(z.images)}',
                '—' if z is None else f'{int(z.baseline_confirmed_images)}/{int(z.images)}',
                '—' if z is None else f'{z.reference_error:.2f}／{z.baseline_reference_error:.2f}'])
        page(f'具体子类稳定性｜每次{h}人',
             p(f'后续20人范围。检查从第{h-5}人开始，持续观察到第{h}人；每张图200个顺序，至少80%明确稳定才计入达标。只列有可评分参考的图。'),
             t(['子类','全量人数','该类达标/可比较图','随机达标/同图','参考偏差：该类/随机'],rows),
             p('每行内部使用同样图片、同样人数；不要求其他子类够人数。不同列举子类的图片集合可能不同，不可直接按达标数量排优劣。人数不足不等于不能收敛。'),
             p('具名子类按训练资料的行为含义对应，不靠组号硬连。全量人数与每张目标图可用人数可能不同。某组同时是参考偏差最低组和净改善最高组时，它们是同一组的两个描述，不是独立发现。'),
             p('稳定允许单簇或多簇；点数不同必分簇，受支持簇至少2人。稳定多簇至少需4人才能在起点形成，因此8人终点下只允许第2—3人起点的检验，不能确认多簇稳定起点。后面的10人及更长观察才有机会检验。'))
    paired=pd.read_csv(OUT/'named_paired_curves.csv.gz')
    multi=paired[paired.config.eq('q95')&paired.reference_allowed&paired.stable_multi.ge(160)]
    multi.to_csv(OUT/'confirmed_multi_examples.csv.gz',index=False)
    examples_multi=multi.drop_duplicates('image_id')
    page('稳定形成多个簇：已保留并实际检验',
         p(f'q=.95下，在有可评分参考的图片中，{multi.image_id.nunique()}张图出现某个人员子集至少80%的顺序处于稳定多簇阶段。相同人员子集被多种描述引用，不算多次独立发现。'),
         t(['图片','范围／分类指标','观察终点／候选起点','稳定多簇顺序数'],[
             [r.image_id.split('_')[-1][:8],('全部' if r.cohort=='all26' else '后续')+'／'+names[r.model],f'{r.horizon}人／{r.k}人',f'{r.stable_multi}/200'] for r in examples_multi.itertuples()]),
         p('每图仅列保存顺序中的第一个符合条件的例子，全部记录另存；这些例子用于说明确实允许并检测到了稳定多簇，不能用来反向决定分类办法或证明某个人群类型普遍收敛。'),
         p('这些结果来自较长的可用人数观察。不能把只有8人的子类回放没有确认多簇，解释成该类必然只有一种标法；从第2或第3人开始检查时，本来就不足以形成两个各有2人支持的簇。'))
    rows=[]
    for cohort,label in [('all26','全部26人'),('current20','后续20人')]:
        for model in order:
            candidate=int(counts.loc[counts.cohort.eq(cohort)&counts.model.eq(model),'groups'].sum())
            z=coverage[coverage.cohort.eq(cohort)&coverage.model.eq(model)]
            tested=z[z.status.eq('can_replay')][['groups','group']].drop_duplicates()
            rows.append([label,names[model],str(candidate),str(len(tested))])
    page('覆盖：没有只保留表现好的子类',
         t(['范围','指标组合','各组数下的候选组总数','至少一图够回放人数'],rows[:15]),
         p('这里统计的是分类配置下的候选组，不是独立发现的人群类型。一个人员子集可在不同指标或组数下重复出现；不能把这些次数当作独立证据。'))
    page('覆盖：后续20人的全部组合',t(['范围','指标组合','候选组总数','至少一图够回放人数'],rows[15:]),
         p(f'本轮回放涉及{coverage.image_id.nunique()}张至少7份无辅助记录的图。实际重复的图内人员子集只有{qa["unique_image_pools"]}个，已共享计算；不足7人的具体子类均保留为人数不足。'),
         p('主展示之外，所有子类都保存q=.95及OSPA30≤6的稳定性结果；分别保留全部图、可评分参考图及明确裁定可标图。所有组数的结果可复核，未按较早稳定挑选类别。'))
    page('当前结论与新增人员如何使用',
         p('已经完成的工作是：15种指标组合与不同组数的分类、逐子类名单重复性、各子类真实标注回放、同图同人数随机对照，以及代表标注的参考偏差。不是仅检查人数够不够，也没有预设必须回到质量中位数二分。'),
         p('分类解释和收敛仍需分开。时间组有较强的名单重复证据；某些联合分类可描述不同质量、速度或修改表现，但一张全量名单不能证明这种类型在新人员中仍成立。scope相关分类尤其受到可用明确裁定图片数量限制。'),
         p('具体子类在部分图片上进入有限观察内的稳定阶段，不等于它对所有图片都稳定，更不等于结果正确。代表偏差需要一起看。未知状态给出的上下界不是置信区间；本轮没有对大量方案选择作最终统计确认。'),
         p('下一批人员应先独立完成校准图，再按事先固定的行为判据归类，并在另一批图片上验证。允许某些人员暂未归类；不为凑人数移动人员。若某个子类有明确含义但人数不够，可有针对性地补充同类证据。'),
         p('每人独立标注一次，后处理再组合A、B、AAB等比例；同一人不能重复冒充多人。具体子类的单独验证优先，不要求所有类型同时收敛。不修改正式资格、任务分发或原始标注。'))
    payload=dict(preset='standard_business_brief; memo_masthead; Chinese font override Microsoft YaHei',header='人员分类 · 具体子类稳定性',
                 date='2026-09-10',filename='人员分类与具体子类稳定性_更新报告.docx',pages=pages)
    assert '导师' not in json.dumps(payload,ensure_ascii=False)
    (OUT/'document_content.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf8')
    md=[]
    for page_data in pages:
        md += ['# '+page_data['title'],'']
        for b in page_data['blocks']:
            if b['type']=='p':md += [b['text'],'']
            elif b['type']=='figure':md += [f'![{b["caption"]}]({Path(b["path"]).name})','']
            else:
                md += ['| '+' | '.join(b['headers'])+' |','|'+'|'.join(['---']*len(b['headers']))+'|']
                md += ['| '+' | '.join(map(str,row))+' |' for row in b['rows']];md += ['']
    md += ['# 全部结果与复现','',
        '[所有组数的成员与平均表现](../group_count_extension/组数与成员附录.md)。各组数、人数、重复性原表均保留在上一层group_count_extension目录。',
        '`classification_availability.csv`完整列出每张至少7份响应图×全部分类配置，区分训练资料无法形成分类；`coverage.csv.gz`进一步列出能分类时各子类实际不同人员数和不足状态。`pool_members.csv.gz`标识每图唯一人员子集，避免把重复子集当独立证据。',
        '`scenarios.csv.gz`连接具体子类与同图同人数基线；`pool_curves.csv.gz`保留每个唯一子集的固定H与合法起点k，三状态相加为200。`pool_quality.csv.gz`是组内选代表后再与参考比较的分数。',
        '`paired_curves.csv.gz`等不带named前缀的文件按组号留作审计；具名子类使用`named_role_map.csv.gz`按每个所用轴高／低的明确训练特征对应，全部方向均保留。`named_paired_curves.csv.gz`是逐图对照；`named_subtype_summary.csv`先按图再按楼汇总；`named_onsets.csv.gz`给出起点。不同覆盖不能直接排名。',
        '主探索输入来自上一轮已审计的原始响应、参考、日志及成对距离。分类始终排除目标楼。方法按本仓库相似场景标注稳定性分析SOP第9节执行；本次不写入正式方法合同。',
        '复现：`python -m tools.thesis_main.analysis.worker_group_count_exploration_20260910 --subtype-repeatability`及`--named-repeatability`；`python -m tools.thesis_main.analysis.worker_subtype_stages_20260910 replay`；`summarize`；`named`；`report`。']
    (OUT/'README_ZH.md').write_text('\n'.join(md),encoding='utf8')
    print('report ready',len(pages),'sections',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['replay','summarize','named','report']);args=parser.parse_args()
    {'replay':replay,'summarize':summarize,'named':named_summary,'report':report}[args.action]()
