"""已验收标签的下游接续；不重新验包、拟合、评分或融合。"""
from pathlib import Path
from collections import Counter
import json
import pandas as pd
from tools.thesis_main.analysis import reaggregate_v21_same_room_oppjoint_fixed_panels_20261029 as sr

ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research/workers/personnel_v21_reselection_20261029'
OUT=ROOT/'research/data/releases/v2.1/final_classification_downstream'
METHODS=['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','RFUSE_GEOM_K2']

def source_table(stage, suffix):
    return pd.read_csv(OUT/'sources'/stage/suffix,low_memory=False)

def save(d,name):
    d.to_csv(OUT/name,index=False,encoding='utf-8-sig')

def members(v):
    return set() if pd.isna(v) or not v else set(v.split('|'))

def classify_blocks(x,y,z,roster):
    a={roster.get(w) for w in x|y};b={roster.get(w) for w in z}
    if None in a|b: return '冻结历史对照','unknown_label'
    if len(a)==1 and len(b)==1 and a!=b: return '当前适用','homogeneous_distinct_blocks'
    return '需改解释','mixed_or_same_class_blocks'

def image_summary(d):
    cols=['gap_A','gap_sym','CB']
    background=d.groupby(['building','image','pool_id','block_id','background_id'],dropna=False)[cols].mean()
    block=background.groupby(level=['building','image','pool_id','block_id']).mean()
    im=block.groupby(level=['building','image','pool_id']).mean().groupby(level=['building','image']).mean()
    valid=im.gap_A.notna()
    return dict(events=len(d),registered_images=len(im),valid_images=int(valid.sum()),buildings=int(im[valid].index.get_level_values('building').nunique()),
                gap_A=im.gap_A.mean(),gap_sym=im.gap_sym.mean(),CB=im.CB.mean(),CB_valid_images=int(im.CB.notna().sum()),positive_A=int(im.gap_A.gt(0).sum()),positive_sym=int(im.gap_sym.gt(0).sum()),
                support_state='有支持' if valid.any() else '无剩余支持，不能识别独立作用')

def adopted_conditions(events):
    return pd.DataFrame([dict(method='TARGET_DSTRUCT_K3',scope='primary',n=int(n),m=7,
        axis='hard_turn_rank_asc',rank_direction='2/3->3/3',images=g.image.nunique(),
        ABC_scored_events=int(g.gap_A.notna().sum()),B8L2_CB_valid_images=image_summary(g)['CB_valid_images'],
        **image_summary(g)) for n,g in events.groupby('n')])

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    frozen=source_table('stage03_completed_ABC','FROZEN_LABELS_ALL_LOBO.csv.gz')
    prior=pd.read_csv(BASE/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    labels=pd.concat([frozen[frozen.method.eq('TARGET_DSTRUCT_K3')],prior[prior.method.isin(['TARGET_DSTRUCT_K2','RFUSE_GEOM_K2'])]],ignore_index=True)
    labels=labels[labels.heldout_building.ne('ALL')]
    labels['known']=sr.as_bool(labels.known)
    assert labels.loc[labels.known,'class_id'].notna().all()
    assert not labels.duplicated(['method','heldout_building','worker_id']).any()
    save(labels,'USED_FINAL_LOBO_LABELS.csv.gz')
    roster={(m,b):dict(zip(g.loc[g.known,'worker_id'],g.loc[g.known,'class_id'])) for (m,b),g in labels.groupby(['method','heldout_building'])}
    # K2旧45法为本次保留粗层；先检查它与最终K3确实在每折嵌套。
    a=labels[labels.method.eq('TARGET_DSTRUCT_K2')];b=labels[labels.method.eq('TARGET_DSTRUCT_K3')]
    join=a.merge(b,on=['heldout_building','worker_id'],suffixes=('_2','_3'))
    assert (join.known_2==join.known_3).all()
    assert join[join.known_2].groupby(['heldout_building','class_id_3']).class_id_2.nunique().eq(1).all()
    panels=sr.load_engine().annotate_budget(pd.read_csv(sr.DESIGN/'PANELS.csv'))
    for c in ['ordinary_comparable','scope_comparable']: panels[c]=sr.as_bool(panels[c])
    links=pd.read_csv(sr.DESIGN/'PANEL_TEAM_LINKS.csv.gz');ep=pd.read_csv(sr.ENDPOINTS,low_memory=False)
    all_summary=[]
    for method in METHODS:
        sr.METHODS=(method,);engine=sr.load_engine();annotated=links.copy();vectors=[];known=[]
        pm=panels.set_index('panel_id')
        for r in links.itertuples():
            meta=pm.loc[r.panel_id];ws=members(r.member_set_key);assert len(ws)==meta.n
            c=Counter(roster[(method,meta.building)].get(w,'unknown') for w in ws)
            vectors.append(json.dumps(dict(sorted(c.items())),separators=(',',':')));known.append('unknown' not in c)
        annotated[method+'_vector']=vectors;annotated[method+'_all_known']=known;annotated['both_methods_all_known']=known
        paired=sr.join_endpoints(panels,annotated,ep,engine.METRICS)
        moments,support=sr.summarize(panels,paired,engine)
        save(annotated,method+'_TEAM_COMPOSITIONS.csv.gz');save(support,method+'_SUPPORT.csv')
        save(moments,method+'_PANEL_DECOMPOSITION.csv.gz')
        for name,frame in zip(['PAIR','GROUP','BUILDING','SUMMARY'],sr.aggregate(moments,engine)):
            save(frame,method+'_'+name+'.csv')
            if name=='SUMMARY':all_summary.append(frame)
    save(pd.concat(all_summary),'SAME_ROOM_SUMMARY.csv')
    # 已展示的v2.1旧分类重点与同房ABC；保留旧事件，不修改其源标签。
    inventories={'previous_focus':BASE/'experiment/focused_design/EVENTS_EXACT.csv.gz',
                 'same_room':sr.RELEASE/'same_room_current_large_design/STRICT_ABC_EVENTS.csv.gz'}
    pools={}
    for p in [sr.RELEASE/'pools/INPUT_SNAPSHOT.json',sr.RELEASE/'admitted_space_extension/pools/INPUT_SNAPSHOT.json']:
        pools.update({x['pool_id']:x for x in json.loads(p.read_text(encoding='utf-8'))['images']})
    audit=[]
    for stage,path in inventories.items():
        d=pd.read_csv(path,low_memory=False)
        for r in d.to_dict('records'):
            blocks=[members(r[c+('_members' if stage=='same_room' else '')]) for c in ['D','X','Y','Z']]
            allw=set.union(*blocks)
            refok=True
            for side in (['_a','_b'] if stage=='same_room' else ['']):
                pool=pools.get(r['pool_id'+side]);meta=pool['meta'] if pool else {}
                refok &= bool(pool) and allw<={v['worker_id'] for v in pool['records']} and meta.get('reference_id')==r['reference_id'+side]
            for method in METHODS:
                status,reason=classify_blocks(*blocks[1:],roster[(method,r['building'])])
                if not refok:status,reason='需改解释','pool_or_reference_mismatch'
                lm=roster[(method,r['building'])]
                audit.append(dict(stage=stage,event_id=r['event_id'],old_method=r['method'],final_method=method,building=r['building'],n=r['n'],m=r['m'],
                    status=status,reason=reason,reference_valid=refok,source_labels='|'.join(sorted({str(lm.get(w,'unknown')) for w in blocks[1]|blocks[2]})),target_labels='|'.join(sorted({str(lm.get(w,'unknown')) for w in blocks[3]}))))
    au=pd.DataFrame(audit);save(au,'OLD_ABC_APPLICABILITY.csv.gz')
    save(au.groupby(['stage','final_method','status','reason'],dropna=False).size().rename('events').reset_index(),'OLD_ABC_COUNTS.csv')
    # 接受审查后的综合事件，只做主方向删样本敏感性。
    u=source_table('stage02_comparison','COMBINED_UNION_EVENTS_WITH_ROLES.csv.gz')
    u=u[(u.method=='TARGET_DSTRUCT_K3')&(u.scope=='primary')&(u.rank_direction=='2/3->3/3')&(u.axis=='hard_turn_rank_asc')&(u.m==7)&u.n.isin([14,20])].copy()
    team={}
    for path in [BASE/'additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz']+list((BASE/'experiment').glob('*_design/EVENTS_EXACT.csv.gz')):
        dd=pd.read_csv(path,usecols=lambda c:c.endswith('_team_key') or c.endswith('_members'),low_memory=False)
        for arm in 'ABC':
            if arm+'_members' in dd:team.update(dict(zip(dd[arm+'_team_key'],dd[arm+'_members'])))
    for arm in 'ABC':u[arm+'_members']=u[arm+'_members'].fillna(u[arm+'_team_key'].map(team))
    assert u[[a+'_members' for a in 'ABC']].notna().all().all()
    for i,r in u.iterrows():
        a,b,c=[members(r[x+'_members']) for x in 'ABC'];bg=a&b;x=a-bg;y=b-bg;z=c-bg
        assert len(bg)==r.n-r.m and len(x)==len(y)==len(z)==r.m and not (x&z or y&z)
        for k,ws in zip(['D','X','Y','Z'],[bg,x,y,z]):u.loc[i,k]='|'.join(sorted(ws))
    ok=u[['B8L2_BA','B8L2_CA','B8L2_CB']].notna().all(axis=1)
    u['gap_A']=(u.B8L2_CA.abs()-u.B8L2_BA.abs()).where(ok)
    u['gap_sym']=((u.B8L2_CA.abs()+u.B8L2_CB.abs())/2-u.B8L2_BA.abs()).where(ok);u['CB']=u.B8L2_CB
    save(u,'TARGET_MAIN_EVENTS.csv.gz');rows=[];coverage=[]
    for n,g in u.groupby('n'):
        rows.append(dict(n=n,omit_type='none',omit_id='',**image_summary(g)))
        g=g.copy()
        g['XY']=g.X+'|'+g.Y
        g['any']=g.D+'|'+g.X+'|'+g.Y+'|'+g.Z
        for role in ['D','X','Y','Z','XY','any']:
            for w in sorted(set.union(*(members(v) for v in g[role]))):
                mask=g[role].map(lambda v:w in members(v))
                coverage.append(dict(n=n,role=role,worker=w,events=int(mask.sum()),event_fraction=float(mask.mean()),images=g.loc[mask,'image'].nunique(),blocks=g.loc[mask,'block_id'].nunique(),backgrounds=g.loc[mask,'background_id'].nunique(),buildings=g.loc[mask,'building'].nunique()))
                remaining=g[~mask]
                matched=g[g.image.isin(remaining.image)]
                rows.append(dict(n=n,omit_type='member_'+role,omit_id=w,baseline_remaining_images_gap_A=image_summary(matched)['gap_A'],**image_summary(remaining)))
        for field in ['block_id','background_id','building']:
            for value in g[field].dropna().unique():rows.append(dict(n=n,omit_type=field,omit_id=value,**image_summary(g[g[field]!=value])))
    save(pd.DataFrame(rows),'SENSITIVITY.csv');save(pd.DataFrame(coverage),'MEMBER_COVERAGE.csv')
    save(adopted_conditions(u),'ADOPTED_CONDITIONS.csv')
    (OUT/'CHECKS.json').write_text(json.dumps(dict(methods=METHODS,panels=len(panels),paired_team_rows=len(links),abc_classifications=len(au),main_events=len(u),
        new_fusion=0,new_fit=0,new_scores=0,same_room_support='each method known teams separately; not matched method comparison',
        sensitivity='omit saved events containing role member / block / background / building; not remove a person and re-fuse',
        source='accepted reaudit README section 8; final K3 stage03; retained K2/RFUSE prior labels; nesting verified'),ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
