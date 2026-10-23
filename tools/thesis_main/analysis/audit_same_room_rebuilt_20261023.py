"""独立核对 R01/R04/R05：从精确成员和端点重新计算，不调用作者分析函数。"""
from pathlib import Path
from collections import Counter
import argparse
import gzip
import json
import math
import numpy as np
import pandas as pd


def members(value):
    return frozenset(str(value).split('|')) - {'', 'nan'}


def check(a, b, name, checks, atol=1e-8):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert a.shape == b.shape, (name, a.shape, b.shape)
    ok = np.isclose(a, b, atol=atol, rtol=1e-10, equal_nan=True)
    assert ok.all(), (name, int((~ok).sum()), a[~ok][:5], b[~ok][:5])
    valid = np.isfinite(a) & np.isfinite(b)
    checks.append({'check': name, 'values': a.size,
                   'max_abs_error': float(np.max(np.abs(a[valid]-b[valid]))) if valid.any() else 0.})


def main(root, out):
    out.mkdir(parents=True, exist_ok=True)
    read = lambda rel, **kw: pd.read_csv(root / rel, low_memory=False, **kw)
    checks = []
    d = read('design/STRICT_ABC_EVENTS.csv.gz', keep_default_na=False)
    req = read('design/ENDPOINT_REQUESTS.csv.gz', keep_default_na=False).set_index('team_key')
    s = read('native_endpoints/ENDPOINT_SCALARS.csv.gz').set_index('team_key')
    assert len(d) == 62676 and d.event_id.is_unique
    assert len(req) == len(s) == 311333 and req.index.is_unique and s.index.is_unique
    assert set(req.index) == set(s.index)
    s = s.loc[req.index]
    for c in ['pool_id', 'member_workers', 'member_object_ids']:
        assert (req[c] == s[c]).all(), c
    check(req.n, s.k, 'request_team_size', checks)
    labels = read('design/inputs/ALL_METHOD_LABELS_LOBO.csv.gz', keep_default_na=False)
    lab = labels.set_index(['condition', 'method', 'heldout_building', 'worker_id'])
    common = read('design/FROZEN_COMMON_CLASS_MEMBERS.csv.gz', keep_default_na=False)
    cm = {(p, m): z.set_index('worker_id') for (p, m), z in common.groupby(['pair_key', 'method'])}
    snapshot = next((root/'engine/frozen_repo').glob('**/fusion/INPUT_SNAPSHOT.json.gz'))
    with gzip.open(snapshot, 'rt', encoding='utf-8') as f:
        pools = {p['pool_id']: p for p in json.load(f)['images']}
    for (pair, method), z in cm.items():
        r = z.iloc[0]
        pa, pb = (pools[r['pool_id_'+v]] for v in 'ab')
        aa, bb = ({x['worker_id']: x['object_id'] for x in p['records']} for p in (pa, pb))
        assert set(z.index) == set(aa) & set(bb)
        for w, row in z.iterrows():
            assert row.object_id_a == aa[w] and row.object_id_b == bb[w]
            label = lab.loc[(row.condition, method, row.building, w)]
            assert row.class_id == (label.coarse_label if label.known else 'unknown')
    lookup = req[['pool_id','member_workers','member_object_ids']].to_dict('index')
    seen = set()
    for row in d.itertuples(index=False):
        z = row._asdict(); blocks = [members(z[k+'_members']) for k in 'DXYZ']
        D, X, Y, Z = blocks
        assert sum(map(len, blocks)) == len(set().union(*blocks))
        assert len(X) == len(Y) == len(Z) == row.m and len(D)+row.m == row.n
        formal = cm[(row.pair_key, row.method)]
        assert set().union(*blocks) <= set(formal.index)
        for block, label in [(X,row.source_class),(Y,row.source_class),(Z,row.target_class)]:
            assert set(formal.loc[list(block), 'class_id']) == {label}
        assert dict(Counter(formal.loc[list(D), 'class_id'])) == json.loads(row.D_class_counts)
        signature = (row.pair_key,row.method,D,tuple(sorted((tuple(sorted(X)),tuple(sorted(Y))))),Z)
        assert signature not in seen; seen.add(signature)
        for role, team in zip('ABC',[D|X,D|Y,D|Z]):
            assert members(z[role+'_members']) == team
            for v in 'ab':
                endpoint = lookup[z[f'team_{role}_{v}']]
                assert members(endpoint['member_workers']) == team
                assert endpoint['pool_id'] == z['pool_id_'+v]
                assert members(endpoint['member_object_ids']) == set(formal.loc[list(team),'object_id_'+v])
    cfg = read('design/CONFIGURATION_COVERAGE.csv', keep_default_na=False).set_index('config_id')
    counts = d.groupby('config_id').size()
    assert set(cfg.index) == set(counts.index)
    check(cfg.selected_unique_events, counts.reindex(cfg.index), 'configuration_coverage', checks)
    for row in cfg.itertuples():
        space = math.comb(row.source_n,row.m)*math.comb(row.source_n-row.m,row.m)//2
        space *= math.comb(row.target_n,row.m)*math.comb(row.common_n-3*row.m,row.n-row.m)
        assert space == int(row.finite_event_space)
        if row.enumerate_all: assert int(row.selected_unique_events) == space
    # 冻结评分公式单独实现，不导入作者 scorer。
    good = s.B8L2.notna()
    assert np.array_equal(good, s.complete_evaluable)
    I, Sb, Di, Hm, Hc = [s.loc[good,c].to_numpy(float) for c in ['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']]
    for metric, scale in [('B8L2',8.),('D10',10.)]:
        loss_floor = 1-I+I*(Sb*Sb/32)
        loss_dir = I*1.5*Di*Di/(Di*Di+scale*scale)
        q = 100*I/(I+np.hypot(loss_floor,loss_dir)+I*((Hm/.8)**2+(Hc/.25)**2))
        q[I == 0] = 0
        check(q,s.loc[good,metric],metric+'_from_components',checks)
    print('成员、配置与305161端点评分分项核对完成', flush=True)
    e = read('results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz').set_index('event_id').loc[d.event_id].reset_index()
    for c in d:
        assert (e[c].fillna('').astype(str) == d[c].astype(str)).all() or c.startswith(('q_','t_','m_over_n')), c
    ids = np.stack([s.index.get_indexer(d[f'team_{r}_{v}']) for v in 'ab' for r in 'ABC'],axis=1).reshape(len(d),2,3)
    assert (ids >= 0).all()
    q = s.B8L2.to_numpy()[ids]; qok = np.isfinite(q).all(axis=(1,2))
    check(qok,e.Q_common6,'Q_common6',checks)
    check((~np.isfinite(q)).mean(axis=(1,2)),e.score_failure_fraction,'all_attempt_failure_fraction',checks)
    metrics = [c[:-7] for c in e if c.endswith('_within') and c[:-7] in s]
    derived = {}
    for metric in metrics:
        v = pd.to_numeric(s[metric],errors='raise').to_numpy()[ids]
        valid = np.isfinite(v).all(axis=(1,2))
        if metric == 'recorded_time_total_seconds': valid &= e.time_common6.to_numpy()
        ba, ca, cb = v[:,:,1]-v[:,:,0],v[:,:,2]-v[:,:,0],v[:,:,2]-v[:,:,1]
        vals = dict(BA=ba.mean(1),CA=ca.mean(1),CB=cb.mean(1),
                    within=np.abs(ba).mean(1),cross=(np.abs(ca)+np.abs(cb)).mean(1)/2,
                    CS=(ca+cb).mean(1)/2)
        vals['extra']=vals['cross']-vals['within']
        for suffix, value in vals.items():
            name=metric+'_'+suffix; value=np.where(valid,value,np.nan)
            check(value,e[name],name,checks);derived[name]=value
    for comp,j,k in [('BA',1,0),('CA',2,0),('CB',2,1)]:
        for name, flag in [('new_score_failure',np.isfinite(q[:,:,k])&~np.isfinite(q[:,:,j])),
                           ('recovered_score',~np.isfinite(q[:,:,k])&np.isfinite(q[:,:,j]))]:
            if name+'_'+comp in e: check(flag.mean(1),e[name+'_'+comp],name+'_'+comp,checks)
        delta=q[:,:,j]-q[:,:,k]
        check(np.where(qok,(delta < -5).mean(1),np.nan),e[comp+'_loss_gt5_fraction'],comp+'_bad_tail',checks)
        for eps in (0,2):
            sign=(delta>eps).astype(int)-(delta < -eps).astype(int)
            states={'both_near_zero':(sign==0).all(1),'same_nonzero':(sign[:,0]==sign[:,1])&(sign[:,0]!=0),
                    'opposite':sign.prod(1)==-1,'one_response':(sign!=0).sum(1)==1,
                    'both_response':(sign!=0).all(1)}
            for state,value in states.items():
                check(np.where(qok,value,np.nan),e[f'eps{eps}_{comp}_{state}'],f'eps{eps}_{comp}_{state}',checks)
    ts = s.time_source_kinds.fillna('').to_numpy()[ids].reshape(len(d),6)
    tv = s.recorded_time_total_seconds.to_numpy()[ids]
    tok=(tv>0).all(axis=(1,2)) & (ts==ts[:,[0]]).all(1) & (ts[:,0]!='')
    tok &= np.array(['|' not in x for x in ts[:,0]])
    check(tok,e.time_common6,'time_common6_independent',checks)
    for comp,j,k in [('BA',1,0),('CA',2,0),('CB',2,1)]:
        ratio=(tv[:,:,j]/tv[:,:,k]).mean(1)
        check(np.where(tok,ratio,np.nan),e['time_ratio_'+comp],'time_ratio_'+comp,checks)
        check(np.where(tok&qok,ratio,np.nan),e['QT_time_ratio_'+comp],'QT_time_ratio_'+comp,checks)
    pd.DataFrame(checks).to_csv(out/'CORE_NUMERIC_CHECKS.csv',index=False)
    # 配置ID固定了图对、方向、n/m；从独立端点差值重聚合。
    e[list(derived)] = pd.DataFrame(derived)
    cols=['B8L2_within','B8L2_cross','B8L2_extra','B8L2_CA','B8L2_CB','D10_extra',
          'score_failure_fraction','new_score_failure_CA','recovered_score_CA']
    summary=[]
    overall=read('results/OVERALL_CONDITIONS.csv').set_index(['subset','method','condition'])
    masks={'ordinary_all':e.ordinary_comparable,'ordinary_pure':e.ordinary_comparable&(e.D_n==0),
           'ordinary_mixed':e.ordinary_comparable&(e.D_n>0),
           'ordinary_mixed_less_half':e.ordinary_comparable&(2*e.m<e.n),
           'ordinary_mixed_half':e.ordinary_comparable&(2*e.m==e.n),
           'ordinary_mixed_more_half':e.ordinary_comparable&(e.D_n>0)&(2*e.m>e.n),
           'ordinary_Q_blocks_within2':e.ordinary_comparable&(e.history_Q_block_range<=2),
           'ordinary_Q_blocks_within5':e.ordinary_comparable&(e.history_Q_block_range<=5)}
    pairrows=[]
    for method in e.method.unique():
        for subset,mask in masks.items():
            z=e[mask&e.method.eq(method)]
            if z.empty:continue
            cg=z.groupby(['config_id','pair_key','building'])[cols].mean().reset_index()
            pairs=cg.groupby(['pair_key','building'])[cols].mean()
            buildings=pairs.groupby('building').mean()
            row=dict(subset=subset,method=method,events=len(z),quality_events=int(z.Q_common6.sum()),
                     pairs=len(pairs),buildings=len(buildings),positive_pairs=int((pairs.B8L2_extra>0).sum()))
            for weighting, table in [('pair_equal',pairs),('building_equal',buildings)]:
                for c in cols:
                    row[weighting+'__'+c]=table[c].mean()
                    check([row[weighting+'__'+c]],[overall.loc[(subset,method,'manual'),weighting+'__'+c]],
                          subset+'/'+method+'/'+weighting+'/'+c,checks)
            summary.append(row)
            pairrows.append(pairs.reset_index().assign(subset=subset,method=method))
    pd.DataFrame(summary).to_csv(out/'INDEPENDENT_MAIN_RESULTS.csv',index=False)
    pd.concat(pairrows).to_csv(out/'INDEPENDENT_PAIR_RESULTS.csv',index=False)
    # 跨视角条件率：先共同支持，再配置均值、图对内条件率、图对等权。
    z=e[e.ordinary_comparable&e.method.eq('V3_BEHAVIOR')&(e.D_n>0)&e.Q_common6]
    response=[]
    for comp in ['BA','CA','CB']:
        cc=[f'eps2_{comp}_{state}' for state in ['both_near_zero','same_nonzero','opposite','one_response','both_response','source_same_n','source_trigger_n']]
        p=z.groupby(['config_id','pair_key'])[cc].mean().groupby('pair_key').mean()
        response.append(dict(comparison=comp,**{c:p[c].mean() for c in cc},
                             source_trigger_same=(p[cc[-2]]/p[cc[-1]].replace(0,np.nan)).mean(),
                             both_trigger_same=(p[cc[1]]/p[cc[4]].replace(0,np.nan)).mean()))
    pd.DataFrame(response).to_csv(out/'INDEPENDENT_RESPONSE_STATES.csv',index=False)
    # 每条实际路径重新核对固定A或固定XYZ，并重算全部分项变化。
    t=read('anchor_paths/ANCHOR_PATH_EFFECTS.csv.gz')
    assert len(t)==35603 and t.path_transition_id.is_unique
    for row in t.itertuples(index=False):
        if row.study_type=='fixed_A_scale':
            assert row.A_members_small == row.A_members_large and row.n_small == row.n_large
        else:
            assert row.m_small == row.m_large and members(row.D_small)<=members(row.D_large)
            z=row._asdict()
            for role in 'ABC':
                assert members(z[role+'_members_small'])-members(row.D_small) == members(z[role+'_members_large'])-members(row.D_large)
    ti=np.stack([s.index.get_indexer(t[f'team_{stage}_{role}_{view}']) for stage in ['small','large'] for view in 'ab' for role in 'ABC'],axis=1).reshape(len(t),2,2,3)
    assert (ti>=0).all()
    for metric in metrics:
        vv=s[metric].to_numpy()[ti];valid=np.isfinite(vv).all(axis=(1,2,3))
        if metric=='recorded_time_total_seconds':valid &= t.time_common12.to_numpy()
        change=vv[:,1]-vv[:,0]
        effects={role+'_change':change[:,:,j].mean(1) for j,role in enumerate('ABC')}
        effects['net_C_minus_B_change']=effects['C_change']-effects['B_change']
        for suffix,value in effects.items():
            check(np.where(valid,value,np.nan),t[metric+'_'+suffix],'path_'+metric+'_'+suffix,checks)
    pd.DataFrame(checks).to_csv(out/'CORE_NUMERIC_CHECKS.csv',index=False)
    receipt=dict(events=len(d),endpoints=len(s),quality_endpoints=int(good.sum()),failure_endpoints=int((~good).sum()),
                 configurations=len(cfg),enumerated_configurations=int(cfg.enumerate_all.sum()),
                 physical_pairs=d.pair_key.nunique(),pools=req.pool_id.nunique(),
                 paths=len(t),numeric_checks=len(checks),all_checked_values=sum(c['values'] for c in checks),
                 classification_training_rerun=False,native_fusion_rerun_in_this_script=False)
    (out/'CORE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root,a.out)
