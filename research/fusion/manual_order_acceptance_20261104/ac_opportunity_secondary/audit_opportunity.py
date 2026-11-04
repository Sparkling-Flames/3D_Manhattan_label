"""Audit residual opportunities in two method and three funnel Q reversals.

Reads frozen, complete registered cohorts and existing assisted outputs only.
No fusion, scoring, team selection, order inference or classification is run.
Run from any working directory with Python, numpy and pandas installed.
"""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
AC = HERE.parent / 'ac'
PEER = HERE.parent / 'ac_peer'
OLD = ROOT / 'research/fusion/manual_order_impact_20261104/ac'
ENDPOINTS = ROOT / 'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv'
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
CHECKS, INPUTS, RESIDUALS, ENDPOINT_ROWS, CONDITIONS, POOLS, ARMS = [], {}, [], [], [], [], []
METHODS = ['OPPSTRUCT_K3', 'TARGET_DSTRUCT_K2', 'V21_DSTRUCT_RAW3_K3']


def read(path, **kwargs):
    path = Path(path)
    INPUTS[str(path.relative_to(ROOT))] = dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return pd.read_csv(path, float_precision='round_trip', low_memory=False, **kwargs)


def load_json(path):
    path=Path(path);data=path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))]=dict(path=str(path.relative_to(ROOT)),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    return json.loads(data.decode('utf-8-sig'))


def save(frame, name):
    data = frame.to_csv(index=False).encode('utf-8-sig')
    (HERE/name).write_bytes(gzip.compress(data,mtime=0) if name.endswith('.gz') else data)


def clean(x):
    if isinstance(x, dict): return {k:clean(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [clean(v) for v in x]
    if isinstance(x, (np.integer,np.bool_)): return x.item()
    if isinstance(x, (float,np.floating)): return float(x) if np.isfinite(x) else None
    return x


def check(name, passed, **details):
    CHECKS.append(dict(check=name,passed=bool(passed),**clean(details)))


def same_numbers(name,a,b):
    a,b=np.asarray(a,float),np.asarray(b,float)
    valid=np.isfinite(a)&np.isfinite(b)
    check(name,a.shape==b.shape and np.allclose(a,b,atol=1e-8,rtol=1e-10,equal_nan=True),
          cells=int(a.size),maximum_absolute_difference=float(np.max(abs(a[valid]-b[valid]))) if valid.any() else 0.)


def truth(s): return s.fillna(False).astype(str).str.lower().isin(['true','1','1.0'])


def patch(old,new,keys):
    old=old.set_index(keys).sort_index();new=new.set_index(keys).sort_index()
    assert old.index.is_unique and new.index.is_unique
    hit=old.index.intersection(new.index)
    old.loc[hit,new.columns.intersection(old.columns)]=new.loc[hit,new.columns.intersection(old.columns)]
    return old.reset_index()


RAW_COLUMNS=['event_id','physical_pair_id','pool_id','image','building','method','condition','layer','scope',
    'n','m','D_n','X_workers','Z_workers','source_class','target_class','source_role_rank','target_role_rank',
    'equal_team_size','pure_cross_class_blocks','reference_id','reference_version','B8L2_CA']
RAW_COLUMNS += [a+'_'+f for a in ['A','C'] for f in ['team_key','workers','B8L2','nodes','score_status',
    'order_status','connection_available','insufficient_nodes','geometry_status','geometry_reason']]
RAW = {}


def raw_pool(pid):
    if pid in RAW: return RAW[pid]
    options=[AC/'source_cache/original_metric_shards'/(pid+'.csv.gz'),
             HERE/'source_cache'/(pid+'.csv.gz'),PEER/'source_cache'/(pid+'.csv.gz')]
    original_path=next(p for p in options if p.exists())
    original=read(original_path,usecols=lambda c:c in RAW_COLUMNS)
    newpath=OLD/'metric_shards'/(pid+'.csv.gz')
    assisted=read(newpath,usecols=lambda c:c in RAW_COLUMNS) if newpath.exists() else original.copy()
    check('raw_event_membership/'+pid,original.event_id.is_unique and assisted.event_id.is_unique
          and set(original.event_id)==set(assisted.event_id))
    original=original.set_index('event_id');assisted=assisted.set_index('event_id').loc[original.index]
    for arm in ['A','C']:
        check('raw_frozen_team/'+pid+'/'+arm,original[arm+'_team_key'].equals(assisted[arm+'_team_key']))
        good=original[arm+'_B8L2'].notna()
        same_numbers('original_scored_endpoint_unchanged/'+pid+'/'+arm,
                     original.loc[good,arm+'_B8L2'],assisted.loc[good,arm+'_B8L2'])
    RAW[pid]=(original.reset_index(),assisted.reset_index())
    return RAW[pid]


def residual_evidence(row,old,new,confirmed):
    """Save every remaining missing event and each of its missing arms."""
    old=old.set_index('event_id');new=new[new.B8L2_CA.isna()].copy()
    for r in new.to_dict('records'):
        previous=old.loc[r['event_id']]
        record=dict(reversal_id=row['reversal_id'],family=row['family'],**r)
        record.update(automatic_A_B8L2=previous.A_B8L2,automatic_C_B8L2=previous.C_B8L2,
                      automatic_B8L2_CA=previous.B8L2_CA)
        for arm in ['A','C']:
            record[arm+'_in_confirmed57']=r[arm+'_team_key'] in confirmed.index
        RESIDUALS.append(record)
        for arm,other in [('A','C'),('C','A')]:
            if pd.notna(r[arm+'_B8L2']):continue
            status=r[arm+'_score_status'];nodes=r[arm+'_nodes'];team=r[arm+'_team_key']
            in57=team in confirmed.index
            missed=in57 and pd.notna(confirmed.loc[team,'B8L2'])
            category=('below_four_fixed_node_ineligible' if status=='below_four' or (pd.notna(nodes) and nodes<4)
                      else 'no_connection_outside_confirmed_order' if status=='no_connection' and not in57
                      else 'invalid_geometry_outside_confirmed_order' if status=='invalid_floor' and not in57
                      else 'confirmed_but_still_unscorable' if in57 else 'other_unresolved')
            ENDPOINT_ROWS.append(dict(reversal_id=row['reversal_id'],family=row['family'],event_id=r['event_id'],
                physical_pair_id=r['physical_pair_id'],pool_id=r['pool_id'],image=r['image'],building=r['building'],
                method=r['method'],n=r['n'],m=r['m'],arm=arm,team_key=team,
                score_status=status,nodes=nodes,order_status=r.get(arm+'_order_status'),
                connection_available=r.get(arm+'_connection_available'),category=category,
                in_confirmed57=in57,confirmed_score_missing_from_consumer=missed,
                counterpart_team_key=r[other+'_team_key'],counterpart_in_confirmed57=r[other+'_team_key'] in confirmed.index,
                counterpart_Q=r[other+'_B8L2'],automatic_Q=previous[arm+'_B8L2'],assisted_Q=r[arm+'_B8L2'],
                members=r.get(arm+'_workers'),reference_id=r['reference_id'],reference_version=r['reference_version']))
    return new


def complete_condition(record):
    e=pd.DataFrame([r for r in ENDPOINT_ROWS if r['reversal_id']==record['reversal_id']])
    events=pd.DataFrame([r for r in RESIDUALS if r['reversal_id']==record['reversal_id']])
    unique=e.drop_duplicates('team_key')
    record.update(residual_events=events.event_id.nunique(),residual_endpoint_occurrences=len(e),
        residual_distinct_endpoints=len(unique),residual_endpoint_in_confirmed57=int(unique.in_confirmed57.sum()),
        confirmed_score_missing_from_consumer=int(e.confirmed_score_missing_from_consumer.sum()),
        residual_events_with_counterpart_in_confirmed57=e.loc[e.counterpart_in_confirmed57,'event_id'].nunique(),
        residual_no_connection_endpoints=int(unique.score_status.eq('no_connection').sum()),
        residual_below_four_endpoints=int(unique.category.eq('below_four_fixed_node_ineligible').sum()),
        residual_invalid_floor_endpoints=int(unique.score_status.eq('invalid_floor').sum()),
        no_connection_endpoints_with_confirmed_counterpart=e.loc[e.score_status.eq('no_connection')&e.counterpart_in_confirmed57,'team_key'].nunique(),
        audit_completed=True,confirmed_order_propagation_complete=not e.confirmed_score_missing_from_consumer.any(),
        all_registered_events_Q_evaluable=False,
        all_registered_opportunities_covered=bool(unique.category.eq('below_four_fixed_node_ineligible').all()),
        opportunity_contract='Every residual endpoint is either given its confirmed order or documented ineligible for fixed-node order repair; unreviewed no_connection/invalid_floor are not counted as covered.')
    check('complete_remaining_event_inventory/'+record['reversal_id'],record['registered_events']-record['assisted_valid_events']==record['residual_events'])
    check('no_confirmed_endpoint_propagation_omission/'+record['reversal_id'],record['confirmed_score_missing_from_consumer']==0)
    CONDITIONS.append(record)


def method_audit(catalog,confirmed):
    d0=read(HERE/'inputs/METHOD_N28_M7_ALL_REGISTERED_DIRECTION_ROWS.csv.gz',dtype={'n_condition':str,'m_condition':str})
    links=read(HERE/'inputs/METHOD_N28_M7_NEUTRAL_A_DESIGN_LINKS.csv.gz')
    keys=['analysis_view','scope','condition','layer','method','role_direction','n_condition','m_condition','pool_id','image','building']
    updates=read(OLD/'AFFECTED_POOLS_ASSISTED.csv.gz',usecols=d0.columns.tolist(),dtype={'n_condition':str,'m_condition':str})
    d1=patch(d0,updates,keys)
    registered=links.drop_duplicates('event_id').groupby(['pool_id','method']).event_id.size()
    expected=d0.groupby(['pool_id','method']).registered_pairs.sum()
    check('method_complete_registration_link_membership',set(registered.index)==set(expected.index))
    same_numbers('method_complete_registration_counts',registered.reindex(expected.index),expected)
    needed=set(d0.loc[d0.registered_pairs>d0.B8L2_CA__valid_pairs,'pool_id'])
    raws=[[],[]]
    for pid in sorted(needed):
        ids=set(links.loc[links.pool_id.eq(pid),'event_id'])
        for side,frame in enumerate(raw_pool(pid)):
            selected=frame[frame.event_id.isin(ids)].copy()
            selected['role_direction']=selected.source_role_rank.astype(int).astype(str)+'->'+selected.target_role_rank.astype(int).astype(str)
            raws[side].append(selected)
    raws=[pd.concat(x,ignore_index=True) for x in raws]
    for side,(raw,expected) in enumerate(zip(raws,[d0,d1])):
        g=raw.groupby(['pool_id','method','role_direction']).agg(registered_pairs=('event_id','nunique'),
            valid_pairs=('B8L2_CA','count'),mean=('B8L2_CA','mean'),mean_absolute=('B8L2_CA',lambda s:s.abs().mean()))
        e=expected[expected.pool_id.isin(needed)].set_index(['pool_id','method','role_direction']).sort_index()
        check('partial_pool_event_membership/'+str(side),set(g.index)==set(e.index))
        same_numbers('partial_pool_complete_event_counts_and_values/'+str(side),
            g.reindex(e.index)[['registered_pairs','valid_pairs','mean','mean_absolute']].to_numpy(),
            e[['registered_pairs','B8L2_CA__valid_pairs','B8L2_CA__mean','B8L2_CA__mean_absolute']].to_numpy())
    for row in catalog[catalog.family.eq('method_comparison')].to_dict('records'):
        left,right=row['method_left'],row['method_right']
        common=set(d0.loc[d0.method.eq(left),'pool_id'])&set(d0.loc[d0.method.eq(right),'pool_id'])
        frames=[d[d.pool_id.isin(common)&d.method.isin([left,right])].copy() for d in [d0,d1]]
        values=[]
        for side,d in enumerate(frames):
            method_mean=d.groupby(['pool_id','method']).B8L2_CA__mean_absolute.mean().unstack('method')
            delta=method_mean[right]-method_mean[left]
            values.append(delta)
            for pid,v in delta.items():
                POOLS.append(dict(reversal_id=row['reversal_id'],family=row['family'],version=['automatic','assisted'][side],
                                  pool_id=pid,left_method=left,right_method=right,left_value=method_mean.loc[pid,left],
                                  right_value=method_mean.loc[pid,right],effect=v))
            for method,g in d.groupby('method'):
                ARMS.append(dict(reversal_id=row['reversal_id'],version=['automatic','assisted'][side],method=method,
                    registered_pools=g.pool_id.nunique(),registered_directions=len(g),registered_events=int(g.registered_pairs.sum()),
                    valid_events=int(g.B8L2_CA__valid_pairs.sum()),residual_events=int((g.registered_pairs-g.B8L2_CA__valid_pairs).sum())))
        same_numbers('method_summary_direction/'+row['reversal_id'],[values[0].mean(),values[1].mean()],[row['old_effect'],row['expanded_effect']])
        selected=[r[r.pool_id.isin(common)&r.method.isin([left,right])] for r in raws]
        residual_evidence(row,*selected,confirmed)
        complete_condition(dict(reversal_id=row['reversal_id'],family=row['family'],scope=row['scope'],
            method=right+' minus '+left,n=28,m=7,role_direction='own available class directions, equally weighted',
            registered_pools=len(common),automatic_valid_pools=int(values[0].notna().sum()),assisted_valid_pools=int(values[1].notna().sum()),
            registered_events=int(frames[0].registered_pairs.sum()),automatic_valid_events=int(frames[0].B8L2_CA__valid_pairs.sum()),
            assisted_valid_events=int(frames[1].B8L2_CA__valid_pairs.sum()),automatic_effect=values[0].mean(),assisted_effect=values[1].mean(),
            complete_registered_effect_direction='not established; retained contrast uses currently evaluable events in each method/direction',
            judgment='尚不能判断',judgment_scope='full registered-event contrast after equal opportunity; current evaluable-support reversal remains valid'))
    save(pd.concat([d0.assign(connection_version='automatic'),d1.assign(connection_version='assisted')]),'METHOD_COMPLETE_DIRECTION_SUPPORT.csv.gz')


def funnel_audit(catalog,confirmed):
    f0=read(AC/'source_cache/POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz')
    fp=read(OLD/'funnel/POOL_DIRECTION_N_M_ASSISTED_PATCH.csv.gz')
    keys=['pool_id','method','n','m','source_class','target_class','metric']
    f1=patch(f0,fp,keys)
    for row in catalog[catalog.family.eq('funnel')].to_dict('records'):
        frames=[]
        for f in [f0,f1]:
            d=f[f.method.eq(row['method'])&f.scope.eq(row['scope'])&f.n.eq(row['n'])&f.m.eq(row['m'])&f.metric.eq('B8L2')]
            if row['role_direction']!='ALL_CANONICAL_DIRECTIONS':d=d[d.role_direction.eq(row['role_direction'])]
            frames.append(d.copy())
        for side,d in enumerate(frames):
            value=d.groupby('pool_id').mean_change.mean()
            same_numbers('funnel_effect/'+row['reversal_id']+'/'+str(side),[value.mean()],[row['old_effect'] if side==0 else row['expanded_effect']])
            for pid,v in value.items():
                POOLS.append(dict(reversal_id=row['reversal_id'],family=row['family'],version=['automatic','assisted'][side],pool_id=pid,effect=v))
        needed=set(frames[1].loc[frames[1].registered_events>frames[1].valid_events,'pool_id'])
        selected=[[],[]]
        for pid in sorted(needed):
            for side,raw in enumerate(raw_pool(pid)):
                d=raw[raw.method.eq(row['method'])&raw.scope.eq(row['scope'])&raw.n.eq(row['n'])&raw.m.eq(row['m'])
                      &raw.condition.eq('manual')&raw.layer.eq('ordinary_manual')&truth(raw.equal_team_size)&truth(raw.pure_cross_class_blocks)]
                if row['role_direction']!='ALL_CANONICAL_DIRECTIONS':
                    sr,tr=[int(v.split('/')[0]) for v in row['role_direction'].split('->')]
                    d=d[d.source_role_rank.eq(sr)&d.target_role_rank.eq(tr)]
                selected[side].append(d)
        selected=[pd.concat(d,ignore_index=True) for d in selected]
        for side,d in enumerate(selected):
            k=['pool_id','source_class','target_class']
            blocks=d.groupby(k+['X_workers','Z_workers'],dropna=False).B8L2_CA.mean()
            got=blocks.groupby(k).mean();cnt=d.groupby(k).B8L2_CA.count();reg=d.groupby(k).event_id.nunique()
            expected=frames[side][frames[side].pool_id.isin(needed)].set_index(k)
            check('funnel_complete_missing_pool_membership/'+row['reversal_id']+'/'+str(side),set(got.index)==set(expected.index))
            same_numbers('funnel_missing_pool_counts_and_XZ_weights/'+row['reversal_id']+'/'+str(side),
                np.column_stack([reg.reindex(expected.index),cnt.reindex(expected.index),got.reindex(expected.index)]),
                expected[['registered_events','valid_events','mean_change']].to_numpy())
        residual_evidence(row,*selected,confirmed)
        complete_condition(dict(reversal_id=row['reversal_id'],family=row['family'],scope=row['scope'],method=row['method'],
            n=int(row['n']),m=int(row['m']),role_direction=row['role_direction'],registered_pools=frames[0].pool_id.nunique(),
            automatic_valid_pools=int(frames[0].groupby('pool_id').mean_change.mean().notna().sum()),
            assisted_valid_pools=int(frames[1].groupby('pool_id').mean_change.mean().notna().sum()),
            registered_events=int(frames[0].registered_events.sum()),automatic_valid_events=int(frames[0].valid_events.sum()),
            assisted_valid_events=int(frames[1].valid_events.sum()),automatic_effect=row['old_effect'],assisted_effect=row['expanded_effect'],
            judgment='条件变化',judgment_scope='current evaluable-support effect retained; residual order opportunity and structural ineligibility separated',
            complete_registered_effect_direction='see peer bound for RAW3; below-four case remains structurally unscorable under fixed nodes'))


def make_report():
    rows=[]
    for r in CONDITIONS:
        label=('RAW3−OPP' if r['reversal_id']=='35e8a9d496cb6656' else 'RAW3−TARGET_K2' if r['family']=='method_comparison'
               else r['method']+' '+r['role_direction'])
        rows.append(f"| {label} | {r['n']}/{r['m']} | {r['registered_pools']} | {r['automatic_valid_pools']}→{r['assisted_valid_pools']} | {r['registered_events']} | {r['automatic_valid_events']}→{r['assisted_valid_events']} | {r['residual_events']} | {r['residual_no_connection_endpoints']} / {r['residual_below_four_endpoints']} / {r['residual_invalid_floor_endpoints']} |")
    report='''# AC 两方法幅度比较与漏斗：完整注册范围的机会残留审计

## 核心结论

**已确认的 57 队顺序没有漏接；完整注册条件仍不能概括为所有人工处理机会均已覆盖。** 方法比较的 55/55 和 53/53 个共同注册池都有可评均值，但内部仍分别有 15/1042、8/969 个注册事件无 Q。按池有数值不能推导为该池内所有事件、所有方向或所有失败端点都得到同等人工处理。

本次仅核对 `ac/Q_REVERSALS.csv` 中 2 行 `method_comparison` 和 3 行 `funnel`；其中 OPP 漏斗具名方向与 ALL_CANONICAL 是同一个 14 事件集合的别名。没有扩至 AC 全库、选择新团队、增加人工顺序、融合、评分或分类选型。`audit_completed=true` 表示这五行条件的登记范围及残余均已核对，不表示剩余失败端点已经获得新人工顺序。

## 完整分母和残余

| 条件 | n/m | 完整注册池 | 原→辅助可评池 | 完整注册事件 | 原→辅助可评事件 | 残余事件 | 残余独立端点：无连接 / 少于4点 / 无效底面 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
'''+ '\n'.join(rows)+'''

两个方法比较中，事件数是左右方法各自注册事件之和，不能解释为同成员成对实验。它们按每方向内可评事件的绝对 ΔQ 均值，再对该方法已有方向等权，最后在两方法共同注册池比较。完整注册事件分母分别 1042、969，与池层 55、53 分母不同。所有计算继续保留无 Q 的缺失状态，未把无 Q 当成 0 分或 0 效应。

## 方法幅度比较的边界

两个比较合并后共有 **17 个剩余事件、18 个缺 Q 端点**；这不是 15+8 个独立新案例。18 个端点都在确认 57 队之外，其中 4 个 `no_connection`、11 个少于 4 点、3 个 `invalid_floor`。这 17 个方法事件的对手也都不在 57 队内。

4 个无连接端点为 S9h-04 的两队（各 6 点）、VFua-04 的一队（6 点）、x8-08 的一队（4 点）。节点数足够不等于已证明能靠排序修复；目前只确认它们没有已提交人工顺序。3 个无效底面端点是另一种几何失败，不将其自动纳入排序修复。少于 4 点的端点在固定节点条件下不能靠重排补足。

当前辅助可评支持上的 RAW3−OPP = −0.103143、RAW3−TARGET_K2 = −1.156838 仍是实际计算结果；原共同可评事件的保持性由 AC 主验收提供。若改问“完整注册事件都在同等机会下处理后，两个方法的效应方向如何”，现有顺序不足以给出该结论，标记为 **尚不能判断**。这是支持与处理机会的条件限制，不是分类优劣证据，也不是漏接已确认结果。

## 漏斗：结构不合格与未覆盖机会分别记录

OPP、primary、28/1 的 1/3→3/3 与 ALL_CANONICAL 都是 14 个注册事件、13 个现可评事件。残余 C 端只有 3 个节点；其 A 端在 57 队内并已接入。这里不存在一个尚未处理、节点足够的无连接对手。该条件的 `all_registered_opportunities_covered=true` 仅依照下述固定节点排序机会合同；`all_registered_events_Q_evaluable=false` 仍明确保留，不能称 14 个事件全部可评。

RAW3、other_admitted、4/4、1/3→2/3 有 16 个注册事件，现可评 13 个。其余 3 个 C 端均在 57 队之外，状态 `no_connection`，节点数 11、8、8。wc2-26 的两个 C 端所对应的 A 端属于已确认 57 队并已接入；rPc6-22 的第三个 C 端及其 A 端都不在队列中。因此，这一完整比较范围确实存在不对称的处理机会。三个端点的冻结原记录与图形核对已由 `ac_peer/RAW3_RESIDUAL_FROZEN_ENDPOINT_RECORDS.json` 保存；此处不重复恢复几何或猜测顺序。

当前 13/16 支持的 −13.675955 不被这项机会审计推翻。AC 同行验收已证明：在其余已评分端点固定、三个未知 C 分数遵守原公式的 [0,100] 范围时，保留缺失或按任一可评子集补入，效应界限均为 **[−20.722480, −1.972480]**，方向仍负。这里的 0/100 是数学界限，不是把缺失 Q 写成观测 0；具体完成后的 Q 与幅度仍未观测。其证据为 [同行界限回执](../ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json) 和 [27 个边界/可评子集场景](../ac_peer/RAW3_PURE_CLASS_MISSING_Q_BOUNDS_SCENARIOS.csv)。本脚本核对该回执的条件、三个残余团队身份和 13/16 支持后引用，不重复评分。不能把“仍有未处理端点”直接等同于“任何方向都不可判断”，也不据此自动开启新的人工任务。

## 机器可读合同与来源

- `CONDITION_OPPORTUNITY_AUDIT.csv`：每个 reversal_id 的完整注册池/事件、原和辅助可评数、残余事件与端点、57 内外及最终字段。
- `RESIDUAL_EVENTS.csv.gz`：五个表行条件逐事件残余；别名和方法共用事件保留 reversal_id，不能跨行求和充当独立样本。
- `RESIDUAL_ENDPOINTS.csv`：每个残余事件的每个缺 Q 端点及对手是否在 57 内。
- `DISTINCT_RESIDUAL_ENDPOINTS.csv`：按 family/team_key 去重，列明所有关联条件和事件。
- `METHOD_COMPLETE_DIRECTION_SUPPORT.csv.gz`：方法比较原和辅助的完整方向层数值与分母。
- `METHOD_ARM_SUPPORT.csv` 与 `POOL_VALUES.csv`：左右方法及池层值；原共同注册池身份保持。
- `inputs/FULL_COHORT_EXTRACTION_RECEIPT.json`：完整原 68858 行池表和 550794 行设计链接的抽取条件、原 SHA-256、输出 SHA-256；离线运行只用已保存精确范围。
- `source_cache/DOWNLOAD_MANIFEST.json`：仅补读 4 个存在实际残余的原池分片；固定 GitHub commit、下载 URL、SHA-256 和精确 Git blob 校验。

`all_registered_opportunities_covered` 的合同是：每个剩余失败端点都有已确认处理，或已证明在固定节点排序条件下结构不合格。队列外的 `no_connection` 与未解决几何问题不算机会覆盖；少于 4 点作为结构不合格单列。它与 `audit_completed`、`confirmed_order_propagation_complete`、`all_registered_events_Q_evaluable` 是四个不同判断。

复现：`python research/fusion/manual_order_acceptance_20261104/ac_opportunity_secondary/audit_opportunity.py`。输入逐文件 SHA-256 见 `INPUT_MANIFEST.json`；使用前五批、本次 AC 验收及同行验收文件。源版本固定为 `ac395e703d1fef573d1ef3e105df0286d62a0468`。
'''
    (HERE/'REPORT_ZH.md').write_text(report,encoding='utf-8')


def main():
    for r in load_json(HERE/'source_cache/DOWNLOAD_MANIFEST.json'):
        data=(ROOT/r['cache']).read_bytes()
        blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        check('frozen_source_blob/'+Path(r['cache']).name,blob==r['github_blob_sha1'] and hashlib.sha256(data).hexdigest()==r['sha256'])
    for r in load_json(HERE/'inputs/FULL_COHORT_EXTRACTION_RECEIPT.json'):
        check('frozen_complete_cohort_extract/'+Path(r['extraction']).name,hashlib.sha256((ROOT/r['extraction']).read_bytes()).hexdigest()==r['sha256'])
    catalog=read(AC/'Q_REVERSALS.csv')
    catalog=catalog[catalog.family.isin(['method_comparison','funnel'])]
    check('exact_five_existing_reversal_rows',len(catalog)==5 and catalog.family.value_counts().to_dict()=={'funnel':3,'method_comparison':2})
    confirmed=read(ENDPOINTS).set_index('team_key')
    method_audit(catalog,confirmed);funnel_audit(catalog,confirmed)
    residual=pd.DataFrame(RESIDUALS);endpoint=pd.DataFrame(ENDPOINT_ROWS);conditions=pd.DataFrame(CONDITIONS)
    method_events=residual[residual.family.eq('method_comparison')].drop_duplicates('event_id')
    method_ends=endpoint[endpoint.family.eq('method_comparison')].drop_duplicates('team_key')
    check('method_residual_union_17_events_18_endpoints',len(method_events)==17 and len(method_ends)==18)
    check('method_residual_all_outside57_no_confirmed_opponent',not method_ends.in_confirmed57.any() and not method_ends.counterpart_in_confirmed57.any())
    check('method_residual_failures_separated',method_ends.score_status.value_counts().to_dict()=={'below_four':11,'no_connection':4,'invalid_floor':3})
    op=conditions[conditions.method.eq('OPPSTRUCT_K3')]
    check('OPP_named_all_alias_complete_cohort',len(op)==2 and op.registered_events.eq(14).all() and op.assisted_valid_events.eq(13).all()
          and set(residual.loc[residual.reversal_id.eq(op.iloc[0].reversal_id),'event_id'])==set(residual.loc[residual.reversal_id.eq(op.iloc[1].reversal_id),'event_id']))
    raw3=conditions[conditions.family.eq('funnel')&conditions.method.eq('V21_DSTRUCT_RAW3_K3')].iloc[0]
    check('RAW3_three_unconfirmed_no_connection_two_confirmed_opponents',raw3.registered_events==16 and raw3.assisted_valid_events==13
          and raw3.residual_no_connection_endpoints==3 and raw3.no_connection_endpoints_with_confirmed_counterpart==2)
    bound=load_json(PEER/'RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json')
    expected_teams={r['C_team_key'] for r in bound['missing_score_variables']}
    actual_teams=set(endpoint.loc[endpoint.reversal_id.eq(raw3.reversal_id),'team_key'])
    check('RAW3_peer_bound_applies_to_same_residual_condition',expected_teams==actual_teams
          and bound['registered_events']==raw3.registered_events and bound['expanded_evaluable_events']==raw3.assisted_valid_events
          and bound['negative_direction_survives_all_legal_completions'] and bound['complete16_effect_upper']<0)
    mask=conditions.reversal_id.eq(raw3.reversal_id)
    conditions.loc[mask,'complete_registered_effect_direction']='negative for every legal completion or retained-missing subset; actual missing endpoint scores and final amplitude unobserved'
    conditions.loc[mask,'legal_completion_effect_lower']=bound['complete16_effect_lower']
    conditions.loc[mask,'legal_completion_effect_upper']=bound['complete16_effect_upper']
    conditions.loc[mask,'completion_bound_source']='../ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json'
    distinct=[]
    for (family,team),g in endpoint.groupby(['family','team_key']):
        r=g.iloc[0].to_dict();r.pop('reversal_id');r.pop('event_id')
        r.update(reversal_ids='|'.join(sorted(set(g.reversal_id))),event_ids='|'.join(sorted(set(g.event_id))),
                 actual_unique_event_count=g.event_id.nunique(),condition_occurrences=len(g))
        distinct.append(r)
    save(conditions,'CONDITION_OPPORTUNITY_AUDIT.csv');save(residual,'RESIDUAL_EVENTS.csv.gz')
    save(endpoint,'RESIDUAL_ENDPOINTS.csv');save(pd.DataFrame(distinct),'DISTINCT_RESIDUAL_ENDPOINTS.csv')
    save(pd.DataFrame(ARMS),'METHOD_ARM_SUPPORT.csv');save(pd.DataFrame(POOLS),'POOL_VALUES.csv')
    save(pd.DataFrame(CHECKS),'CHECKS.csv');make_report()
    failures=[r for r in CHECKS if not r['passed']]
    manifest=list(INPUTS.values())+[dict(path=str(Path(__file__).relative_to(ROOT)),bytes=Path(__file__).stat().st_size,
        sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())]
    (HERE/'INPUT_MANIFEST.json').write_text(json.dumps(dict(source_commit=COMMIT,files=manifest),ensure_ascii=False,indent=2)+'\n')
    summary=dict(audit_completed=not failures,status='PASS' if not failures else 'FAIL',checks=len(CHECKS),passed=len(CHECKS)-len(failures),
        failed_checks=failures,source_commit=COMMIT,scope_reversal_rows=5,
        all_registered_opportunities_covered=bool(conditions.all_registered_opportunities_covered.all()),
        confirmed_order_propagation_complete=bool(conditions.confirmed_order_propagation_complete.all()),
        all_registered_events_Q_evaluable=False,method_union_residual_events=len(method_events),method_union_residual_endpoints=len(method_ends),
        new_teams=0,new_orders=0,new_fusions=0,new_scores=0,classification_selection_runs=0,
        machine_readable_conditions='CONDITION_OPPORTUNITY_AUDIT.csv')
    (HERE/'CHECKS.json').write_text(json.dumps(clean(summary),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(clean(summary),ensure_ascii=False,indent=2),flush=True)
    if failures: raise SystemExit(1)


if __name__=='__main__':main()
