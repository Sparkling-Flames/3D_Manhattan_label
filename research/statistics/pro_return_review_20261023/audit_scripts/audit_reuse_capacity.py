from pathlib import Path
import itertools,json,sys
import numpy as np
import pandas as pd
ROOT=Path(sys.argv[1])
p=pd.read_csv(ROOT/'design/PANELS.csv');l=pd.read_csv(ROOT/'design/PANEL_TEAM_LINKS.csv.gz')
lab=pd.read_csv(ROOT/'results/taxonomy_response/inputs/LABELS_AND_HISTORIES_REQUIRED.csv.gz')
lab=lab[(lab.condition=='manual')&(lab.method=='V3_BEHAVIOR')]
lookup={(r.heldout_building,r.worker_id):r.coarse_label if r.known else 'unknown' for r in lab.itertuples()}
pm=p.set_index('panel_id')
cache={};n=0
for r in l.itertuples():
    pp=pm.loc[r.panel_id];key=(pp.building,r.member_set_key)
    if key not in cache:
        counts={}
        for w in r.member_set_key.split('|'):
            label=lookup[(pp.building,w)];counts[label]=counts.get(label,0)+1
        cache[key]=counts
    assert cache[key]==json.loads(r.structure_vector)
    n+=1
for pp in p.itertuples():
    z=l[l.panel_id==pp.panel_id]
    cand=pp.candidates.split('|');core=set(str(pp.core).split('|')) if pd.notna(pp.core) else set()
    assert len(z)==len(set(z.member_set_key))==pp.n_finite_teams
    assert set(z.selected)==set('|'.join(c) for c in itertools.combinations(sorted(cand),pp.k_selected))
    assert all(set(r.member_set_key.split('|'))==core|set(r.selected.split('|')) for r in z.itertuples())

# Search already computed exact teams across candidate panels at the same n.
# No endpoint creation or new fusion is involved.
rows=[]; examples=[]; triples=[]
ep=pd.concat([pd.read_csv(f,float_precision='round_trip') for f in sorted((ROOT/'results/native/parts').glob('*.csv.gz'))]).set_index('team_key')
centers={}
for pp in p.itertuples():
    centers[(pp.building,pp.class_lo)]=pp.turn_center_lo
    centers[(pp.building,pp.class_hi)]=pp.turn_center_hi
effect_rows=[]
ordinary=p[p.ordinary_comparable]
pl=l.merge(ordinary[['panel_id','pair_key','building','groups','n']],on='panel_id')
for (pair,n),g in pl.groupby(['pair_key','n']):
    g=g.drop_duplicates('member_set_key').reset_index(drop=True)
    if len(g)<2 or n<=4:continue
    workers=sorted(set('|'.join(g.member_set_key).split('|')));wi={w:i for i,w in enumerate(workers)}
    masks=np.array([sum(1<<wi[w] for w in s.split('|')) for s in g.member_set_key],dtype=np.int64)
    classes=sorted(set(c for d in g.structure_vector for c in json.loads(d)))
    vec=np.array([[json.loads(d).get(c,0) for c in classes] for d in g.structure_vector])
    i,j=np.triu_indices(len(g),1)
    m=np.array([int(v).bit_count()//2 for v in masks[i]^masks[j]])
    use=m>4;i=i[use];j=j[use];m=m[use]
    delta=vec[j]-vec[i]
    changed=np.abs(delta).sum(axis=1)//2
    pure=(changed==m)&((delta>0).sum(axis=1)==1)&((delta<0).sum(axis=1)==1)
    same=changed==0
    for ai,ci,mm in zip(i[pure],j[pure],m[pure]):
        for ai,ci in [(ai,ci),(ci,ai)]:
            retained=masks[ai]&masks[ci]
            valid=(masks&masks[ai]==retained)&(masks&masks[ci]==retained)&(vec==vec[ai]).all(axis=1)
            for bi in np.flatnonzero(valid):
                triples.append({'pair_key':pair,'building':g.building.iloc[0],'n':int(n),'m':int(mm),'members_A':g.iloc[ai].member_set_key,'members_B':g.iloc[bi].member_set_key,'members_C':g.iloc[ci].member_set_key})
    for kind,sel in [('pure_class_block',pure),('same_composition',same)]:
        for mm in sorted(set(m[sel])):
            sel2=sel&(m==mm)
            rows.append({'pair_key':pair,'building':g.building.iloc[0],'groups':g.groups.iloc[0],'n':int(n),'m':int(mm),'kind':kind,'events':int(sel2.sum())})
            a,b=i[sel2][0],j[sel2][0]
            examples.append({'pair_key':pair,'building':g.building.iloc[0],'n':int(n),'m':int(mm),'kind':kind,'members_a':g.iloc[a].member_set_key,'members_b':g.iloc[b].member_set_key,'panel_a':g.iloc[a].panel_id,'panel_b':g.iloc[b].panel_id,'team_a_view_a':g.iloc[a].team_key_a,'team_a_view_b':g.iloc[a].team_key_b,'team_b_view_a':g.iloc[b].team_key_a,'team_b_view_b':g.iloc[b].team_key_b})
            src=i[sel2].copy();dst=j[sel2].copy()
            if kind=='pure_class_block':
                direction=(vec[dst]-vec[src])@np.array([centers[(g.building.iloc[0],c)] for c in classes])
                rev=direction<0;src,dst=np.where(rev,dst,src),np.where(rev,src,dst)
            base={'pair_key':pair,'building':g.building.iloc[0],'groups':g.groups.iloc[0],'n':int(n),'m':int(mm),'kind':kind,'events':len(src)}
            q=[];turn=[];failed=[]
            for side in ['a','b']:
                old=ep.loc[g.iloc[src]['team_key_'+side]];new=ep.loc[g.iloc[dst]['team_key_'+side]]
                q.append(new.B8L2.to_numpy()-old.B8L2.to_numpy())
                turn.append(new.fusion_turn_n.to_numpy()-old.fusion_turn_n.to_numpy())
                failed.append((~old.complete_evaluable.to_numpy(bool),~new.complete_evaluable.to_numpy(bool)))
            q=np.array(q).T;turn=np.array(turn).T;qok=np.isfinite(q).all(axis=1);tok=np.isfinite(turn).all(axis=1)
            base.update(q_valid=int(qok.sum()),turn_valid=int(tok.sum()),q_coverage=qok.mean(),turn_coverage=tok.mean(),
                any_of_four_failed=np.mean(failed[0][0]|failed[0][1]|failed[1][0]|failed[1][1]),
                failure_before=np.mean(np.r_[failed[0][0],failed[1][0]]),failure_after=np.mean(np.r_[failed[0][1],failed[1][1]]),
                new_failure=np.mean(np.r_[~failed[0][0]&failed[0][1],~failed[1][0]&failed[1][1]]),
                recovered_failure=np.mean(np.r_[failed[0][0]&~failed[0][1],failed[1][0]&~failed[1][1]]))
            if qok.any():
                z=q[qok];s=np.where(z>2,1,np.where(z< -2,-1,0))
                base.update(q_mean_delta=np.mean(z) if kind=='pure_class_block' else np.nan,q_mean_abs_delta=np.mean(abs(z)),q_view_gap=np.mean(abs(z[:,0]-z[:,1])),
                    q_both_up=np.mean((s[:,0]>0)&(s[:,1]>0)),q_both_down=np.mean((s[:,0]<0)&(s[:,1]<0)),
                    q_same_nonzero=np.mean((s[:,0]*s[:,1])>0),q_opposite=np.mean(s[:,0]*s[:,1]<0),q_both_small=np.mean((s==0).all(axis=1)),q_one_small=np.mean((s==0).sum(axis=1)==1))
            if tok.any():
                z=turn[tok];s=np.sign(z)
                base.update(turn_mean_delta=np.mean(z) if kind=='pure_class_block' else np.nan,turn_mean_abs_delta=np.mean(abs(z)),
                    turn_both_zero=np.mean((s==0).all(axis=1)),turn_same_nonzero=np.mean(s[:,0]*s[:,1]>0),turn_opposite=np.mean(s[:,0]*s[:,1]<0),turn_one_zero=np.mean((s==0).sum(axis=1)==1))
            if qok.any():assert abs(sum(base[c] for c in ['q_same_nonzero','q_opposite','q_both_small','q_one_small'])-1)<1e-10
            if tok.any():assert abs(sum(base[c] for c in ['turn_both_zero','turn_same_nonzero','turn_opposite','turn_one_zero'])-1)<1e-10
            assert abs(base['failure_after']-base['failure_before']-base['new_failure']+base['recovered_failure'])<1e-10
            effect_rows.append(base)
r=pd.DataFrame(rows);e=pd.DataFrame(examples)
r.to_csv(ROOT/'INDEPENDENT_EXISTING_LARGE_BLOCK_COUNTS.csv',index=False)
e.to_csv(ROOT/'INDEPENDENT_EXISTING_LARGE_BLOCK_EXAMPLES.csv',index=False)
t=pd.DataFrame(triples);t.to_csv(ROOT/'INDEPENDENT_EXISTING_LARGE_BLOCK_ABC.csv',index=False)
result={'verified_structure_vector_links':len(l),'verified_complete_panels':len(p),'existing_large_block_support':[]}
result['strict_abc_with_disjoint_blocks']={'events':len(t),'pairs':int(t.pair_key.nunique()) if len(t) else 0,'buildings':int(t.building.nunique()) if len(t) else 0}
eff=pd.DataFrame(effect_rows);eff.to_csv(ROOT/'INDEPENDENT_EXISTING_LARGE_BLOCK_EFFECTS_BY_PAIR_N_M.csv',index=False)
effect_summaries=[]
for kind,z0 in eff.groupby('kind'):
    for mm in ['all']+sorted(set(z0.m)):
        z=z0 if mm=='all' else z0[z0.m==mm]
        nums=[c for c in z if c not in ['pair_key','building','groups','n','m','kind','events','q_valid','turn_valid']]
        pairframe=z.groupby(['pair_key','building','groups'])[nums].mean().reset_index()
        group=pairframe.assign(group_id=pairframe.groups.str.split('|')).explode('group_id').groupby(['building','group_id'])[nums].mean().reset_index()
        summ=group.groupby('building')[nums].mean().mean().to_dict()
        effect_summaries.append({'kind':kind,'m':mm,'pairs':z.pair_key.nunique(),'buildings':z.building.nunique(),'groups':group.group_id.nunique(),'events':int(z.events.sum()),'q_valid_events':int(z.q_valid.sum()),'turn_valid_events':int(z.turn_valid.sum()),**summ})
es=pd.DataFrame(effect_summaries);es.to_csv(ROOT/'INDEPENDENT_EXISTING_LARGE_BLOCK_EFFECTS_SUMMARY.csv',index=False)
result['exploratory_large_block_effects']=json.loads(es.to_json(orient='records',force_ascii=False))
if len(r):
    for kind,z in r.groupby('kind'):
        result['existing_large_block_support'].append({'kind':kind,'pairs':int(z.pair_key.nunique()),'buildings':int(z.building.nunique()),'events':int(z.events.sum()),'m_min':int(z.m.min()),'m_max':int(z.m.max()),'n_min':int(z.n.min()),'n_max':int(z.n.max())})
(ROOT/'INDEPENDENT_REUSE_CAPACITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
