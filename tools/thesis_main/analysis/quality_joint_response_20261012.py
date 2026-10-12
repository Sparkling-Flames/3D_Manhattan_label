"""整体与局部高度共同变化的固定组合诊断，不选择正式质量模型。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path

if __package__:
    from .quality_top_height_response_20261012 import analytic_case, response_terms, components, read_json, save_json, distribution, validate_development_gates
    from .quality_top_residual_20261012 import spherical_sym_distance
    from .quality_height_conditioning_20261012 import coordinate_key
else:
    from quality_top_height_response_20261012 import analytic_case, response_terms, components, read_json, save_json, distribution, validate_development_gates
    from quality_top_residual_20261012 import spherical_sym_distance
    from quality_height_conditioning_20261012 import coordinate_key
from audit_geometry import flatness


def configurations(inputs,protocol):
    result={c['name']:dict(kind='response',config=c) for c in protocol['candidates']}
    for c in inputs['previous_review']['configs']:
        if c['name'] in ('Q_dbounded1_max_height','Q_dbounded1_max_top'):
            result[c['name']]=dict(kind='legacy',config=c)
    return result


def terms(m,c):
    return (response_terms if c['kind']=='response' else components)(m,c['config'])


def operator_effects(m,c):
    full=terms(m,c)
    no_g=dict(m,Hmean=0.,height_mean_ratio=1.)
    no_l=dict(m,Hcenter=0.)
    both=dict(no_g,Hcenter=0.)
    qg,ql,q0=(terms(x,c)['score'] for x in (no_g,no_l,both))
    local_drop=ql-full['score']
    isolated_local=q0-qg
    return dict(score=full['score'],global_loss=full['global_height_loss'],local_loss=full['local_height_loss'],
                top_loss=full['top_boundary_loss'],score_both_height_zero=q0,
                global_marginal_points=qg-full['score'],local_marginal_points=local_drop,
                local_isolated_points=isolated_local,
                local_structurally_blocked=(full['local_height_loss']>1e-12 and
                    ((c['kind']=='legacy' and c['config']['height_combine']=='max' and full['global_height_loss']>=full['local_height_loss']) or
                     (c['kind']=='legacy' and c['config']['top_combine']=='max' and full['top_boundary_loss']>=full['global_height_loss']+full['local_height_loss']))),
                local_unmasked_by_global=isolated_local<=1e-12 and local_drop>1e-12,
                local_visibility_fraction=local_drop/isolated_local if isolated_local>1e-12 else None)


def make_control(ratio,local,scale):
    c=analytic_case(ratio,local)
    a,g=deepcopy(c['annotation']),deepcopy(c['reference'])
    for geo in (a,g):
        for ring in geo.values():
            for p in ring: p[0]*=scale; p[2]*=scale
    minimum=min(p[1] for p in a['top3d'])
    m=None
    if minimum>0:
        m=dict(c['metrics'],S_top_deg=float(spherical_sym_distance(a['top3d'],g['top3d'],n=2048)),flat=flatness(a,n=512)['flat'],height_mean_ratio=ratio)
    return dict(id=f'r{ratio}_l{local}_s{scale}',ratio=ratio,local=local,scale=scale,annotation=a,reference=g,
                minimum_top_y=minimum,status='available' if minimum>0 else 'out_of_camera_domain',metrics=m)


def monotonicity(controls,design,candidates):
    by_key={(c['ratio'],c['local'],c['scale']):c for c in controls}
    pairs=[]
    def add(keys,axis):
        for k0,k1 in zip(keys,keys[1:]):
            a,b=by_key[k0],by_key[k1]
            if a['status']==b['status']=='available': pairs.append((a,b,axis))
    lower=sorted([r for r in design['global_ratios'] if r<=1],reverse=True)
    upper=sorted([r for r in design['global_ratios'] if r>=1])
    for scale in design['horizontal_scales']:
        for ratio in design['global_ratios']:
            add([(ratio,l,scale) for l in design['local_rms']],'local')
        for local in design['local_rms']:
            for ratios,axis in [(lower,'global_low'),(upper,'global_high')]:
                add([(r,local,scale) for r in ratios],axis)
    out={}
    for name in candidates:
        comparisons=[dict(before=a['id'],after=b['id'],axis=axis,score_delta=b['effects'][name]['score']-a['effects'][name]['score'],
                          high_resolution_score_delta=terms(b['high_resolution_metrics'],candidates[name])['score']-terms(a['high_resolution_metrics'],candidates[name])['score']) for a,b,axis in pairs]
        out[name]=dict(comparisons=comparisons,compared=len(comparisons),
                       increases=sum(p['score_delta']>1e-8 for p in comparisons),
                       unchanged=sum(abs(p['score_delta'])<=1e-8 for p in comparisons),
                       decreases=sum(p['score_delta']<-1e-8 for p in comparisons))
    return out


def run(inputs,protocol,previous,design):
    validate_development_gates([dict(record_id=r['id']) for r in inputs['rows']],inputs['gates'])
    candidates=configurations(inputs,protocol)
    controls=[]
    high_score_errors=[]
    for scale in design['horizontal_scales']:
        for ratio in design['global_ratios']:
            for local in design['local_rms']:
                c=make_control(ratio,local,scale)
                c['effects']=None
                if c['metrics'] is not None:
                    c['effects']={name:operator_effects(c['metrics'],cfg) for name,cfg in candidates.items()}
                    high=dict(c['metrics'],S_top_deg=float(spherical_sym_distance(c['annotation']['top3d'],c['reference']['top3d'],n=8192)),flat=flatness(c['annotation'],n=2048)['flat'])
                    c['high_resolution_metrics']=high
                    for name,cfg in candidates.items():
                        high_score_errors.append(abs(terms(high,cfg)['score']-c['effects'][name]['score']))
                controls.append(c)
    old={r['id']:r['scores'] for r in previous['development']}
    groups={}
    for r in sorted(inputs['rows'],key=lambda r:r['id']):
        groups.setdefault(coordinate_key(r,inputs['geometries'][r['object_id']]),[]).append(r)
    records,unique,group_list,parity=[],[],[],[]
    for members in groups.values():
        representative=members[0]['id']
        group_list.append(dict(representative=representative,members=[r['id'] for r in members]))
        for r in members:
            effects={name:operator_effects(r['metrics'],cfg) for name,cfg in candidates.items()}
            parity.extend(abs(effects[name]['score']-old[r['id']][name]) for name in old[r['id']])
            out={k:r[k] for k in ('id','image_id','image_code','building_id','applicability_confirmed')}
            out|=dict(coordinate_representative=representative,Hmean=r['metrics']['Hmean'],Hcenter=r['metrics']['Hcenter'],effects=effects)
            records.append(out)
            if r['id']==representative: unique.append(out)
    if max(parity)>1e-9: raise ValueError(('Previous score replay mismatch',max(parity)))
    strata,selected={},{}
    for name,qual in [('all',None),('confirmed',True),('unknown',False)]:
        rr=[r for r in records if qual is None or r['applicability_confirmed']==qual]
        uu=[r for r in unique if qual is None or r['applicability_confirmed']==qual]
        def summary(rows):
            return dict(count=len(rows),Hmean=distribution([r['Hmean'] for r in rows]),Hcenter=distribution([r['Hcenter'] for r in rows]),
                        global_ge_inherited_scale=sum(r['Hmean']>=.5 for r in rows),local_ge_inherited_scale=sum(r['Hcenter']>=.25 for r in rows),
                        both_ge_inherited_scales=sum(r['Hmean']>=.5 and r['Hcenter']>=.25 for r in rows),
                        candidates={n:dict(local_visibility=distribution([r['effects'][n]['local_visibility_fraction'] for r in rows if r['effects'][n]['local_visibility_fraction'] is not None]),
                                           local_zero_marginal_count=sum(r['effects'][n]['local_loss']>0 and abs(r['effects'][n]['local_marginal_points'])<=1e-12 for r in rows),
                                           local_structurally_blocked_count=sum(r['effects'][n]['local_structurally_blocked'] for r in rows),
                                           local_unmasked_by_global_count=sum(r['effects'][n]['local_unmasked_by_global'] for r in rows),
                                           visibility_unavailable_count=sum(r['effects'][n]['local_visibility_fraction'] is None for r in rows)) for n in candidates})
        strata[name]=dict(record_statistics=summary(rr),coordinate_group_statistics=summary(uu))
        if qual is None: continue
        for key in ('Hmean','Hcenter','relative4_local_visibility'):
            value=lambda r:r['effects']['relative4']['local_visibility_fraction'] if key=='relative4_local_visibility' else -r[key]
            for r in sorted([r for r in uu if value(r) is not None],key=lambda r:(value(r),r['id']))[:3]:
                selected.setdefault(r['id'],[]).append(f'{name}:{key}')
    t20=next(r for r in records if r['id']=='R00397')
    selected.setdefault(t20['coordinate_representative'],[]).append('reviewed_T20')
    return dict(schema='quality_joint_response_results_v1',controls=controls,monotonicity=monotonicity(controls,design,candidates),records=records,coordinate_groups=group_list,
                strata=strata,selected_cases=[next(r for r in unique if r['id']==rid)|dict(reasons=reasons,human_grade=None) for rid,reasons in selected.items()],
                verification=dict(previous_score_cells=len(parity),maximum_previous_score_delta=max(parity),maximum_control_score_resolution_delta=max(high_score_errors)),
                scope=dict(formal_score_changed=False,new_human_grades=False,holdout_used=False,raw_inputs_modified=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study',type=Path,default=Path('research/quality_top_height_response_20261012'))
    p.add_argument('--figures',action='store_true')
    args=p.parse_args()
    s=args.study
    out=run(read_json(s/'inputs.json'),read_json(s/'protocol.json'),read_json(s/'results.json'),read_json(s/'joint_response_design.json'))
    save_json(s/'joint_response.json',out)
    if args.figures: figure(out,s/'joint_response.png')
    print(out['verification'])
    print({k:{key:v[key] for key in ('compared','increases','unchanged','decreases')} for k,v in out['monotonicity'].items()})


def figure(out,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    by_id={c['id']:c for c in out['controls']}
    names=['relative2','relative4','relative4_weakTop']
    for offset,cid,color,label in [(-.18,'r1_l0.2_s0.5','#9babb7','Correct mean, local RMS 20%'),(.18,'r1.2_l0.2_s0.5','#146c94','Mean +20%, local RMS 20%')]:
        values=[by_id[cid]['effects'][n]['score'] for n in names]
        bars=axes[0].bar(np.arange(3)+offset,values,.36,color=color,label=label)
        axes[0].bar_label(bars,fmt='%.2f',fontsize=9,padding=2)
    axes[0].set(xticks=np.arange(3),xticklabels=['Quadratic','Quartic','Quartic + weak St'],ylabel='Candidate score',ylim=(0,80),title='Angular compensation: mean error increases, score may rise')
    axes[0].legend(fontsize=8)
    ratios=[1,1.2,1.5,2,3]
    for name,label,color in [('relative2','Quadratic sum','#146c94'),('relative4','Quartic sum','#698c42'),('Q_dbounded1_max_height','Max of height losses','#b44b43')]:
        values=[next(c for c in out['controls'] if c['scale']==2 and c['local']==.1 and c['ratio']==r)['effects'][name]['local_marginal_points'] for r in ratios]
        axes[1].plot(ratios,values,'o-',label=label,color=color)
    axes[1].set(xlabel='Annotation / reference mean height',ylabel='Marginal score drop from local RMS = 10%',title='Exact masking differs from reciprocal-score compression',ylim=(-.5,15))
    axes[1].legend(fontsize=8)
    fig.savefig(path,dpi=170)
    plt.close(fig)


if __name__=='__main__': main()
