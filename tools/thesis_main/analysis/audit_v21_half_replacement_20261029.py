"""半队替换的逐图诊断；复用保存事件，不拟合类别或执行融合。"""
from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/workers/personnel_v21_reselection_20261029'
OUT = ROOT / 'research/data/releases/v2.1/simulated_population_evidence/exchange'
KEY = ['method', 'condition', 'layer', 'scope', 'source_class', 'target_class', 'n', 'm']

def flags(r):
    gap, cb = r['B8L2_gap'], r['B8L2_CB']
    return dict(amplitude_nonpositive=bool(pd.notna(gap) and gap <= 0),
                quality_nonpositive=bool(pd.notna(cb) and cb <= 0),
                missing_common_quality=bool(pd.isna(gap)),
                geometry_larger_despite_Q_gap=bool(pd.notna(gap) and gap <= 0 and r.get('geometry_bev_distance_gap', np.nan) > 0))

def main():
    all_rows=[]; counts=[]; events=[]; reasons=[]
    sources={'focused': BASE/'analysis/focused_compact/EVENT_EFFECTS_COMPLETE.csv.gz',
             'screen': BASE/'additional_delivery/packages/05A/analysis/global_screen_compact/EVENT_EFFECTS_COMPLETE.csv.gz'}
    for stage, path in sources.items():
        d=pd.read_csv(path, low_memory=False); d=d[d.n.eq(2*d.m)].copy()
        pair=pd.read_csv(path.parent/'PAIR_GEOMETRY.csv.gz')
        lookup={tuple(sorted((r.team_1,r.team_2))):r.geometry_bev_distance for r in pair.itertuples()}
        for arm in ['AB','AC','BC']:
            d['bev_'+arm]=[lookup.get(tuple(sorted((a,b))),np.nan) for a,b in zip(d[arm[0]+'_team_key'],d[arm[1]+'_team_key'])]
        d['geometry_bev_distance_gap']=(d.bev_AC+d.bev_BC)/2-d.bev_AB
        ok=d[['B8L2_BA','B8L2_CA','B8L2_CB']].notna().all(axis=1)
        d['C_between_A_B']=np.where(ok,((d.B8L2_CA>=np.minimum(0,d.B8L2_BA))&(d.B8L2_CA<=np.maximum(0,d.B8L2_BA))).astype(float),np.nan)
        d['loss_components_opposed']=np.where(ok,((d[['boundary_loss_CB','direction_loss_CB','height_loss_CB']].min(axis=1)<0)&(d[['boundary_loss_CB','direction_loss_CB','height_loss_CB']].max(axis=1)>0)).astype(float),np.nan)
        endpoint_path=(BASE/'experiment/focused_endpoints/ENDPOINT_SCALARS.csv.gz' if stage=='focused' else BASE/'additional_delivery/packages/05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz')
        ep=pd.read_csv(endpoint_path,low_memory=False).set_index('team_key')
        assert ep.index.is_unique
        for arm in 'ABC':
            for field in ['B8L2','nodes','half_vote_nodes']:
                d[arm+'_'+field]=d[arm+'_team_key'].map(ep[field])
            for field in ['score_status','geometry_reason']:
                d[arm+'_'+field]=d[arm+'_team_key'].map(ep[field])
        d['stage']=stage
        design_path=(BASE/'experiment/focused_design/EVENTS_EXACT.csv.gz' if stage=='focused' else BASE/'additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz')
        design=pd.read_csv(design_path,usecols=['event_id','D','X','Y','Z'])
        d=d.merge(design,on='event_id',validate='one_to_one')
        assert d[['D','X','Y','Z']].notna().all().all()
        events.append(d)
        for arm in 'ABC':
            bad=d[d[arm+'_B8L2'].isna()]
            for key,g in bad.groupby(KEY+[arm+'_score_status',arm+'_geometry_reason'],dropna=False):
                reasons.append(dict(zip(KEY+['score_status','geometry_reason'],key),stage=stage,arm=arm,events=len(g),images=g.image.nunique()))
        assert np.allclose(d.B8L2_cross-d.B8L2_within,d.B8L2_gap,equal_nan=True)
        assert not d.event_id.duplicated().any()
        numeric=[c for c in d.select_dtypes(include=['number','bool']) if c not in KEY]
        # 先池内再图内等权；不同阶段、方向与目标难度不混合。
        pool=d.groupby(KEY+['official_difficulty','building','image','pool_id'],dropna=False)[numeric].mean().reset_index()
        images=pool.groupby(KEY+['official_difficulty','building','image'],dropna=False)[numeric].mean().reset_index()
        images['stage']=stage; images['source_table']=path.relative_to(ROOT).as_posix()
        images=pd.concat([images,images.apply(lambda r:pd.Series(flags(r)),axis=1)],axis=1)
        all_rows.append(images)
        for key,g in images.groupby(KEY+['official_difficulty'],dropna=False):
            row=dict(zip(KEY+['official_difficulty'],key));row.update(stage=stage,images=len(g),buildings=g.building.nunique(),
                gap_valid=int(g.B8L2_gap.notna().sum()),gap_positive=int(g.B8L2_gap.gt(0).sum()),
                CB_valid=int(g.B8L2_CB.notna().sum()),CB_positive=int(g.B8L2_CB.gt(0).sum()),
                mean_gap=g.B8L2_gap.mean(),mean_CB=g.B8L2_CB.mean(),
                amplitude_nonpositive=int(g.amplitude_nonpositive.sum()),quality_nonpositive=int(g.quality_nonpositive.sum()),
                missing_common_quality=int(g.missing_common_quality.sum()))
            counts.append(row)
    image=pd.concat(all_rows,ignore_index=True)
    image.to_csv(OUT/'HALF_REPLACEMENT_IMAGE_DIAGNOSTICS.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(counts).to_csv(OUT/'HALF_REPLACEMENT_DIFFICULTY.csv',index=False,encoding='utf-8-sig')
    abnormal=image[image.amplitude_nonpositive|image.quality_nonpositive|image.missing_common_quality]
    abnormal.to_csv(OUT/'HALF_REPLACEMENT_EXCEPTION_COMPONENTS.csv',index=False,encoding='utf-8-sig')
    pd.concat(events,ignore_index=True).to_csv(OUT/'HALF_REPLACEMENT_EVENT_DIAGNOSTICS.csv.gz',index=False,encoding='utf-8-sig')
    pd.DataFrame(reasons).to_csv(OUT/'HALF_REPLACEMENT_UNSCORABLE_REASONS.csv',index=False,encoding='utf-8-sig')
    (OUT/'HALF_REPLACEMENT_CHECKS.json').write_text(json.dumps({'image_condition_rows':len(image),'exception_rows':len(abnormal),
        'classification_selection':'undecided','new_fusion':False,'new_labels':False,
        'contract':'stage and class direction separate; pool then image equal; per-metric finite support; flags describe scalar evidence, not causal attribution; official difficulty unknown retained',
        'MV50':'n=2m; threshold=m; all m block members must support the same correspondence group to reach threshold alone; D can also reach threshold alone'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(len(image),len(abnormal))

if __name__=='__main__': main()
