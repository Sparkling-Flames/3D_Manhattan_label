"""Independent saved-event audit; no author aggregation functions are imported."""
from pathlib import Path
from collections import Counter
import json
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
B = HERE.parent / 'unpacked'
R = B / '06A/research/workers/personnel_exchange_discrimination_20261025'
F = B / '06C/research/workers/personnel_exchange_discrimination_20261025/final'


def read(path, cols=None):
    return pd.read_csv(path, usecols=(lambda c: c in cols) if cols else None, low_memory=False)


def split(value):
    return set(str(value).split('|')) if pd.notna(value) and str(value) else set()


def frame_equal(a, b, context):
    assert a.index.equals(b.index), context
    for c in a.columns:
        if pd.api.types.is_numeric_dtype(a[c]):
            assert np.allclose(a[c], b[c], equal_nan=True, atol=1e-9, rtol=1e-10), (context, c)
        else:
            assert a[c].fillna('').eq(b[c].fillna('')).all(), (context, c)


def balanced(frame, columns):
    direction = ['pool_id', 'image', 'building', 'difficulty', 'source_class', 'target_class']
    cell = frame.groupby(direction + ['block_id', 'background_target_n'], dropna=False)[columns].mean()
    block = cell.groupby(level=direction + ['block_id'], dropna=False).mean()
    direct = block.groupby(level=direction, dropna=False).mean()
    pool = direct.groupby(level=['pool_id', 'image', 'building', 'difficulty'], dropna=False).mean()
    building = pool.groupby(level='building').mean()
    return pool, building


def add_roles(frame, stage):
    name = 'REVERSE_CLASS_SIZE_ROLES.csv' if stage.startswith('reverse') else 'FOLD_CLASS_ROLE_MAP.csv'
    centers = read(R / 'analysis' / stage / name)
    centers['smallest_class'] = centers.class_people.eq(centers.groupby(['method', 'heldout_building']).class_people.transform('min'))
    for side in ['source', 'target']:
        v = centers[['method', 'heldout_building', 'class_id', 'highest_turn', 'largest_class', 'smallest_class']]
        v = v.rename(columns={'heldout_building':'building', 'class_id':side+'_class',
                              **{c:side+'_'+c for c in ['highest_turn','largest_class','smallest_class']}})
        frame = frame.merge(v, on=['method','building',side+'_class'], validate='many_to_one')
    return frame


def role_mask(frame, role):
    if role == 'largest_to_highest_turn':
        return frame.source_largest_class & frame.target_highest_turn & ~frame.source_highest_turn
    if role == 'into_smallest_class':
        return ~frame.source_smallest_class & frame.target_smallest_class
    if role == 'between_nonsmall_classes':
        return ~frame.source_smallest_class & ~frame.target_smallest_class
    assert role == 'higher_Q|slower|more_turns'
    return frame.historical_q_direction.eq('higher_Q') & frame.history_target_minus_source_m_all_log_time.gt(0) & frame.historical_turn_direction.eq('more_turns')


def main():
    events = read(F / 'ALL_EVENTS_EXACT.csv.gz')
    inv = read(F / 'UNIQUE_ENDPOINT_INVENTORY.csv.gz').set_index('team_key')
    links = read(F / 'EVENT_ENDPOINT_LINKS.csv.gz')
    labels = read(R / 'final/LABELS_LOBO.csv.gz')
    assert events.event_id.is_unique and inv.index.is_unique
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    labels = labels.set_index(['method','heldout_building','worker_id']).class_id.fillna('unknown').to_dict()
    endpoint_sets = inv.member_workers.map(split).to_dict()
    expected_links = []
    class_vector_mismatches = []
    for row in events.itertuples(index=False):
        blocks = {x:split(getattr(row,x)) for x in 'DXYZ'}
        abc = pd.notna(row.B_team_key)
        relevant = 'DXYZ' if abc else 'DXZ'
        for i,x in enumerate(relevant):
            for y in relevant[i+1:]:
                assert not (blocks[x] & blocks[y]), (row.event_id,x,y,'overlap')
        assert len(blocks['D']) == row.n-row.m
        for x in ('XYZ' if abc else 'XZ'):
            assert len(blocks[x]) == row.m, (row.event_id,x,'size')
            cls = row.target_class if x=='Z' else row.source_class
            assert all(labels[(row.method,row.building,w)] == cls for w in blocks[x]), (row.event_id,x,'class')
        for arm,block in [('A','X'),('B','Y'),('C','Z')]:
            if arm=='B' and not abc: continue
            members = split(getattr(row,arm+'_members'))
            key = getattr(row,arm+'_team_key')
            assert members == blocks['D']|blocks[block] and len(members)==row.n, (row.event_id,arm)
            assert endpoint_sets[key] == members, (row.event_id,arm,'endpoint members')
            e=inv.loc[key]
            assert e.pool_id==row.pool_id and e.k==row.n and e.condition=='manual' and e.layer=='ordinary_manual'
            actual = Counter(labels[(row.method,row.building,w)] for w in members)
            stored = {k:int(v) for k,v in (x.rsplit(':',1) for x in getattr(row,arm+'_class_vector').split('|'))}
            # Unknown labels can be named UNK by the design rather than unknown.
            if 'unknown' in actual and 'unknown' not in stored:
                actual['UNK'] = actual.pop('unknown')
            assert all(actual[k]==v for k,v in stored.items()) and all(k in stored for k in actual), (row.event_id,arm,'vector',actual,stored)
            expected_links.append((row.event_id,arm,key))
    actual_links = set(links[['event_id','arm','team_key']].itertuples(index=False,name=None))
    assert len(actual_links)==len(links)==len(expected_links)
    assert actual_links==set(expected_links)
    assert set(links.team_key)==set(inv.index)
    ledger = {'events':len(events),'ABC':int(events.B_team_key.notna().sum()),'AC':int(events.B_team_key.isna().sum()),
              'endpoint_links':len(links),'unique_endpoints':len(inv),'images':events.image.nunique(),
              'buildings':events.building.nunique(),'methods':events.method.nunique(),
              'all_member_block_label_vector_endpoint_checks':'passed'}
    (HERE/'LEDGER_CHECK.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    print('LEDGER',ledger,flush=True)

    scalar_paths = {
        'results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz':B/'02B/results/screen/NATIVE_ENDPOINT_SCALARS.csv.gz',
        'results/batch02/ENDPOINT_SCALARS.csv.gz':B/'04B/results/batch02/ENDPOINT_SCALARS.csv.gz',
        'results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz':B/'05/results/size_paths/NATIVE_ENDPOINT_SCALARS.csv.gz',
        'results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz':B/'05/results/large_team_ac_tail/NATIVE_ENDPOINT_SCALARS.csv.gz'}
    fields=['B8L2','D10','IoU3D100','source_time_total_seconds','nodes','floor_turn5_n','omission','extension','height_mean_ratio']
    ep_parts=[]
    for name,path in scalar_paths.items():
        ep=read(path,['team_key','member_workers','score_available','pool_id','k']+fields).set_index('team_key')
        keys=inv.index[inv.scalar_source.eq(name)]
        assert keys.isin(ep.index).all()
        selected=ep.loc[keys]
        frame_equal(inv.loc[keys,['B8L2','D10','member_workers','pool_id','k']],selected[['B8L2','D10','member_workers','pool_id','k']],name)
        ep_parts.append(selected)
    ep=pd.concat(ep_parts)
    assert ep.index.is_unique
    # Four main source event tables. Endpoint values, not the saved contrasts, are used below.
    stages={'screen':B/'02A/results/screen/EVENT_METRICS.csv.gz',
            'confirm':B/'04A1/results/confirm/EVENT_METRICS.csv.gz',
            'reverse_screen':B/'04A2/results/reverse_screen/EVENT_METRICS.csv.gz',
            'reverse_confirm':B/'04A2/results/reverse_confirm/EVENT_METRICS.csv.gz'}
    metrics={}; field_checks=[]
    for stage,path in stages.items():
        meta=['event_id','pool_id','image','building','difficulty','phase','method','n','m','source_class','target_class',
              'block_id','background_target_n','background_id','A_team_key','B_team_key','C_team_key',
              'historical_q_direction','historical_turn_direction','history_target_minus_source_m_all_log_time']
        effect=[f'{m}_{s}' for m in fields for s in ['within','cross','gap','BA','CA','CB']]
        flags=['A_failed','B_failed','C_failed','C_loss10_CA','C_loss10_CB','C_failure_or_loss10_CA','C_failure_or_loss10_CB','record_time_CA_pct','record_time_CB_pct']
        geometry=[f'{m}_{s}' for m in ['geometry_bev_distance','geometry_pair_angle','geometry_top_angle','geometry_bottom_angle'] for s in ['within','cross','gap']]
        d=read(path,meta+effect+flags+geometry+[a+'_'+m for a in 'ABC' for m in fields])
        assert set(d.event_id)==set(events.loc[events.stage.eq(stage),'event_id'])
        for a in 'ABC':
            for m in fields:
                from_ep=d[a+'_team_key'].map(ep[m])
                assert np.allclose(from_ep,d[a+'_'+m],equal_nan=True,atol=1e-9,rtol=1e-10),(stage,a,m,'scalar')
                d[a+'_'+m]=from_ep
        for m in fields:
            a,b,c=[d[x+'_'+m] for x in 'ABC'];ok=a.notna()&b.notna()&c.notna()
            expected={'within':(b-a).abs().where(ok),'cross':((c-a).abs()+(c-b).abs()).div(2).where(ok),
                      'BA':b-a,'CA':c-a,'CB':c-b}
            expected['gap']=expected['cross']-expected['within']
            for s,v in expected.items():
                key=m+'_'+s
                assert np.allclose(v,d[key],equal_nan=True,atol=1e-9,rtol=1e-10),(stage,key,'effect')
                d[key]=v
        for a in 'ABC':
            fail=d[a+'_B8L2'].isna()
            assert np.array_equal(fail,d[a+'_failed']);d[a+'_failed']=fail.astype(float)
        for comp,base in [('CA','A'),('CB','B')]:
            delta=d['B8L2_'+comp]
            vals={
                'C_loss10_'+comp:delta.lt(-10).astype(float).where(delta.notna()),
                'C_failure_or_loss10_'+comp:(d.C_failed.eq(1)|delta.lt(-10)).astype(float).where(d[base+'_failed'].eq(0)),
                'record_time_'+comp+'_pct':100*(d.C_source_time_total_seconds/d[base+'_source_time_total_seconds']-1)}
            for name,value in vals.items():
                assert np.allclose(value,d[name],equal_nan=True,atol=1e-9,rtol=1e-10),(stage,name,'risk/time')
                d[name]=value
        metrics[stage]=add_roles(d,stage)
        field_checks.append({'stage':stage,'events':len(d),'scalar_fields':len(fields),'contrasts_and_risks':'passed'})
        print('EVENT_FIELDS',field_checks[-1],flush=True)
    pd.DataFrame(field_checks).to_csv(HERE/'EVENT_FIELD_CHECKS.csv',index=False)
    table=read(R/'analysis/FINAL_CONDITIONS_COMPACT.csv')
    checks=[];pool_results=[];summary=[]
    for t in table.itertuples(index=False):
        allrows=metrics[t.stage]
        d=allrows[(allrows.phase==t.phase)&(allrows.method==t.method)&(allrows.n==t.n)&(allrows.m==t.m)]
        d=d[role_mask(d,t.role)]
        assert len(d)==t.attempted_events and d.pool_id.nunique()==t.attempted_images
        cols=[m+'_'+s for m in ['B8L2','D10','IoU3D100','nodes','floor_turn5_n','omission','extension','height_mean_ratio'] for s in ['within','cross','gap','BA','CA','CB']]
        cols += ['A_failed','B_failed','C_failed','C_loss10_CA','C_loss10_CB','C_failure_or_loss10_CA','C_failure_or_loss10_CB','record_time_CA_pct','record_time_CB_pct']
        cols += [m+'_'+s for m in ['geometry_bev_distance','geometry_pair_angle','geometry_top_angle','geometry_bottom_angle'] for s in ['within','cross','gap']]
        pools,buildings=balanced(d,cols)
        report={k:getattr(t,k) for k in ['stage','phase','method','role','n','m']}
        values={}
        for m in ['B8L2','D10','IoU3D100','nodes','floor_turn5_n','omission','extension','height_mean_ratio','geometry_bev_distance','geometry_pair_angle','geometry_top_angle','geometry_bottom_angle']:
            for s in ['within','cross','gap','BA','CA','CB']:
                key=m+'_'+s;target=key+'_image_equal'
                if key in pools and hasattr(t,target):values[target]=pools[key].mean()
            for name,v in [('valid_images',pools[m+'_gap'].count()),('valid_buildings',buildings[m+'_gap'].count()),
                           ('gap_positive_images',pools[m+'_gap'].gt(1e-9).sum()),('gap_positive_buildings',buildings[m+'_gap'].gt(1e-9).sum())]:
                if hasattr(t,m+'_'+name):values[m+'_'+name]=int(v)
            if m=='B8L2':values['B8L2_ratio_of_image_means']=pools[m+'_cross'].mean()/pools[m+'_within'].mean()
        for name in ['A_failed','B_failed','C_failed','C_loss10_CA','C_loss10_CB','C_failure_or_loss10_CA','C_failure_or_loss10_CB','record_time_CA_pct','record_time_CB_pct']:
            values[name+'_image_equal']=pools[name].mean();values[name+'_valid_images']=pools[name].count();values[name+'_valid_events']=d[name].count()
            if not name.startswith('record_time'):
                values[name+'_raw_count']=d[name].eq(1).sum();values[name+'_raw_valid_events']=d[name].count()
                values[name+'_affected_images']=d.loc[d[name].eq(1),'pool_id'].nunique()
                values[name+'_affected_buildings']=d.loc[d[name].eq(1),'building'].nunique()
        for key,value in values.items():
            expected=getattr(t,key)
            ok=np.isclose(value,expected,equal_nan=True,atol=1e-8,rtol=1e-9)
            checks.append({**report,'field':key,'recomputed':value,'delivered':expected,'match':bool(ok)})
        summary.append({**report,'attempted_events':len(d),'attempted_images':d.pool_id.nunique(),**values})
        pp=pools.reset_index();pp['stage']=t.stage;pp['phase']=t.phase;pp['method']=t.method;pp['role']=t.role;pp['n']=t.n;pp['m']=t.m;pool_results.append(pp)
    c=pd.DataFrame(checks);c.to_csv(HERE/'CONDITION_FIELD_CHECKS.csv',index=False)
    pd.DataFrame(summary).to_csv(HERE/'CONDITIONS_RECOMPUTED.csv',index=False)
    pool=pd.concat(pool_results);pool.to_csv(HERE/'POOL_RECOMPUTED.csv.gz',index=False)
    print('CONDITIONS',len(summary),'FIELDS',len(c),'MISMATCHES',int((~c.match).sum()),flush=True)
    if (~c.match).any():print(c[~c.match].to_string(index=False))
    assert c.match.all()
    # Same-pool comparisons retain only jointly observed effects, never failed-as-zero.
    common=[]
    for new,old,n,m,role in [('DSTRUCT_K3','V3_BEHAVIOR_coarse',18,7,'largest_to_highest_turn'),('RFUSE_GEOMQ_K3','RFUSE_GEOMQ_K2',20,6,'into_smallest_class')]:
        a=pool[(pool.method==new)&(pool.n==n)&(pool.m==m)&(pool.role==role)&pool.phase.eq('selection_heldout_building')]
        z=pool[(pool.method==old)&(pool.n==n)&(pool.m==m)&(pool.role==role)&pool.phase.eq('selection_heldout_building')]
        cols=['pool_id','B8L2_within','B8L2_cross','B8L2_gap']
        merged=a.merge(z[cols],on='pool_id',suffixes=('_new','_old')).dropna(subset=['B8L2_gap_new','B8L2_gap_old'])
        merged['gap_difference']=merged.B8L2_gap_new-merged.B8L2_gap_old
        bg=merged.groupby('building').gap_difference.mean()
        result={'new':new,'old':old,'n':n,'m':m,'images':len(merged),'buildings':len(bg),'new_within':merged.B8L2_within_new.mean(),'new_cross':merged.B8L2_cross_new.mean(),'old_within':merged.B8L2_within_old.mean(),'old_cross':merged.B8L2_cross_old.mean(),'gap_difference':merged.gap_difference.mean(),'positive_images':int(merged.gap_difference.gt(1e-9).sum()),'positive_buildings':int(bg.gt(1e-9).sum())}
        common.append(result)
    pd.DataFrame(common).to_csv(HERE/'COMMON_POOL_COMPARISONS.csv',index=False)
    print('COMMON',json.dumps(common),flush=True)
    d=metrics['confirm'];d=d[(d.method=='DSTRUCT_K3')&(d.n==18)&(d.m==7)&d.phase.eq('selection_heldout_building')]
    a=set(d.loc[role_mask(d,'largest_to_highest_turn'),'event_id'])
    z=set(d.loc[d.historical_q_direction.eq('higher_Q') & d.history_target_minus_source_m_all_log_time.lt(0) & d.historical_turn_direction.eq('more_turns'),'event_id'])
    print('DSTRUCT_ROLE_EQUIVALENCE',len(a),len(z),a==z,flush=True)
    (HERE/'ROLE_EQUIVALENCE.json').write_text(json.dumps({'largest_to_highest_turn_events':len(a),'higherQ_faster_moreturn_events':len(z),'equal':a==z},indent=2),encoding='utf-8')


if __name__=='__main__':
    main()
