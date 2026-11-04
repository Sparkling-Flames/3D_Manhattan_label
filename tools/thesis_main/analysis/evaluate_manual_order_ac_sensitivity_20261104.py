"""Affected AC sensitivity panels and their exact downstream summaries.

The original definitions, orientations, member panels and weights are reused.
Only affected condition groups are reaggregated from their complete saved pool
support.  No fusion, score fitting, label selection or new team construction.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import importlib
from pathlib import Path
import sys
import numpy as np
import pandas as pd

from .evaluate_manual_order_ac_20261104 import (
    AC, OUT, ROOT, VERSION, TOLERANCE, save, jsave, read_json, compare, align,
    normalized_text)

SOURCE=AC/'stage05_sensitivity'
NAMES=['MEMBER_PANELS','BACKGROUND_CHANGES','FIXED_BLOCK_BACKGROUND_STEPS',
       'FIXED_A_REPLACEMENT_STEPS','UNEQUAL_DECOMPOSITION','COMPLETE_COALITIONS','SAMPLING_BATCHES']
IDENTITIES={
 'MEMBER_PANELS':['pool_id','panel_kind','panel_id'],
 'BACKGROUND_CHANGES':['pool_id','method','block_id','n','m','baseline_event_id','changed_event_id','background_profile'],
 'FIXED_BLOCK_BACKGROUND_STEPS':['pool_id','method','path_id','event_from','event_to'],
 'FIXED_A_REPLACEMENT_STEPS':['pool_id','method','path_id','event_from','event_to'],
 'UNEQUAL_DECOMPOSITION':['pool_id','method','parent_contrast_id','member_rep'],
 'COMPLETE_COALITIONS':['pool_id','method','event_id','analysis_orientation_sign'],
 'SAMPLING_BATCHES':['pool_id','method','cell_id'],
}


def modules():
    sys.path.insert(0,str(SOURCE/'code'))
    import analyze_population_sensitivity as s
    import enrich_sensitivity_amplitudes as amplitude
    return s,amplitude


def identities(frame,keys):
    d=frame[keys].copy()
    for c in keys:
        d[c]=normalized_text(d[c])
        if c in {'n','m','n_from','n_to','m_from','m_to','member_rep'}:
            d[c]=d[c].map(lambda x:format(float(x),'.12g') if x and x.replace('.','',1).isdigit() else x)
    return pd.MultiIndex.from_frame(d)


def subset(frame,selected,keys):
    wanted=identities(selected,keys)
    return frame[identities(frame,keys).isin(wanted)].copy()


def read_subset(path,selected,keys,chunk=15000):
    parts=[]
    for d in pd.read_csv(path,chunksize=chunk,low_memory=False):
        p=subset(d,selected,keys)
        if len(p):parts.append(p)
    if parts:return pd.concat(parts,ignore_index=True)
    return pd.read_csv(path,nrows=0)


def changed_rows(old,new,keys):
    a,b=align(old,keys),align(new,keys)
    assert a.index.equals(b.index)
    change=pd.Series(False,index=a.index)
    for col in a:
        x,y=a[col],b[col]
        nx,ny=pd.to_numeric(x,errors='coerce'),pd.to_numeric(y,errors='coerce')
        numeric=(x.isna()|nx.notna()).all() and (y.isna()|ny.notna()).all()
        if numeric:
            change |= (nx.isna()^ny.isna())|((nx.astype(float)-ny.astype(float)).abs()>TOLERANCE)
        else:
            change |= normalized_text(x).ne(normalized_text(y))
    return a[change].reset_index(),b[change].reset_index()


def patch(frame,values,keys):
    target=align(frame,keys);v=align(values,keys)
    ix=target.index.intersection(v.index)
    target.loc[ix,v.columns]=v.loc[ix]
    return target.reset_index()[frame.columns]


def numeric(d,s):
    wanted=set(s.META+s.METRICS+[a+'_'+m for a in ['A','C'] for m in s.ARM_METRICS])
    d=d.reindex(columns=sorted(wanted)).copy()
    for c in s.METRICS+[a+'_'+m for a in ['A','C'] for m in s.ARM_METRICS]:
        d[c]=pd.to_numeric(d[c],errors='coerce').astype(float)
    return d


def call_main(module,args):
    saved=sys.argv
    try:
        sys.argv=[module.__file__]+[str(a) for a in args]
        module.main()
    finally:sys.argv=saved


def raw_panels(out,s):
    pids=[p.name[:-7] for p in (OUT/'metric_shards').glob('*.csv.gz')]
    selected=pd.DataFrame({'pool_id':pids})
    links=read_subset(AC/'stage01_registered/DESIGN_LINKS.csv.gz',selected,['pool_id'])
    for c in s.LINK:
        if c not in links:links[c]=np.nan
    links=links[s.LINK]
    roles={}
    for r in pd.read_csv(AC/'stage01_capacity/FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv').to_dict('records'):
        if s.finite(r['primary_role_rank']):roles[r['method'],r['heldout_building'],r['class_id']]=float(r['primary_role_rank'])
    funcs=[s.member_panels,s.background_changes,lambda d,l:s.paths(d,l,False),
           lambda d,l:s.paths(d,l,True),s.unequal_decomposition,
           lambda d,l:s.coalitions(d,l,roles),s.batches]
    rawold,rawnew=defaultdict(list),defaultdict(list)
    for pid in pids:
        before=numeric(pd.read_csv(AC/'stage04_metrics/metric_shards'/(pid+'.csv.gz'),low_memory=False),s)
        after=numeric(pd.read_csv(OUT/'metric_shards'/(pid+'.csv.gz'),low_memory=False),s)
        lg=links[links.pool_id.eq(pid)]
        for name,func in zip(NAMES,funcs):
            a,b=func(before,lg),func(after,lg)
            if len(a):rawold[name].append(a);rawnew[name].append(b)
        print('AC sensitivity original/assisted panels',pid,flush=True)
    parity=[];counts=[]
    for name in NAMES:
        if not rawold[name]:continue
        old,new=pd.concat(rawold[name],ignore_index=True),pd.concat(rawnew[name],ignore_index=True)
        keys=IDENTITIES[name]
        original=read_subset(SOURCE/'results_v1'/(name+'.csv.gz'),selected,['pool_id'])
        parity.extend(compare(original,old,keys,'original_sensitivity:'+name))
        save(old,out/'raw_automatic'/(name+'.csv.gz'));save(new,out/'raw_assisted'/(name+'.csv.gz'))
        changed_before,changed_after=changed_rows(old,new,keys)
        save(changed_before,out/'changed_raw_automatic'/(name+'.csv.gz'))
        save(changed_after,out/'changed_raw_assisted'/(name+'.csv.gz'))
        oldpool,newpool=s.pool_summary(name,old),s.pool_summary(name,new)
        save(oldpool,out/'pool_automatic'/(name+'.csv.gz'));save(newpool,out/'pool_assisted'/(name+'.csv.gz'))
        gkeys,_=s.summary_spec(name,oldpool)
        fullkey=gkeys+['pool_id','image','building']
        saved_pool=read_subset(SOURCE/'results_v1'/(name+'_POOL_SUMMARY.csv.gz'),selected,['pool_id'])
        parity.extend(compare(saved_pool,oldpool,fullkey,'original_pool_sensitivity:'+name))
        counts.append(dict(table=name,regenerated_raw_rows=len(old),changed_raw_rows=len(changed_after),
                           regenerated_pool_rows=len(oldpool),
                           changed_pool_rows=len(changed_rows(oldpool,newpool,fullkey)[0])))
    save(pd.DataFrame(parity),out/'RAW_AND_POOL_PARITY.csv')
    save(pd.DataFrame(counts),out/'DEPENDENCY_COUNTS.csv')
    return counts


def aggregate(out,s,amplitude):
    olddest=out/'automatic_affected_conditions';newdest=out/'assisted_affected_conditions'
    groups={};parity=[]
    for name in NAMES:
        path=out/'pool_automatic'/(name+'.csv.gz')
        if not path.exists():continue
        a=pd.read_csv(path,low_memory=False);b=pd.read_csv(out/'pool_assisted'/(name+'.csv.gz'),low_memory=False)
        keys,_=s.summary_spec(name,a);fullkey=keys+['pool_id','image','building']
        ch0,ch1=changed_rows(a,b,fullkey)
        if ch0.empty:continue
        groups[name]=ch0[keys].drop_duplicates()
        old=read_subset(SOURCE/'results_v1'/(name+'_POOL_SUMMARY.csv.gz'),groups[name],keys)
        new=patch(old,b,fullkey)
        save(old,olddest/'pool_summaries/affected'/(name+'.csv.gz'))
        save(new,newdest/'pool_summaries/affected'/(name+'.csv.gz'))
        save(groups[name],out/'affected_group_identities'/(name+'.csv.gz'))
    for dest in (olddest,newdest):
        dest.mkdir(parents=True,exist_ok=True)
        _,n=s.aggregate(dest)
        jsave(dest/'SENSITIVITY_RECEIPT.json',{'image_balanced_summary_rows':n,'partial_scope':'affected condition groups, complete original pool support'})
        call_main(amplitude,['--results',dest])
    allchanges=[]
    for version in ('','_V2'):
        fn='SENSITIVITY_IMAGE_BALANCED_SUMMARY'+version+'.csv.gz'
        a=pd.read_csv(olddest/fn,low_memory=False);b=pd.read_csv(newdest/fn,low_memory=False)
        for name,g in groups.items():
            keys,_=s.summary_spec(name,g);keys=keys+['metric']
            old=a[a.analysis_table.eq(name)];new=b[b.analysis_table.eq(name)]
            wanted=g.copy();wanted['analysis_table']=name
            frozen=read_subset(SOURCE/'results_v1'/fn,wanted,['analysis_table']+keys[:-1])
            parity.extend(compare(frozen,old,keys,'original_sensitivity_summary'+version+':'+name))
            if version=='_V2':
                c0,c1=changed_rows(old,new,keys)
                aa,bb=align(c0,keys),align(c1,keys)
                delta=aa.add_prefix('automatic_').join(bb.add_prefix('assisted_')).reset_index()
                delta['analysis_table']=name
                allchanges.append(delta)
    save(pd.DataFrame(parity),out/'SUMMARY_PARITY.csv')
    save(pd.concat(allchanges,ignore_index=True),out/'SENSITIVITY_SUMMARY_CHANGES.csv.gz')
    return {'changed_tables':list(groups),'changed_summary_rows':sum(map(len,allchanges))}


def advanced(out,s):
    # Correct per-metric >=2 member-variation denominator, keeping singleton
    # descriptive ranges out of inference, exactly as the original v2 correction.
    import correct_member_variability_denominators as member
    import summarize_complete_decomposition_support as decomp
    import add_decomposition_size_coverage as sizes
    parity=[];counts={}
    jobs=[('MEMBER_PANELS',member.KEY,IDENTITIES['MEMBER_PANELS'],'member_variability_v2'),
          ('UNEQUAL_DECOMPOSITION',[k for k in decomp.KEY if k!='parent_background_stratum'],
           IDENTITIES['UNEQUAL_DECOMPOSITION'],'three_leg_common_support_v2')]
    for name,groups,rowkey,folder in jobs:
        ch=pd.read_csv(out/'changed_raw_assisted'/(name+'.csv.gz'),low_memory=False)
        if ch.empty:counts[name]={'changed':False};continue
        selected=ch[groups].drop_duplicates()
        old=read_subset(SOURCE/'results_v1'/(name+'.csv.gz'),selected,groups)
        overlay=pd.read_csv(out/'raw_assisted'/(name+'.csv.gz'),low_memory=False)
        new=patch(old,overlay,rowkey)
        olddir=out/folder/'automatic';newdir=out/folder/'assisted'
        for dest,frame in [(olddir,old),(newdir,new)]:
            save(frame,dest/'SOURCE_ROWS.csv.gz')
            if name=='MEMBER_PANELS':
                call_main(member,['--panels',dest/'SOURCE_ROWS.csv.gz','--out',dest])
            else:
                args=['--paths',dest/'SOURCE_ROWS.csv.gz','--capacity',AC/'stage01_capacity/POOL_METHOD_CAPACITY.csv.gz','--out',dest]
                call_main(decomp,args);call_main(sizes,args)
        files=['MEMBER_VARIABILITY_VALID_GE2_SUMMARY.csv.gz'] if name=='MEMBER_PANELS' else [
            'COMMON_VALID_THREE_LEG_IMAGE_SUMMARY.csv.gz','COMMON_VALID_DECOMPOSITION_SIZE_COVERAGE.csv.gz']
        ownchanges=[]
        for fn in files:
            a=pd.read_csv(olddir/fn,low_memory=False);b=pd.read_csv(newdir/fn,low_memory=False)
            keys=(member.KEY if name=='MEMBER_PANELS' else decomp.KEY)+['metric']
            frozen=read_subset(SOURCE/folder/fn,selected,groups)
            parity.extend(compare(frozen,a,keys,'original_'+folder+':'+fn))
            c0,c1=changed_rows(a,b,keys)
            delta=align(c0,keys).add_prefix('automatic_').join(align(c1,keys).add_prefix('assisted_')).reset_index()
            save(delta,out/folder/(fn.replace('.csv.gz','_CHANGES.csv.gz')))
            ownchanges.append({'file':fn,'changed_rows':len(delta)})
        counts[name]={'selected_source_rows':len(old),'outputs':ownchanges}
    save(pd.DataFrame(parity),out/'ADVANCED_PARITY.csv')
    return counts


def outside(out,s):
    import match_existing_outside_backgrounds as m
    pids=[p.name[:-7] for p in (OUT/'metric_shards').glob('*.csv.gz')]
    ptable=pd.DataFrame({'pool_id':pids})
    links=read_subset(AC/'stage01_registered/DESIGN_LINKS.csv.gz',ptable,['pool_id']).reindex(columns=m.LINK)
    aa,bb=[],[]
    for pid in pids:
        lg=links[links.pool_id.eq(pid)]
        for target,folder in [(aa,AC/'stage04_metrics'),(bb,OUT)]:
            d=numeric(pd.read_csv(folder/'metric_shards'/(pid+'.csv.gz'),low_memory=False),s)
            frame=m.match_pool(d,lg)
            if len(frame):target.append(frame)
    old,new=pd.concat(aa,ignore_index=True),pd.concat(bb,ignore_index=True)
    keys=['background_comparison_id']
    frozen=read_subset(SOURCE/'exact_outside_background_v1/EXACT_NEUTRAL_OUTSIDE_BACKGROUND_PAIRS.csv.gz',ptable,['pool_id'])
    parity=compare(frozen,old,keys,'original_exact_background_pairs')
    save(old,out/'exact_outside_background/automatic_pairs.csv.gz');save(new,out/'exact_outside_background/assisted_pairs.csv.gz')
    c0,c1=changed_rows(old,new,keys)
    if c0.empty:
        save(pd.DataFrame(parity),out/'EXACT_BACKGROUND_PARITY.csv')
        return {'changed_raw_pairs':0}
    pa,pb=m.summarize_pool(old),m.summarize_pool(new)
    pk=m.GROUP+['pool_id','image','building']
    frozenpool=read_subset(SOURCE/'exact_outside_background_v1/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz',ptable,['pool_id'])
    parity.extend(compare(frozenpool,pa,pk,'original_exact_background_pool'))
    ga,gb=changed_rows(pa,pb,pk);groups=ga[m.GROUP].drop_duplicates()
    target=read_subset(SOURCE/'exact_outside_background_v1/EXACT_NEUTRAL_OUTSIDE_POOL_SUMMARY.csv.gz',groups,m.GROUP)
    changed=patch(target,pb,pk)
    od=out/'exact_outside_background/automatic';nd=out/'exact_outside_background/assisted'
    for dest,p,r in [(od,target,c0),(nd,changed,c1)]:
        save(r,dest/'pool_shards/affected.csv.gz');save(p,dest/'pool_summaries/affected.csv.gz');m.aggregate(dest)
    fn='EXACT_NEUTRAL_OUTSIDE_IMAGE_BALANCED_SUMMARY.csv.gz'
    oldsum=pd.read_csv(od/fn,low_memory=False);newsum=pd.read_csv(nd/fn,low_memory=False)
    frozen=read_subset(SOURCE/'exact_outside_background_v1'/fn,groups,m.GROUP)
    parity.extend(compare(frozen,oldsum,m.GROUP+['metric'],'original_exact_background_summary'))
    sa,sb=changed_rows(oldsum,newsum,m.GROUP+['metric'])
    changes=align(sa,m.GROUP+['metric']).add_prefix('automatic_').join(align(sb,m.GROUP+['metric']).add_prefix('assisted_')).reset_index()
    save(changes,out/'exact_outside_background/SUMMARY_CHANGES.csv.gz')
    save(pd.DataFrame(parity),out/'EXACT_BACKGROUND_PARITY.csv')
    return {'changed_raw_pairs':len(c0),'changed_summary_rows':len(changes)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT/'sensitivity')
    parser.add_argument('--phase',choices=['raw','summary','advanced','outside','all'],default='all')
    args=parser.parse_args();s,amplitude=modules();out=args.out;out.mkdir(parents=True,exist_ok=True)
    receipt=read_json(out/'SENSITIVITY_IMPACT_RECEIPT.json') if (out/'SENSITIVITY_IMPACT_RECEIPT.json').exists() else {
        'analysis_version':VERSION,'new_fusions':0,'new_scores':0,'new_teams':0,'new_classifications':0,
        'missing_Q_imputed':False,'frozen_role_labels_changed':False,'original_files_modified':False}
    # Preserve a per-phase receipt.  Separate resumed phases may finish long
    # after startup; never write the receipt snapshot read at startup over a
    # different completed phase's evidence.  The finalizer also joins these
    # immutable phase receipts before delivery.
    jobs={'raw':lambda:raw_panels(out,s),
          'summary':lambda:aggregate(out,s,amplitude),
          'advanced':lambda:advanced(out,s),
          'outside':lambda:outside(out,s)}
    for phase,run in jobs.items():
        if args.phase not in (phase,'all'):continue
        value=run()
        jsave(out/('PHASE_RECEIPT_'+phase+'.json'),
              {'analysis_version':VERSION,'phase':phase,'result':value})
        if (out/'SENSITIVITY_IMPACT_RECEIPT.json').exists():
            receipt.update(read_json(out/'SENSITIVITY_IMPACT_RECEIPT.json'))
        for path in sorted(out.glob('PHASE_RECEIPT_*.json')):
            saved=read_json(path);receipt[saved['phase']]=saved['result']
        receipt[phase]=value
        jsave(out/'SENSITIVITY_IMPACT_RECEIPT.json',receipt)
    print(receipt,flush=True)


if __name__=='__main__':main()
