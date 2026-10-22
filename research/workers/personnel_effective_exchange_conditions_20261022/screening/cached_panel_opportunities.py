"""Exact unused common-background opportunities inside cached member panels.

Counts every legally labelled actual oriented ABC contrast in each complete
C(12,6) panel by class-count combinatorics. Does not enumerate/recompute fusion
endpoints. Panel totals are deliberately not called global unique ABC totals.
"""
from __future__ import annotations
from common_screening import *
from functools import lru_cache
import itertools,time

@lru_cache(maxsize=None)
def vectors(cap,total):
    if len(cap)==0:return ((),) if total==0 else ()
    out=[]
    for k in range(max(0,total-sum(cap[1:])),min(cap[0],total)+1):
        out.extend((k,)+rest for rest in vectors(cap[1:],total-k))
    return tuple(out)

def ways(cap,take):return math.prod(math.comb(a,b) if a>=b else 0 for a,b in zip(cap,take))

@lru_cache(maxsize=None)
def census(cap,parents,m,parent_fixed):
    N=sum(cap);anchor_total=math.comb(N,6) if N>=6 else 0
    if N<6+m:return dict(anchor_total=anchor_total,eligible_anchors=0,eligible_backgrounds=0,ABC_triples=0)
    parent_levels=sorted(set(parents));valid_g=set();eligible_a=0;triples=0
    for a in vectors(cap,6):
        aw=ways(cap,a);out=tuple(c-v for c,v in zip(cap,a));has=False
        for x in vectors(a,m):
            same=ways(out,x)
            if not same:continue
            if parent_fixed:
                xp=[sum(v for v,p in zip(x,parents) if p==label) for label in parent_levels]
                op=[sum(v for v,p in zip(out,parents) if p==label) for label in parent_levels]
                cross=ways(op,xp)-same
            else:cross=math.comb(N-6,m)-same
            if cross<=0:continue
            has=True;triples+=aw*ways(a,x)*same*cross
            valid_g.add(tuple(v-t for v,t in zip(a,x)))
        if has:eligible_a+=aw
    return dict(anchor_total=anchor_total,eligible_anchors=eligible_a,
      eligible_backgrounds=sum(ways(cap,g) for g in valid_g),ABC_triples=triples)

def main():
    start=time.time();panels=pd.read_csv(COMPOSITION/'PANELS.csv',keep_default_na=False)
    labels=pd.read_csv(COMPOSITION/'delivery/FROZEN_EVALUATION_LABELS.csv.gz')
    lm={key:g.set_index('worker_id')[['class_id','parent_class']].to_dict('index')
        for key,g in labels.groupby(['method_id','tier','condition','heldout_building'])}
    ev=pd.read_csv(HERE/'EVENTS_UNIFIED.csv.gz',usecols=['comparison','prior_stages','panel_id','method_id','tier',
       'condition','building','source_domain','n','m','parent_fixed','actual_exchange_id','common_background_id','team_A'])
    ev=ev[ev.comparison.eq('ABC_matched')&ev.prior_stages.str.contains('PANEL')]
    observed={key:g for key,g in ev.groupby(['panel_id','method_id','tier','m'])}
    membership=pd.read_csv(COMPOSITION/'PANEL_MEMBERSHIP.csv.gz',usecols=['panel_id','team_key'])
    endpoints=pd.read_csv(COMPOSITION/'delivery/ENDPOINT_KEY_INDEX.csv.gz',usecols=['team_key'])
    available=set(endpoints.team_key)
    cache=membership.assign(cached=membership.team_key.isin(available)).groupby('panel_id').agg(
       registered=('team_key','nunique'),cached=('cached','sum')).to_dict('index')
    rows=[]
    for panel in panels.to_dict('records'):
        for (method,tier,condition,building),mapping in lm.items():
            if (condition,building)!=(panel['condition'],panel['building']):continue
            variable=workers(panel['variable_workers']);base=workers(panel['background_workers'])
            missing_base=sorted(set(base)-set(mapping));known=[w for w in variable if w in mapping]
            classes=sorted({mapping[w]['class_id'] for w in known})
            counts=tuple(sum(mapping[w]['class_id']==cl for w in known) for cl in classes)
            pnames=[next(mapping[w]['parent_class'] for w in known if mapping[w]['class_id']==cl) for cl in classes]
            canonical_parents=tuple(sorted(set(pnames)).index(v) for v in pnames)
            for m in range(1,7):
                for fixed in [False,True] if tier=='fine' else [False]:
                    z=observed.get((panel['panel_id'],method,tier,m),pd.DataFrame())
                    if len(z) and fixed:z=z[z.parent_fixed]
                    result=census(counts,canonical_parents,m,fixed) if not missing_base else dict(anchor_total=0,eligible_anchors=0,eligible_backgrounds=0,ABC_triples=0)
                    actual=z.actual_exchange_id.nunique() if len(z) else 0
                    backgrounds=z.common_background_id.nunique() if len(z) else 0
                    anchors=z.team_A.nunique() if len(z) else 0
                    # All current teams/results, including failures, count as
                    # cached. Success is never a prerequisite to opportunity.
                    assert cache[panel['panel_id']]['cached']==cache[panel['panel_id']]['registered']==924
                    assert actual<=result['ABC_triples'],(panel['panel_id'],method,tier,m,fixed,actual,result)
                    assert backgrounds<=result['eligible_backgrounds']
                    row={k:panel[k] for k in ['panel_id','pool_id','image','building','condition','difficulty','source_domain','n','variable_workers','background_workers']}
                    row.update(method_id=method,tier=tier,m=m,parent_fixed_only=fixed,known_variable_n=len(known),
                      unknown_background_workers='|'.join(missing_base),unknown_variable_workers='|'.join(sorted(set(variable)-set(known))),
                      variable_class_capacities=canonical_counts(dict(zip(classes,counts))),cached_endpoint_results=924,
                      valid_labelled_anchor_teams=result['anchor_total'],eligible_anchor_teams=result['eligible_anchors'],
                      all_eligible_distinct_common_backgrounds=result['eligible_backgrounds'],
                      all_oriented_actual_ABC_contrasts=str(result['ABC_triples']),
                      archived_distinct_ABC=actual,archived_distinct_backgrounds=backgrounds,archived_distinct_anchor_teams=anchors,
                      unused_common_backgrounds=result['eligible_backgrounds']-backgrounds,
                      unused_eligible_anchor_teams=result['eligible_anchors']-anchors,
                      unregistered_ABC_contrasts=str(result['ABC_triples']-actual),
                      new_native_fusion_required=0,
                      counting_identity='complete per-panel census; not deduplicated across overlapping panels or methods',
                      priority='different_background' if result['eligible_backgrounds']>backgrounds else 'different_members_same_background' if result['ABC_triples']>actual else 'no_additional_matched_contrast')
                    rows.append(row)
    d=pd.DataFrame(rows)
    receipt=save_csv('CACHED_PANEL_MEMBER_BACKGROUND_OPPORTUNITIES.csv.gz',d)
    # Reuse the old explicitly limited twelve-anchor search denominator as its
    # own identity, never substitute it for this all-anchor finite-panel count.
    old=pd.read_csv(COMPOSITION/'matched/PANEL_OPPORTUNITIES.csv.gz')
    oldreceipt=save_csv('REUSED_TWELVE_ANCHOR_OPPORTUNITIES.csv.gz',old)
    summary=d.groupby(['condition','method_id','tier','source_domain','m','parent_fixed_only']).agg(
      panels=('panel_id','size'),images=('image','nunique'),buildings=('building','nunique'),
      panels_with_extra_background=('unused_common_backgrounds',lambda s:int(s.gt(0).sum())),
      panel_background_incidence_available=('all_eligible_distinct_common_backgrounds','sum'),
      panel_background_incidence_used=('archived_distinct_backgrounds','sum'),
      panel_background_incidence_unused=('unused_common_backgrounds','sum')).reset_index()
    sr=save_csv('CACHED_OPPORTUNITY_SUMMARY.csv',summary)
    save_json('CACHE_OPPORTUNITY_COMPLETION.json',dict(status='complete',seconds=time.time()-start,
      rows=len(d),panels=len(panels),cached_endpoints_checked=len(available),files=[receipt,oldreceipt,sr],
      native_calls=0,new_events_constructed=0,base_data_version='v2',
      root_full_inventory_capacity_reference='../expanded_blocks/INITIAL_FULL_POOL_CAPACITY.csv',
      joint_additional_exchange_owner='../joint_exchange/',
      caution='Totals are per panel. Overlapping panels/methods must not be added as global distinct contrasts. Entire finite 924-team endpoint spaces have already been fused, including failures.'))
    print(json.dumps(dict(status='complete',rows=len(d),seconds=time.time()-start)),flush=True)

if __name__=='__main__':main()
