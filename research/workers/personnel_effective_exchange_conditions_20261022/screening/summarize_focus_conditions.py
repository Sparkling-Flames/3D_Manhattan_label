"""Readable complete-component decisions for inherited and screened conditions."""
from __future__ import annotations
from common_screening import *
from screen_conditions import read_events,balanced,ALL_METRICS,METRICS_CORE
from internal_lobo_check import ci_values

FOCUS=[
 dict(focus_id='A2_manual_n17m9',condition='manual',method_id='A2_relation',tier='single',source_domain='all_formal',n=17,m=9,basis='any',direction='',selection_identity='inherited_prior_candidate',use='same-composition stability / cross-composition risk'),
 dict(focus_id='M_fine_n10m5_M01_to_M00',condition='manual',method_id='M_structure',tier='fine',source_domain='all_formal',n=10,m=5,basis='raw',direction='M01:5 -> M00:5',selection_identity='inherited_prior_candidate',use='parent-fixed fine-class stability; limited original building support'),
 dict(focus_id='M_fine_n10m6_M01_to_M00',condition='manual',method_id='M_structure',tier='fine',source_domain='all_formal',n=10,m=6,basis='raw',direction='M01:6 -> M00:6',selection_identity='inherited_prior_candidate',use='parent-fixed fine-class stability / quality loss direction'),
 dict(focus_id='BEHAVIOR_manual_n10m7_all_roles',condition='manual',method_id='V3_BEHAVIOR',tier='coarse',source_domain='all_formal',n=10,m=7,basis='any',direction='',selection_identity='inherited_prior_candidate',use='broad observed candidate; folds and directions still separated in exact tables'),
 dict(focus_id='BEHAVIOR_TURN3_E2_to_E3_n10m7',condition='manual',method_id='V3_BEHAVIOR',tier='coarse',source_domain='all_formal',n=10,m=7,basis='role',direction='TURN/K3/E2:7 -> TURN/K3/E3:7',selection_identity='training-role refinement of inherited candidate',use='increased historical turn/detail expression'),
 dict(focus_id='JOINT_CQT5_C2Q1T2_to_C5Q5T4_n10m7',condition='manual',method_id='V3_JOINT_QT',tier='coarse',source_domain='all_formal',n=10,m=7,basis='role',direction='CQT/K5/C2,Q1,T2:7 -> CQT/K5/C5,Q5,T4:7',selection_identity='selected by uniform broad screen on explored outcomes',use='joint structural/Q/T quality and shape response'),
 dict(focus_id='JOINT_CQT5_C2Q1T2_to_C5Q5T4_n20m7',condition='manual',method_id='V3_JOINT_QT',tier='coarse',source_domain='all_formal',n=20,m=7,basis='role',direction='CQT/K5/C2,Q1,T2:7 -> CQT/K5/C5,Q5,T4:7',selection_identity='same-direction larger-team comparison',use='test attenuation at a larger team size'),
 dict(focus_id='SP_semi_coarse_n12m4_add_LOW_seat',condition='semi',method_id='SP_scale',tier='coarse',source_domain='all_formal',n=12,m=4,basis='raw',direction='SP_OTHER:4 -> SP_LOW:1|SP_OTHER:3',selection_identity='selected by uniform broad screen on explored outcomes',use='scale-related stability / failure and quality risk'),
 dict(focus_id='SP_semi_fine_n12m4_add_A_seat_parent_fixed',condition='semi',method_id='SP_scale',tier='fine',source_domain='all_formal',n=12,m=4,basis='raw',direction='SP_T:4 -> SP_A:1|SP_T:3',selection_identity='selected by uniform broad screen on explored outcomes',use='additional parent-fixed scale distinction'),
 dict(focus_id='MV_semi_fine_n10m4_QL1_to_QL2',condition='semi',method_id='MV_QTScopeSemi_semi_new',tier='fine',source_domain='all_formal_labelled',n=10,m=4,basis='raw',direction='QL.1:4 -> QL.2:4',selection_identity='selected by uniform broad screen on explored outcomes',use='conditional quality change within low-Q parent'),
 dict(focus_id='MV_manual_fine_n10m5_QL2_to_QL1',condition='manual',method_id='MV_QTD_manual_new',tier='fine',source_domain='all_formal_labelled',n=10,m=5,basis='raw',direction='QL.2:5 -> QL.1:5',selection_identity='selected by uniform broad screen on explored outcomes',use='recorded-time reduction with limited average Q cost'),
 dict(focus_id='F01_manual_n10m4_C02_to_C01',condition='manual',method_id='F01',tier='coarse',source_domain='new_only_labelled',n=10,m=4,basis='raw',direction='C02:4 -> C01:4',selection_identity='selected by uniform broad screen on explored outcomes',use='high-Q-domain recorded-time tradeoff; AC-only if same-class arm unavailable'),
]

def main():
    d=read_events();pieces=[];opportunities=[]
    for case in FOCUS:
        mask=np.ones(len(d),dtype=bool)
        for f in ['condition','method_id','tier','source_domain','n','m']:mask &= d[f].eq(case[f]).to_numpy()
        sub=d[mask].copy()
        for orientation in ['registered_direction','opposite_direction'] if case['basis']!='any' else ['all_directions']:
            direction=case['direction']
            if orientation=='opposite_direction':direction=' -> '.join(direction.split(' -> ')[::-1])
            x=sub if case['basis']=='any' else sub[sub['raw_block_direction' if case['basis']=='raw' else 'role_block_direction'].eq(direction)]
            for comparison in ['ABC_matched','AC_only']:
                z=x[x.comparison.eq(comparison)].copy()
                opportunities.append(dict(case,orientation=orientation,comparison=comparison,
                    events=len(z),images=z.image.nunique(),buildings=z.building.nunique(),status='observed' if len(z) else 'no_archived_condition_event'))
                if not len(z):continue
                z['focus_id']=case['focus_id'];z['orientation']=orientation
                z['candidate_id']=case['focus_id']+'|'+orientation+'|'+comparison
                pieces.append(z)
    x=pd.concat(pieces,ignore_index=True)
    bg,im,b=balanced(x,ALL_METRICS)
    metadata={r['focus_id']:r for r in FOCUS};rows=[];support=[]
    for cid,g in x.groupby('candidate_id'):
        z=b.loc[cid];images=im.loc[cid];meta=metadata[g.focus_id.iloc[0]]
        sup=dict(**meta,orientation=g.orientation.iloc[0],comparison=g.comparison.iloc[0],candidate_id=cid,
          events=len(g),backgrounds=g.common_background_id.nunique(),images=g.image.nunique(),buildings=g.building.nunique(),
          actual_exchange_sets=g.actual_exchange_id.nunique(),unique_teams=len(set(g.team_A)|set(g.team_C)|set(g.team_B.dropna())),
          class_seat_min=int(g.composition_turnover_AC.min()),class_seat_max=int(g.composition_turnover_AC.max()),
          parent_fixed_events=int(g.parent_fixed.sum()),Q5_source_matched_events=int(g.source_and_historyQ5_matched.sum()),
          source_matched_events=int(g.same_source_counts.sum()),A_failed=int(g.A_failure.sum()),
          B_failed=int(g.B_failure.sum()) if g.B_failure.notna().any() else None,C_failed=int(g.C_failure.sum()),
          selected_families='|'.join(sorted(g.fold_selected_family.astype(str).unique())),
          fine_k_min=g.fold_fine_k.min(),fine_k_max=g.fold_fine_k.max(),coarse_k_min=g.fold_coarse_k.min(),coarse_k_max=g.fold_coarse_k.max())
        support.append(sup)
        for metric in ALL_METRICS:
            v=g[metric].dropna().to_numpy(float);iv=images[metric].dropna().to_numpy(float);bv=z[metric].dropna().to_numpy(float)
            if not len(v):continue
            lo,hi=ci_values(bv)
            rows.append(dict(focus_id=meta['focus_id'],orientation=sup['orientation'],comparison=sup['comparison'],
                metric=metric,events=len(g),valid_events=len(v),event_mean=v.mean(),event_median=np.median(v),
                images=g.image.nunique(),valid_images=len(iv),image_mean=iv.mean(),image_median=np.median(iv),
                positive_images=int((iv>1e-10).sum()),negative_images=int((iv< -1e-10).sum()),zero_images=int((abs(iv)<=1e-10).sum()),
                buildings=g.building.nunique(),valid_buildings=len(bv),building_mean=bv.mean(),building_median=np.median(bv),
                positive_buildings=int((bv>1e-10).sum()),negative_buildings=int((bv< -1e-10).sum()),zero_buildings=int((abs(bv)<=1e-10).sum()),
                building_bootstrap_lo95=lo,building_bootstrap_hi95=hi))
    receipts=[]
    for name,table in [('FOCUS_DEFINITIONS_AND_OPPORTUNITIES.csv',pd.DataFrame(opportunities)),
       ('FOCUS_CONDITION_SUPPORT.csv',pd.DataFrame(support)),('FOCUS_ALL_COMPONENT_METRICS.csv.gz',pd.DataFrame(rows)),
       ('FOCUS_BUILDING_COMPONENTS.csv.gz',b.reset_index()),('FOCUS_IMAGE_COMPONENTS.csv.gz',im.reset_index()),
       ('FOCUS_EVENT_MEMBERSHIP.csv.gz',x[['focus_id','orientation','comparison','candidate_id','analysis_event_id','event_id']])]:
        receipts.append(save_csv(name,table))
    save_json('FOCUS_SUMMARY_COMPLETION.json',dict(status='complete',focus_definitions=FOCUS,files=receipts,
      data_version='v2',native_calls=0,discovery_note='Inherited candidates and broad-screen discoveries are explicitly marked; no new blind-test claim.',
      inference='Building bootstrap intervals describe repeated explored evidence; no multiple-comparison or external-validation claim.'))
    print(json.dumps(dict(status='complete',focus_conditions=len(support),metric_rows=len(rows))),flush=True)

if __name__=='__main__':main()
