"""Update the strict side of existing AC bridges from the audited half-team patch."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from .evaluate_manual_order_ac_20261104 import ROOT,AC,OUT,RESULT,save,jsave,compare,align,iter_jsonl
from .evaluate_manual_order_ac_sensitivity_20261104 import changed_rows,patch,subset

SOURCE=AC/'stage05_funnel_bridge'
CONTEXTS={}
CELL=['strict_source_family','pool_id','image','building','scope','method','n','m','source_class','target_class',
      'canonical_source_class','canonical_target_class','strict_to_canonical_sign','strict_role_direction']


def normalized(original,half,s):
    out=original.copy().set_index('event_id')
    for r in half.to_dict('records'):
        if r['event_id'] not in out.index:continue
        own=out.loc[r['event_id']];sign=own.strict_to_canonical_sign
        for k in ['A_team_key','B_team_key','C_team_key']:
            assert r[k]==own[k],(r['event_id'],k)
        bound=[CONTEXTS[r[a+'_team_key']] for a in 'ABC' if r[a+'_team_key'] in CONTEXTS]
        assert bound and all(v==(own.reference_id,own.reference_version) for v in bound)
        for k in ['reference_id','reference_version']:
            if pd.notna(r.get(k)):assert r[k]==own[k],(r['event_id'],k)
        values={}
        for metric in s.SCALAR_METRICS:
            v=[]
            for leg in ['BA','CA','CB']:
                col=metric+'__delta_'+leg
                if col not in r:col=metric+'_'+leg
                v.append(pd.to_numeric(r.get(col),errors='coerce'))
            ba,ca,cb=v;valid=all(np.isfinite(x) for x in v)
            values.update({metric+'_BA':ba,metric+'_strict_CA':ca,metric+'_strict_CB':cb,
                metric+'_canonical_CA':sign*ca,metric+'_canonical_CB':sign*cb,metric+'_abs_CA':abs(ca),
                metric+'_ABC_valid':valid,metric+'_within_AB':abs(ba) if valid else np.nan,
                metric+'_G_A':abs(ca)-abs(ba) if valid else np.nan,
                metric+'_G_S':(abs(ca)+abs(cb))/2-abs(ba) if valid else np.nan})
        for metric in s.PAIR_METRICS:
            ab,ac,bc=[pd.to_numeric(r.get(metric+'_'+leg),errors='coerce') for leg in ['AB','AC','BC']]
            valid=all(np.isfinite(v) for v in [ab,ac,bc])
            values.update({metric+'_AB':ab,metric+'_AC':ac,metric+'_BC':bc,metric+'_ABC_valid':valid,
                metric+'_G_A':ac-ab if valid else np.nan,metric+'_G_S':(ac+bc)/2-ab if valid else np.nan})
        out.loc[r['event_id'],list(values)]=list(values.values())
    return out.reset_index()[original.columns]


def aggregate(d,s):
    result=[]
    for key,g in d.groupby(CELL,dropna=False,sort=True):
        base=dict(zip(CELL,key));base.update(registered_ABC_events=len(g),registered_blocks=g.block_id.nunique())
        for metric in s.SCALAR_METRICS+s.PAIR_METRICS:
            fields=({'strict_signed_CA':metric+'_strict_CA','canonical_signed_CA':metric+'_canonical_CA',
                     'absolute_CA':metric+'_abs_CA','within_AB':metric+'_within_AB','G_A':metric+'_G_A','G_S':metric+'_G_S'}
                    if metric in s.SCALAR_METRICS else {'absolute_CA':metric+'_AC','within_AB':metric+'_AB','G_A':metric+'_G_A','G_S':metric+'_G_S'})
            row=dict(base,metric=metric)
            for label,col in fields.items():
                bg=g.groupby('block_id')[col].mean();v=g[col].dropna()
                row.update({label+'_mean':bg.mean(),label+'_valid_events':len(v),label+'_valid_blocks':int(bg.notna().sum()),label+'_event_p10':v.quantile(.1) if len(v) else np.nan})
            row['ABC_valid_events']=int(g[metric+'_ABC_valid'].sum());result.append(row)
    return pd.DataFrame(result)


def bridge_summary(d,s):
    rows=[];keys=['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric']
    for key,g in d[d.new_AC_condition_match.eq('both')].groupby(keys,dropna=False):
        oldcol='strict_signed_CA_mean' if key[-1] in s.SCALAR_METRICS else 'absolute_CA_mean'
        z=g[g[oldcol].notna()&g.new_strict_direction_signed_or_distance_mean.notna()]
        rows.append(dict(zip(keys,key),matched_target_pools=len(g),jointly_evaluable_pools=len(z),buildings=z.building.nunique(),
            strict_signed_or_distance_mean=z[oldcol].mean(),direct_AC_signed_or_distance_mean=z.new_strict_direction_signed_or_distance_mean.mean(),
            strict_absolute_CA_mean=z.absolute_CA_mean.mean(),direct_AC_absolute_CA_mean=z.new_absolute_change_mean.mean(),strict_within_AB_mean=z.within_AB_mean.mean(),
            strict_G_A_mean=z.G_A_mean.mean(),strict_G_S_mean=z.G_S_mean.mean(),strict_G_A_positive_pools=int(z.G_A_mean.gt(1e-9).sum()),strict_G_A_valid_pools=int(z.G_A_mean.notna().sum()),
            direct_AC_positive_pools=int(z.new_strict_direction_signed_or_distance_mean.gt(1e-9).sum()) if key[-1] in s.SCALAR_METRICS else None,
            direct_AC_negative_pools=int(z.new_strict_direction_signed_or_distance_mean.lt(-1e-9).sum()) if key[-1] in s.SCALAR_METRICS else None,
            signed_direction_agreement_pools=int((np.sign(z[oldcol])==np.sign(z.new_strict_direction_signed_or_distance_mean)).sum()) if key[-1] in s.SCALAR_METRICS else None,
            note='New AC has no B; historical within/G metrics are a separate strict-ABC reference, not a new cross-minus-within estimate.'))
    return pd.DataFrame(rows)


def main():
    global CONTEXTS
    CONTEXTS={r['team_key']:(r['reference_id'],r['reference_version']) for r in iter_jsonl(RESULT/'endpoints/ENDPOINTS.jsonl.gz')}
    sys.path.insert(0,str(SOURCE/'code'));import prepare_strict_bridge as s
    out=OUT/'strict_bridge';out.mkdir(exist_ok=True)
    old=pd.read_csv(SOURCE/'STRICT_NORMALIZED_EVENTS.csv.gz',low_memory=False)
    h0=pd.read_csv(RESULT/'half_qonly/HALF_AUTOMATIC_EVENTS.csv.gz',low_memory=False)
    h1=pd.read_csv(RESULT/'half_qonly/HALF_ASSISTED_EVENTS.csv.gz',low_memory=False)
    h1=h1[h1.human_order_applied_arms.notna()&h1.human_order_applied_arms.ne('')]
    h0=h0[h0.event_id.isin(h1.event_id)]
    before=old[old.event_id.isin(h1.event_id)]
    assert len(before)==13
    parity=compare(before,normalized(before,h0,s),['event_id'],'original_13_strict_normalized_events')
    new=normalized(old,h1,s)
    save(new,out/'STRICT_NORMALIZED_EVENTS.csv.gz')
    chosen=before[CELL].drop_duplicates();a=aggregate(subset(old,chosen,CELL),s);b=aggregate(subset(new,chosen,CELL),s)
    original_summary=pd.read_csv(SOURCE/'STRICT_IMAGE_CONDITION_METRICS.csv.gz',low_memory=False)
    keys=CELL+['metric'];parity.extend(compare(subset(original_summary,chosen,CELL),a,keys,'original_strict_condition_summary'))
    patched=patch(original_summary,b,keys);save(patched,out/'STRICT_IMAGE_CONDITION_METRICS.csv.gz')
    bridge=pd.read_csv(SOURCE/'STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz',low_memory=False)
    # Direct AC affected events have no canonical condition overlap with the
    # frozen strict reference; the historical strict side still changes.
    ac=pd.read_csv(OUT/'AFFECTED_EVENT_METRICS_AUTOMATIC.csv.gz',low_memory=False)
    ck=['pool_id','method','n','m','source_class','target_class']
    sk=original_summary.rename(columns={'source_class':'strict_source_class','target_class':'strict_target_class','canonical_source_class':'source_class','canonical_target_class':'target_class'})[ck].drop_duplicates()
    assert ac.merge(sk,on=ck).empty
    ix=bridge[ keys ].copy();v=b.set_index(keys)
    enhanced=bridge.copy()
    positions=pd.MultiIndex.from_frame(ix).isin(v.index)
    ixidx=pd.MultiIndex.from_frame(ix.loc[positions])
    for col in b:
        if col not in keys:enhanced.loc[positions,col]=v.loc[ixidx,col].to_numpy()
    save(enhanced,out/'STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz')
    a,b=bridge_summary(bridge,s),bridge_summary(enhanced,s)
    k=['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric']
    parity.extend(compare(pd.read_csv(SOURCE/'STRICT_ABC_DIRECT_AC_COMMON_CONDITION_SUMMARY.csv'),a,k,'original_joint_strict_direct_summary'))
    save(b,out/'STRICT_ABC_DIRECT_AC_COMMON_CONDITION_SUMMARY.csv')
    c0,c1=changed_rows(a,b,k);save(align(c0,k).add_prefix('automatic_').join(align(c1,k).add_prefix('assisted_')).reset_index(),out/'STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz')
    brief=pd.read_csv(SOURCE/'STRICT_M10_COMMON_CONDITION_BRIEF.csv')
    ten=enhanced[enhanced.strict_source_family.eq('latest_m9_m10')&enhanced.m.eq(10)&enhanced.metric.isin(['B8L2','D10'])&enhanced.new_AC_condition_match.eq('both')]
    save(ten[brief.columns],out/'STRICT_M10_COMMON_CONDITION_BRIEF.csv')
    pair=pd.read_csv(SOURCE/'STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz')
    assert not (pair.F_event_id.isin(ac.event_id)|pair.B_event_id.isin(ac.event_id)).any()
    save(pd.DataFrame(parity),out/'PARITY.csv')
    jsave(out/'STRICT_BRIDGE_RECEIPT.json',dict(strict_changed_events=13,new_direct_AC_in_strict_conditions=0,
        strict66_background_changed_pairs=0,changed_joint_summary_rows=len(c1),
        labels_and_pair_identities_unchanged=True,new_ABC_created=False,source_half='half_qonly/HALF_ASSISTED_EVENTS.csv.gz',
        note='Existing strict ABC is a distinct reference; direct AC still has no B team.'))
    print('strict bridge completed',len(c1),flush=True)


if __name__=='__main__':main()
