"""All exact member replacements across paired finite room-view panels.

Every finite panel is exhaustively contrasted. Output is sufficient stratum
statistics plus deterministically reconstructible endpoint/mask keys, rather
than millions of duplicate geometries. Target values never select teams.
"""
from pathlib import Path
import argparse, gzip, json, math, collections, hashlib, warnings, os
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

METRICS = ['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n',
           'S_bottom_deg','dir','Hmean','Hcenter','height_mean_ratio','iou_2d','IoU3D100',
           'omission','extension','ref_node_recall_5','ref_edge_recall_5',
           'diag_corner_recall_05','diag_wall_coverage_05','geometry_area_h2',
           'recorded_time_total_seconds','log_recorded_time']
EPS = {'B8L2':2.,'D10':2.,'nodes':0.,'fusion_turn_n':0.,'fusion_short_turn_edges':0.,'fusion_redundancy_n':0.,
       'S_bottom_deg':.1,'dir':.2,'Hmean':.02,'Hcenter':.02,'height_mean_ratio':.02,
       'iou_2d':.02,'IoU3D100':2.,'omission':.02,'extension':.02,'ref_node_recall_5':.01,
       'ref_edge_recall_5':.01,'diag_corner_recall_05':.01,'diag_wall_coverage_05':.02,
       'geometry_area_h2':.05,'recorded_time_total_seconds':5.,'log_recorded_time':np.log(1.05)}
ANALYSIS_VERSION = 'SRCC23_exact_changes_v2_symmetric_source'


def analysis_subsets(d):
    door=d.layer_a.astype(str).str.contains('doorway')|d.layer_b.astype(str).str.contains('doorway')
    ordinary=d.ordinary_comparable.astype(bool)
    scope=d.scope_comparable.astype(bool)
    return [('ordinary_mid',d[ordinary&(d.n==d.mid_n)&(d.replicate==0)]),
            ('ordinary_all_n',d[ordinary]),
            ('doorway_involved',d[~ordinary&door]),
            ('scope_different',d[~ordinary&~door&~scope]),
            ('other_adoption_state',d[~ordinary&~door&scope])]


def finite(x):
    return x is not None and isinstance(x,(int,float,np.integer,np.floating)) and np.isfinite(x)


def atomic_csv(path, frame):
    tmp=path.with_name(path.name+'.tmp')
    raw=frame.to_csv(index=False).encode()
    tmp.write_bytes(gzip.compress(raw,mtime=0))
    os.replace(tmp,path)


def read_pool(native, pool):
    path=native/'pools'/(pool+'.json.gz')
    if not path.exists(): return {}
    with gzip.open(path,'rt') as f: obj=json.load(f)
    rows={r['team_key']:r for r in obj['teams']}
    for r in rows.values():
        t=r.get('recorded_time_total_seconds')
        r['log_recorded_time']=math.log(t) if finite(t) and t>0 else None
    return rows


def state_rates(a,b,eps):
    sa=np.where(a>eps,1,np.where(a < -eps,-1,0)); sb=np.where(b>eps,1,np.where(b < -eps,-1,0))
    symmetric_source_n=int(np.sum(sa!=0)+np.sum(sb!=0))
    nonzero_same=int(np.sum((sa==sb)&(sa!=0)))
    return {
      'both_small':float(np.mean((sa==0)&(sb==0))),
      'both_positive':float(np.mean((sa==1)&(sb==1))),
      'both_negative':float(np.mean((sa==-1)&(sb==-1))),
      'both_nonzero_same':float(np.mean((sa==sb)&(sa!=0))),
      'opposite':float(np.mean((sa*sb)==-1)),
      'one_small':float(np.mean((sa==0)^(sb==0))),
      'source_positive_target_positive':float(np.mean(sb[sa>0]>0)) if np.any(sa>0) else np.nan,
      'source_negative_target_negative':float(np.mean(sb[sa<0]<0)) if np.any(sa<0) else np.nan,
      'source_nonsmall_n':int(np.sum(sa!=0)),
      'source_nonsmall_target_same':float(np.mean(sb[sa!=0]==sa[sa!=0])) if np.any(sa!=0) else np.nan,
      'both_nonsmall_n':int(np.sum((sa!=0)&(sb!=0))),
      'both_nonsmall_same':float(np.mean(sa[(sa!=0)&(sb!=0)]==sb[(sa!=0)&(sb!=0)])) if np.any((sa!=0)&(sb!=0)) else np.nan,
      'symmetric_source_trigger_n':symmetric_source_n,
      'symmetric_source_trigger_same':2*nonzero_same/symmetric_source_n if symmetric_source_n else np.nan,
      'symmetric_source_trigger_opposite':2*int(np.sum(sa*sb<0))/symmetric_source_n if symmetric_source_n else np.nan,
    }


def summarize_panel(panel, links, pools):
    links=links.sort_values('selected_mask').reset_index(drop=True)
    keys_a=links.team_key_a.tolist();keys_b=links.team_key_b.tolist()
    if not all(k in pools[0] for k in keys_a) or not all(k in pools[1] for k in keys_b): return None
    records=[[pools[side][k] for k in keys] for side,keys in [(0,keys_a),(1,keys_b)]]
    arrays={m:[np.array([r.get(m) if finite(r.get(m)) else np.nan for r in rr],float) for rr in records] for m in METRICS}
    count=len(links);ii,jj=np.triu_indices(count,1)
    h=links.hi_selected.to_numpy(int);masks=links.selected_mask.to_numpy(int)
    rev=h[jj]<h[ii];i=np.where(rev,jj,ii);j=np.where(rev,ii,jj)
    actual_m=np.array([(int(a)^int(b)).bit_count()//2 for a,b in zip(masks[i],masks[j])])
    r=h[j]-h[i]
    d={m:[v[j]-v[i] for v in av] for m,av in arrays.items()}
    complete=[np.array([bool(z.get('complete_evaluable')) for z in rr],bool) for rr in records]
    full_four=complete[0][i]&complete[0][j]&complete[1][i]&complete[1][j]
    results=[]
    for mm,rr in sorted(set(zip(actual_m,r))):
        use=(actual_m==mm)&(r==rr)
        row={'panel_id':panel.panel_id,'m':int(mm),'r':int(rr),'kind':'same_composition' if rr==0 else ('pure_class_block' if rr==mm else 'mixed_class_block'),
             'contrasts':int(use.sum()),'four_complete_n':int(full_four[use].sum()),'four_complete_rate':float(full_four[use].mean())}
        for side,cc in zip(['a','b'],complete):
            row['valid_gain_'+side]=float(np.mean((~cc[i[use]])&cc[j[use]]))
            row['valid_loss_'+side]=float(np.mean(cc[i[use]]&(~cc[j[use]])))
            row['both_failed_'+side]=float(np.mean((~cc[i[use]])&(~cc[j[use]])))
        for metric,(da,db) in d.items():
            good=use&np.isfinite(da)&np.isfinite(db)
            prefix=metric+'__';row[prefix+'n']=int(good.sum())
            if not good.any():continue
            x,y=da[good],db[good]
            row.update({prefix+'mean_a':float(x.mean()),prefix+'mean_b':float(y.mean()),
                        prefix+'mean_abs_a':float(np.mean(np.abs(x))),prefix+'mean_abs_b':float(np.mean(np.abs(y))),
                        prefix+'view_gap_mean':float(np.mean(np.abs(x-y))),prefix+'view_gap_p90':float(np.quantile(np.abs(x-y),.9)),
                        prefix+'sign_agreement_zero_included':float(np.mean(np.sign(x)==np.sign(y)))})
            row.update({prefix+k:v for k,v in state_rates(x,y,EPS[metric]).items()})
            if metric in ('B8L2','D10'):
                for eps in (0.,1.,5.):
                    row.update({prefix+'eps'+str(int(eps))+'_'+k:v for k,v in state_rates(x,y,eps).items()})
                row[prefix+'copy_source_mae']=float(np.mean(np.abs(y-x)))
                row[prefix+'zero_effect_mae']=float(np.mean(np.abs(y)))
                row[prefix+'symmetric_zero_effect_mae']=float(np.mean((np.abs(x)+np.abs(y))/2))
                g=np.abs(x)>EPS[metric]
                row[prefix+'source_trigger_n']=int(g.sum())
                if g.any():
                    row[prefix+'source_trigger_copy_mae']=float(np.mean(np.abs(y[g]-x[g])))
                    row[prefix+'source_trigger_zero_mae']=float(np.mean(np.abs(y[g])))
                gb=np.abs(y)>EPS[metric]
                if g.sum()+gb.sum():
                    row[prefix+'symmetric_source_trigger_copy_mae']=float((np.abs(y[g]-x[g]).sum()+np.abs(y[gb]-x[gb]).sum())/(g.sum()+gb.sum()))
                    row[prefix+'symmetric_source_trigger_zero_mae']=float((np.abs(y[g]).sum()+np.abs(x[gb]).sum())/(g.sum()+gb.sum()))
            if metric in ('B8L2','fusion_turn_n','dir','log_recorded_time'):
                row[prefix+'correlation']=float(np.corrcoef(x,y)[0,1]) if len(x)>2 and np.std(x)>1e-12 and np.std(y)>1e-12 else np.nan
        # Explicit structure--quality cross-table. Structure is effective turn
        # count, not raw annotation count or assumed shared physical vertices.
        qa,qb=d['B8L2'];ta,tb=d['fusion_turn_n'];na,nb=d['nodes']
        good=use&np.isfinite(qa)&np.isfinite(qb)&np.isfinite(ta)&np.isfinite(tb)
        row['structure_quality_n']=int(good.sum())
        if good.any():
            qop=(qa*qb<0)&(np.abs(qa)>2)&(np.abs(qb)>2)
            same_structure=(ta==tb)&(ta!=0)
            row['same_nonzero_turn_step_q_opposite']=float(np.mean((same_structure&qop)[good]))
            row['zero_turn_step_q_opposite']=float(np.mean(((ta==0)&(tb==0)&qop)[good]))
            row['turn_step_opposite']=float(np.mean((ta*tb<0)[good]))
            row['same_nonzero_turn_step_n']=int(np.sum(good&same_structure))
            row['same_nonzero_turn_step_q_opposite_conditional']=float(np.mean(qop[good&same_structure])) if np.any(good&same_structure) else np.nan
            row['zero_node_step_q_opposite']=float(np.mean(((na==0)&(nb==0)&qop)[good]))
        results.append(row)
    # Save a modest, reproducible mechanism search index. Ranking is discovery,
    # not independent validation or an estimate of incidence.
    candidates=[]
    qa,qb=d['B8L2'];ta,tb=d['fusion_turn_n'];na,nb=d['nodes']
    good=np.isfinite(qa)&np.isfinite(qb)&np.isfinite(ta)&np.isfinite(tb)&(r>0)
    patterns={
       'same_nonzero_structure_quality_opposite':good&(ta==tb)&(ta!=0)&(qa*qb<0)&(np.abs(qa)>2)&(np.abs(qb)>2),
       'same_nonzero_structure_both_quality_gain':good&(ta==tb)&(ta!=0)&(qa>2)&(qb>2),
       'same_nonzero_structure_both_quality_loss':good&(ta==tb)&(ta!=0)&(qa< -2)&(qb< -2),
       'zero_structure_quality_opposite':good&(ta==0)&(tb==0)&(qa*qb<0)&(np.abs(qa)>5)&(np.abs(qb)>5),
       'one_structure_quality_opposite':good&((ta==0)^(tb==0))&(qa*qb<0)&(np.abs(qa)>2)&(np.abs(qb)>2),
       'both_quality_stable':good&(np.abs(qa)<.1)&(np.abs(qb)<.1),
    }
    for pattern,mask in patterns.items():
        inds=np.flatnonzero(mask)
        if not len(inds):continue
        rank=np.minimum(np.abs(qa[inds]),np.abs(qb[inds]))
        if pattern=='both_quality_stable':rank=-rank
        # Two candidates per panel, with different possible block sizes.
        ordered=inds[np.argsort(rank)[::-1]]
        chosen=[]
        for ix in ordered:
            if not chosen or actual_m[ix] not in {actual_m[z] for z in chosen}:
                chosen.append(ix)
            if len(chosen)==2:break
        for ix in chosen:
            a,b=int(i[ix]),int(j[ix]);ma,mb=int(masks[a]),int(masks[b])
            ca,cb=set(links.iloc[a].selected.split('|')),set(links.iloc[b].selected.split('|'))
            case={'pattern':pattern,'panel_id':panel.panel_id,'mask_from':ma,'mask_to':mb,'m':int(actual_m[ix]),'r':int(r[ix]),
                 'team_from_a':keys_a[a],'team_to_a':keys_a[b],'team_from_b':keys_b[a],'team_to_b':keys_b[b],
                 'removed':'|'.join(sorted(ca-cb)),'added':'|'.join(sorted(cb-ca)),
                 'actual_core':'|'.join(sorted(set(panel.core.split('|') if isinstance(panel.core,str) and panel.core else [])|(ca&cb)))}
            case['event_key']='SRCC23E_'+hashlib.sha256(f'{panel.panel_id}|{ma}|{mb}'.encode()).hexdigest()[:20]
            for metric in METRICS:
                case['delta_'+metric+'_a']=d[metric][0][ix];case['delta_'+metric+'_b']=d[metric][1][ix]
            candidates.append(case)
    return results,candidates


def summarize_global(strata, panels, out):
    merged=strata.merge(panels,on='panel_id',validate='many_to_one')
    merged['mid_n']=[max(3,k,min(N-k,N//2)) for k,N in zip(merged.k_selected,merged.known_common_n)]
    merged['n_budget_fraction']=merged.n/merged.known_common_n
    merged['budget']=pd.cut(merged.n_budget_fraction,[0,.42,.58,1.01],labels=['lower','middle','higher'],right=True).astype(str)
    keys=['kind','m','r']
    numeric=[c for c in strata.columns if c not in ['panel_id','kind','m','r']]
    rows=[];groups_out=[];buildings_out=[];pairs_out=[]
    for subset,dd in analysis_subsets(merged):
        if not len(dd):continue
        # Finite class-pair panels have equal weight per direct image pair.
        pair=dd.groupby(keys+['building','pair_key','groups'],dropna=False)[numeric].mean().reset_index()
        pair['subset']=subset;pairs_out.append(pair)
        expanded=pair.assign(group_id=pair.groups.str.split('|')).explode('group_id')
        group=expanded.groupby(keys+['building','group_id'],dropna=False)[numeric].mean().reset_index();group['subset']=subset;groups_out.append(group)
        building=group.groupby(keys+['building'],dropna=False)[numeric].mean().reset_index();building['subset']=subset;buildings_out.append(building)
        for key,g in building.groupby(keys,dropna=False):
            sr=dd[(dd.kind==key[0])&(dd.m==key[1])&(dd.r==key[2])]
            row={'subset':subset,'kind':key[0],'m':key[1],'r':key[2], 'panels':sr.panel_id.nunique(),'pairs':sr.pair_key.nunique(),
                 'images':len(set(sr.image_a)|set(sr.image_b)),'groups':len(set('|'.join(sr.groups).split('|'))),
                 'buildings':sr.building.nunique(),'attempted_contrasts':int(sr.contrasts.sum()),
                 'four_complete_contrasts':int(sr.four_complete_n.sum())}
            row['finite_q_contrasts']=int(sr['B8L2__n'].sum())
            row.update({k:float(g[k].mean()) for k in numeric})
            rows.append(row)
    pd.DataFrame(rows).to_csv(out/'SUMMARY_BUILDING_EQUAL.csv',index=False)
    pd.concat(pairs_out,ignore_index=True).to_csv(out/'PAIR_RESULTS.csv.gz',index=False)
    pd.concat(groups_out,ignore_index=True).to_csv(out/'GROUP_RESULTS.csv.gz',index=False)
    pd.concat(buildings_out,ignore_index=True).to_csv(out/'BUILDING_RESULTS.csv',index=False)
    return pd.DataFrame(rows)


def main(design,native,out):
    out.mkdir(parents=True,exist_ok=True);(out/'by_pair').mkdir(exist_ok=True)
    panels=pd.read_csv(design/'PANELS.csv').fillna({'core':''})
    links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz')
    linked={k:g for k,g in links.groupby('panel_id',sort=False)}
    results=[];cases=[];pending=[];complete_panel_n=0
    for pair,pp in panels.groupby('pair_key',sort=False):
        stem=hashlib.sha256(pair.encode()).hexdigest()[:20]
        path=out/'by_pair'/(stem+'.csv.gz');cpath=out/'by_pair'/(stem+'_cases.csv.gz')
        donepath=out/'by_pair'/(stem+'.json')
        receipt=json.loads(donepath.read_text()) if donepath.exists() else {}
        if path.exists() and receipt.get('panels')==len(pp) and receipt.get('version')==ANALYSIS_VERSION:
            try:
                result=pd.read_csv(path)
                try:candidate=pd.read_csv(cpath)
                except pd.errors.EmptyDataError:candidate=pd.DataFrame()
                results.append(result);cases.append(candidate);complete_panel_n+=len(pp);continue
            except (EOFError,gzip.BadGzipFile,pd.errors.ParserError,pd.errors.EmptyDataError):
                print('rebuilding interrupted scalar summary cache',stem,flush=True)
        poola=read_pool(native,pp.iloc[0].pool_id_a);poolb=read_pool(native,pp.iloc[0].pool_id_b)
        pr,pc=[],[];ndone=0
        for p in pp.itertuples():
            z=summarize_panel(p,linked[p.panel_id],[poola,poolb])
            if z is None:
                pending.append(p.panel_id);continue
            rr,cc=z;pr.extend(rr);pc.extend(cc);ndone+=1
        if pr:
            result,candidate=pd.DataFrame(pr),pd.DataFrame(pc)
            results.append(result);cases.append(candidate);complete_panel_n+=ndone
            if ndone==len(pp):
                atomic_csv(path,result);atomic_csv(cpath,candidate)
                donepath.write_text(json.dumps({'pair_key':pair,'panels':ndone,'version':ANALYSIS_VERSION}))
        print(json.dumps({'pair_key':pair,'panels_done':ndone,'panels_total':len(pp)}),flush=True)
    if not results:
        print('No complete panels yet');return
    frame=pd.concat(results,ignore_index=True);frame.to_csv(out/'CONTRAST_STRATA.csv.gz',index=False)
    cs=pd.concat(cases,ignore_index=True);cs.to_csv(out/'CANDIDATE_EVENTS.csv.gz',index=False)
    summary=summarize_global(frame,panels,out)
    receipt={'analysis_version':ANALYSIS_VERSION,'total_panels':len(panels),'complete_panels':complete_panel_n,'pending_panels':pending,'all_complete':not pending,
             'strata':len(frame),'finite_panel_comparison_events':int(frame.contrasts.sum()),'case_search_rows':len(cs),
             'quality_threshold_main':2,'sensitivity_thresholds':[0,1,5],'geometry_thresholds':EPS,
             'aggregation':'within finite stratum, class-pair panels/replicates -> direct pair -> direct declared group -> building; building equal',
             'main_budget':'replicate 0 and clipped floor(N/2); all team sizes separately retained',
             'class_direction':'lower to higher LOBO turn_history center; actual source/target class IDs and family retained',
             'failure_denominator':'all pair comparisons; effect summaries require four finite endpoints; missing not zero'}
    (out/'ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    show=[c for c in ['subset','kind','m','r','pairs','images','buildings','attempted_contrasts','B8L2__both_small','B8L2__both_nonzero_same','B8L2__opposite','B8L2__one_small','B8L2__view_gap_mean','fusion_turn_n__both_small','fusion_turn_n__both_nonzero_same'] if c in summary]
    print('Complete panels',complete_panel_n,'/',len(panels));print(summary[show].to_string(index=False))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--design',type=Path,required=True);ap.add_argument('--native',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    warnings.filterwarnings('ignore',category=RuntimeWarning)
    main(a.design,a.native,a.out)
