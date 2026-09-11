"""组数不固定为二：沿用四信息块，保留小组，分开检查名单重复性与收敛人数。"""
from pathlib import Path
from functools import lru_cache
from math import comb
import json
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, cut_tree
from tools.thesis_main.analysis import worker_four_block_exploration_20260910 as base

OUT=base.OUT/'group_count_extension'


def partitions(p, model, counts):
    """一次拟合层次树，检查多个组数；单人组如实保留，不丢弃整套分类。"""
    if len(p)<2:return {}
    parts=[]
    for block in model:
        x=p[base.BLOCKS[block]].to_numpy(float)
        if not np.isfinite(x).all() or (x.std(0)<1e-10).any():return {}
        parts.append((x-x.mean(0))/x.std(0)/np.sqrt(x.shape[1]))
    tree=linkage(np.concatenate(parts,axis=1),method='ward')
    allowed=[k for k in counts if 2<=k<len(p)]
    if not allowed:return {}
    raw=cut_tree(tree,n_clusters=allowed)
    first=base.BLOCKS[model[0]][0];answer={}
    for j,k in enumerate(allowed):
        means=p.assign(group=raw[:,j]).groupby('group')[first].mean().sort_values(kind='stable')
        mapping={label:i+1 for i,label in enumerate(means.index)}
        answer[k]=np.array([mapping[label] for label in raw[:,j]])
    return answer


def run():
    OUT.mkdir(exist_ok=True)
    members=pd.read_csv(base.OUT/'members.csv',dtype={'worker_id':str})
    members=members[members.variant.eq('primary')&members.panel.eq('native')&members.model.ne('Q_median2')]
    groups=[];full=[];halves=[];capacity=[];ranges={}
    for (cohort,model),p in members.groupby(['cohort','model']):
        ks=list(range(2,len(p)//2+1));ranges[(cohort,model)]=ks
        for k,labels in partitions(p,model,ks).items():
            sizes=np.bincount(labels)[1:]
            full.append(dict(cohort=cohort,model=model,groups=k,workers=len(p),sizes='|'.join(map(str,sizes)),
                             singleton_groups=int((sizes==1).sum()),min_size=int(sizes.min()),max_size=int(sizes.max())))
            for label,z in p.assign(group=labels).groupby('group'):
                axes=[a for b in model for a in base.BLOCKS[b]]
                groups.append(dict(cohort=cohort,model=model,groups=k,group=int(label),n=len(z),
                    worker_ids='|'.join(sorted(z.worker_id,key=int)),
                    axis_means=z[axes].mean().to_dict(),support='singleton' if len(z)==1 else 'multiple_people'))
            if k==2 and p.status.eq('usable').all():
                assert np.array_equal(labels[:,None]==labels[None,:],p.label.to_numpy()[:,None]==p.label.to_numpy()[None,:])
    for cohort in ['all26','current20']:
        data=pd.read_csv(base.OUT/'axes_primary.csv.gz',dtype={'worker_id':str})
        if cohort=='current20':data=data[data.current20_member]
        buildings=set(data.building_id);cache=base.prepare_axis_cache(data);rng=np.random.default_rng(base.SEED)
        for repeat in range(100):
            left=set(rng.permutation(sorted(buildings))[:len(buildings)//2])
            for support,n,b in [('primary_6rows_3buildings',6,3),('diagnostic_3rows_2buildings',3,2)]:
                a=base.fit_axis_cache(cache,left,n,b);z=base.fit_axis_cache(cache,buildings-left,n,b)
                for combo in base.COMBOS:
                    model=''.join(combo);ks=ranges[(cohort,model)]
                    pa=base.model_profiles(a,combo,False);pz=base.model_profiles(z,combo,False)
                    aa=partitions(pa,model,ks);zz=partitions(pz,model,ks)
                    for k in ks:
                        row=dict(cohort=cohort,model=model,groups=k,repeat=repeat,support=support,
                                 available=False,no_singletons=False,shared_workers=0,all_groups_represented=False,ari=np.nan)
                        if k in aa and k in zz:
                            match=pa[['worker_id']].assign(a=aa[k]).merge(pz[['worker_id']].assign(z=zz[k]),on='worker_id')
                            available=len(match)>=4
                            row.update(available=available,shared_workers=len(match),
                                no_singletons=min(np.bincount(aa[k])[1:])>=2 and min(np.bincount(zz[k])[1:])>=2,
                                all_groups_represented=match.a.nunique()==k and match.z.nunique()==k,
                                ari=base.reuse.adjusted_rand(match.a,match.z) if available else np.nan)
                        halves.append(row)
            if repeat%25==24:print('group count halves',cohort,repeat+1,flush=True)
    # 收敛资料检查：仍用不含目标楼的分类输入，按真实不同人员计数；不伪装成新收敛回放。
    folds=pd.read_csv(base.OUT/'fold_members.csv.gz',dtype={'worker_id':str})
    folds=folds[folds.variant.eq('primary')&folds.panel.eq('native')&folds.model.ne('Q_median2')]
    manual=pd.read_csv(base.OUT/'manual.csv.gz',dtype={'worker_id':str})
    for (cohort,model,building),p in folds.groupby(['cohort','model','heldout_building']):
        assert all(building not in str(s).split('|') for s in p.training_buildings)
        tasks=manual[manual.building_id.eq(building)]
        if cohort=='current20':tasks=tasks[tasks.current20_member]
        for k,labels in partitions(p,model,ranges[(cohort,model)]).items():
            for image,z in tasks.groupby('image_id'):
                present=set(z.worker_id)
                counts=[len(set(p.loc[labels==label,'worker_id'])&present) for label in range(1,k+1)]
                capacity.append(dict(cohort=cohort,model=model,groups=k,building_id=building,image_id=image,
                    counts='|'.join(map(str,counts)),groups_with_7=int(sum(n>=7 for n in counts)),
                    groups_with_8=int(sum(n>=8 for n in counts)),groups_with_13=int(sum(n>=13 for n in counts)),
                    all_groups_with_7=all(n>=7 for n in counts),all_groups_with_8=all(n>=8 for n in counts),
                    reference_allowed=bool(z.reference_allowed.all())))
    pd.DataFrame(full).to_csv(OUT/'group_counts.csv',index=False)
    (OUT/'group_members.json').write_text(json.dumps(groups,ensure_ascii=False,indent=2),encoding='utf8')
    h=pd.DataFrame(halves);h.to_csv(OUT/'half_comparisons.csv.gz',index=False)
    h.groupby(['cohort','model','groups','support']).agg(attempts=('repeat','size'),available=('available','sum'),
        no_singletons=('no_singletons','sum'),all_groups_represented=('all_groups_represented','sum'),
        shared_workers_median=('shared_workers','median'),ari_median=('ari','median')).reset_index().to_csv(OUT/'repeatability.csv',index=False)
    pd.DataFrame(capacity).to_csv(OUT/'convergence_capacity.csv.gz',index=False)
    (OUT/'PLAN_AND_QA.json').write_text(json.dumps(dict(information_combinations=15,cohorts=2,full_configs=len(full),
        group_count_range='2 through floor(eligible workers / 2); singleton outputs preserved, not validated types',
        half_attempt_rows=len(h),capacity_rows=len(capacity),two_group_accepted_partitions_match_previous=True,
        target_building_excluded=True,primary='existing audited primary axes, native eligibility, equal information block weight',
        algorithm='Ward unchanged; variable group count; no balanced-size constraints or retrospective merging',
        caveat='No new convergence replay or quality prediction; capacity is a data sufficiency audit, not convergence evidence',
        formal_protocol_changed=False),ensure_ascii=False,indent=2),encoding='utf8')
    report()


def report():
    from tools.thesis_main.analysis.build_worker_four_block_report_20260910 import NAMES
    names={m:n.replace('scope','规则判断').replace('自动二分','自动分组') for m,n in NAMES.items()}
    d=pd.read_csv(OUT/'group_counts.csv');r=pd.read_csv(OUT/'repeatability.csv')
    c=pd.read_csv(OUT/'convergence_capacity.csv.gz');members=json.loads((OUT/'group_members.json').read_text('utf8'))
    lines=['# 人员分类：放开组数后的补充探索','',
        '## 研究目标与不均分约束','',
        '优先目标是确认至少一个含义清楚、在新图片或新增人员上仍有证据支持的具体人群子类，其标注能进入稳定阶段。不是把全体均分成若干组，也不是要求所有组同时收敛。人数比例本身不是分类质量指标；自然得到接近人数可以保留，但不能把接近均分当作优点，也不能为制造不均衡而人为调整。','',
        '本轮Ward没有各组人数相等的配额，但算法本身仍有偏好，因此人数表不是自然类型已成立的证明。旧方案一按质量中位数切两档确实带有均分倾向，现在仅作为历史对照，不再预设为最终应退回的方案。只用质量粗分仍可探索，但不能把从中间切开当作已经发现两种人群。','',
        '某组很小，或其他人员暂时无法归类，不应使整套分类自动作废。证据不足的人可以保持未定，不能仅因为“剩余”就命名为一种稳定类型。识别人员子类时不能利用待验证图片上的收敛结果反向挑人；历史上筛出的候选仍需独立验证。','',
        '此前固定两组是分析者自行增加的限制，不是用户要求。前一报告只能评价所用算法下的二分方案，不能据此排除更多组，也不能认定复杂指标组合没有价值。','',
        '本次沿用质量、时间、规则判断、半自动行为的15种组合，分别检查后续20人和全部26人。从2组一直检查到可分类人数的一半；例如20人检查2—10组。这个上限用于探索多人子类，不代表最佳组数。自动算法仍可能产生单人组，原样保留并标记。','',
        '人员子类的组数用“组数”表示，标注人数用k表示，两者不要混淆。某个人被分成单独一组，可以提示特殊行为，但一个人不能证明可重复的人群类型。','',
        '这里只改变组数，保留原Ward自动分组算法与各信息块相同权重；没有强行均分，也没有为避免小组而重新合并。更换算法、权重或按单项高低交叉分组仍是不同的问题。','']
    for cohort,label in [('current20','后续20人'),('all26','全部26人')]:
        lines += ['## '+label+'：2—5组分别分了多少人','',
                  '| 指标组合 | 实际可分类人数 | 2组 | 3组 | 4组 | 5组 |','|---|---|---|---|---|---|']
        for model,g in d[d.cohort.eq(cohort)].groupby('model',sort=False):
            vals=[]
            for k in range(2,6):
                z=g[g.groups.eq(k)].iloc[0];vals.append(z.sizes.replace('|','／')+(' *' if z.singleton_groups else ''))
            lines.append('| '+' | '.join([names[model],str(g.workers.iloc[0]),*vals])+' |')
        lines += ['','* 表示包含单人组，人数照列，不删除其他组，也不把单人当成已验证的类型。完整2组至上限的人数及名单见后文。','']
    lines += ['## 多分组后，名单是否还能重复出现','',
        '将楼分成互不重叠的两批，分别分类，重复100次。主要检查仍要求每个所选方向至少6份记录、3栋楼。另保留3份、2栋楼的补充检查；两者不能混称。单人组不再使整次比较被删除，但单独统计两边均没有单人组的次数。','',
        '一致程度1代表相同分组，0附近代表与随机对应接近。只在共有人员上计算，不把不可计算记为0；可比次数、共有人员数及所有组是否在共有人员中出现都保留。高组数的一致程度不能单独用来选最佳组数。','',
        '| 后续20人：指标 | 组数 | 可以比较/100 | 两边均无单人组/100 | 一致程度中位数 |','|---|---|---|---|---|']
    for row in r[r.cohort.eq('current20')&r.support.eq('primary_6rows_3buildings')&r.groups.le(5)].itertuples():
        lines.append(f'| {names[row.model]} | {row.groups} | {row.available} | {row.no_singletons} | '+(f'{row.ari_median:.3f}' if pd.notna(row.ari_median) else '资料不足')+' |')
    lines += ['','## 更多组与收敛研究：分类成立和人数够用分开判断','',
        '要沿用“至少继续观察5人”的判据，从第2人检查稳定至少需7名同类人员；从第8人检查至少需13人。分出3组或4组可以是合理的行为分类，即使眼下某组只有3—5人；这时是收敛证据不足，不是自动证明分类错误。这里的7人或13人是观察长度要求，不是人员分类配额。','',
        '首先看是否存在某个可解释子类有足够人数进一步检验；“所有组都有7人”仅说明能否同时比较全部子类，不作为方案能否继续研究的门槛。当前表格只是资料充足性检查，尚不能确认具体哪一类收敛。','',
        '下面使用不含目标楼的资料重新分组，再核对该楼每张图实际有多少名该类人员。表中列的是图片数，且只计有可评分参考的图片；它不是稳定图片数，也没有运行新的收敛回放。组号只表示各次分类中按首项指标排序，跨图不保证同一份名单。','',
        '| 后续20人：指标 | 组数 | 至少一组有7人的图 | 所有组都有7人的图 |','|---|---|---|---|']
    for (model,k),g in c[c.cohort.eq('current20')&c.groups.le(5)&c.reference_allowed].groupby(['model','groups']):
        lines.append(f'| {names[model]} | {k} | {int(g.groups_with_7.gt(0).sum())} | {int(g.all_groups_with_7.sum())} |')
    lines += ['','## 全部组数、成员与组平均表现','',
        '以下数值均为考虑任务差异后的人员效应均值。质量是参考偏差，时间为log(1+有效秒数)，规则是两种scope误判，半自动为修改幅度与净改善；不把这些数值当成绝对正确率或秒数。仅在同一组合内比较各组，不能把不同指标的数值大小直接比较。','']
    axisnames={'quality':'参考偏差','time':'用时','scope_reject':'误拒可标图','scope_accept':'误收不可标图','edit':'修改幅度','benefit':'净改善'}
    for cohort,label in [('current20','后续20人'),('all26','全部26人')]:
        for model in sorted(set(d.model)):
            lines += ['### '+label+'／'+names[model],'']
            for row in [z for z in members if z['cohort']==cohort and z['model']==model]:
                axes='，'.join(f'{axisnames[a]} {v:+.3f}' for a,v in row['axis_means'].items())
                lines += [f"{row['groups']}组方案的组{row['group']}：{row['n']}人；"+'、'.join('W'+w for w in row['worker_ids'].split('|'))+'。组平均：'+axes+'。','']
    lines += ['## 方法边界与文件','',
        '这是历史探索的组数扩展，没有改变原始标注、scope裁定、正式资格或协议。沿用上一级已审计数据。本次尚未重做各组数的跨图质量预测和标法收敛曲线，不能将原两组回放结果贴到三组或四组名单上。','',
        '`group_counts.csv`每行为人员范围×指标组合×组数；`group_members.json`每行为其中一个组；`half_comparisons.csv.gz`每行为一次拆分与支持要求；`repeatability.csv`汇总100次；`convergence_capacity.csv.gz`每行为目标图及不含目标楼的分组结果，统计不同人员人数。','',
        '复现：`python -m tools.thesis_main.analysis.worker_group_count_exploration_20260910`。更多组不能只看是否分得出来，还要看可解释性、名单重复性、每组样本支持，以及新增同类人员后的稳定性。']
    start=lines.index('## 全部组数、成员与组平均表现');end=lines.index('## 方法边界与文件')
    (OUT/'组数与成员附录.md').write_text('\n'.join(lines[start:end]),encoding='utf8')
    lines=lines[:start]+['## 完整成员附录','','[查看全部组数、成员名单与组平均表现](组数与成员附录.md)','']+lines[end:]
    (OUT/'README_ZH.md').write_text('\n'.join(lines),encoding='utf8')
    print('finished',len(d),'configurations',flush=True)


@lru_cache(maxsize=None)
def expected_jaccard(n,a,b):
    """固定组大小，独立均匀选人时的精确Jaccard期望；不把大组重合自动视为复现。"""
    if a+b==0:return np.nan
    return sum(comb(a,x)*comb(n-a,b-x)/comb(n,b)*x/(a+b-x)
               for x in range(max(0,a+b-n),min(a,b)+1))


def subtype_repeatability():
    limits=pd.read_csv(OUT/'group_counts.csv').groupby(['cohort','model'])['groups'].max().to_dict();rows=[]
    for cohort in ['all26','current20']:
        data=pd.read_csv(base.OUT/'axes_primary.csv.gz',dtype={'worker_id':str})
        if cohort=='current20':data=data[data.current20_member]
        buildings=set(data.building_id);cache=base.prepare_axis_cache(data);rng=np.random.default_rng(base.SEED)
        for repeat in range(100):
            left=set(rng.permutation(sorted(buildings))[:len(buildings)//2])
            for support,n,b in [('primary_6rows_3buildings',6,3),('diagnostic_3rows_2buildings',3,2)]:
                aa=base.fit_axis_cache(cache,left,n,b);bb=base.fit_axis_cache(cache,buildings-left,n,b)
                for combo in base.COMBOS:
                    model=''.join(combo);ks=list(range(2,limits[(cohort,model)]+1))
                    a=base.model_profiles(aa,combo,False);z=base.model_profiles(bb,combo,False)
                    la=partitions(a,model,ks);lz=partitions(z,model,ks)
                    for k in ks:
                        match=None
                        if k in la and k in lz:match=a[['worker_id']].assign(a=la[k]).merge(z[['worker_id']].assign(b=lz[k]),on='worker_id')
                        for label in range(1,k+1):
                            row=dict(cohort=cohort,model=model,groups=k,group=label,support=support,repeat=repeat,
                                available=False,both_at_least_2=False,left_n=0,right_n=0,shared_workers=0,
                                jaccard=np.nan,chance_jaccard=np.nan,adjusted_jaccard=np.nan)
                            if match is not None and len(match)>=4:
                                x=set(match[match.a.eq(label)].worker_id);y=set(match[match.b.eq(label)].worker_id)
                                row.update(shared_workers=len(match),left_n=len(x),right_n=len(y))
                                if x|y:
                                    observed=len(x&y)/len(x|y);chance=expected_jaccard(len(match),len(x),len(y))
                                    row.update(available=True,both_at_least_2=len(x)>=2 and len(y)>=2,
                                        jaccard=observed,chance_jaccard=chance,
                                        adjusted_jaccard=(observed-chance)/(1-chance) if chance<1-1e-12 else np.nan)
                            rows.append(row)
            if repeat%25==24:print('subtype repeatability',cohort,repeat+1,flush=True)
    d=pd.DataFrame(rows);d.to_csv(OUT/'subtype_repeatability_attempts.csv.gz',index=False)
    result=d.groupby(['cohort','model','groups','group','support']).agg(attempts=('repeat','size'),
        available=('available','sum'),both_at_least_2=('both_at_least_2','sum'),
        jaccard_median=('jaccard','median'),chance_jaccard_median=('chance_jaccard','median'),
        adjusted_jaccard_median=('adjusted_jaccard','median')).reset_index()
    result.to_csv(OUT/'subtype_repeatability.csv',index=False)
    print('subtype repeatability complete',len(d),flush=True)


def named_groups(p,model,labels):
    """按训练均值的高/低给出可跨分割对应的含义；并列保留None，绝不看目标结果。"""
    means=p.assign(group=labels).groupby('group')[[a for b in model for a in base.BLOCKS[b]]].mean()
    roles={}
    for axis in means:
        for direction in ['low','high']:
            extreme=means[axis].min() if direction=='low' else means[axis].max()
            matches=means.index[np.isclose(means[axis],extreme,atol=1e-10,rtol=1e-8)]
            roles[axis+'_'+direction]=int(matches[0]) if len(matches)==1 else None
    return roles


def named_repeatability():
    limits=pd.read_csv(OUT/'group_counts.csv').groupby(['cohort','model'])['groups'].max().to_dict();rows=[]
    for cohort in ['all26','current20']:
        data=pd.read_csv(base.OUT/'axes_primary.csv.gz',dtype={'worker_id':str})
        if cohort=='current20':data=data[data.current20_member]
        buildings=set(data.building_id);cache=base.prepare_axis_cache(data);rng=np.random.default_rng(base.SEED)
        for repeat in range(100):
            left=set(rng.permutation(sorted(buildings))[:len(buildings)//2])
            for support,n,b in [('primary_6rows_3buildings',6,3),('diagnostic_3rows_2buildings',3,2)]:
                aa=base.fit_axis_cache(cache,left,n,b);bb=base.fit_axis_cache(cache,buildings-left,n,b)
                for combo in base.COMBOS:
                    model=''.join(combo);ks=range(2,limits[(cohort,model)]+1)
                    a=base.model_profiles(aa,combo,False);z=base.model_profiles(bb,combo,False)
                    la=partitions(a,model,ks);lz=partitions(z,model,ks)
                    for k in ks:
                        ra=named_groups(a,model,la[k]) if k in la else {}
                        rz=named_groups(z,model,lz[k]) if k in lz else {}
                        common=set(a.worker_id)&set(z.worker_id)
                        for role in [axis+'_'+direction for b in combo for axis in base.BLOCKS[b] for direction in ['low','high']]:
                            row=dict(cohort=cohort,model=model,groups=k,role=role,support=support,repeat=repeat,
                                available=False,both_at_least_2=False,jaccard=np.nan,chance_jaccard=np.nan,adjusted_jaccard=np.nan)
                            if ra.get(role) is not None and rz.get(role) is not None and len(common)>=4:
                                x=set(a.loc[la[k]==ra[role],'worker_id'])&common;y=set(z.loc[lz[k]==rz[role],'worker_id'])&common
                                if x|y:
                                    obs=len(x&y)/len(x|y);chance=expected_jaccard(len(common),len(x),len(y))
                                    row.update(available=True,both_at_least_2=len(x)>=2 and len(y)>=2,jaccard=obs,chance_jaccard=chance,
                                        adjusted_jaccard=(obs-chance)/(1-chance) if chance<1-1e-12 else np.nan)
                            rows.append(row)
            if repeat%25==24:print('named subtype repeatability',cohort,repeat+1,flush=True)
    d=pd.DataFrame(rows);d.to_csv(OUT/'named_repeatability_attempts.csv.gz',index=False)
    d.groupby(['cohort','model','groups','role','support']).agg(attempts=('repeat','size'),available=('available','sum'),
        both_at_least_2=('both_at_least_2','sum'),jaccard_median=('jaccard','median'),
        adjusted_jaccard_median=('adjusted_jaccard','median')).reset_index().to_csv(OUT/'named_repeatability.csv',index=False)
    print('named repeatability finished',len(d),flush=True)


if __name__=='__main__':
    import sys
    named_repeatability() if '--named-repeatability' in sys.argv else subtype_repeatability() if '--subtype-repeatability' in sys.argv else run()
