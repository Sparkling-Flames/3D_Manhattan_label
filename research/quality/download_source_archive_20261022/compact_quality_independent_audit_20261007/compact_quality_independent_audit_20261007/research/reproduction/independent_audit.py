"""Independent audit of supplied compact results: no imports of analysis implementations.
Recompute descriptive statistics from frozen input tables, eligibility from input objects,
LOBO predictions from direct matched worker pivots, and raw-coordinate geometry checks.
"""
from pathlib import Path
import argparse,json,itertools,sys

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=PROJECT/'unpacked/quality_compact_20261007',help='Extracted compact package root containing inputs/, results/, src/ and reproduce.py')
parser.add_argument('--prior-review',type=Path,default=PROJECT/'prior_unpacked/five_rounds/quality_audit_five_rounds_20261007',help='Extracted five-round audit root containing research/information_study/')
parser.add_argument('--expanded',type=Path,default=PROJECT/'prior_unpacked/expanded_input',help='Extracted expanded input root containing current/panel.json')
parser.add_argument('--official-output',type=Path,default=HERE/'official_run',help='Output directory from the compact reproduce.py run')
parser.add_argument('--output',type=Path,default=HERE,help='Directory for independent audit results; existing audit outputs are replaced')
parser.add_argument('--check-paths',action='store_true',help='Validate input paths and exit without importing numeric libraries or recomputing results')
args=parser.parse_args()
ROOT=args.source.expanduser().resolve();PRIOR=args.prior_review.expanduser().resolve();EXPANDED=args.expanded.expanduser().resolve();RUN=args.official_output.expanduser().resolve();OUT=args.output.expanduser().resolve()
required=[ROOT/'inputs/panel.json',ROOT/'inputs/manual_metrics_reused.csv',ROOT/'inputs/common24_input.json',ROOT/'inputs/prior_full_metrics_reused.csv',ROOT/'inputs/fusion_candidates.json',ROOT/'results',PRIOR/'research/information_study/D_full_panel_metrics.csv',EXPANDED/'current/panel.json',RUN/'manual_scored.csv',RUN/'natural_pair_comparisons.csv',RUN/'broad_lobo_pairs.csv',RUN/'broad_lobo_scales.csv']
missing=[str(p) for p in required if not p.exists()]
if missing:parser.error('Missing required inputs:\n  '+'\n  '.join(missing))
if args.check_paths:
    print(json.dumps({'status':'paths_ok','source':str(ROOT),'prior_review':str(PRIOR),'expanded':str(EXPANDED),'official_output':str(RUN),'output':str(OUT),'required_paths_checked':len(required)},indent=2));raise SystemExit(0)
OUT.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode=True
import numpy as np,pandas as pd
from shapely.geometry import Polygon
checks=[];results={}
def check(name,condition,**details):
    checks.append(dict(check=name,passed=bool(condition),**details))
    if not condition: print('FAILED',name,details)
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x
def save(p,x):
    p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
panel=json.loads((ROOT/'inputs/panel.json').read_text()); images={x['code']:x for x in panel['images']}
records={(x['code'],r['id']):r for x in panel['images'] for r in x['annotations']}
references={(x['code'],r['version']):r for x in panel['images'] for r in x['references']}
d=pd.read_csv(ROOT/'inputs/manual_metrics_reused.csv')
check('no_duplicate_image_worker_reference',not d.duplicated(['image','worker','reference_version']).any())
check('raw_manual_copy_exact', (ROOT/'inputs/manual_metrics_reused.csv').read_bytes()==(PRIOR/'research/information_study/D_full_panel_metrics.csv').read_bytes())
check('current_panel_copy_exact', (ROOT/'inputs/panel.json').read_bytes()==(EXPANDED/'current/panel.json').read_bytes())
d['eligible']=[all([r.get('quality_candidate') is True,r.get('main_quality_gate',{}).get('status')=='candidate_pending_geometry',r.get('condition')=='manual',r.get('independent') is True,r.get('consensus_eligible') is True]) for r in [records[(im,rid)] for im,rid in zip(d.image,d.id)]]
d['quality_gate']=[records[(im,rid)].get('main_quality_gate',{}).get('status') for im,rid in zip(d.image,d.id)]
rename={'centroid_distance_normalized':'C','top_mae_deg':'U','bottom_mae_deg':'B','top3d_symmetric_mean_h':'T','floor3d_symmetric_mean_h':'F'}
d=d.rename(columns=rename);d['L']=1-d.iou;d['LC']=d.L+.5*d.C;d['T_relative']=d['T']/np.sqrt(d.reference_area_h2)
main=d[d.eligible & d.reference_version.eq('original')].copy()
results['coverage']={'old_original':len(d[d.reference_version.eq('original')]),'old_images':d[d.reference_version.eq('original')].image.nunique(),'new_original':len(main),'images':main.image.nunique(),'buildings':main.building.nunique(),'range':main.iou.count(),'angle':main.U.count(),'threeD':main['T'].count(),'provenance':main.angular_provenance.value_counts().to_dict(),'excluded_by_gate':d[d.reference_version.eq('original') & ~d.eligible].quality_gate.value_counts().to_dict()}
check('main_counts',tuple(results['coverage'][k] for k in ['old_original','old_images','new_original','images','buildings','range','angle','threeD'])==(2181,226,1537,154,22,1536,1002,1536))
check('gate_result_matches_saved',np.array_equal(d.eligible,pd.read_csv(RUN/'manual_scored.csv').primary_candidate))
# Reconstruct every current primary reference footprint independently from raw pixel formula.
def raw_xyz(r):
    p=np.array(r['points'],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)%2 or len(p)<6 or not np.isfinite(p).all():raise ValueError('invalid_array')
    if np.any(p<0) or np.any(p[:,0]>1024) or np.any(p[:,1]>512):raise ValueError('outside_continuous_canvas')
    top=p[::2];bot=p[1::2];u=2*np.pi*(bot[:,0]/1024-.5);phi=np.pi*(.5-bot[:,1]/512)
    if np.any(phi>=0):raise ValueError('floor_not_below_horizon')
    rho=-1/np.tan(phi);x=rho*np.sin(u);z=-rho*np.cos(u)
    poly=Polygon(np.c_[x,z])
    if not poly.is_valid or poly.area<=1e-12:raise ValueError('invalid_polygon')
    h=rho*np.tan(np.pi*(.5-top[:,1]/512))
    return np.c_[x,h,z],np.c_[x,-np.ones(len(x)),z],poly
geom=[]
for r in main.itertuples():
    try:
        a=raw_xyz(records[(r.image,r.id)])[2];g=raw_xyz(references[(r.image,'original')])[2];inter=a.intersection(g).area
        iou=inter/(a.area+g.area-inter);C=a.centroid.distance(g.centroid)/np.sqrt(g.area);O=g.difference(a).area/g.area;E=a.difference(g).area/g.area
        geom.append(dict(image=r.image,id=r.id,status='ok',iou_error=iou-r.iou,C_error=C-r.C,identity_error=iou-(1-O)/(1+E)))
    except ValueError as e:geom.append(dict(image=r.image,id=r.id,status='unavailable',reason=str(e),saved_missing=pd.isna(r.iou)))
ge=pd.DataFrame(geom);ge.to_csv(OUT/'independent_primary_geometry.csv',index=False)
results['geometry']={'ok':sum(ge.status=='ok'),'max_iou_error':ge.iou_error.abs().max(),'max_C_error':ge.C_error.abs().max(),'max_identity_error':ge.identity_error.abs().max(),'failures':ge[ge.status!='ok'].to_dict('records')}
check('primary_range_independent_raw_geometry',results['geometry']['max_iou_error']<1e-12 and results['geometry']['max_C_error']<1e-12 and sum(ge.status=='ok')==1536)
# Independently reconstruct directed conflict matrices. Rows source, columns destination.
keys=['L','C','U','B','T','F']; tol=np.array([1e-4,1e-4,.1,.1,.01,.01]);nats=[]
for (im,ver),g in d[d.eligible].groupby(['image','reference_version']):
    g=g.dropna(subset=keys).reset_index(drop=True);x=g[keys].to_numpy();delta=x[None,:,:]-x[:,None,:]
    base=(delta[:,:,0]<-1e-4)&(delta[:,:,1]<=1e-4)&(delta[:,:,2]<=.1)&(delta[:,:,3]<=.1)
    bounds=(g.top3d_a_to_g_mean_quadrature_bound_h+g.top3d_g_to_a_mean_quadrature_bound_h).to_numpy()/2
    for i,j in np.argwhere(base):
        dv=delta[i,j];nats.append(dict(image=im,reference_version=ver,from_id=g.id.iloc[i],to_id=g.id.iloc[j],T_alert=dv[4]>.01,robust=dv[4]-bounds[i]-bounds[j]>.01,upper_only=dv[4]>.01 and dv[5]<=.01))
nat=pd.DataFrame(nats);nat.to_csv(OUT/'independent_natural_pairs.csv',index=False)
results['natural']=nat.groupby('reference_version').agg(base_pairs=('from_id','size'),alert_pairs=('T_alert','sum'),robust=('robust','sum'),upper_only=('upper_only','sum')).to_dict('index')
expected=pd.read_csv(RUN/'natural_pair_comparisons.csv').rename(columns={'upper3d_alert':'T_alert','upper3d_alert_certified_by_sampling_bound':'robust','upper_only_alert':'upper_only'})
ix=['image','reference_version','from_id','to_id'];check('natural_pair_ids_flags',nat.set_index(ix).sort_index().equals(expected[ix+['T_alert','robust','upper_only']].set_index(ix).sort_index()))
# Worker profiles independently build worker x image pivots, complete panels and ranks.
common=json.loads((ROOT/'inputs/common24_input.json').read_text());all10=[x['code'] for x in common['images']];sub=main[main.image.isin(all10)]
counts=sub.groupby('image').U.count();same6=sorted(counts[counts==24].index);profile=[]
for label,ims in [('all10',all10),('same6',same6)]:
    v=sub[sub.image.isin(ims)];assert v.groupby('worker').image.nunique().eq(len(ims)).all()
    m=v.groupby('worker')[keys+['iou','LC','T_relative']].mean()
    for k in ['L','LC','U','B','T','T_relative']:m[k+'_rank']=m[k].rank(method='average')
    m['domain']=label;profile.append(m.reset_index())
pf=pd.concat(profile);pf.to_csv(OUT/'independent_worker_profiles.csv',index=False);p10=pf[pf.domain=='all10'].set_index('worker');p6=pf[pf.domain=='same6'].set_index('worker')
results['worker']={'all10':all10,'same6':same6,'IoU10_LC10_max_rank':abs(p10.L_rank-p10.LC_rank).max(),'IoU10_IoU6_max_rank':abs(p10.L_rank-p6.L_rank).max(),'IoU10_IoU6_mean_rank':abs(p10.L_rank-p6.L_rank).mean(),'P004':{'all10':p10.loc['P004','L_rank'],'same6':p6.loc['P004','L_rank']}}
check('worker_rank_claims',results['worker']['IoU10_LC10_max_rank']==6 and results['worker']['IoU10_IoU6_max_rank']==13 and results['worker']['P004']=={'all10':18.,'same6':5.})
# Independent wide-pivot LOBO: intersection worker menus, train-only medians; no original code imports.
core=['L','C','U','B'];feats=core+['T','T_relative','LC'];q=main.dropna(subset=feats).copy();lookup=q.set_index(['image','worker']);build=q.groupby('image').building.first();workers=sorted(q.worker.unique());pairrows=[];supports=[];scales=[]
for held in sorted(q.building.unique()):
    train=q[q.building!=held];test=q[q.building==held];scale=np.median(np.stack([z[core+['T','T_relative']].median().to_numpy() for _,z in train.groupby('image')]),axis=0);scale=np.maximum(scale,1e-12);scales.append(dict(held_building=held,**dict(zip(core+['T','T_relative'],scale))))
    menus={w:set(z.image) for w,z in train.groupby('worker')}
    for im,z in test.groupby('image'):
        rows={r.worker:r for r in z.itertuples()}
        for wa,wb in itertools.combinations(sorted(rows),2):
            a,b=rows[wa],rows[wb];difference=np.array([getattr(a,k)-getattr(b,k) for k in core]);t=tol[:4]
            b_better=bool(np.all(difference>=-t) and np.any(difference>t));a_better=bool(np.all(difference<=t) and np.any(difference<-t))
            if b_better==a_better:continue
            ims=sorted(menus.get(wa,set())&menus.get(wb,set()));n_bld=len({build[im2] for im2 in ims});eligible=len(ims)>=3 and n_bld>=2
            supports.append(dict(image=im,building=held,a_worker=wa,b_worker=wb,shared_train_images=len(ims),shared_train_buildings=n_bld,eligible=eligible))
            if not eligible:continue
            av=np.array([lookup.loc[(im2,wa),feats].to_numpy(float) for im2 in ims]);bv=np.array([lookup.loc[(im2,wb),feats].to_numpy(float) for im2 in ims]);dv=(av-bv).mean(0);s4=np.sum(dv[:4]/scale[:4]);scores=[dv[0],dv[6],s4,s4+dv[4]/scale[4],s4+dv[5]/scale[5]];exp=1 if b_better else -1
            for scheme,score in zip(['S0','S1','S4','S5','S5_relative'],scores):pairrows.append(dict(image=im,building=held,a_worker=wa,b_worker=wb,scheme=scheme,score_difference=score,expected_sign=exp,correct=.5 if abs(score)<=1e-12 else float(np.sign(score)==exp)))
lo=pd.DataFrame(pairrows);lo.to_csv(OUT/'independent_broad_lobo_pairs.csv',index=False);pd.DataFrame(scales).to_csv(OUT/'independent_lobo_scales.csv',index=False);pd.DataFrame(supports).to_csv(OUT/'independent_lobo_support.csv',index=False)
ix=['image','building','a_worker','b_worker','scheme'];saved=pd.read_csv(RUN/'broad_lobo_pairs.csv').set_index(ix).sort_index();actual=lo.set_index(ix).sort_index()
check('independent_LOBO_same_pair_labels_predictions',actual.index.equals(saved.index) and np.array_equal(actual.expected_sign,saved.expected_sign) and np.array_equal(actual.correct,saved.correct),max_score_error=float(abs(actual.score_difference-saved.score_difference).max()))
check('independent_LOBO_same_scales',np.allclose(pd.DataFrame(scales).set_index('held_building').sort_index(),pd.read_csv(RUN/'broad_lobo_scales.csv').set_index('held_building').sort_index(),rtol=1e-13,atol=1e-13))
image_acc=lo.groupby(['scheme','building','image']).correct.mean();building_acc=image_acc.groupby(['scheme','building']).mean();overall=building_acc.groupby('scheme').mean();pair_weight=lo.groupby('scheme').correct.mean();image_weight=image_acc.groupby('scheme').mean()
results['LOBO']={'records':len(q),'raw_images':q.image.nunique(),'images':lo.image.nunique(),'buildings':lo.building.nunique(),'pairs':len(lo)//5,'attempted':len(supports),'prediction_ties':int(lo.correct.eq(.5).sum()),'building_equal':overall.to_dict(),'image_equal':image_weight.to_dict(),'pair_equal':pair_weight.to_dict(),'train_min_images':min(r['shared_train_images'] for r in supports if r['eligible']),'train_min_buildings':min(r['shared_train_buildings'] for r in supports if r['eligible'])}
# Fusion common domains from frozen source metrics and state completeness.
f=pd.read_csv(ROOT/'inputs/prior_full_metrics_reused.csv');f=f[f.kind.eq('fusion')].rename(columns=rename);f['L']=1-f.iou;f['LC']=f.L+.5*f.C;states=json.loads((ROOT/'inputs/fusion_candidates.json').read_text())['states'];state_summary={};rosters=[]
for s in states:
    c=s['result'].get('candidate') or {};state_summary.setdefault(s['route'],[0,0]);state_summary[s['route']][0]+=1;state_summary[s['route']][1]+=bool(c.get('points'))
    rr=[r for r in images[s['image']]['annotations'] if r.get('independent') and r.get('consensus_eligible') and r.get('condition')=='manual' and r.get('main_consensus_gate',{}).get('status') in ['main_candidate','oos_doorway_exploratory','stable_nonorthogonal_separate']]
    actual_ids=set(d[d.image.eq(s['image']) & d.reference_version.eq('original')].id)
    rosters.append(set(r['id'] for r in rr)==actual_ids and len(rr)==s['n'])
fo=f[f.reference_version.eq('original')];range_ims=set.intersection(*[set(z[z.iou.notna()].image) for _,z in fo.groupby('route')]);angle_ims=set.intersection(*[set(z[z.U.notna() & z.B.notna()].image) for _,z in fo.groupby('route')]);fm=fo[fo.image.isin(angle_ims)].groupby('route')[['iou','LC','U','B','T','F']].mean();fm.to_csv(OUT/'independent_fusion_matched.csv')
base_pairs=0;alerts=0
for im,z in fo.groupby('image'):
    a=z[z.route=='paired'].iloc[0]
    for _,b in z[z.route!='paired'].iterrows():
        if not a[keys].notna().all() or not b[keys].notna().all():continue
        if b.L<a.L-1e-4 and b.C<=a.C+1e-4 and b.U<=a.U+.1 and b.B<=a.B+.1:base_pairs+=1;alerts+=b['T']>a['T']+.01
results['fusion']={'states':len(states),'complete':sum(v[1] for v in state_summary.values()),'by_route':state_summary,'range_common_images':len(range_ims),'angle_common_images':len(angle_ims),'full_pool_angle_common_images':sum(d[d.image.eq(im)&d.reference_version.eq('original')].U.notna().all() for im in angle_ims),'base_pairs':base_pairs,'T_alerts':int(alerts),'mean_same24':fm.to_dict('index'),'pool_roster_same_ids':all(rosters)}
check('fusion_counts_and_rosters',len(states)==220 and sum(v[1] for v in state_summary.values())==210 and len(range_ims)==35 and len(angle_ims)==24 and base_pairs==13 and alerts==0 and all(rosters))
# Compare every recomputed official CSV to archived CSV, allowing only tiny numeric drift.
comp=[]
for file in RUN.glob('*.csv'):
    archive=ROOT/'results'/file.name
    if not archive.exists():continue
    a=pd.read_csv(file);b=pd.read_csv(archive);ok=a.shape==b.shape and a.columns.tolist()==b.columns.tolist();err=0.
    if ok:
        for col in a:
            if pd.api.types.is_numeric_dtype(a[col]) and pd.api.types.is_numeric_dtype(b[col]):
                ok=ok and bool(np.allclose(a[col],b[col],rtol=1e-12,atol=1e-12,equal_nan=True));err=max(err,float(abs(a[col]-b[col]).max()) if not pd.api.types.is_bool_dtype(a[col]) else 0.)
            else:ok=ok and a[col].fillna('<NA>').equals(b[col].fillna('<NA>'))
    comp.append(dict(file=file.name,passed=ok,max_numeric_error=err,rows=len(a)))
save(OUT/'official_archive_csv_comparison.json',comp);check('official_reproduction_all_csv_match',all(x['passed'] for x in comp),tables=len(comp))
results['checks']=checks;save(OUT/'independent_audit.json',results);print(json.dumps(results,ensure_ascii=False,indent=2,default=lambda v:v.item() if isinstance(v,np.generic) else str(v)))
if not all(x['passed'] for x in checks):sys.exit(1)
