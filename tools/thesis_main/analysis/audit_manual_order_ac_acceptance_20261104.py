"""Independent AC acceptance and support-composition decomposition.

Reads the frozen source at ac395e7 and the five immutable manual-order batches.
Does not fuse, score, select teams, fit classifiers, or adopt coordinate edits.
Aggregations below are written independently of the earlier overlay runners.
Frozen producer code is read only to identify the registered estimands.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from functools import lru_cache

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OLD = ROOT / 'research/fusion/manual_order_impact_20261104/ac'
OUT = ROOT / 'research/fusion/manual_order_acceptance_20261104/ac'
CACHE = OUT / 'source_cache'
TOL = 1e-7
COMMIT = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
GROUP = ['analysis_view', 'scope', 'condition', 'layer', 'method', 'role_direction',
         'n_condition', 'm_condition']
SPECS = {
 'MEMBER_PANELS': ['scope','condition','layer','method','panel_kind','role_direction','n','m'],
 'BACKGROUND_CHANGES': ['scope','condition','layer','method','comparison','background_profile','role_direction','n','m'],
 'FIXED_BLOCK_BACKGROUND_STEPS': ['scope','condition','layer','method','role_direction','n_from','n_to','m_from','m_to'],
 'FIXED_A_REPLACEMENT_STEPS': ['scope','condition','layer','method','role_direction','n_from','m_from','m_to'],
 'UNEQUAL_DECOMPOSITION': ['scope','condition','layer','method','role_direction','background_profile'],
 'COMPLETE_COALITIONS': ['scope','condition','layer','method','role_direction','number_condition','unknown_background_included'],
 'SAMPLING_BATCHES': ['scope','condition','layer','method','role_direction','n','m'],
}
THREE = ['scope','condition','layer','method','role_direction','background_profile','parent_background_stratum']
EXACT = ['scope','condition','layer','method','role_direction','n','m','background_change_type']
COHORT = ['method','scope','role_direction','n','m','metric']
AUDITS: list[dict] = []
CONSUMERS: list[dict] = []
FILTERS = {}
RUNTIME_INPUTS = set()


def clean(v):
    if isinstance(v, dict): return {str(k): clean(x) for k,x in v.items()}
    if isinstance(v, (list,tuple,np.ndarray)): return [clean(x) for x in v]
    if isinstance(v, np.generic): return clean(v.item())
    if isinstance(v, float) and not math.isfinite(v): return None
    return v


def jsave(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def save(frame, path):
    path.parent.mkdir(parents=True,exist_ok=True)
    content=frame.to_csv(index=False).encode('utf-8-sig')
    if path.name.endswith('.gz'): content=gzip.compress(content,mtime=0)
    path.write_bytes(content)


@lru_cache(maxsize=80)
def read(path):
    RUNTIME_INPUTS.add(Path(path))
    return pd.read_csv(path,low_memory=False)


def norm(x):
    if pd.isna(x): return ''
    if isinstance(x,(bool,np.bool_)): return str(bool(x)).lower()
    if isinstance(x,(int,float,np.number)): return format(float(x),'.12g')
    return str(x)


def pick(frame, condition, keys):
    cachekey=(id(frame),tuple(keys))
    hit=FILTERS.get(cachekey)
    if hit is None or hit[0] is not frame:
        tmp=pd.DataFrame({key:frame[key].map(norm) for key in keys},index=frame.index)
        groups=tmp.groupby(list(keys),dropna=False,sort=False).indices
        # Hold the frame reference so Python cannot recycle its id underneath the cache.
        FILTERS[cachekey]=(frame,groups)
        hit=FILTERS[cachekey]
    target=tuple(norm(condition[key]) for key in keys)
    if len(keys)==1: target=target[0]
    idx=hit[1].get(target,[])
    return frame.iloc[idx].copy()


def assert_close(name, observed, expected, tolerance=TOL, **metadata):
    a=np.asarray(observed,dtype=float);b=np.asarray(expected,dtype=float)
    a,b=np.broadcast_arrays(a,b)
    finite=np.isfinite(a)&np.isfinite(b)
    missing=np.isfinite(a)^np.isfinite(b)
    dif=np.abs(a-b)
    mism=int(np.sum(missing|(finite&(dif>tolerance))))
    row=dict(check=name,numeric_cells=int(a.size),mismatches=mism,
             maximum_absolute_difference=float(dif[finite].max()) if finite.any() else 0.,**metadata)
    AUDITS.append(row)
    if mism: raise AssertionError((name,row,a.ravel()[:8],b.ravel()[:8]))


def imaged(pool, value='value'):
    if pool.empty: return pd.DataFrame(columns=['image','building','value'])
    result=pool.groupby(['image','building'],dropna=False)[value].mean().reset_index()
    return result.rename(columns={value:'value'})


def effect(image, statistic):
    if 'building' in statistic:
        return image.groupby('building',dropna=False).value.mean().mean()
    return image.value.mean()


def descriptives(values):
    x=pd.to_numeric(pd.Series(values),errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
    n=len(x)
    return dict(n=n,mean=x.mean(),absolute=x.abs().mean(),median=x.median(),
        p10=x.quantile(.1) if n else np.nan,p90=x.quantile(.9) if n else np.nan,
        minimum=x.min(),maximum=x.max(),positive=int(x.gt(1e-9).sum()),negative=int(x.lt(-1e-9).sum()),
        zero=int(x.abs().le(1e-9).sum()),fraction=float(x.gt(1e-9).mean()) if n else np.nan)


def compare_record_values(name,computed,expected):
    a=pd.DataFrame(computed);b=pd.DataFrame(expected)
    fields=sorted(set(a)&set(b))
    assert len(a)==len(b)
    assert_close(name,a[fields],b[fields],fields=json.dumps(fields,ensure_ascii=False))


def main_numeric_record(pp,gi,gb,metric):
    col=metric+'__mean';x=descriptives(gi[col]);xb=descriptives(gb[col])
    r=dict(valid_images=x['n'],valid_buildings=xb['n'],image_mean=x['mean'],building_balanced_mean=xb['mean'],
        image_median=x['median'],image_p10=x['p10'],image_p90=x['p90'],image_min=x['minimum'],image_max=x['maximum'],
        positive_images=x['positive'],negative_images=x['negative'],tied_images=x['zero'],positive_image_fraction=x['fraction'],
        positive_buildings=xb['positive'],negative_buildings=xb['negative'],
        valid_pairs=pp[metric+'__valid_pairs'].sum(),valid_pools=pp[metric+'__valid_pairs'].gt(0).sum(),
        registered_pools=pp.pool_id.nunique(),registered_pairs=pp.registered_pairs.sum(),
        registered_images=gi.image.nunique(),registered_buildings=gi.building.nunique())
    for key in ['actual_n_A_min','actual_n_A_max','actual_n_C_min','actual_n_C_max','actual_m_X_min','actual_m_X_max']:
        r[key]=pp[key].min() if key.endswith('_min') else pp[key].max()
    for suffix in ['mean_absolute','event_positive_fraction','event_p10','event_p50','event_p90','event_loss10_fraction','event_gain10_fraction']:
        key=metric+'__'+suffix;r['image_balanced_'+suffix]=gi[key].mean() if key in gi else np.nan
    return r


def rowkey(row, keys):
    return '|'.join(norm(row[k]) for k in keys)


def attach_id(frame, keys):
    frame=frame.copy()
    frame['_key']=frame[keys].apply(lambda r:rowkey(r,keys),axis=1)
    assert frame._key.is_unique, ('nonunique_rows',keys)
    return frame.set_index('_key',drop=False)


def patch_frame(before, after, keys):
    a=attach_id(before,keys);b=attach_id(after,keys)
    ids=a.index.intersection(b.index)
    a.loc[ids,b.columns]=b.loc[ids,b.columns]
    return a.drop(columns='_key').reset_index(drop=True)


def metric_audit():
    """Fresh frozen shards independently establish which events actually changed."""
    oldparts=[];newparts=[];fieldrows=[];common=[]
    targets=read(ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_REFERENCE_BINDINGS.csv')
    expected=set(targets.loc[targets.module.eq('ac_registered'),'event_id'])
    changed=set(); fixed=list(read(OLD/'FIXED_METADATA_PARITY.csv').field)
    for path in sorted((CACHE/'original_metric_shards').glob('*.csv.gz')):
        a=read(path).set_index('event_id'); b=read(OLD/'metric_shards'/path.name).set_index('event_id').reindex(a.index)
        assert a.index.is_unique and b.index.is_unique and set(a)==set(b)
        diffrows=pd.Series(False,index=a.index)
        for field in a:
            x,y=a[field],b[field]
            nx,ny=pd.to_numeric(x,errors='coerce'),pd.to_numeric(y,errors='coerce')
            num=(x.isna()|nx.notna()).all() and (y.isna()|ny.notna()).all()
            if num:
                dx=(nx.astype(float)-ny.astype(float)).abs()
                diff=(nx.isna()^ny.isna())|(dx>TOL)
            else: diff=x.map(norm).ne(y.map(norm));dx=pd.Series(np.nan,index=a.index)
            diffrows |= diff
            unexpected=diff&~a.index.isin(expected)
            if field in fixed: assert not diff.any(),('fixed_field',field)
            assert not unexpected.any(),('unbound_change',field,list(a.index[unexpected])[:3])
            fieldrows.append(dict(pool_id=path.name[:-7],field=field,rows=len(a),changed_cells=int(diff.sum()),
                unexpected_changed_cells=int(unexpected.sum()),fixed_field=field in fixed,
                maximum_absolute_change=dx.max()))
        changed |= set(a.index[diffrows])
        for metric in ['B8L2_CA','D10_CA','A_B8L2','C_B8L2','A_D10','C_D10']:
            x=a[metric].astype(float);y=b[metric].astype(float)
            both=x.notna()&y.notna(); gained=x.isna()&y.notna();lost=x.notna()&y.isna()
            assert_close('original_common_event_'+metric,y[both],x[both],pool_id=path.name[:-7])
            assert not lost.any()
            common.append(dict(pool_id=path.name[:-7],metric=metric,registered_events=len(a),
                old_valid=int(x.notna().sum()),expanded_valid=int(y.notna().sum()),
                original_common_valid=int(both.sum()),newly_valid=int(gained.sum()),lost_valid=int(lost.sum()),
                max_change_on_original_common=(y[both]-x[both]).abs().max()))
        oldparts.append(a.reset_index());newparts.append(b.reset_index())
    assert changed==expected,(len(changed),len(expected),changed-expected,expected-changed)
    before=pd.concat(oldparts,ignore_index=True);after=pd.concat(newparts,ignore_index=True)
    oldaff=before[before.event_id.isin(expected)];newaff=after[after.event_id.isin(expected)]
    assert len(newaff)==339 and newaff.physical_pair_id.nunique()==245
    assert oldaff.B8L2_CA.notna().sum()==0
    valid=newaff[newaff.B8L2_CA.notna()]
    assert len(valid)==257 and valid.physical_pair_id.nunique()==193
    save(pd.DataFrame(fieldrows),OUT/'FRESH_ORIGINAL_FIELD_ACCEPTANCE.csv.gz')
    save(pd.DataFrame(common),OUT/'ORIGINAL_COMMON_EVENT_SUPPORT.csv')
    save(newaff,OUT/'AFFECTED_EVENTS_RECHECKED.csv.gz')
    print('fresh_shards_accepted',len(before),'events',len(changed),'affected',flush=True)
    return before,after


def load_main_pools():
    subset=OUT/'inputs/MAIN_ORIGINAL_SELECTED_POOLS.csv.gz'
    if subset.exists():
        local=read(subset)
        after=patch_frame(local,read(OLD/'AFFECTED_POOLS_ASSISTED.csv.gz'),GROUP+['pool_id','image','building'])
        return local,after
    source=read(CACHE/'POOL_CONDITION_EFFECTS.csv.gz')
    changed=read(OLD/'MAIN_AFFECTED_GROUP_IDENTITIES.csv')
    wanted=set(changed.apply(lambda r:rowkey(r,GROUP),axis=1))
    local=source[source.apply(lambda r:rowkey(r,GROUP),axis=1).isin(wanted)].copy()
    save(local,OUT/'inputs/MAIN_ORIGINAL_SELECTED_POOLS.csv.gz')
    after=patch_frame(local,read(OLD/'AFFECTED_POOLS_ASSISTED.csv.gz'),GROUP+['pool_id','image','building'])
    return local,after


def support_summary(statsrow):
    names=['valid_images','valid_buildings','valid_pools','valid_pairs','valid_paths','valid_parents',
           'valid_common_images','valid_common_buildings','metric_valid_images','metric_valid_buildings',
           'metric_valid_events','jointly_evaluable_pools','buildings']
    return {n:clean(statsrow.get(n)) for n in names if n in statsrow}


def catalogue_pair(tag, before, after, keys, statistics, source, extra=None):
    a=attach_id(before,keys);b=attach_id(after,keys)
    assert set(a.index)==set(b.index),(tag,'summary_identity')
    b=b.loc[a.index]
    result=[]
    for statistic in statistics:
        x=pd.to_numeric(a[statistic],errors='coerce');y=pd.to_numeric(b[statistic],errors='coerce')
        mask=x.notna()&y.notna()&(x*y<0)&(x.abs()>TOL)&(y.abs()>TOL)
        for key in a.index[mask]:
            ar,br=a.loc[key],b.loc[key]
            identity={k:clean(ar[k]) for k in keys}
            ident=json.dumps(dict(family=tag,statistic=statistic,**identity),ensure_ascii=False,sort_keys=True)
            result.append(dict(reversal_id=hashlib.sha256(ident.encode()).hexdigest()[:16],family=tag,
                statistic=statistic,**identity,old_effect=x.loc[key],expanded_effect=y.loc[key],
                effect_change=y.loc[key]-x.loc[key],old_support=json.dumps(support_summary(ar),ensure_ascii=False),
                expanded_support=json.dumps(support_summary(br),ensure_ascii=False),
                aggregation_unit='building' if 'building' in statistic else ('pool' if tag in ['funnel','method_comparison','strict_bridge'] else 'image'),
                source=source,source_keys=json.dumps(identity,ensure_ascii=False,sort_keys=True),
                interpretation_status='需改写',**(extra or {})))
    return result


def from_changes(tag, path, keys, statistics, extra=None):
    d=read(OLD/path)
    def side(prefix):
        cols=keys+[c for c in d if c.startswith(prefix)]
        out=d[cols].rename(columns={c:c[len(prefix):] for c in cols if c.startswith(prefix)})
        # Some heterogeneous sensitivity exports contain both key and prefixed key.
        return out.loc[:,~out.columns.duplicated()]
    return catalogue_pair(tag,side('automatic_'),side('assisted_'),keys,statistics,
                          str((OLD/path).relative_to(ROOT)),extra)


def make_catalogue():
    out=[]
    for tag,od,nd,keys in [
        ('main','main_automatic_reproduced','main_assisted_affected_conditions',GROUP),
        ('context','context_common/automatic','context_common/assisted',GROUP+['context_axis','context_value'])]:
        name='FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz' if tag=='context' else 'CONDITION_METRIC_SUMMARY.csv.gz'
        out+=catalogue_pair(tag,read(OLD/od/name),read(OLD/nd/name),keys+['metric'],
            ['image_mean','building_balanced_mean'],str((OLD/nd/name).relative_to(ROOT)))
    sa=read(OLD/'sensitivity/automatic_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz')
    sb=read(OLD/'sensitivity/assisted_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz')
    for name,keys in SPECS.items():
        a=sa[sa.analysis_table.eq(name)];b=sb[sb.analysis_table.eq(name)]
        out+=catalogue_pair('sensitivity',a,b,keys+['analysis_table','metric'],
            ['image_mean','building_balanced_mean'],
            str((OLD/'sensitivity/assisted_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz').relative_to(ROOT)),
            {'support_contract':'separate_leg_support_legacy; prefer three_leg_common' if name=='UNEQUAL_DECOMPOSITION' else 'metric_specific'})
    out+=catalogue_pair('three_leg',
        read(OLD/'sensitivity/three_leg_common_support_v2/automatic/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz'),
        read(OLD/'sensitivity/three_leg_common_support_v2/assisted/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz'),THREE+['metric'],
        [leg+'_'+stat for leg in ['total','equal','addition'] for stat in ['image_mean','building_balanced_mean']],
        str((OLD/'sensitivity/three_leg_common_support_v2/assisted/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz').relative_to(ROOT)),
        {'support_contract':'all_three_legs_finite_on_same_path; equal middle-within-parent then parents,pools,images'})
    out+=catalogue_pair('exact_background',
        read(OLD/'sensitivity/exact_outside_background/automatic/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz'),
        read(OLD/'sensitivity/exact_outside_background/assisted/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz'),
        EXACT+['metric'],['image_mean','building_balanced_mean'],
        str((OLD/'sensitivity/exact_outside_background/assisted/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz').relative_to(ROOT)))
    out+=from_changes('method_comparison','context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz',
        ['method_left','method_right','n','m','metric'],['right_minus_left_absolute_change'],
        {'scope':'primary','condition':'manual','support_contract':'both frozen methods valid on the same pool'})
    out+=from_changes('funnel','funnel/FUNNEL_CHANGES.csv.gz',COHORT,['mean_change'])
    out+=from_changes('strict_bridge','strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz',
        ['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'],
        ['strict_signed_or_distance_mean','strict_G_A_mean','strict_G_S_mean'],{'scope':'primary','condition':'manual'})
    result=pd.DataFrame(out).sort_values(['family','source_keys','statistic']).reset_index(drop=True)
    assert result.reversal_id.is_unique
    result['quality_score_metric']=result.metric.astype(str).str.contains('B8L2')
    result['D10_metric']=result.metric.astype(str).str.contains('D10')
    def semantic(r):
        metric=r['metric'];family=r['family']
        if family=='method_comparison': return 'frozen_method_absolute_amplitude_contrast; descriptive, not classifier superiority'
        if metric.startswith(('A_','C_')): return 'single_arm_metric_or_background_change; not the AC treatment contrast'
        if 'risk' in metric: return 'output_state_or_missingness_risk_difference; does not impute missing quality'
        if 'centroid_' in metric and 'distance' not in metric: return 'signed_coordinate_difference; sign is not quality improvement'
        if metric.startswith(('geometry_area','height_mean')): return 'geometric_size_difference; sign is not quality improvement'
        if 'fusion_turn' in metric or 'short_turn' in metric or metric.startswith('nodes'): return 'topology_count_difference; sign is not quality improvement'
        if family=='sensitivity' and r.get('analysis_table')=='SAMPLING_BATCHES': return 'sampling_batch_sensitivity_difference; not policy efficacy'
        if family=='sensitivity' and r.get('analysis_table') in ['FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS']: return 'difference_between_registered_AC_effects; retain background/replacement path'
        if family=='three_leg': return 'registered_common_support_three_leg_effect; addition includes specified remaining target-class members'
        if 'B8L2' in metric or 'D10' in metric: return 'signed_quality_difference_in_frozen_direction'
        return 'metric_component_difference; interpret according to the frozen metric definition'
    result['metric_semantics']=result.apply(semantic,axis=1)
    result['independent_new_experiments']=0
    return result


class Inputs:
    def __init__(self,events0,events1):
        self.events=[events0,events1]
        self.eventindex=[d.set_index('event_id') for d in self.events]
        self.main=list(load_main_pools())
        self.context=read(CACHE/'POOL_TARGET_CONDITIONS.csv')
        m0=read(CACHE/'METHOD_POOL_ALL_DIRECTION_EFFECTS.csv.gz')
        c=read(OLD/'context_common/METHOD_POOL_ALL_DIRECTION_CHANGES.csv.gz')
        mk=['pool_id','image','building','method','n_condition','m_condition']
        upd=c[mk+[x for x in c if x.startswith('assisted_')]].rename(columns={x:x[9:] for x in c if x.startswith('assisted_')})
        self.method=[m0,patch_frame(m0,upd,mk)]
        f0=read(CACHE/'POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz')
        fk=['pool_id','method','n','m','source_class','target_class','metric']
        self.funnel=[f0,patch_frame(f0,read(OLD/'funnel/POOL_DIRECTION_N_M_ASSISTED_PATCH.csv.gz'),fk)]
        self.strict=[read(CACHE/'STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz'),
                     read(OLD/'strict_bridge/STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz')]
        self.views=None
        self.threeraw=None

    def main_views(self):
        if self.views is None:
            spec=importlib.util.spec_from_file_location('frozen_main_membership',CACHE/'summarize_ac_effects.py')
            definition=importlib.util.module_from_spec(spec);spec.loader.exec_module(definition)
            RUNTIME_INPUTS.add(CACHE/'summarize_ac_effects.py')
            # The membership rule is a frozen design rule; scalar aggregation is independent.
            subset=OUT/'inputs/DESIGN_LINKS_AFFECTED_POOLS.csv.gz'
            if subset.exists(): links=read(subset)
            else:
                wanted=set(self.events[0].pool_id)
                chunks=[]
                for chunk in pd.read_csv(CACHE/'DESIGN_LINKS.csv.gz',chunksize=100000,low_memory=False):
                    chunks.append(chunk[chunk.pool_id.isin(wanted)])
                links=pd.concat(chunks,ignore_index=True)
                save(links,subset)
            self.links=links
            result=[]
            for d in self.events:
                d=d.copy();known=d.source_role_rank.notna()&d.target_role_rank.notna()
                d['role_direction']=np.where(known,d.source_role_rank.map(norm)+'->'+d.target_role_rank.map(norm),d.source_class.astype(str)+'->'+d.target_class.astype(str))
                result.append(definition.views(d,links.reindex(columns=definition.LINK_COLS)))
            self.views=result
        return self.views

    def three_raw(self):
        if self.threeraw is None:
            cap=read(CACHE/'POOL_METHOD_CAPACITY.csv.gz').drop_duplicates('pool_id').set_index('pool_id').pool_n
            result=[]
            for side in ['automatic','assisted']:
                d=read(OLD/f'sensitivity/three_leg_common_support_v2/{side}/SOURCE_ROWS.csv.gz').copy()
                nd=d.parent_D_workers.fillna('').map(lambda x:len(x.split('|')) if x else 0)
                outside=d.pool_id.map(cap)-d.n_small-d.n_large+2*nd
                assert (outside>=nd).all()
                d['parent_background_stratum']=np.where(nd.eq(0),'zero_D',np.where(nd.eq(outside),'all_outside_D','partial_outside_D'))
                result.append(d)
            self.threeraw=result
        return self.threeraw

    def pool_values(self,r,side):
        family=r['family'];metric=r['metric']
        if family in ['main','context']:
            if family=='main': d=pick(self.main[side],r,GROUP)
            else:
                # Saved image rows contain the complete frozen context scope.
                sub='automatic' if side==0 else 'assisted'
                d=read(OLD/f'context_common/{sub}/IMAGE_CONDITION_EFFECTS.csv.gz')
                condition=dict(r);condition['analysis_view']=r['analysis_view']+'|ctx:'+r['context_axis']+'='+str(r['context_value'])
                d=pick(d,condition,GROUP);d['pool_id']=d.image
            return d[['pool_id','image','building',metric+'__mean']].rename(columns={metric+'__mean':'value'})
        if family=='sensitivity':
            name=r['analysis_table'];folder='automatic' if side==0 else 'assisted'
            d=read(OLD/f'sensitivity/{folder}_affected_conditions/pool_summaries/affected/{name}.csv.gz')
            d=pick(d,r,SPECS[name]);col=metric+'__pool_mean'
            return d[['pool_id','image','building',col]].rename(columns={col:'value'})
        if family=='three_leg':
            folder='automatic' if side==0 else 'assisted'
            d=read(OLD/f'sensitivity/three_leg_common_support_v2/{folder}/COMMON_VALID_THREE_LEG_POOL_SUMMARY.csv.gz')
            d=pick(d,r,THREE+['metric']);leg=r['statistic'].split('_')[0]
            return d[['pool_id','image','building',leg]].rename(columns={leg:'value'})
        if family=='exact_background':
            folder='automatic' if side==0 else 'assisted'
            d=read(OLD/f'sensitivity/exact_outside_background/{folder}/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz')
            d=pick(d,r,EXACT);col=metric+'__pool_mean'
            return d[['pool_id','image','building',col]].rename(columns={col:'value'})
        if family=='method_comparison':
            d=pick(self.method[side],{'n_condition':r['n'],'m_condition':r['m']},['n_condition','m_condition'])
            col=metric+'__mean_absolute';keys=['pool_id','image','building']
            a=d[d.method.eq(r['method_left'])][keys+[col]].rename(columns={col:'left'})
            b=d[d.method.eq(r['method_right'])][keys+[col]].rename(columns={col:'right'})
            z=a.merge(b,on=keys,validate='one_to_one');z['value']=z.right-z.left
            return z
        if family=='funnel':
            keys=[c for c in COHORT if c!='role_direction']
            d=pick(self.funnel[side],r,keys)
            if r['role_direction']!='ALL_CANONICAL_DIRECTIONS': d=d[d.role_direction.eq(r['role_direction'])]
            return d.groupby(['pool_id','image','building'],dropna=False).mean_change.mean().reset_index().rename(columns={'mean_change':'value'})
        if family=='strict_bridge':
            d=pick(self.strict[side],r,['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'])
            d=d[d.new_AC_condition_match.eq('both')]
            signed='strict_signed_CA_mean'
            if d[signed].notna().sum()==0: signed='absolute_CA_mean'
            d=d[d[signed].notna()&d.new_strict_direction_signed_or_distance_mean.notna()]
            col={'strict_signed_or_distance_mean':signed,'strict_G_A_mean':'G_A_mean','strict_G_S_mean':'G_S_mean'}[r['statistic']]
            return d[['pool_id','image','building',col]].rename(columns={col:'value'})
        raise ValueError(family)


def unit_decomposition(catalogue,inputs):
    """Exact change = within-old-unit update + entry of newly supported units."""
    allunits=[];summaries=[]
    for i,r in enumerate(catalogue.to_dict('records')):
        p0,p1=[inputs.pool_values(r,s) for s in [0,1]]
        ims=[imaged(p) for p in [p0,p1]]
        agg=r['aggregation_unit']
        if agg=='pool':
            units=[p[['pool_id','image','building','value']].copy().rename(columns={'pool_id':'unit_id'}) for p in [p0,p1]]
        elif agg=='building':
            units=[]
            for im in ims:
                u=im.groupby('building',dropna=False).value.mean().reset_index();u['unit_id']=u.building;u['image']=''
                units.append(u)
        else:
            units=[im.assign(unit_id=im.image) for im in ims]
        merged=units[0][['unit_id','image','building','value']].rename(columns={'value':'old_value'}).merge(
            units[1][['unit_id','image','building','value']].rename(columns={'value':'expanded_value'}),
            on=['unit_id','image','building'],how='outer',validate='one_to_one')
        x=merged.old_value;y=merged.expanded_value;old=x.notna();new=y.notna();both=old&new;gain=~old&new;lost=old&~new
        assert not lost.any(),('lost_unit',r['reversal_id'])
        assert_close(r['reversal_id']+'_old_aggregate',x.mean(),r['old_effect'])
        assert_close(r['reversal_id']+'_expanded_aggregate',y.mean(),r['expanded_effect'])
        n0=int(old.sum());n1=int(new.sum());ng=int(gain.sum())
        within=float((y[both]-x[both]).sum()/n1) if n1 else np.nan
        entry=float((y[gain]-x[old].mean()).sum()/n1) if n1 else np.nan
        assert_close(r['reversal_id']+'_support_change_closure',within+entry,r['effect_change'])
        merged['reversal_id']=r['reversal_id'];merged['unit_type']=agg
        merged['support_origin']=np.select([both,gain,lost],['original_supported_unit','new_supported_unit','lost_supported_unit'],default='still_unsupported')
        merged['old_weight']=np.where(old,1/n0,0.);merged['expanded_weight']=np.where(new,1/n1,0.)
        # Zero here is an aggregation contribution for absent observations, never an imputed Q.
        merged['old_weighted_contribution']=np.where(old,x/n0,0.)
        merged['expanded_weighted_contribution']=np.where(new,y/n1,0.)
        merged['contribution_change']=merged.expanded_weighted_contribution-merged.old_weighted_contribution
        merged['old_or_new_Q_missing_is_preserved']=True
        allunits.append(merged)
        summaries.append(dict(reversal_id=r['reversal_id'],old_units=n0,expanded_units=n1,new_units=ng,
            old_effect=x.mean(),expanded_effect=y.mean(),expanded_effect_on_original_units=y[both].mean(),
            effect_of_new_units=y[gain].mean(),within_original_units_contribution=within,
            new_units_composition_contribution=entry,
            old_images=int(ims[0].value.notna().sum()),expanded_images=int(ims[1].value.notna().sum()),
            new_image_ids='|'.join(sorted(set(ims[1].loc[ims[1].value.notna(),'image'])-set(ims[0].loc[ims[0].value.notna(),'image']))),
            changed_original_image_ids='|'.join(sorted(set(ims[0].merge(ims[1],on=['image','building'],suffixes=('_old','_new')).loc[lambda d:d.value_old.notna()&d.value_new.notna()&((d.value_new-d.value_old).abs()>TOL),'image'])))))
        if i%250==0: print('reversal_decomposed',i,'/',len(catalogue),flush=True)
    return pd.DataFrame(summaries),pd.concat(allunits,ignore_index=True)


def analysis_atoms(r,side,inputs):
    """Metric-specific analysis rows and exact registered event provenance.

    A row can be an event, a multi-event path, or an existing panel. Expanding
    the events within an old panel changes that panel's mean; this is not a
    change to the Q values on the original event support.
    """
    family=r['family'];metric=r['metric'];folder='automatic' if side==0 else 'assisted'
    if family=='main':
        d=pick(inputs.main_views()[side],r,GROUP).copy()
        d['atom_id']=d.event_id;d['event_ids']=d.event_id;d['value']=d[metric]
        d['atom_kind']='registered_method_event'
    elif family=='sensitivity':
        name=r['analysis_table']
        d=pick(read(OLD/f'sensitivity/raw_{folder}/{name}.csv.gz'),r,SPECS[name]).copy()
        d['value']=d[metric]
        if name=='MEMBER_PANELS':
            d=d[d.unique_pairs.gt(1)].copy();d['atom_id']=d.pool_id+'|'+d.panel_id
            d['atom_kind']='frozen_member_panel; events may expand within panel'
        elif name=='SAMPLING_BATCHES':
            d['atom_id']=d.pool_id+'|'+d.cell_id
            d['event_ids']=d.batch0_event_ids.fillna('')+'|'+d.batch1_event_ids.fillna('')
            d['atom_kind']='frozen_two_batch_cell; per-batch Q support is metric-specific'
        elif name in ['FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS']:
            d['atom_id']=d.pool_id+'|'+d.path_id+'|'+d.event_from+'|'+d.event_to
            d['event_ids']=d.event_from+'|'+d.event_to;d['atom_kind']='two_registered_event_step'
        elif name=='COMPLETE_COALITIONS':
            d['atom_id']=d.event_id+'|orientation:'+d.analysis_orientation_sign.map(norm)
            d['event_ids']=d.event_id;d['atom_kind']='registered_coalition_event_in_frozen_analysis_orientation'
        elif name=='UNEQUAL_DECOMPOSITION':
            d['atom_id']=d.pool_id+'|'+d.parent_contrast_id+'|'+d.member_rep.map(norm)
            d['event_ids']=d.total_event_id+'|'+d.equal_event_id+'|'+d.addition_event_id
            d['atom_kind']='legacy_leg_specific_path'
        elif name=='BACKGROUND_CHANGES':
            d['atom_id']=d.pool_id+'|'+d.baseline_event_id+'|'+d.changed_event_id
            d['event_ids']=d.baseline_event_id+'|'+d.changed_event_id;d['atom_kind']='two_registered_background_events'
        else: raise ValueError(name)
    elif family=='three_leg':
        d=pick(inputs.three_raw()[side],r,THREE).copy();leg=r['statistic'].split('_')[0]
        cols=[metric+'__'+s for s in ['total','equal','addition']]
        valid=np.isfinite(d[cols]).all(axis=1)
        d['value']=d[metric+'__'+leg].where(valid)
        d['atom_id']=d.pool_id+'|'+d.parent_contrast_id+'|'+d.member_rep.map(norm)
        d['event_ids']=d.total_event_id+'|'+d.equal_event_id+'|'+d.addition_event_id
        d['atom_kind']='all_three_legs_finite_on_same_middle_path'
    elif family=='exact_background':
        d=pick(read(OLD/f'sensitivity/exact_outside_background/{folder}_pairs.csv.gz'),r,EXACT).copy()
        d['value']=d[metric];d['atom_id']=d.background_comparison_id
        d['event_ids']=d.neutral_event_id+'|'+d.outside_event_id;d['atom_kind']='exact_XZ_two_background_comparison'
    elif family=='method_comparison':
        target={'analysis_view':'A_fixed_n','scope':'primary','condition':'manual','n_condition':r['n'],'m_condition':r['m']}
        d=pick(inputs.main_views()[side],target,list(target)).copy()
        d=d[d.method.isin([r['method_left'],r['method_right']])].copy()
        d['value']=d[metric].abs();d['atom_id']=d.event_id;d['event_ids']=d.event_id
        d['comparison_side']=np.where(d.method.eq(r['method_left']),'left','right')
        d['atom_kind']='absolute_event_change; directions then frozen methods paired by pool'
    elif family=='funnel':
        d=pick(inputs.events[side],r,['scope','method','n','m']).copy()
        truth=lambda s:s.astype(str).str.lower().isin(['true','1','1.0'])
        d=d[d.condition.eq('manual')&d.layer.eq('ordinary_manual')&truth(d.equal_team_size)&truth(d.pure_cross_class_blocks)].copy()
        if r['role_direction']!='ALL_CANONICAL_DIRECTIONS':
            src,trg=[int(x.split('/')[0]) for x in r['role_direction'].split('->')]
            d=d[d.source_role_rank.eq(src)&d.target_role_rank.eq(trg)].copy()
        d['value']=d[metric+'_CA'];d['atom_id']=d.event_id;d['event_ids']=d.event_id
        d['atom_kind']='registered_event; average backgrounds in exact_XZ block then blocks then pools'
    else: raise ValueError(('no_Q_atom_definition',family))
    if len(d): assert d.atom_id.is_unique,(r['reversal_id'],'duplicate_atoms')
    return d


def pipe(value):
    return [x for x in str(value).split('|') if x and x!='nan'] if pd.notna(value) else []


def q_detail(qcatalog,inputs):
    atoms=[];events=[];proofs=[]
    with gzip.open(ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz','rt',encoding='utf-8-sig') as stream:
        endpoints={r['team_key']:r for r in map(json.loads,stream)}
    RUNTIME_INPUTS.add(ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINTS.jsonl.gz')
    all_old=inputs.eventindex[0];all_new=inputs.eventindex[1]
    for r in qcatalog.to_dict('records'):
        before,after=[analysis_atoms(r,s,inputs) for s in [0,1]]
        a=before.set_index('atom_id');b=after.set_index('atom_id')
        assert set(a.index)==set(b.index),(r['reversal_id'],'atom_identity_changed')
        b=b.loc[a.index]
        x=a.value.astype(float);y=b.value.astype(float)
        changed=(x.isna()^y.isna())|((x-y).abs()>TOL)
        assert changed.any(),('unexplained_Q_reversal',r['reversal_id'])
        affectedatoms=b.loc[changed]
        allids=sorted({eid for value in affectedatoms.event_ids for eid in pipe(value)})
        # All changed rows must trace to the nine affected original pools.
        assert set(allids)<=set(all_new.index),(r['reversal_id'],'unresolved_event_trace',set(allids)-set(all_new.index))
        trace_old=all_old.loc[allids];trace_new=all_new.loc[allids]
        common=trace_old.B8L2_CA.notna()&trace_new.B8L2_CA.notna()
        assert_close('Q_reversal_original_event_common_'+r['reversal_id'],trace_old.loc[common,'B8L2_CA'],trace_new.loc[common,'B8L2_CA'])
        gained=trace_old.B8L2_CA.isna()&trace_new.B8L2_CA.notna()
        missing_arms=[]
        for aid in affectedatoms.index:
            ar,br=a.loc[aid],b.loc[aid]
            record=dict(reversal_id=r['reversal_id'],family=r['family'],statistic=r['statistic'],
                analysis_atom_id=aid,analysis_atom_kind=br['atom_kind'],pool_id=br.pool_id,image=br.image,building=br.building,
                old_value=ar.value,expanded_value=br.value,
                support_transition='newly_evaluable_analysis_row' if pd.isna(ar.value) and pd.notna(br.value) else 'expanded_inputs_within_existing_analysis_row',
                event_ids=br.event_ids,
                new_Q_event_ids='|'.join(eid for eid in pipe(br.event_ids) if eid in gained.index and gained.loc[eid]))
            for col in ['method','parent_contrast_id','member_rep','parent_D_workers','small_team','middle_team','large_team',
                        'event_from','event_to','A_from','A_to','C_from','C_to','n_from','n_to','m_from','m_to',
                        'input_A_team_key','input_C_team_key','analysis_orientation_sign','number_condition',
                        'unknown_background_included','neutral_A_team_key','outside_A_team_key','neutral_C_team_key','outside_C_team_key',
                        'batch0_event_ids','batch1_event_ids','comparison_side']:
                if col in br: record[col]=br[col]
            atoms.append(record)
        for eid in allids:
            ar,br=trace_old.loc[eid],trace_new.loc[eid]
            rec=dict(reversal_id=r['reversal_id'],event_id=eid,physical_pair_id=br.physical_pair_id,
                pool_id=br.pool_id,image=br.image,building=br.building,scope=br.scope,method=br.method,
                source_class=br.source_class,target_class=br.target_class,source_role_rank=br.source_role_rank,target_role_rank=br.target_role_rank,
                n_A=br.n_A,n_C=br.n_C,m_X=br.m_X,m_Z=br.m_Z,D_workers=br.D_workers,X_workers=br.X_workers,Z_workers=br.Z_workers,
                A_team_key=br.A_team_key,C_team_key=br.C_team_key,
                A_members='|'.join(sorted(set(pipe(br.D_workers)+pipe(br.X_workers)))),
                C_members='|'.join(sorted(set(pipe(br.D_workers)+pipe(br.Z_workers)))),
                original_A_Q=ar.A_B8L2,original_C_Q=ar.C_B8L2,expanded_A_Q=br.A_B8L2,expanded_C_Q=br.C_B8L2,
                original_delta_Q=ar.B8L2_CA,expanded_delta_Q=br.B8L2_CA,
                source_Q_support='newly_evaluable_pair' if gained.loc[eid] else ('original_common_pair' if common.loc[eid] else 'still_without_pair_Q'),
                A_review_id=endpoints.get(br.A_team_key,{}).get('review_id',''),
                C_review_id=endpoints.get(br.C_team_key,{}).get('review_id',''),
                analysis_atom_ids='|'.join(str(aid) for aid,val in affectedatoms.event_ids.items() if eid in pipe(val)))
            events.append(rec)
        # Q data unchanged on original events; a derived batch/panel mean can
        # still move as additional events enter that same already-valid panel.
        proofs.append(dict(reversal_id=r['reversal_id'],original_event_Q_values_changed=0,
            original_estimate_on_exact_original_Q_event_support=r['old_effect'],
            assisted_estimate_on_exact_original_Q_event_support=r['old_effect'],
            original_common_estimate_relation='保持',
            changed_analysis_rows=int(changed.sum()),new_analysis_rows=int((x.isna()&y.notna()).sum()),
            already_valid_analysis_rows_with_expanded_inputs=int((x.notna()&y.notna()&((x-y).abs()>TOL)).sum()),
            traced_events=len(allids),newly_evaluable_Q_events=int(gained.sum()),
            newly_evaluable_physical_pairs=int(trace_new.loc[gained,'physical_pair_id'].nunique()),
            newly_evaluable_Q_images='|'.join(sorted(trace_new.loc[gained,'image'].unique())),
            old_Q_missing_never_scored_as_zero=True,
            support_proof='fresh frozen event metrics; fixed event membership and weights when original validity mask is retained'))
    atomframe=pd.DataFrame(atoms);eventframe=pd.DataFrame(events);proofframe=pd.DataFrame(proofs)
    save(atomframe,OUT/'Q_REVERSAL_CHANGED_ANALYSIS_ROWS.csv.gz')
    save(eventframe,OUT/'Q_REVERSAL_EVENT_TEAM_TRACE.csv.gz')
    save(proofframe,OUT/'Q_REVERSAL_ORIGINAL_COMMON_SUPPORT.csv')
    # Statistical views that reuse the same exact changed inputs remain visible
    # but are explicitly labelled as the same evidence, not counted as new trials.
    groups=[]
    for rid,d in eventframe.groupby('reversal_id',sort=False):
        new=d[d.source_Q_support.eq('newly_evaluable_pair')]
        signature='|'.join(sorted(new.event_id))
        groups.append(dict(reversal_id=rid,new_event_evidence_set_id=hashlib.sha256(signature.encode()).hexdigest()[:16],
            new_event_ids=signature,new_physical_pair_ids='|'.join(sorted(set(new.physical_pair_id)))))
    save(pd.DataFrame(groups),OUT/'Q_REVERSAL_EVIDENCE_ALIASES.csv')
    print('Q_event_traces_complete',len(proofframe),'estimands',len(eventframe),'links',flush=True)


def accept_additional_consumers(inputs):
    def record(name,rows,definition):
        CONSUMERS.append(dict(consumer=name,checked_metric_rows=rows,result='验收通过',
            source='frozen source plus immutable batch04 lower-level records',coverage=definition,new_experiments=0))
    # The local main tables are reconstructed directly from registered events.
    # Neither the mean nor the valid denominator is read back from a summary.
    for side,folder in enumerate(['AUTOMATIC','ASSISTED']):
        view=inputs.main_views()[side]
        expected=read(OLD/f'AFFECTED_POOLS_{folder}.csv.gz')
        metrics=[c[:-6] for c in expected if c.endswith('__mean')]
        keys=GROUP+['pool_id','image','building']
        numeric=view[metrics].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
        grouped=numeric.groupby([view[c] for c in keys],dropna=False)
        mean=grouped.mean().rename(columns=lambda c:c+'__mean').reset_index()
        counts=grouped.count().rename(columns=lambda c:c+'__valid_pairs').reset_index()
        extra=[]
        deltas=[m for m in metrics if m+'__mean_absolute' in expected]
        for values,suffix in [(numeric[deltas].abs(),'__mean_absolute'),
                              (numeric[deltas].gt(1e-9).astype(float).where(numeric[deltas].notna()),'__event_positive_fraction')]:
            extra.append(values.groupby([view[k] for k in keys],dropna=False).mean().rename(columns=lambda c:c+suffix).reset_index())
        qmetrics=[m for m in ['B8L2_CA','D10_CA'] if m in metrics]
        qgroup=numeric[qmetrics].groupby([view[k] for k in keys],dropna=False)
        for q,label in [(.1,'p10'),(.5,'p50'),(.9,'p90')]:
            extra.append(qgroup.quantile(q).rename(columns=lambda c:c+'__event_'+label).reset_index())
        for mask,label in [(numeric[qmetrics].lt(-10),'loss10'),(numeric[qmetrics].gt(10),'gain10')]:
            vals=mask.astype(float).where(numeric[qmetrics].notna())
            extra.append(vals.groupby([view[k] for k in keys],dropna=False).mean().rename(columns=lambda c:c+'__event_'+label+'_fraction').reset_index())
        combined=mean.merge(counts,on=keys,validate='one_to_one')
        for frame in extra:combined=combined.merge(frame,on=keys,validate='one_to_one')
        got=attach_id(combined,keys)
        old=attach_id(expected,keys);got=got.reindex(old.index)
        cols=[c for c in got if c not in keys+['_key']]
        assert_close(folder+'_event_to_main_pool',got[cols],old[cols],fields=json.dumps(cols))
        record(folder+'_main_event_to_pool',len(got),'all metric means/counts, absolute effects, event quantiles, direction and gain/loss fractions')
    # The funnel has a different weight contract from the main table: first
    # backgrounds inside the exact X/Z block, then equally weighted blocks.
    fields={m:m+'_CA' for m in ['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','geometry_area_h2','height_mean_h']}
    fields.update({'geometry_pair_angle':'geometry_pair_angle_AC','geometry_centroid_distance':'geometry_centroid_distance_AC',
        'record_time_pct':'record_time_CA_pct_source_matched','record_time_seconds':'record_time_CA_seconds_source_matched',
        'fusion_failure_risk':'fusion_failure_observed_risk_change_CA','incomplete_output_risk':'output_not_complete_risk_change_CA'})
    keys=['pool_id','method','n','m','source_class','target_class']
    for side in [0,1]:
        d=inputs.events[side];truth=lambda x:x.astype(str).str.lower().isin(['true','1','1.0'])
        d=d[d.condition.eq('manual')&d.layer.eq('ordinary_manual')&truth(d.equal_team_size)&truth(d.pure_cross_class_blocks)].copy()
        block=d.groupby(keys+['X_workers','Z_workers'],dropna=False)[list(fields.values())].mean()
        mean=block.groupby(keys,dropna=False).mean();bn=block.groupby(keys,dropna=False).count()
        vn=d.groupby(keys,dropna=False)[list(fields.values())].count()
        absolute=d.copy();absolute[list(fields.values())]=absolute[list(fields.values())].abs()
        am=absolute.groupby(keys+['X_workers','Z_workers'],dropna=False)[list(fields.values())].mean().groupby(keys,dropna=False).mean()
        expected=inputs.funnel[side];expected=expected[expected.pool_id.isin(d.pool_id)]
        got=[];want=[]
        for r in expected.to_dict('records'):
            key=tuple(r[k] for k in keys);col=fields[r['metric']]
            got.append([mean.loc[key,col],am.loc[key,col],vn.loc[key,col],bn.loc[key,col]])
            want.append([r['mean_change'],r['mean_absolute_change'],r['valid_events'],r['valid_blocks']])
        assert_close(str(side)+'_funnel_events_to_XZ_blocks_to_pool',got,want)
        record(str(side)+'_funnel_event_to_pool',len(got),'both signed and absolute effects; exact XZ blocks, finite event and block counts')
    # Frozen context axes are inputs. Verify both their selected support and
    # all context consumer means against the saved image-level tables.
    for side,folder in enumerate(['automatic','assisted']):
        expected=read(OLD/f'context_common/{folder}/FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz')
        got=[];want=[]
        for r in expected.to_dict('records'):
            d=pick(inputs.main[side],r,GROUP)
            axis=r['context_axis']
            ctx=inputs.context[['pool_id',axis]].drop_duplicates('pool_id')
            d=d.merge(ctx,on='pool_id',how='left',validate='many_to_one')
            cv=d[axis].fillna('ungraded_or_unavailable').astype(str)
            d=d[cv.eq(str(r['context_value']))]
            cols=[c for c in d if c.endswith(('__mean','__mean_absolute')) or '__event_' in c]
            im=d.groupby(['image','building'],dropna=False)[cols].mean().reset_index()
            bu=im.groupby('building',dropna=False)[cols].mean().reset_index()
            got.append(main_numeric_record(d,im,bu,r['metric']));want.append(r)
        compare_record_values(folder+'_frozen_context_consumers',got,want)
        record(folder+'_frozen_context',len(got),'all numeric context summary fields; frozen target conditions; no difficulty redefinition')
    # Member variability keeps the original valid>=2 metric-specific gate.
    for side in ['automatic','assisted']:
        raw=read(OLD/f'sensitivity/member_variability_v2/{side}/SOURCE_ROWS.csv.gz')
        summary=read(OLD/f'sensitivity/member_variability_v2/{side}/MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz')
        got=[];want=[]
        for r in summary.to_dict('records'):
            d=pick(raw,r,SPECS['MEMBER_PANELS']);d=d[d.unique_pairs.gt(1)].copy()
            metric=r['metric'];base=metric.rsplit('__',1)[0]
            d['value']=d[metric].where(d[base+'__valid'].ge(2))
            pool=d.groupby(['pool_id','image','building'],dropna=False).value.mean().reset_index()
            im=imaged(pool);bu=im.groupby('building').value.mean()
            x=descriptives(im.value)
            got.append(dict(registered_multi_pair_panels=len(d),valid_panels=d.value.notna().sum(),
                registered_pools=pool.pool_id.nunique(),valid_pools=pool.value.notna().sum(),registered_images=pool.image.nunique(),
                valid_images=x['n'],valid_buildings=bu.notna().sum(),image_mean=x['mean'],
                image_mean_absolute_of_image_mean=x['absolute'],image_balanced_mean_absolute_within_pool=x['mean'],
                image_median=x['median'],image_p10=x['p10'],image_min=x['minimum'],image_max=x['maximum'],
                positive_images=x['positive'],negative_images=x['negative'],zero_images=x['zero'],
                positive_image_fraction=x['fraction'],building_balanced_mean=bu.mean()))
            want.append(r)
        compare_record_values(side+'_member_valid_ge2_raw_to_summary',got,want)
        record(side+'_member_valid_ge2',len(got),'all numeric variability summary fields; no singleton variance/range interpreted as zero variation')
    # Exact-background records retain separate X/Z blocks and D variants.
    for side in ['automatic','assisted']:
        raw=read(OLD/f'sensitivity/exact_outside_background/{side}_pairs.csv.gz')
        local=read(OLD/f'sensitivity/exact_outside_background/{side}/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz')
        # Saved complete condition pool files include unaffected pools. Only
        # the nine freshly read pools can be derived from the local raw table.
        keys=EXACT+['pool_id','image','building']
        metrics=[c[:-11] for c in local if c.endswith('__pool_mean')]
        block=raw.groupby(keys+['X_workers','Z_workers'],dropna=False)[metrics].mean().reset_index()
        absolute=raw.copy();absolute[metrics]=absolute[metrics].abs()
        ab=absolute.groupby(keys+['X_workers','Z_workers'],dropna=False)[metrics].mean().reset_index()
        pool=block.groupby(keys,dropna=False)[metrics].mean().rename(columns=lambda c:c+'__pool_mean').reset_index()
        for frame,op,suffix in [(block,'count','__valid_blocks'),(ab,'mean','__pool_mean_abs'),
                               (block,'min','__pool_min'),(block,'max','__pool_max')]:
            own=getattr(frame.groupby(keys,dropna=False)[metrics],op)().rename(columns=lambda c:c+suffix).reset_index()
            pool=pool.merge(own,on=keys,validate='one_to_one')
        ab2=block.copy();ab2[metrics]=ab2[metrics].abs()
        own=ab2.groupby(keys,dropna=False)[metrics].mean().rename(columns=lambda c:c+'__pool_abs_of_D_variant_mean').reset_index()
        pool=pool.merge(own,on=keys,validate='one_to_one')
        wanted=local[local.pool_id.isin(raw.pool_id)]
        g=attach_id(pool,keys);w=attach_id(wanted,keys);g=g.reindex(w.index)
        cols=[c for c in pool if c not in keys]
        assert_close(side+'_exact_XZ_raw_to_pool',g[cols],w[cols])
        summary=read(OLD/f'sensitivity/exact_outside_background/{side}/EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz')
        got=[];want=[]
        for r in summary.to_dict('records'):
            d=pick(local,r,EXACT);metric=r['metric'];col=metric+'__pool_mean';im=imaged(d,col);bu=im.groupby('building').value.mean()
            ab=imaged(d,metric+'__pool_mean_abs');x=descriptives(im.value)
            got.append(dict(registered_pools=d.pool_id.nunique(),valid_pools=d[col].notna().sum(),registered_images=d.image.nunique(),
                valid_images=x['n'],valid_buildings=bu.notna().sum(),image_mean=x['mean'],image_mean_abs=x['absolute'],
                image_mean_absolute_of_image_mean=x['absolute'],image_balanced_mean_absolute_within_pool=ab.value.mean(),
                building_balanced_mean_absolute_within_pool=ab.groupby('building').value.mean().mean(),
                image_median=x['median'],image_p10=x['p10'],image_min=x['minimum'],image_max=x['maximum'],
                positive_images=x['positive'],negative_images=x['negative'],positive_image_fraction=x['fraction'],building_balanced_mean=bu.mean(),
                matched_XZ_blocks=d.matched_XZ_blocks.sum(),matched_background_pairs=d.matched_background_pairs.sum()))
            want.append(r)
        compare_record_values(side+'_exact_XZ_pool_to_summary',got,want)
        record(side+'_exact_XZ',len(got),'all numeric exact-background summaries; separate abs-before/after-D-averaging; exact block weights')
    # All strict-ABC bridge changed means are checked on their true common
    # target-pool support. Direct AC has no B; this remains a reused comparator.
    changes=read(OLD/'strict_bridge/STRICT_BRIDGE_SUMMARY_CHANGES.csv.gz')
    got=[];want=[]
    for r in changes.to_dict('records'):
        for side,prefix in enumerate(['automatic_','assisted_']):
            d=pick(inputs.strict[side],r,['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'])
            d=d[d.new_AC_condition_match.eq('both')]
            scalar=r['metric'] not in ['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
            col='strict_signed_CA_mean' if scalar else 'absolute_CA_mean'
            z=d[d[col].notna()&d.new_strict_direction_signed_or_distance_mean.notna()]
            rr=dict(matched_target_pools=len(d),jointly_evaluable_pools=len(z),buildings=z.building.nunique(),
                strict_signed_or_distance_mean=z[col].mean(),direct_AC_signed_or_distance_mean=z.new_strict_direction_signed_or_distance_mean.mean(),
                strict_absolute_CA_mean=z.absolute_CA_mean.mean(),direct_AC_absolute_CA_mean=z.new_absolute_change_mean.mean(),
                strict_within_AB_mean=z.within_AB_mean.mean(),strict_G_A_mean=z.G_A_mean.mean(),strict_G_S_mean=z.G_S_mean.mean(),
                strict_G_A_positive_pools=z.G_A_mean.gt(1e-9).sum(),strict_G_A_valid_pools=z.G_A_mean.notna().sum(),
                direct_AC_positive_pools=z.new_strict_direction_signed_or_distance_mean.gt(1e-9).sum() if scalar else np.nan,
                direct_AC_negative_pools=z.new_strict_direction_signed_or_distance_mean.lt(-1e-9).sum() if scalar else np.nan,
                signed_direction_agreement_pools=(np.sign(z[col])==np.sign(z.new_strict_direction_signed_or_distance_mean)).sum() if scalar else np.nan)
            got.append(rr);want.append({c[len(prefix):]:v for c,v in r.items() if c.startswith(prefix)})
    compare_record_values('strict_ABC_common_pool_bridge',got,want)
    record('strict_ABC_bridge',len(changes),'all numeric bridge summary fields; joint strict/direct pool support; G component support distinct')
    # The published global denominator follows directly from the final state
    # counts; independently verify the local transitions and physical dedup.
    flags=['Q_missing','fusion_execution_exception','fusion_structural_failure','output_invalid_geometry',
           'fusion_failure_observed','measurement_exception','reference_floor_only','output_not_complete']
    sk=['condition','layer','scope','low_key_output_state','high_key_output_state','low_key_score_status','high_key_score_status']
    sk += ['low_key_'+x for x in flags]+['high_key_'+x for x in flags]
    for side,folder in enumerate(['automatic','assisted']):
        d=inputs.events[side].drop_duplicates('physical_pair_id').copy();rows=[]
        for r in d.to_dict('records'):
            lo,hi=('A','C') if r['A_team_key']<r['C_team_key'] else ('C','A')
            out={k:r[k] for k in ['condition','layer','scope']}
            for target,arm in [('low_key',lo),('high_key',hi)]:
                for k in ['output_state','score_status']+flags: out[target+'_'+k]=r[arm+'_'+k]
            rows.append(out)
        actual=pd.DataFrame(rows).groupby(sk,dropna=False).size().reset_index(name='unique_physical_pairs')
        expected=read(OLD/f'states/{folder}/GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
        a=attach_id(actual,sk);b=attach_id(expected,sk)
        assert set(a.index)==set(b.index)
        a=a.reindex(b.index)
        assert_close(folder+'_physical_state_counts',a.unique_physical_pairs,b.unique_physical_pairs)
        record(folder+'_physical_state_cells',len(actual),'physical_pair_id deduplicated; low/high is native team key order, not role direction')
    allstate=read(OLD/'states/GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
    frozen=read(CACHE/'GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
    local0=read(OLD/'states/automatic/GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
    local1=read(OLD/'states/assisted/GLOBAL_DEDUPLICATED_PHYSICAL_PAIR_OUTPUT_STATES.csv')
    def count_patch(base,old,new,keys,fields):
        a=attach_id(base,keys);b=attach_id(old,keys);c=attach_id(new,keys)
        return a[fields].subtract(b[fields],fill_value=0).add(c[fields],fill_value=0)
    counts=count_patch(frozen,local0,local1,sk,['unique_physical_pairs','target_pools'])
    actual=attach_id(allstate,sk)
    counts=counts[counts.unique_physical_pairs.gt(0)].reindex(actual.index)
    assert_close('global_physical_count_patch_from_fresh_frozen_source',counts,actual[['unique_physical_pairs','target_pools']])
    teams=read(OLD/'states/UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv')
    tk=['condition','layer','scope','output_state','score_status']+flags
    counts=count_patch(read(CACHE/'UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv'),
        read(OLD/'states/automatic/UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv'),
        read(OLD/'states/assisted/UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv'),tk,['unique_requested_teams','target_pools'])
    actual=attach_id(teams,tk);counts=counts[counts.unique_requested_teams.gt(0)].reindex(actual.index)
    assert_close('global_unique_team_count_patch_from_fresh_frozen_source',counts,actual[['unique_requested_teams','target_pools']])
    domain=read(OLD/'states/STATE_DOMAIN_DENOMINATOR_SUMMARY.csv')
    got=[];want=[]
    for r in domain.to_dict('records'):
        d=pick(allstate,r,['condition','layer','scope']);n=d.unique_physical_pairs
        masks=[~d.low_key_Q_missing&~d.high_key_Q_missing,d.low_key_Q_missing^d.high_key_Q_missing,
               d.low_key_Q_missing&d.high_key_Q_missing,d.low_key_fusion_failure_observed|d.high_key_fusion_failure_observed]
        got.append([n.sum()]+[n[mask].sum() for mask in masks])
        want.append([r['physical_pairs'],r['both_present_pairs'],r['one_missing_pairs'],r['both_missing_pairs'],r['observed_failure_pairs']])
    assert_close('global_state_domain_denominators',got,want)
    assert allstate.unique_physical_pairs.sum()==412839
    assert read(OLD/'states/UNIQUE_REQUESTED_TEAM_OUTPUT_STATE_COUNTS.csv').unique_requested_teams.sum()==478012
    record('global_physical_and_team_state_domains',len(domain),'412839 registered physical pairs and 478012 unique teams retained')
    CONSUMERS.append(dict(consumer='global_state_building_support_witnesses',checked_metric_rows=len(allstate),result='保留原见证检查',
        source=str((OLD/'states/BUILDING_SUPPORT_AMBIGUITIES.json').relative_to(ROOT)),
        coverage='global counts and target-pool supports independently recomputed; global state-cell building counts use the prior frozen example-event set witnesses, not a fresh full-domain event reread',
        new_experiments=0))


def accept_raw_sensitivity(inputs):
    """Check the propagation from saved events into all seven raw consumers.

    These formulas are evaluated here from the saved event identities. The
    earlier sensitivity writer and its helper functions are not executed.
    """
    metrics=['B8L2_CA','D10_CA','IoU3D100_CA','S_bottom_deg_CA','dir_CA','Hmean_CA','omission_CA','extension_CA',
        'fusion_turn_n_CA','fusion_short_turn_edges_CA','nodes_CA','ref_node_recall_5_CA','ref_edge_recall_5_CA',
        'geometry_area_h2_pct_CA','height_mean_h_pct_CA','centroid_x_h_CA','centroid_z_h_CA','geometry_bev_distance_AC',
        'geometry_centroid_distance_AC','record_time_CA_pct_source_matched','record_time_CA_seconds_source_matched',
        'record_time_CA_seconds_single_source','record_time_per_member_CA_pct_single_source','Q_missing_risk_change_CA',
        'fusion_failure_observed_risk_change_CA','output_not_complete_risk_change_CA']
    armmetrics=['B8L2','D10','fusion_turn_n','nodes','Q_missing','fusion_failure_observed','output_not_complete']
    acols=[a+'_'+m for a in ['A','C'] for m in armmetrics]
    def fnum(v):
        try: return float(v)
        except (TypeError,ValueError): return np.nan
    def finite(v): return math.isfinite(fnum(v))
    def reverse(value,metric):
        if not finite(value): return np.nan
        value=float(value)
        if metric.endswith('_AC'): return value
        if 'pct' in metric: return 100*(1/(1+value/100)-1) if 1+value/100>0 else np.nan
        if '_ratio_' in metric and '_log_ratio_' not in metric: return 1/value if value>0 else np.nan
        return -value
    for side,folder in enumerate(['automatic','assisted']):
        source=inputs.events[side][['event_id','A_team_key','C_team_key']+metrics+acols].set_index('event_id').to_dict('index')
        def view(eid,input_A):
            row=source[eid];normal=input_A==row['A_team_key']
            assert normal or input_A==row['C_team_key']
            out={m:fnum(row[m]) if normal else reverse(row[m],m) for m in metrics}
            for arm,other in [('A','C'),('C','A')]:
                for m in armmetrics: out[arm+'_'+m]=fnum(row[(arm if normal else other)+'_'+m])
            return out
        for name in SPECS:
            raw=read(OLD/f'sensitivity/raw_{folder}/{name}.csv.gz');got=[];want=[]
            def append(r,col,value):
                if col in r: got.append(value);want.append(fnum(r[col]))
            for r in raw.to_dict('records'):
                if name=='MEMBER_PANELS':
                    events=[source[eid] for eid in pipe(r['event_ids'])]
                    for metric in metrics+acols:
                        vals=np.array([fnum(e[metric]) for e in events]);x=vals[np.isfinite(vals)];n=len(x)
                        pairs={'valid':n,'mean':x.mean() if n else np.nan,'sd':x.std(ddof=1) if n>1 else np.nan,
                            'min':x.min() if n else np.nan,'max':x.max() if n else np.nan,
                            'span':x.max()-x.min() if n else np.nan,'mean_abs':np.abs(x).mean() if n else np.nan,
                            'positive_fraction':np.mean(x>1e-9) if n else np.nan,'negative_fraction':np.mean(x< -1e-9) if n else np.nan,
                            'sign_flip':float(np.any(x>1e-9)&np.any(x< -1e-9)) if n>1 else np.nan}
                        for suffix,value in pairs.items(): append(r,metric+'__'+suffix,value)
                elif name in ['BACKGROUND_CHANGES','FIXED_BLOCK_BACKGROUND_STEPS','FIXED_A_REPLACEMENT_STEPS']:
                    if name=='BACKGROUND_CHANGES':
                        a=view(r['baseline_event_id'],r['baseline_A_team_key']);b=view(r['changed_event_id'],r['changed_A_team_key'])
                        suffixes=['baseline','changed','effect_difference']
                    else:
                        a=view(r['event_from'],r['A_from']);b=view(r['event_to'],r['A_to']);suffixes=['from','to','step_difference']
                    for metric in metrics:
                        values=[a[metric],b[metric],b[metric]-a[metric]]
                        for suffix,value in zip(suffixes,values):append(r,metric+'__'+suffix,value)
                        col=metric+'__effect_difference_four_team_source_matched'
                        if col in r: append(r,col,values[-1] if norm(r['all_four_time_source_count_matched'])=='true' else np.nan)
                    if name=='BACKGROUND_CHANGES':
                        for metric in acols: append(r,metric+'__background_difference',b[metric]-a[metric])
                elif name=='UNEQUAL_DECOMPOSITION':
                    a=view(r['total_event_id'],r['small_team']);b=view(r['equal_event_id'],r['small_team']);c=view(r['addition_event_id'],r['middle_team'])
                    for metric in metrics:
                        for leg,value in [('total',a[metric]),('equal',b[metric]),('addition',c[metric])]:append(r,metric+'__'+leg,value)
                        isadd=not (metric.endswith('_AC') or 'pct' in metric or ('_ratio_' in metric and '_log_ratio_' not in metric))
                        closure=a[metric]-b[metric]-c[metric] if isadd and all(finite(x[metric]) for x in [a,b,c]) else np.nan
                        opposite=float(b[metric]*c[metric]< -1e-18) if finite(b[metric]) and finite(c[metric]) else np.nan
                        append(r,metric+'__closure_error',closure);append(r,metric+'__parts_opposite_sign',opposite)
                elif name=='COMPLETE_COALITIONS':
                    values=view(r['event_id'],r['input_A_team_key'])
                    for metric in metrics+acols: append(r,metric,values[metric])
                elif name=='SAMPLING_BATCHES':
                    parts=[[source[eid] for eid in pipe(r['batch'+str(i)+'_event_ids'])] for i in [0,1]]
                    for metric in metrics:
                        vv=[np.array([fnum(x[metric]) for x in part]) for part in parts];vv=[v[np.isfinite(v)] for v in vv]
                        av,bv=[v.mean() if len(v) else np.nan for v in vv]
                        for col,value in [('batch0_mean',av),('batch1_mean',bv),('mean_difference',bv-av),('batch0_valid',len(vv[0])),('batch1_valid',len(vv[1]))]:
                            append(r,metric+'__'+col,value)
                        sa=0 if finite(av) and abs(av)<=1e-9 else np.sign(av);sb=0 if finite(bv) and abs(bv)<=1e-9 else np.sign(bv)
                        append(r,metric+'__direction_agreement',float(sa==sb) if finite(av) and finite(bv) else np.nan)
            assert_close(folder+'_'+name+'_saved_events_to_raw',got,want)
            CONSUMERS.append(dict(consumer=folder+'_'+name+'_raw',checked_metric_rows=len(raw),
                source=str((OLD/f'sensitivity/raw_{folder}/{name}.csv.gz').relative_to(ROOT)),result='验收通过',
                coverage='independent metric formulas from fresh frozen/assisted event rows; exact team orientation',new_experiments=0))
        print('raw_sensitivity_accepted',folder,flush=True)


def accept_population_numeric(inputs):
    """Check the non-mean fields of the complete changed method/funnel cohorts."""
    changes=read(OLD/'context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz')
    got=[];want=[]
    for r in changes.to_dict('records'):
        for side,prefix in enumerate(['automatic_','assisted_']):
            z=pick(inputs.method[side],{'n_condition':r['n'],'m_condition':r['m']},['n_condition','m_condition'])
            col=r['metric']+'__mean_absolute';keys=['pool_id','image','building']
            left=z[z.method.eq(r['method_left'])];right=z[z.method.eq(r['method_right'])]
            join=left[keys+[col]].merge(right[keys+[col]],on=keys,suffixes=('_left','_right'),validate='one_to_one')
            valid=join[join[col+'_left'].notna()&join[col+'_right'].notna()]
            delta=valid[col+'_right']-valid[col+'_left']
            got.append(dict(common_registered_pools=len(join),valid_common_images=len(valid),valid_common_buildings=valid.building.nunique(),
                left_image_mean_absolute_change=valid[col+'_left'].mean(),right_image_mean_absolute_change=valid[col+'_right'].mean(),
                right_minus_left_absolute_change=delta.mean(),right_absolute_larger_images=delta.gt(1e-9).sum(),
                left_full_coverage_pools=len(left),right_full_coverage_pools=len(right)))
            want.append({c[len(prefix):]:v for c,v in r.items() if c.startswith(prefix)})
    compare_record_values('common_method_all_numeric_fields',got,want)
    CONSUMERS.append(dict(consumer='common_method_full_numeric',checked_metric_rows=len(changes),result='验收通过',
        coverage='all numeric support, side-specific amplitude, paired contrast, direction-count fields; common pool list fixed',source='fresh frozen METHOD_POOL_ALL_DIRECTION_EFFECTS and exact local overlay',new_experiments=0))
    changes=read(OLD/'funnel/FUNNEL_CHANGES.csv.gz')
    got=[];want=[];static=[]
    dynamic=['valid_pools','mean_change','median_change','p10_change','p90_change','positive_pools','negative_pools','nearzero_pools','positive_fraction',
        'measured_pools','metric_valid_events','registered_events','metric_all_registered_events_valid_pools','mean_absolute_change_over_pools',
        'pools_with_native_execution_exception','pools_with_structural_failure','pools_with_invalid_geometry','pools_with_measurement_exception',
        'metric_valid_images','metric_valid_buildings','native_complete_no_valid_metric_pools','native_complete_unmeasured_pools','measured_no_valid_metric_pools',
        'nonzero_difference_pools']
    for r in changes.to_dict('records'):
        for side,prefix in enumerate(['automatic_','assisted_']):
            d=pick(inputs.funnel[side],r,[c for c in COHORT if c!='role_direction'])
            if r['role_direction']!='ALL_CANONICAL_DIRECTIONS':d=d[d.role_direction.eq(r['role_direction'])]
            fields={'mean_change':'mean','mean_absolute_change':'mean','valid_events':'sum','registered_events':'sum',
                'fusion_execution_exception_pair_events':'sum','fusion_structural_failure_pair_events':'sum',
                'output_invalid_geometry_pair_events':'sum','measurement_exception_pair_events':'sum','image':'first','building':'first'}
            pools=d.groupby('pool_id',dropna=False).agg(fields)
            x=descriptives(pools.mean_change);n=x['n'];valid=pools[pools.valid_events.gt(0)]
            rr=dict(valid_pools=n,mean_change=x['mean'],median_change=x['median'],p10_change=x['p10'],p90_change=x['p90'],
                positive_pools=x['positive'],negative_pools=x['negative'],nearzero_pools=x['zero'],positive_fraction=x['fraction'],
                measured_pools=len(pools),metric_valid_events=pools.valid_events.sum(),registered_events=pools.registered_events.sum(),
                metric_all_registered_events_valid_pools=pools.valid_events.eq(pools.registered_events).sum(),
                mean_absolute_change_over_pools=pools.mean_absolute_change.mean(),
                pools_with_native_execution_exception=pools.fusion_execution_exception_pair_events.gt(0).sum(),
                pools_with_structural_failure=pools.fusion_structural_failure_pair_events.gt(0).sum(),
                pools_with_invalid_geometry=pools.output_invalid_geometry_pair_events.gt(0).sum(),
                pools_with_measurement_exception=pools.measurement_exception_pair_events.gt(0).sum(),
                metric_valid_images=valid.image.nunique(),metric_valid_buildings=valid.building.nunique(),
                native_complete_no_valid_metric_pools=r[prefix+'native_complete_registered_pools']-n,
                native_complete_unmeasured_pools=r[prefix+'native_complete_registered_pools']-len(pools),
                measured_no_valid_metric_pools=len(pools)-n,nonzero_difference_pools=x['positive']+x['negative'])
            if r['metric'] in ['geometry_pair_angle','geometry_centroid_distance']:
                for col in ['positive_pools','negative_pools','positive_fraction']:rr[col]=np.nan
            got.append(rr);want.append({c[len(prefix):]:v for c,v in r.items() if c.startswith(prefix)})
        staticcols=[c[10:] for c in r if c.startswith('automatic_') and c[10:] not in dynamic]
        for c in staticcols:
            av,bv=r['automatic_'+c],r['assisted_'+c]
            assert norm(av)==norm(bv),('changed_fixed_funnel_field',c)
    compare_record_values('funnel_all_dynamic_numeric_fields',got,want)
    CONSUMERS.append(dict(consumer='funnel_full_numeric',checked_metric_rows=len(changes),result='验收通过',
        coverage='all dynamic numeric fields rederived, including quantiles/extremes, support, status counts and amplitude; fixed capacity/registration fields unchanged',
        source='fresh frozen POOL_DIRECTION_N_M_METRIC_SUPPORT plus verified local event/block overlay',new_experiments=0))


def accept_consumers(inputs):
    """Reproduce complete affected consumer means from their own lower level inputs."""
    def record(tag,n,source,meaning):
        CONSUMERS.append(dict(consumer=tag,checked_metric_rows=n,source=source,
            result='保持或按实际新支持更新',coverage=meaning,new_experiments=0))
        print('consumer_accepted',tag,n,flush=True)
    accept_raw_sensitivity(inputs)
    # Every affected main summary, including components, is recomputed from
    # complete original pool support with only the local pool records overlaid.
    for side,folder in enumerate(['main_automatic_reproduced','main_assisted_affected_conditions']):
        pool=inputs.main[side]
        means=[c for c in pool if c.endswith(('__mean','__mean_absolute')) or '__event_' in c]
        im=pool.groupby(GROUP+['image','building'],dropna=False)[means].mean().reset_index()
        bu=im.groupby(GROUP+['building'],dropna=False)[means].mean().reset_index()
        imgroups={key:g for key,g in im.groupby(GROUP,dropna=False)}
        bugroups={key:g for key,g in bu.groupby(GROUP,dropna=False)}
        pgr={key:g for key,g in pool.groupby(GROUP,dropna=False)}
        expected=read(OLD/f'{folder}/CONDITION_METRIC_SUMMARY.csv.gz')
        got=[];want=[]
        for row in expected.to_dict('records'):
            key=tuple(row[k] for k in GROUP)
            # n/m are categorical in the original summary (integer and frontier labels).
            matches=[k for k in imgroups if tuple(map(norm,k))==tuple(map(norm,key))]
            assert len(matches)==1,(folder,key)
            gi=imgroups[matches[0]];gb=bugroups[matches[0]];pp=pgr[matches[0]];col=row['metric']+'__mean';metric=row['metric']
            if col not in gi: continue
            r=main_numeric_record(pp,gi,gb,metric)
            got.append(r);want.append(row)
        compare_record_values('complete_main_'+folder,got,want)
        record(folder,len(got),'inputs/MAIN_ORIGINAL_SELECTED_POOLS.csv.gz plus immutable batch04 affected pool overlay',
               'all numeric support/mean/absolute/median/quantile/extreme/direction/gain-loss fields of affected summary rows')
    # All seven sensitivity families: metric-specific pool means, image means,
    # building means, and image support, not a global count substitution.
    for side in ['automatic','assisted']:
        expected=read(OLD/f'sensitivity/{side}_affected_conditions/SENSITIVITY_IMAGE_BALANCED_SUMMARY_V2.csv.gz')
        for name,keys in SPECS.items():
            pool=read(OLD/f'sensitivity/{side}_affected_conditions/pool_summaries/affected/{name}.csv.gz')
            summary=expected[expected.analysis_table.eq(name)]
            got=[];want=[]
            for r in summary.to_dict('records'):
                d=pick(pool,r,keys);metric=r['metric'];col=metric+'__pool_mean';im=imaged(d,col)
                ab=imaged(d,metric+'__pool_mean_abs');x=descriptives(im.value);bu=im.groupby('building').value.mean()
                rr=dict(registered_pools=d.pool_id.nunique(),valid_pools=d[col].notna().sum(),registered_images=d.image.nunique(),
                    valid_images=x['n'],valid_buildings=bu.notna().sum(),analysis_rows=d.panel_rows.sum(),
                    image_mean=x['mean'],image_mean_absolute_of_image_mean=x['absolute'],
                    image_balanced_mean_absolute_within_pool=ab.value.mean(),building_balanced_mean_absolute_within_pool=ab.groupby('building').value.mean().mean(),
                    image_median=x['median'],image_p10=x['p10'],image_min=x['minimum'],image_max=x['maximum'],
                    observed_analysis_row_min=d[metric+'__pool_min'].min(),observed_analysis_row_max=d[metric+'__pool_max'].max(),
                    positive_images=x['positive'],negative_images=x['negative'],zero_images=x['zero'],
                    positive_image_fraction=x['fraction'],building_balanced_mean=bu.mean())
                got.append(rr);want.append(r)
            compare_record_values(side+'_'+name+'_consumer',got,want)
            record(side+'_'+name,len(got),f'../manual_order_impact_20261104/ac/sensitivity/{side}_affected_conditions/pool_summaries/affected/{name}.csv.gz',
                   'all V2 numeric summary fields: support, means, abs-before/after averaging, median/P10/extremes/direction fractions')
    # Corrected common-three-leg means and path counts are checked directly from
    # the complete raw affected condition groups, independently of saved pools.
    for side,folder in enumerate(['automatic','assisted']):
        raw=inputs.three_raw()[side]
        summary=read(OLD/f'sensitivity/three_leg_common_support_v2/{folder}/COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz')
        got=[];want=[]
        for r in summary.to_dict('records'):
            registered=pick(raw,r,THREE);cols=[r['metric']+'__'+s for s in ['total','equal','addition']]
            d=registered[np.isfinite(registered[cols]).all(axis=1)].copy()
            legs=['total','equal','addition'];d=d.rename(columns=dict(zip(cols,legs)))
            for leg in legs:d[leg+'_abs']=d[leg].abs()
            d['opposite']=(d.equal*d.addition< -1e-18).astype(float)
            fields=legs+[leg+'_abs' for leg in legs]+['opposite']
            parent=d.groupby(['pool_id','image','building','parent_contrast_id'],dropna=False)[fields].mean().reset_index()
            pool=parent.groupby(['pool_id','image','building'],dropna=False)[fields].mean().reset_index()
            im=pool.groupby(['image','building'],dropna=False)[fields].mean();bu=im.groupby('building').mean()
            rr=dict(registered_paths=len(registered),registered_parents=registered.parent_contrast_id.nunique(),registered_images=registered.image.nunique(),
                valid_paths=len(d),valid_parents=d.parent_contrast_id.nunique(),valid_images=len(im),valid_buildings=len(bu),
                opposite_equal_addition_path_fraction_image_balanced=im.opposite.mean(),
                max_raw_path_closure_error=np.nan,image_balanced_mean_closure_error=np.nan)
            for leg in legs:
                x=descriptives(im[leg]);rr.update({leg+'_image_mean':x['mean'],leg+'_image_mean_abs_of_mean':x['absolute'],
                    leg+'_image_balanced_path_abs_mean':im[leg+'_abs'].mean(),leg+'_building_balanced_mean':bu[leg].mean(),
                    leg+'_positive_images':x['positive'],leg+'_negative_images':x['negative'],leg+'_zero_images':x['zero'],
                    leg+'_image_p10':x['p10'],leg+'_image_min':x['minimum'],leg+'_image_max':x['maximum']})
            if r['metric_kind']=='additive_difference' and len(d):
                rr['max_raw_path_closure_error']=(d.total-d.equal-d.addition).abs().max()
                rr['image_balanced_mean_closure_error']=im.total.mean()-im.equal.mean()-im.addition.mean()
            # The frozen writer leaves per-leg count fields blank for an empty
            # common path set, rather than recording a tested zero direction.
            if not len(d):
                for key in list(rr):
                    if any(key.startswith(leg+'_') for leg in legs):rr[key]=np.nan
            got.append(rr);want.append(r)
        compare_record_values(folder+'_three_leg_raw_to_summary',got,want)
        record(folder+'_three_leg_corrected',len(got),'immutable batch04 full common-three-leg SOURCE_ROWS',
               'all numeric common-path summary fields including abs-before/after means, quantiles/extremes/signs/closure; exact parent weights')
    # Funnel and method contrasts are additionally checked as full changed
    # summary sets rather than only at their sign reversals.
    for name,path,keys,stat in [
        ('method_comparison','context_common/COMMON_POOL_METHOD_COMPARISON_CHANGES.csv.gz',['method_left','method_right','n','m','metric'],'right_minus_left_absolute_change'),
        ('funnel','funnel/FUNNEL_CHANGES.csv.gz',COHORT,'mean_change')]:
        d=read(OLD/path);got=[];want=[]
        for r in d.to_dict('records'):
            r['family']=name;r['statistic']=stat
            for side,prefix in enumerate(['automatic_','assisted_']):
                pool=inputs.pool_values(r,side);got.append(pool.value.mean());want.append(r[prefix+stat])
        assert_close(name+'_all_changed_means',got,want)
        record(name,len(d),str((OLD/path).relative_to(ROOT)),
               'full original registered pool table, metric-specific paired support and frozen weights')
    # Direct 50% headline conditions have no gain in paired Q from this branch.
    e0,e1=inputs.events
    affected=e1[e1.event_id.isin(read(OLD/'AFFECTED_EVENT_METRICS_ASSISTED.csv.gz').event_id)]
    primary=affected[affected.scope.eq('primary')&affected.n.isin([14,16,18,20,22])&affected.m.eq(affected.n/2)]
    assert len(primary)==0
    record('direct_AC_50_percent_main',0,'fresh frozen event shards and affected event bindings',
           'primary n/m 14/7,16/8,18/9,20/10,22/11 not directly hit; strict ABC bridge remains separate')
    accept_additional_consumers(inputs)
    accept_population_numeric(inputs)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    e0,e1=metric_audit()
    inputs=Inputs(e0,e1)
    catalog=make_catalogue()
    save(catalog,OUT/'ALL_EFFECT_MEAN_REVERSALS.csv.gz')
    save(catalog[catalog.quality_score_metric],OUT/'Q_REVERSALS.csv')
    print('catalogue',len(catalog),'Q',int(catalog.quality_score_metric.sum()),flush=True)
    decomposition,units=unit_decomposition(catalog,inputs)
    save(decomposition,OUT/'REVERSAL_SUPPORT_DECOMPOSITION.csv.gz')
    save(units,OUT/'REVERSAL_UNIT_CONTRIBUTIONS.csv.gz')
    detailed=catalog.merge(decomposition,on='reversal_id',suffixes=('','_recomputed'),validate='one_to_one')
    save(detailed[detailed.quality_score_metric],OUT/'Q_REVERSALS_WITH_SUPPORT.csv')
    q_detail(detailed[detailed.quality_score_metric],inputs)
    accept_consumers(inputs)
    save(pd.DataFrame(AUDITS),OUT/'NUMERICAL_ACCEPTANCE.csv.gz')
    save(pd.DataFrame(CONSUMERS),OUT/'CONSUMER_ACCEPTANCE.csv')
    runtime=[]
    for p in sorted(RUNTIME_INPUTS):
        runtime.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),provided_in_current_supplement=str(p).startswith(str(OUT))))
    save(pd.DataFrame(runtime),OUT/'RUNTIME_INPUTS.csv')
    jsave(OUT/'DELIVERY_EXCLUSIONS.json',{'safe_to_exclude':[
        'source_cache/POOL_CONDITION_EFFECTS.csv.gz','source_cache/DESIGN_LINKS.csv.gz',
        'source_cache/EXTRA_SOURCE_MANIFEST.json','Q_TRACE_RUN.log'],
        'reason':'The exact frozen affected-condition pool subset and affected-pool registered link subset are bundled in inputs/. Script prefers these subsets. Full original SHA256 and immutable GitHub URL remain in source manifests.',
        'requires_previous_batches':'01 through 05; this supplemental script reads their unchanged output paths.'})
    checks=dict(status='PASS',source_repository_commit=COMMIT,original_batches_changed=False,
        new_teams=0,new_fusions=0,new_endpoint_scores=0,new_classifications=0,coordinate_candidate_adopted=False,
        affected_method_events=339,affected_physical_pairs=245,new_Q_method_events=257,new_Q_physical_pairs=193,
        all_metric_effect_mean_reversal_rows=len(catalog),Q_reversal_rows=int(catalog.quality_score_metric.sum()),
        numerical_checks=len(AUDITS),numeric_cells=sum(x['numeric_cells'] for x in AUDITS),
        mismatches=sum(x['mismatches'] for x in AUDITS),consumer_groups=len(CONSUMERS),
        missing_Q_imputed=False,tolerance=TOL,
        count_note='Rows are estimands/metrics/weightings and include view aliases; they are not independent new experiments.')
    jsave(OUT/'CHECKS.json',checks)
    print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__=='__main__': main()
