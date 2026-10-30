"""Reaggregate the latest frozen TARGET main events; preserve actual endpoints.

No class fit, team selection, new experiment or quality-zero imputation.
"""
from pathlib import Path
import gzip, hashlib, itertools, json, os
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
WS=ROOT.parent
SOURCE=ROOT/'source/research/data/releases/v2.1/final_classification_downstream'
OUT=ROOT/'stage01_half_team'
OUT.mkdir(parents=True,exist_ok=True)
def save(d,n):d.to_csv(OUT/n,index=False,encoding='utf-8-sig')
def members(s):return set(str(s).split('|')) if pd.notna(s) else set()
def aggregate(d,columns):
    keys=['n','building','image','pool_id','block_id','background_id']
    x=d.groupby(keys,dropna=False)[columns].mean()
    for level in [keys[:-1],keys[:-2],keys[:3]]:x=x.groupby(level=level,dropna=False).mean()
    return x.reset_index()

def main():
    e=pd.read_csv(SOURCE/'TARGET_MAIN_EVENTS.csv.gz',low_memory=False)
    assert e.event_id.is_unique and set(e.n)=={14,20} and e.m.eq(7).all()
    ok=e[['B8L2_BA','B8L2_CA','B8L2_CB']].notna().all(axis=1)
    assert np.allclose(e.gap_A,(e.B8L2_CA.abs()-e.B8L2_BA.abs()).where(ok),equal_nan=True)
    assert np.allclose(e.gap_sym,((e.B8L2_CA.abs()+e.B8L2_CB.abs())/2-e.B8L2_BA.abs()).where(ok),equal_nan=True)
    teams={}
    for row in e.to_dict('records'):
        b={k:members(row[k]) for k in 'DXYZ'}
        assert not any(b[x]&b[y] for x,y in itertools.combinations(b,2))
        assert len(b['D'])==row['n']-7 and all(len(b[k])==7 for k in 'XYZ')
        for arm,block in zip('ABC','XYZ'):
            k=row[arm+'_team_key'];ws=members(row[arm+'_members'])
            assert ws==b['D']|b[block]
            val={'team_key':k,'pool_id':row['pool_id'],'image':row['image'],'building':row['building'],'n':row['n'],'members':'|'.join(sorted(ws))}
            assert k not in teams or teams[k]==val
            teams[k]=val
    wanted=set(teams);scalars=[];source_receipts=[]
    base=WS/'repo/research/workers/personnel_v21_reselection_20261029'
    paths=[base/'experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz',base/'experiment/fixed_A_m_endpoints/ENDPOINT_SCALARS.csv.gz',base/'additional_delivery/packages/05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz']
    # The deliverable includes the exact selected source endpoints. A standalone
    # replay does not need the much larger historical repository or its caches.
    if not all(p.exists() for p in paths):
        portable=OUT/'SAVED_ENDPOINT_SCALARS.csv.gz'
        if not portable.exists():raise FileNotFoundError('Need bundled stage01_half_team/SAVED_ENDPOINT_SCALARS.csv.gz or all three original scalar archives')
        paths=[portable]
    for p in paths:
        selected=[]
        for part in pd.read_csv(p,chunksize=10000,low_memory=False):
            f=part[part.team_key.isin(wanted)].copy()
            if len(f):
                if 'scalar_source' not in f:f['scalar_source']=str(p.relative_to(WS))
                selected.append(f)
        q=pd.concat(selected,ignore_index=True) if selected else pd.DataFrame()
        scalars.append(q);source_receipts.append({'path':str(p),'sha256':hashlib.file_digest(p.open('rb'),'sha256').hexdigest(),'selected_rows':len(q)})
    s=pd.concat(scalars,ignore_index=True)
    checks=[]
    for k,g in s.groupby('team_key'):
        for col in ['B8L2','D10','nodes','minimum_support']:
            a=g[col].dropna().to_numpy(float)
            assert len(a)==0 or np.max(a)-np.min(a)<1e-8,(k,col)
    s=s.drop_duplicates('team_key').set_index('team_key')
    assert wanted<=set(s.index),(len(wanted-set(s.index)),list(wanted-set(s.index))[:5])
    save(s.reset_index(),'SAVED_ENDPOINT_SCALARS.csv.gz')
    for arm in 'ABC':
        for field in s.columns:
            if field not in ['member_workers','pool_id','image','building','condition','layer','difficulty']:
                e[arm+'__'+field]=e[arm+'_team_key'].map(s[field])
    parity=[]
    for met in ['B8L2','D10','S_bottom_deg','omission','extension','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h','boundary_loss','direction_loss','height_loss']:
        for pair in ['BA','CA','CB']:
            a=e[pair[0]+'__'+met]-e[pair[1]+'__'+met];b=e[met+'_'+pair]
            valid=a.notna()&b.notna();err=float((a[valid]-b[valid]).abs().max()) if valid.any() else 0
            assert err<1e-8,(met,pair,err)
            parity.append({'metric':met,'pair':pair,'common_events':int(valid.sum()),'maximum_error':err})
    e['C_between_A_B']=np.where(ok,(e.B8L2_CA.between(e.B8L2_BA.clip(upper=0),e.B8L2_BA.clip(lower=0))).astype(float),np.nan)
    e['opposed_CB_loss_components']=np.where(e[['boundary_loss_CB','direction_loss_CB','height_loss_CB']].notna().all(axis=1),((e[['boundary_loss_CB','direction_loss_CB','height_loss_CB']].min(axis=1)<-1e-10)&(e[['boundary_loss_CB','direction_loss_CB','height_loss_CB']].max(axis=1)>1e-10)).astype(float),np.nan)
    for threshold in [90,95]:e['all_Q_at_least_'+str(threshold)]=np.where(ok,e[[a+'__B8L2' for a in 'ABC']].min(axis=1).ge(threshold).astype(float),np.nan)
    for met in ['B8L2','D10']:
        e[met+'_within']=e[met+'_BA'].abs().where(ok)
        e[met+'_cross_direct']=e[met+'_CA'].abs().where(ok)
        e[met+'_cross_symmetric']=((e[met+'_CA'].abs()+e[met+'_CB'].abs())/2).where(ok)
    nums=[x for x in e.select_dtypes(include=['number','bool']) if x not in ['n','m','pool_n']]
    images=aggregate(e,nums)
    images['nonpositive_same_origin']=images.gap_A.le(0)
    images['nonpositive_symmetric']=images.gap_sym.le(0)
    images['C_not_better_than_B']=images.CB.le(0)
    images['no_joint_Q']=images.gap_A.isna()
    images['numerical_exception_union']=images[['nonpositive_same_origin','nonpositive_symmetric','C_not_better_than_B','no_joint_Q']].any(axis=1)
    unavailable=e.groupby(['n','image']).gap_A.apply(lambda x:x.isna().any()).rename('some_events_unscorable').reset_index()
    images=images.merge(unavailable,on=['n','image'],validate='one_to_one')
    images['partial_event_status_only']=images.some_events_unscorable & ~images.numerical_exception_union
    images['any_requested_exception']=images.numerical_exception_union|images.some_events_unscorable
    counts=e.groupby(['n','image']).size().rename('registered_events').reset_index()
    images=images.merge(counts,on=['n','image'],validate='one_to_one')
    save(images,'ALL_IMAGE_RESULTS.csv.gz')
    save(images[(images.n==14)&images.numerical_exception_union],'LATEST_HALF_NUMERIC_EXCEPTION_UNION_32.csv')
    save(images[(images.n==14)&images.any_requested_exception],'LATEST_HALF_ALL_EXCEPTION_IMAGES.csv')
    save(images[(images.n==14)&images.nonpositive_symmetric],'LATEST_HALF_SYMMETRIC_NONPOSITIVE_21.csv')
    save(e,'EVENTS_WITH_ENDPOINTS.csv.gz')
    ex=set(images.loc[(images.n==14)&images.any_requested_exception,'image'])
    case_events=e[e.image.isin(ex)].copy()
    save(case_events,'ALL_EXCEPTION_EVENTS_AND_20_7_CONTEXT.csv.gz')
    needed={r[a+'_team_key'] for r in case_events.to_dict('records') for a in 'ABC'}
    t=pd.DataFrame(teams.values());t['mechanism_required']=t.team_key.isin(needed);save(t,'TEAM_REQUESTS.csv')
    # Exact X/Y/Z identity links, retaining added/replaced D and source stage.
    idcols=['pool_id','X','Y','Z'];a=e[e.n==14];b=e[e.n==20]
    links=a.merge(b,on=idcols,suffixes=('_14','_20'))
    rows=[]
    for r in links.to_dict('records'):
        d14=members(r['D_14']);d20=members(r['D_20'])
        q={k:r[k] for k in idcols}
        q.update({k:r[k] for k in ['event_id_14','event_id_20','image_14','building_14','D_14','D_20','source_stage_14','source_stage_20']})
        q.update(D14_subset_D20=d14<=d20,D_added='|'.join(sorted(d20-d14)),D_removed='|'.join(sorted(d14-d20)),D_shared=len(d14&d20),change_identification='same exact X/Y/Z; total n, actual background and MV50 threshold change jointly')
        for col in ['gap_A','gap_sym','CB','B8L2_within','B8L2_cross_direct','B8L2_cross_symmetric']:
            q[col+'_14']=r[col+'_14'];q[col+'_20']=r[col+'_20'];q[col+'_20_minus_14']=r[col+'_20']-r[col+'_14']
        rows.append(q)
    save(pd.DataFrame(rows),'EXACT_XYZ_14_7_TO_20_7.csv')
    summaries=[]
    for n,g in images.groupby('n'):
        z=dict(n=int(n),m=7,registered_images=len(g),buildings=g.building.nunique(),events=int(g.registered_events.sum()))
        for c in ['gap_A','gap_sym','CB']:
            x=g[c].dropna();z.update({c+'_valid_images':len(x),c+'_mean':x.mean(),c+'_median':x.median(),c+'_p10':x.quantile(.1),c+'_positive_images':int(x.gt(0).sum()),c+'_nonpositive_images':int(x.le(0).sum())})
        z['all_exception_images']=int(g.any_requested_exception.sum());summaries.append(z)
    save(pd.DataFrame(summaries),'MAIN_CHECKED_SUMMARY.csv')
    save(pd.DataFrame(parity),'EVENT_SCALAR_PARITY.csv')
    (OUT/'SOURCE_AND_CHECKS.json').write_text(json.dumps({'source_commit':'13a7861334749805a86dc19e9ea79fcaa71020c0','latest_event_table_rows':len(e),'unique_teams':len(teams),'all_exception_half_images':len(ex),'mechanism_requested_teams':len(needed),'exact_XYZ_context_pairs':len(links),'new_physical_teams':0,'classification_selection':'undecided; frozen labels are working analysis objects','sources':source_receipts},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summaries,ensure_ascii=False));print('exception images',len(ex),'trace requests',len(needed),'exact XYZ contexts',len(links))

if __name__=='__main__':main()
