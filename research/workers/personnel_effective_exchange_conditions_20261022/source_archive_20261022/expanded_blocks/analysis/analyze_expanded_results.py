"""Incremental, read-only analysis of the newly registered finite exchanges.

Writes only expanded_blocks/analysis. Reads a cell only after its completion
receipt, adds compact member/subgroup summaries once, and balances true common
backgrounds -> images -> buildings. Partial outputs are explicitly provisional.
No scoring, geometry reconstruction or native fusion is performed here.
"""
from __future__ import annotations
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[k]='1'
from pathlib import Path
import sys,json,math,time,collections,argparse,warnings
import numpy as np,pandas as pd
warnings.filterwarnings('ignore',category=pd.errors.PerformanceWarning)
HERE=Path(__file__).resolve().parent
EX=HERE.parent;NEW=EX.parent
sys.path.insert(0,str(NEW/'screening'))
import common_screening as io
io.HERE=HERE
from common_screening import save_csv,save_json,digest,sha

CORE=['common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage',
 'same_B8L2','cross_B8L2','cross_D10','cross_IoU3D100','cross_iou_2d',
 'cross_ref_node_recall_5','cross_ref_edge_recall_5','cross_omission','cross_extension',
 'cross_fusion_turn_n','cross_fusion_short_turn_edges','cross_fusion_redundancy_n',
 'common_geometry_advantage_floor_jaccard_difference','common_geometry_advantage_mean_height_prism_pair_difference',
 'stable_advantage','A_failure','B_failure','C_failure','same_loss_gt10','cross_loss_gt10',
 'same_failure_or_loss_gt10','cross_failure_or_loss_gt10','cross_complete_to_failure',
 'cross_recorded_time_pct','same_recorded_time_pct','cross_B8L2_time_qualified',
 'cross_history_block_Q_change','same_history_block_Q_change','fraction_cross_larger_abs_Q']
AUX_METRICS=[m for m in CORE if m not in ['cross_complete_to_failure']]
MEMBER_METRICS=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
CONTEXT=['cell_id','panel_id','pool_id','image','building','condition','layer','difficulty','method_id','tier',
 'n','m_AB','source_class','target_class','source_role','target_role','selected_family','training_turn_direction',
 'background_index','member_design','overlap_priority_seed_image']
BASE=['condition','layer','method_id','tier','source_domain','n','m','parent_fixed']
VIEWS=['method_n_m','class_direction','training_turn_direction','family_and_turn']

def truth(s):
    if pd.api.types.is_bool_dtype(s):return s.astype(float)
    return s.astype(str).str.lower().map({'true':1.,'false':0.,'1':1.,'0':0.,'1.0':1.,'0.0':0.})

def aux_cell(part):
    cell=part['cell_id'];source=EX/'results'/cell;completion=source/'COMPLETION.json'
    marker=HERE/'extra_cells'/cell/'COMPLETION.json'
    if marker.exists():
        old=json.loads(marker.read_text())
        assert old['source_completion_sha256']==sha(completion)
        return old
    path=source/'EVENTS_COMPLETE.csv.gz'
    restored=None
    if not path.exists():
        path=HERE/'rebuilt_event_inputs'/cell/'EVENTS_COMPLETE.csv.gz'
        restoration=path.with_name('REBUILD_RECEIPT.json')
        if not restoration.exists():
            raise FileNotFoundError(f'{cell}: original event file absent; run restore_event_inputs_from_delivery.py first')
        restored=json.loads(restoration.read_text())
        original=json.loads(completion.read_text())
        assert restored['original_event_gzip_sha256']==original['event_result']['sha256']
        assert restored['sha256']==sha(path) and restored['rows']==int(part['events'])
    want=set(['event_id','physical_triple_id','panel_id','source_domain','n','same_source_counts',
        'source_and_historyQ5_matched','recorded_time_single_source','same_B8L2','cross_B8L2']+CORE+
        [a+'_'+f for a in 'ABC' for f in MEMBER_METRICS+['failure']]+['team_'+a for a in 'ABC'])
    d=pd.read_csv(path,usecols=lambda c:c in want,low_memory=False)
    assert len(d)==int(part['events'])
    for c in ['A_failure','B_failure','C_failure','same_source_counts','source_and_historyQ5_matched','recorded_time_single_source']:
        if c not in d:d[c]=np.nan
        d[c]=truth(d[c])
    for arm,letter in [('same','B'),('cross','C')]:
        q=pd.to_numeric(d[arm+'_B8L2'],errors='coerce')
        d[arm+'_failure_or_loss_gt10']=np.where(d[letter+'_failure'].eq(1),1.,np.where(q.notna(),q.lt(-10),np.nan))
    d['cross_complete_to_failure']=(d.A_failure.eq(0)&d.C_failure.eq(1)).astype(float)
    d['cross_B8L2_time_qualified']=d.cross_B8L2.where(d.recorded_time_single_source.eq(1))
    for metric in AUX_METRICS:
        if metric not in d:d[metric]=np.nan
    auxiliary=[];member=[];values=[];core=[]
    for panel,g in d.groupby('panel_id'):
        for stratum,mask in [('all',np.ones(len(g),bool)),('source_matched',g.same_source_counts.eq(1)),
                             ('source_Q5_matched',g.source_and_historyQ5_matched.eq(1))]:
            z=g[mask]
            r=dict(cell_id=cell,panel_id=panel,source_domain=g.source_domain.iloc[0],stratum=stratum,
                total_registered_events=len(g),events=len(z),source_matched_events=int(g.same_source_counts.eq(1).sum()),
                source_Q5_matched_events=int(g.source_and_historyQ5_matched.eq(1).sum()),
                time_qualified_events=int(g.recorded_time_single_source.eq(1).sum()))
            for metric in AUX_METRICS+['cross_complete_to_failure']:
                v=pd.to_numeric(z[metric],errors='coerce').dropna().to_numpy(float)
                r[metric]=float(v.mean()) if len(v) else np.nan;r[metric+'__valid']=len(v)
                if metric in ['same_B8L2','cross_B8L2','abs_Q_change_advantage']:
                    r[metric+'__median']=float(np.median(v)) if len(v) else np.nan
                    r[metric+'__q05']=float(np.quantile(v,.05)) if len(v) else np.nan
            auxiliary.append(r)
        cv=g[['panel_id','same_B8L2','cross_B8L2','abs_Q_change_advantage']].copy()
        core.append(cv)
        for arm in 'ABC':
            cols=['team_'+arm,arm+'_failure']+[arm+'_'+m for m in MEMBER_METRICS]
            z=g[[c for c in cols if c in g]].drop_duplicates('team_'+arm).copy()
            role='same_composition_source' if arm in 'AB' else 'changed_composition_target'
            r=dict(cell_id=cell,panel_id=panel,arm=arm,composition_role=role,unique_member_sets=len(z),
                failed_member_sets=int(z[arm+'_failure'].sum()),failed_fraction=float(z[arm+'_failure'].mean()))
            for metric in MEMBER_METRICS:
                field=arm+'_'+metric
                v=pd.to_numeric(z[field],errors='coerce').dropna().to_numpy(float) if field in z else np.array([])
                r[metric+'_valid_member_sets']=len(v)
                for stat,fn in [('mean',np.mean),('median',np.median),('std',np.std),('min',np.min),('max',np.max)]:
                    r[metric+'_'+stat]=float(fn(v)) if len(v) else np.nan
                for q in [.05,.1,.9,.95]:r[metric+'_q'+str(int(q*100)).zfill(2)]=float(np.quantile(v,q)) if len(v) else np.nan
            member.append(r)
            z=z.rename(columns={'team_'+arm:'team_key',arm+'_failure':'failure',**{arm+'_'+m:m for m in MEMBER_METRICS}})
            z['panel_id']=panel;z['cell_id']=cell;z['arm']=arm;values.append(z)
    prefix='extra_cells/'+cell+'/'
    files=[save_csv(prefix+'PANEL_AUXILIARY.csv.gz',pd.DataFrame(auxiliary)),
      save_csv(prefix+'MEMBER_RESPONSE.csv.gz',pd.DataFrame(member)),
      save_csv(prefix+'MEMBER_ENDPOINT_VALUES.csv.gz',pd.concat(values,ignore_index=True)),
      save_csv(prefix+'CORE_EVENT_VALUES.csv.gz',pd.concat(core,ignore_index=True))]
    result=dict(status='complete',cell_id=cell,events=len(d),source_completion_sha256=sha(completion),
      source_event_sha256=sha(path),files=files,native_calls=0,scoring_calls=0,
      source_event_storage='delivered_raw_CSV_restoration' if restored else 'original_per_cell_file',
      original_event_gzip_sha256=restored['original_event_gzip_sha256'] if restored else sha(path))
    save_json(prefix+'COMPLETION.json',result)
    return result

def define_group(d,view,cohort,difficulty):
    x=d.copy()
    if cohort!='all_images':x=x[x.seed_cohort.eq(cohort)]
    x['view']=view;x['cohort']=cohort
    x['difficulty_stratum']=x.difficulty if difficulty else 'ALL'
    if view=='method_n_m':x['direction']='all_registered_class_directions'
    elif view=='class_direction':
        x['direction']=np.where(x.method_id.str.startswith('V3_'),x.source_role+' -> '+x.target_role,x.source_class+' -> '+x.target_class)
    elif view=='training_turn_direction':x['direction']=x.training_turn_direction
    else:x['direction']=x.selected_family+' / '+x.training_turn_direction
    keys=BASE+['view','cohort','direction','difficulty_stratum']
    idx=x[keys].drop_duplicates()
    idx['summary_id']=[digest(list(r))[:24] for r in idx.itertuples(index=False,name=None)]
    return x.merge(idx,on=keys,validate='many_to_one'),idx

def boot(v):
    if len(v)<3:return np.nan,np.nan
    rng=np.random.default_rng(2026102203);a=v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1)
    return tuple(np.quantile(a,[.025,.975]))

def summarize(d,registered,metrics,core_values,view,cohort,bydifficulty,status):
    x,idx=define_group(d,view,cohort,bydifficulty)
    reg,allidx=define_group(registered,view,cohort,bydifficulty)
    bg=x.groupby(['summary_id','building','image','background_id'],dropna=False)[metrics].mean()
    im=bg.groupby(level=['summary_id','building','image']).mean()
    b=im.groupby(level=['summary_id','building']).mean()
    gg={k:g for k,g in x.groupby('summary_id')};bb={k:g.droplevel('summary_id') for k,g in b.groupby(level='summary_id')}
    ii={k:g.droplevel('summary_id') for k,g in im.groupby(level='summary_id')};backs={k:g.droplevel('summary_id') for k,g in bg.groupby(level='summary_id')}
    regs={k:g for k,g in reg.groupby('summary_id')}
    medians={}
    if len(x):
        join=core_values.merge(x[['panel_id','summary_id']].drop_duplicates(),on='panel_id')
        medians=join.groupby('summary_id')[['same_B8L2','cross_B8L2','abs_Q_change_advantage']].median().to_dict('index')
    support=[];rows=[];selected=[]
    for meta in allidx.to_dict('records'):
        sid=meta['summary_id'];r=regs[sid];g=gg.get(sid,pd.DataFrame());supportrow=dict(meta,
          status=status,registered_panels=r.panel_id.nunique(),complete_panels=g.panel_id.nunique() if len(g) else 0,
          registered_images=r.image.nunique(),complete_images=g.image.nunique() if len(g) else 0,
          registered_buildings=r.building.nunique(),complete_buildings=g.building.nunique() if len(g) else 0,
          registered_events=int(pd.to_numeric(r.registered_oriented_ABC).sum()),complete_events=int(g.events.sum()) if len(g) else 0,
          complete_backgrounds=g.background_id.nunique() if len(g) else 0,
          extra_background_coverage_is_finite_registered_subset=True)
        support.append(supportrow)
        if not len(g):continue
        for metric in metrics:
            v=bb[sid][metric].dropna().to_numpy(float);iv=ii[sid][metric].dropna().to_numpy(float);pv=backs[sid][metric].dropna().to_numpy(float)
            n=pd.to_numeric(g[metric+'__valid'],errors='coerce').fillna(0).to_numpy(float)
            mean=pd.to_numeric(g[metric],errors='coerce').to_numpy(float)
            valid=np.isfinite(mean)&(n>0);evcount=int(n[valid].sum())
            if not(evcount or len(v)):continue
            lo,hi=boot(v) if metric in CORE else (np.nan,np.nan)
            item=dict(summary_id=sid,metric=metric,valid_events=evcount,
              event_weighted_mean=float(np.sum(mean[valid]*n[valid])/n[valid].sum()) if evcount else np.nan,
              exact_event_median=medians.get(sid,{}).get(metric,np.nan),
              valid_backgrounds=len(pv),background_mean=float(pv.mean()) if len(pv) else np.nan,
              background_median=float(np.median(pv)) if len(pv) else np.nan,
              positive_backgrounds=int((pv>1e-10).sum()),negative_backgrounds=int((pv< -1e-10).sum()),zero_backgrounds=int((abs(pv)<=1e-10).sum()),
              valid_images=len(iv),image_mean=float(iv.mean()) if len(iv) else np.nan,image_median=float(np.median(iv)) if len(iv) else np.nan,
              positive_images=int((iv>1e-10).sum()),negative_images=int((iv< -1e-10).sum()),zero_images=int((abs(iv)<=1e-10).sum()),
              valid_buildings=len(v),building_mean=float(v.mean()) if len(v) else np.nan,building_median=float(np.median(v)) if len(v) else np.nan,
              positive_buildings=int((v>1e-10).sum()),negative_buildings=int((v< -1e-10).sum()),zero_buildings=int((abs(v)<=1e-10).sum()),
              building_bootstrap_lo95=lo,building_bootstrap_hi95=hi)
            rows.append(item)
            if metric in CORE:selected.append(dict(supportrow,**item))
    return pd.DataFrame(rows),pd.DataFrame(selected),pd.DataFrame(support),im.reset_index(),b.reset_index()

def prepare_registered(reg):
    reg=reg.copy();reg['n']=pd.to_numeric(reg.n).astype(int);reg['m']=pd.to_numeric(reg.m).astype(int)
    reg['parent_fixed']=reg.method_id.eq('M_structure')&reg.tier.eq('fine')
    # Frozen requests use the known formally eligible pool; preserve their
    # actual domain spelling when the evaluated event supplies it.
    reg['source_domain']='all_formal_label_known'
    reg['selected_family']=reg.selected_family.fillna('legacy_fixed_method')
    reg['training_turn_direction']=reg.training_turn_direction.fillna('unknown')
    reg['seed_cohort']=np.where(truth(reg.overlap_priority_seed_image).eq(1),'priority_seed_images','additional_images')
    reg['background_id']=[digest([p,b])[:24] for p,b in zip(reg.pool_id,reg.common_background.fillna(''))]
    return reg

def run(require_complete=False):
    started=time.time();index=pd.read_csv(EX/'REGISTERED_EVENT_PARTS.csv',keep_default_na=False)
    registered=prepare_registered(pd.read_csv(EX/'REGISTERED_MEMBER_PANELS.csv.gz',low_memory=False))
    ready=[];pending=[]
    for part in index.to_dict('records'):
        marker=EX/'results'/part['cell_id']/'COMPLETION.json'
        if not marker.exists():pending.append(part);continue
        receipt=json.loads(marker.read_text())
        assert receipt['status']=='complete' and receipt['exported_events']==int(part['events']) and receipt['missing_events']==0
        ready.append(part)
    full=not pending
    if require_complete and not full:raise RuntimeError(f'Expansion incomplete: {len(pending)} registered cells remain')
    status='FINAL_COMPLETE' if full else 'PARTIAL_NOT_FINAL'
    save_csv('PENDING_CELLS.csv',pd.DataFrame(pending,columns=index.columns))
    panels=[];auxiliary=[];members=[];coreframes=[];extra=[]
    for i,part in enumerate(ready):
        extra.append(aux_cell(part));cell=part['cell_id']
        p=pd.read_csv(EX/'results'/cell/'PANEL_SUMMARY.csv.gz',low_memory=False)
        panels.append(p)
        folder=HERE/'extra_cells'/cell
        auxiliary.append(pd.read_csv(folder/'PANEL_AUXILIARY.csv.gz'))
        members.append(pd.read_csv(folder/'MEMBER_RESPONSE.csv.gz'))
        coreframes.append(pd.read_csv(folder/'CORE_EVENT_VALUES.csv.gz'))
        if (i+1)%25==0:
            save_json('ANALYSIS_PROGRESS.json',dict(status=status,ready_cells=len(ready),pending_cells=len(pending),extra_cells_completed=i+1,native_calls=0))
    if not panels:
        save_json('ANALYSIS_PROGRESS.json',dict(status=status,ready_cells=0,pending_cells=len(pending),native_calls=0));return
    p=pd.concat(panels,ignore_index=True);a=pd.concat(auxiliary,ignore_index=True);member=pd.concat(members,ignore_index=True)
    p['selected_family']=p.selected_family.fillna('legacy_fixed_method')
    p['training_turn_direction']=p.training_turn_direction.fillna('unknown')
    core_values=pd.concat(coreframes,ignore_index=True)
    assert p.panel_id.is_unique
    aux=a[a.stratum.eq('all')].set_index('panel_id')
    p=p.set_index('panel_id')
    for f in ['source_domain','source_matched_events','source_Q5_matched_events','time_qualified_events',
              'same_failure_or_loss_gt10','cross_failure_or_loss_gt10','cross_complete_to_failure','cross_B8L2_time_qualified']:
        p[f]=aux[f]
        if f+'__valid' in aux:p[f+'__valid']=aux[f+'__valid']
    p=p.reset_index();p['m']=pd.to_numeric(p.m_AB).astype(int)
    p['fraction_cross_larger_abs_Q']=p['abs_Q_change_advantage__positive']
    p['fraction_cross_larger_abs_Q__valid']=p['abs_Q_change_advantage__valid']
    # Actual source-domain identity from the frozen event must propagate to
    # the full pending denominator, even before the cell finishes.
    domains=p.groupby('method_id').source_domain.unique().to_dict()
    for method,values in domains.items():
        assert len(values)==1,(method,values)
        registered.loc[registered.method_id.eq(method),'source_domain']=values[0]
    join=[c for c in registered.columns if c not in p.columns or c=='panel_id']
    p=p.merge(registered[join],on='panel_id',validate='one_to_one')
    assert int(p.events.sum())==sum(int(r['events']) for r in ready)
    metrics=[f for f in p if f+'__valid' in p and not f.endswith(('__median','__positive','__negative'))]
    for f in metrics:p[f]=pd.to_numeric(p[f],errors='coerce')
    save_csv('PANEL_COMPLETE_RESULTS_'+status+'.csv.gz',p)
    save_csv('MEMBER_RESPONSE_'+status+'.csv.gz',member.merge(p[CONTEXT+['source_domain','m','seed_cohort','background_id']],on=['cell_id','panel_id'],validate='many_to_one'))
    save_csv('MATCHED_HISTORY_AUXILIARY_'+status+'.csv.gz',a.merge(p[['panel_id']+BASE+['image','building','difficulty','seed_cohort','background_id','source_role','target_role']],on='panel_id',suffixes=('','_context'),validate='many_to_one'))
    allsmall=[];allsupport=[];allcomponents=[];imageframes=[];buildingframes=[]
    for view in VIEWS:
        for cohort in ['all_images','priority_seed_images','additional_images']:
            for bydiff in [False,True]:
                long,small,support,images,buildings=summarize(p,registered,metrics,core_values,view,cohort,bydiff,status)
                allcomponents.append(long);allsmall.append(small);allsupport.append(support)
                imageframes.append(images);buildingframes.append(buildings)
        save_json('ANALYSIS_PROGRESS.json',dict(status=status,ready_cells=len(ready),pending_cells=len(pending),last_view=view,native_calls=0,seconds=time.time()-started))
    prefix='FINAL' if full else 'PARTIAL'
    files=[]
    for name,frames in [('ALL_COMPONENT_SUMMARY',allcomponents),('CORE_SUMMARY',allsmall),('COVERAGE',allsupport),
       ('IMAGE_MEANS',imageframes),('BUILDING_MEANS',buildingframes)]:
        d=pd.concat(frames,ignore_index=True);assert not d.duplicated(['summary_id','metric'] if 'metric' in d else ['summary_id','building','image'] if name=='IMAGE_MEANS' else ['summary_id','building'] if name=='BUILDING_MEANS' else ['summary_id']).any()
        files.append(save_csv(prefix+'_'+name+'.csv.gz',d))
    # Same-source / historical-Q5 matching is an explanatory supplement. It
    # never gates the main total composition effect or erases unmatched rows.
    context=list(dict.fromkeys(CONTEXT+BASE+['seed_cohort','background_id']))
    auxcontext=a.merge(p[context],on=['cell_id','panel_id','source_domain'],validate='many_to_one')
    matched=[]
    for stratum in ['source_matched','source_Q5_matched']:
        aa=auxcontext[auxcontext.stratum.eq(stratum)].copy()
        aa['fraction_cross_larger_abs_Q']=np.nan;aa['fraction_cross_larger_abs_Q__valid']=0
        for view in ['method_n_m','class_direction','training_turn_direction']:
            for cohort in ['all_images','priority_seed_images','additional_images']:
                _,small,_,_,_=summarize(aa,registered,AUX_METRICS,core_values.iloc[:0],view,cohort,False,status)
                small['historical_match_stratum']=stratum;matched.append(small)
    files.append(save_csv(prefix+'_HISTORY_MATCHED_CORE_SUMMARY.csv.gz',pd.concat(matched,ignore_index=True)))
    result=dict(status=status,registered_cells=len(index),complete_cells=len(ready),pending_cells=len(pending),
      registered_events=int(pd.to_numeric(index.events).sum()),complete_events=int(p.events.sum()),
      registered_panels=len(registered),complete_panels=len(p),complete_images=p.image.nunique(),complete_buildings=p.building.nunique(),
      input_registration_sha256=sha(EX/'REGISTERED_EVENT_PARTS.csv'),member_panel_sha256=sha(EX/'REGISTERED_MEMBER_PANELS.csv.gz'),
      files=files,native_calls=0,scoring_calls=0,seconds=time.time()-started,base_data_version='v2',
      weighting='actual common background -> image -> building, equal at each level',
      matching='ABC same actual background, n and m; parent fixed for old M fine',
      partial_is_not_final=not full,raw_component_event_medians='provided only for same/cross B8L2 and matched absolute-change advantage; other medians are exact background/image/building medians',
      source_member_space='each registered finite paired-slot or full 2m-choose-m source space, target fixed-reservoir census; not full formal-pool combinations',
      seed_cohort='additional_images are additional to the old priority-seed image list, not claimed unseen data or new external buildings')
    save_json(prefix+'_ANALYSIS_COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--require-complete',action='store_true');args=ap.parse_args();run(args.require_complete)
