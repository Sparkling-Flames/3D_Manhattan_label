#!/usr/bin/env python3
"""Recompute research-only aggregators from fixed, already measured components.
Usage: python reproduce.py --output results_replay
For full native tables: --tables /path/to/restored/results --source-audit /path/to/object_and_input_audit.json
Never overwrites an output directory; never repairs geometry or grants eligibility.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys,itertools
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr,kendalltau
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from models import COMPONENTS, losses,aggregate
from geometry import (direction_rms,interior_angles,matched_angle_error,
                      simplify_collinear,floor_iou,spherical_bottom_distance)

def json_dump(path,obj):
    def clean(x):
        if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [clean(v) for v in x]
        if isinstance(x,(np.integer,)):return int(x)
        if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
        if isinstance(x,np.bool_):return bool(x)
        return x
    path.write_text(json.dumps(clean(obj),ensure_ascii=False,indent=2),encoding='utf-8')

def load_table(path):
    lines=path.read_text(encoding='utf-8').splitlines()
    header=next(i for i,l in enumerate(lines) if 'record_id,' in l and 'object_id,' in l)
    import io
    return pd.read_csv(io.StringIO('\n'.join(lines[header:])))

def recover_metadata(path):
    text=path.read_text(encoding='utf-8'); records=[]
    try:records=json.loads(text)['records']
    except (json.JSONDecodeError,KeyError):
        pos=text.index('[',text.index('"records"'))+1; decoder=json.JSONDecoder()
        while pos<len(text):
            match=re.search(r'\S',text[pos:])
            if not match:break
            pos+=match.start()
            if text[pos]==',':pos+=1;continue
            try:r,n=decoder.raw_decode(text[pos:]);records.append(r);pos+=n
            except json.JSONDecodeError:break
    out={}
    for r in records:
        src=r.get('source',{});c=src.get('condition')
        if c not in ('manual','semi'):continue
        out[r['object_id']]={'condition':c,'hash':r.get('points_sha256'),
                             'source_path':src.get('path'),'source_annotation':src.get('annotation')}
    return out

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='results_replay')
    parser.add_argument('--tables',type=Path,default=ROOT/'inputs')
    parser.add_argument('--source-audit',type=Path,default=ROOT/'inputs/source_audit_excerpt.txt')
    args=parser.parse_args();out=Path(args.output)
    if not out.is_absolute():out=ROOT/out
    if out.exists() and any(out.iterdir()):raise SystemExit('Refusing to overwrite nonempty output directory')
    out.mkdir(parents=True,exist_ok=True)
    cfg=json.loads((ROOT/'config.json').read_text());w=np.array([cfg['weights'][c] for c in COMPONENTS])
    tables=[]; files=[]
    for stem in ['FINAL_ordinary','FINAL_doorway','FINAL_severe','FINAL_history']:
        choices=[args.tables/(stem+'.csv'),args.tables/(stem+'.txt')]
        p=next((x for x in choices if x.exists()),None)
        if p is None:continue
        t=load_table(p);t['input_table']=p.name;tables.append(t)
        files.append({'path':str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p),
                      'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'rows':len(t)})
    df=pd.concat(tables,ignore_index=True)
    meta=recover_metadata(args.source_audit) if args.source_audit.exists() else {}
    df['condition']='unknown_not_recovered';df['condition_evidence']='not_available'
    for i,r in df.iterrows():
        m=meta.get(r.object_id)
        if m and m['hash']==r.input_hash:
            df.at[i,'condition']=m['condition'];df.at[i,'condition_evidence']='source_audit_hash_bound'
    # Quarantine truncation; hold status takes priority over numerical availability.
    needed=['record_id','object_id','image_id','reference_object_id','input_hash','reference_hash',
            'iou_2d','S_bottom_deg','dir','Hmean','Hcenter','working_Q','iou3d_pct','status']
    finite=np.isfinite(df[['iou_2d','S_bottom_deg','dir','Hmean','Hcenter','working_Q','iou3d_pct']].to_numpy(dtype=float)).all(axis=1)
    complete=df[needed].notna().all(axis=1)&finite
    allowed=df.status.eq('conditional_complete') & complete
    df['execution_status']=np.where(allowed,'scored',np.where(df.status.eq('held'),'held_unchanged','incomplete_quarantined'))
    p=losses(df.iou_2d,df.S_bottom_deg,df.dir,df.Hmean,df.Hcenter)
    p[~allowed]=np.nan
    scores,s=aggregate(p,w)
    for j,c in enumerate(COMPONENTS):df['p_'+c]=p[:,j];df['s_'+c]=100*s[:,j]
    for k,v in scores.items():df[k]=v
    df['raw_3d_iou']=np.where(allowed,df.iou3d_pct,np.nan)
    for label,weights in cfg['weight_sensitivity'].items():
        ww=[weights[c] for c in COMPONENTS]
        alternatives,_=aggregate(p,ww)
        df['A_'+label]=alternatives['arithmetic_candidate']
        df['RA_'+label]=alternatives['range_anchored_A']
    df['delta_A_minus_WQ']=df.arithmetic_candidate-df.WQ_LS08
    df['delta_G_minus_WQ']=df.geometric_control-df.WQ_LS08
    df['formula_replay_error']=df.WQ_LS08-df.working_Q
    df['bound_key']=df.record_id.astype(str)+'|'+df.object_id.astype(str)+'|'+df.reference_object_id.astype(str)
    # One actual answer is not multiplied by its reference variants in primary summaries.
    multiplicity=df.loc[allowed].groupby('object_id').reference_object_id.nunique()
    multi=set(multiplicity[multiplicity>1].index)
    df['multi_reference_answer']=df.object_id.isin(multi)
    scored=df.loc[allowed].copy()
    df.to_csv(out/'per_case.csv',index=False)
    df.loc[~allowed].to_csv(out/'held_and_incomplete.csv',index=False)
    base=scored.loc[~scored.multi_reference_answer].drop_duplicates(['object_id','reference_object_id'])
    modelnames=['WQ_LS08','arithmetic_candidate','geometric_control','range_anchored_A','raw_3d_iou']
    def describe(key,g):
        d={'stratum':key,'n':len(g),'images':g.image_id.nunique(),'workers':g.worker_id.nunique(),
           'known_condition_n':int(g.condition.isin(['manual','semi']).sum()),
           'inherited_not_blind':True}
        for model in modelnames:
            a=g[model];d[model+'_mean']=a.mean();d[model+'_median']=a.median()
            d[model+'_min']=a.min();d[model+'_max']=a.max()
        d['A_mean_delta']=g.delta_A_minus_WQ.mean();d['A_max_delta']=g.delta_A_minus_WQ.max()
        for m in modelnames[1:]:
            d[m+'_spearman_WQ']=spearmanr(g.WQ_LS08,g[m]).statistic if len(g)>2 else np.nan
            d[m+'_kendall_WQ']=kendalltau(g.WQ_LS08,g[m]).statistic if len(g)>2 else np.nan
        return d
    summaries=[]
    # Overall numeric summaries are explicitly condition-unresolved; not mode-stratified validation.
    for use,g in base.groupby('effective_use',dropna=False):summaries.append(describe('numeric_only:'+str(use),g))
    for (use,condition),g in base.groupby(['effective_use','condition'],dropna=False):
        summaries.append(describe(str(use)+'|'+condition,g))
    ordinary=base[base.source_layer.eq('ordinary')]
    for explicit,g in ordinary.groupby('explicitly_ordinary'):
        summaries.append(describe('ordinary_explicit='+str(explicit)+'_numeric_only',g))
    pd.DataFrame(summaries).to_csv(out/'stratum_summary.csv',index=False)
    img=base.groupby(['effective_use','condition','image_id','reference_object_id'],dropna=False)[modelnames].mean().reset_index()
    img.to_csv(out/'image_equal_weight_inputs.csv',index=False)
    # Fixed cut migration is not a validated quality-class assessment.
    migrations=[]
    for (use,condition),g in base.groupby(['effective_use','condition'],dropna=False):
        for cut in cfg['illustrative_score_cuts']:
            for m in modelnames[1:]:
                a=g.WQ_LS08.ge(cut);b=g[m].ge(cut)
                migrations.append({'effective_use':use,'condition':condition,'cut':cut,'candidate':m,
                    'n':len(g),'above_WQ':int(a.sum()),'above_candidate':int(b.sum()),
                    'up':int((~a&b).sum()),'down':int((a&~b).sum()),
                    'meaning':'unrecalibrated_numerical_cut_only'})
    pd.DataFrame(migrations).to_csv(out/'cut_migration.csv',index=False)
    # Pairs never cross task/reference/known condition. Unknown remains labelled, not presumed manual.
    pairs=[]
    for keys,g in base.groupby(['effective_use','condition','image_id','reference_object_id'],dropna=False):
        for (_,a),(_,b) in itertools.combinations(g.iterrows(),2):
            r={'effective_use':keys[0],'condition':keys[1],'image_id':keys[2],'reference_object_id':keys[3],
               'record_a':a.record_id,'record_b':b.record_id,'object_a':a.object_id,'object_b':b.object_id,
               'condition_validated_pair':keys[1] in ('manual','semi')}
            for m in modelnames:r[m+'_gap']=a[m]-b[m]
            r['A_reversal']=r['WQ_LS08_gap']*r['arithmetic_candidate_gap']<-1e-12
            r['G_reversal']=r['WQ_LS08_gap']*r['geometric_control_gap']<-1e-12
            r['RA_reversal']=r['WQ_LS08_gap']*r['range_anchored_A_gap']<-1e-12
            r['IoU_reversal']=r['WQ_LS08_gap']*r['raw_3d_iou_gap']<-1e-12
            pairs.append(r)
    pp=pd.DataFrame(pairs);pp.to_csv(out/'same_binding_pairs.csv',index=False)
    # Workers: only known condition, inherited ordinary use, no inherited barriers. Do not grant formal eligibility.
    known=ordinary[ordinary.condition.isin(['manual','semi']) & ordinary.personnel_barriers.eq('[]')]
    ww=known.groupby(['condition','worker_id']).agg(n=('record_id','count'),n_images=('image_id','nunique'),
        **{m:(m,'mean') for m in modelnames}).reset_index()
    ww['minimum_support']=ww.n.ge(cfg['minimum_worker_records'])
    for m in modelnames:ww[m+'_rank']=ww.where(ww.minimum_support).groupby('condition')[m].rank(ascending=False)
    ww.to_csv(out/'worker_support_and_available_means.csv',index=False)
    # Score-level marginal effect, not arbitrary summation of component drops.
    contributions=[]
    for j,c in enumerate(COMPONENTS):
        p0=p.copy();p0[:,j]=np.where(allowed,0,np.nan);n,_=aggregate(p0,w)
        for m in ['WQ_LS08','arithmetic_candidate','geometric_control','range_anchored_A']:
            col='remove_'+c+'_gain_'+m;df[col]=n[m]-df[m]
            for use,g in df.loc[allowed].groupby('effective_use'):
                contributions.append({'effective_use':use,'component':c,'model':m,
                    'mean_remove_component_gain':g[col].mean(),'max_remove_component_gain':g[col].max()})
    df.to_csv(out/'per_case.csv',index=False)
    pd.DataFrame(contributions).to_csv(out/'component_marginal_effects.csv',index=False)
    # Balanced rule-based follow-up list: deltas both tails, raw-IoU disagreement, typical, severe and held.
    selected={}
    def add(rows,reason):
        for _,r in rows.iterrows():selected.setdefault(r.bound_key,{'row':r,'reasons':[]})['reasons'].append(reason)
    for use,g in base.groupby('effective_use'):
        add(g.nlargest(2,'delta_A_minus_WQ'),'largest_A_uplift_in_'+use)
        add(g.nsmallest(2,'delta_A_minus_WQ'),'smallest_A_uplift_in_'+use)
        idx=(g.WQ_LS08-g.WQ_LS08.median()).abs().sort_values().index[:1];add(g.loc[idx],'typical_WQ_in_'+use)
    g=ordinary.copy();g['raw_gap']=g.raw_3d_iou-g.WQ_LS08
    add(g.nlargest(2,'raw_gap'),'raw_IoU_far_above_WQ');add(g.nsmallest(2,'raw_gap'),'raw_IoU_far_below_WQ')
    if len(pp):
        rev=pp[pp.A_reversal].copy();rev['min_gap']=np.minimum(abs(rev.WQ_LS08_gap),abs(rev.arithmetic_candidate_gap))
        for _,r in rev.nlargest(2,'min_gap').iterrows():
            add(base[base.record_id.isin([r.record_a,r.record_b])],'paired_rank_reversal_no_visual_verdict')
    tmp=ordinary.copy();tmp['ra_delta']=tmp.range_anchored_A-tmp.WQ_LS08
    add(tmp.nlargest(2,'ra_delta'),'range_anchored_A_largest_uplift')
    add(tmp.nsmallest(2,'ra_delta'),'range_anchored_A_smallest_uplift_or_decline')
    held=df[df.status.eq('held')].sort_values('record_id').head(2);add(held,'negative_control_held_no_score')
    chosen=[]
    fields=['record_id','object_id','image_id','image_code','worker_id','condition','reference_object_id',
            'reference_version','input_hash','reference_hash','effective_use','original_holdout','exposure',
            'execution_status']+modelnames+['delta_A_minus_WQ']
    for v in selected.values():
        r=v['row'];item={f:r.get(f) for f in fields};item['selection_reasons']=';'.join(v['reasons'])
        item['review_status']='not_reviewed_in_this_study';item['independent_blind_validation']=False;chosen.append(item)
    pd.DataFrame(chosen).to_csv(out/'followup_review_manifest.csv',index=False)
    blinded=pd.DataFrame(chosen).drop(columns=modelnames+['delta_A_minus_WQ'])
    blinded.to_csv(out/'followup_review_bindings_without_scores.csv',index=False)
    # Analytic aggregation tests on identical losses and explicit geometric counterexamples.
    operator=[]
    for j,c in enumerate(COMPONENTS):
        for value in [0,.01,.0625,.16,.25,.6,1,1.5,4,10,100,1e6]:
            x=np.zeros(5);x[j]=value;n,_=aggregate(x,w)
            operator.append({'component':c,'loss':value,**{m:float(v) for m,v in n.items()},
                             'kind':'loss_space_intervention_not_a_real_independent_annotation'})
    pd.DataFrame(operator).to_csv(out/'single_component_response.csv',index=False)
    square=np.array([[-1.,-1.],[1.,-1.],[1.,1.],[-1.,1.]])
    geometries=[]
    for theta in [90,75,60,45,30,15,5,1]:
        v=np.array([2*np.cos(np.deg2rad(theta)),2*np.sin(np.deg2rad(theta))]);u=np.array([2.,0.])
        a=np.array([[0.,0.],u,u+v,v]);a-=a.mean(axis=0)
        geometries.append(('rhombus_'+str(theta),a,square,list(zip(range(4),range(4)))))
    for scale in [.2,.5,1,2,5]:geometries.append(('uniform_scale_'+str(scale),square*scale,square,list(zip(range(4),range(4)))))
    phi=np.deg2rad(30); rot=np.array([[np.cos(phi),-np.sin(phi)],[np.sin(phi),np.cos(phi)]])
    geometries.append(('rotated_square',square@rot.T,square,list(zip(range(4),range(4)))))
    L=np.array([[-1.5,-1.5],[1.5,-1.5],[1.5,.3],[.3,.3],[.3,1.5],[-1.5,1.5]])
    geometries.append(('legal_concave_self',L,L,list(zip(range(6),range(6)))))
    trap=np.array([[-1.,-1.],[1.,-1.],[.5,1.],[-.5,1.]])
    geometries.append(('legal_nonorthogonal_reference_self',trap,trap,list(zip(range(4),range(4)))))
    branch=np.array([[-1.,-1.],[1.,-1.],[1.,.7],[1.3,.7],[1.3,.9],[1.,.9],[1.,1.],[-1.,1.]])
    geometries.append(('omitted_narrow_orthogonal_branch',square,branch,None))
    subdiv=np.array([[-1.,-1.],[0.,-1.],[1.,-1.],[1.,1.],[-1.,1.]])
    simp=simplify_collinear(subdiv)
    geometries.append(('collinear_subdivision_canonical_copy',simp,square,list(zip(range(4),range(4)))))
    grow=[];payload=[]
    for name,a,b,corr in geometries:
        angle=matched_angle_error(a,b,corr);I=floor_iou(a,b);Sb=spherical_bottom_distance(a,b);D=direction_rms(a)
        n,_=aggregate(losses(I,Sb,D,0.,0.),w)
        rec={'case':name,'I':I,'Sb_probe_deg':Sb,'D_deg':D,'raw_3d_iou':100*I,
             'angle_available':angle['available'],'angle_RMS_deg':angle.get('matched_angle_rms_deg'),
             'role':'synthetic_measurement_probe_not_human_validation',**{m:float(v) for m,v in n.items()}}
        grow.append(rec);payload.append({'case':name,'candidate_xy':a.tolist(),'reference_xy':b.tolist(),
                                         'correspondence':corr,'angle_diagnostics':angle})
    pd.DataFrame(grow).to_csv(out/'geometry_probes.csv',index=False);json_dump(out/'geometry_probe_inputs.json',payload)
    heights=[]
    for ratio in [1,1.1,1.2,1.5,2,3,4,10]:
        n,_=aggregate(losses(1,0,0,abs(ratio-1),0),w)
        heights.append({'kind':'uniform_total_height_ratio','amplitude':ratio,'Hm':abs(ratio-1),'Hc':0.,
                        'raw_3d_iou':100*min(1,ratio)/max(1,ratio),
                        **{m:float(v) for m,v in n.items()}})
    for a in [0,.1,.2,.4,.6,.8]:
        # Square side=2; alternating total corner heights 2+a and 2-a.
        # Exact uniform-perimeter RMS of linear edge heights, divided by reference mean=2.
        Hc=a/(2*np.sqrt(3));n,_=aggregate(losses(1,0,0,0,Hc),w)
        heights.append({'kind':'alternating_corner_height_perimeter_analytic','amplitude':a,'Hm':0.,'Hc':Hc,
                        'raw_3d_iou':100.,**{m:float(v) for m,v in n.items()}})
    pd.DataFrame(heights).to_csv(out/'height_probes.csv',index=False)

    audit={'pinned_commit':cfg['pinned_commit'],'input_files':files,'native_rows':len(df),
           'execution_status_counts':df.execution_status.value_counts().to_dict(),
           'scored_by_source_layer':scored.source_layer.value_counts().to_dict(),
           'condition_counts':df.condition.value_counts().to_dict(),
           'scored_condition_counts':scored.condition.value_counts().to_dict(),
           'known_source_metadata_objects':len(meta),'multi_reference_answers':list(multi),
           'unique_scored_objects':scored.object_id.nunique(),'unique_scored_bindings':scored.bound_key.nunique(),
           'baseline_max_abs_error':float(df.formula_replay_error.abs().max()),
           'harmonic_max_abs_error':float(abs(df.WQ_LS08-df.harmonic_exact_rewrite).max()),
           'A_below_WQ_count':int((df.delta_A_minus_WQ < -1e-10).sum()),
           'G_below_WQ_count':int((df.delta_G_minus_WQ < -1e-10).sum()),
           'pairs_n':len(pp),'A_reversals_numeric_only':int(pp.A_reversal.sum()) if len(pp) else 0,
           'RA_reversals_numeric_only':int(pp.RA_reversal.sum()) if len(pp) else 0,
           'condition_validated_pairs_n':int(pp.condition_validated_pair.sum()) if len(pp) else 0,
           'workers_reaching_minimum_known_condition_support':int(ww.minimum_support.sum()),
           'followup_bindings':len(chosen),
           'full_718_comparison_completed':False,'geometry_rebuilt_for_native_rows':False,
           'limitation':'Only extracted-table inputs; ordinary ends with a partial record. Unknown manual/semi not inferred. No population accuracy, independent blind validation, or formal worker ranking claim.'}
    json_dump(out/'execution_audit.json',audit)
    print(json.dumps(audit,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
