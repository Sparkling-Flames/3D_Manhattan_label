"""Finite-panel geometry effects repeated in directly adopted room views.

Enumerates every within-panel unordered pair. Direction is increasing high-class
count, then increasing selection mask. It consumes native endpoint checkpoints;
no additional fusion or quality scoring. Panel summary checkpoints permit an
incremental run while native endpoints are still being computed.
"""
from __future__ import annotations
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import argparse
from collections import Counter, OrderedDict
import gzip
import itertools
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd
from geometric_effects import prepare, compare
from new_team_engine import save, save_csv, gs

META=['panel_id','pair_key','building','groups','image_a','image_b','pool_id_a','pool_id_b',
      'ordinary_comparable','relation_tier','scope_comparable','layer_a','layer_b',
      'difficulty_a','difficulty_b','method','selected_family','class_lo','class_hi',
      'n','m_max','k_selected','candidate_n','known_common_n','replicate','core','candidates']
FIELDS=['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bottom_angular_mean_deg',
        'top_angular_mean_deg','angle_deg','signed_height_change_mean_h']


def finite(x):
    return isinstance(x,(int,float,np.integer,np.floating)) and np.isfinite(x)


def delta(a,b,key):
    x,y=a.get(key),b.get(key)
    return float(y-x) if finite(x) and finite(y) else None


def corr(a,b):
    if len(a)<3 or np.std(a)==0 or np.std(b)==0:return None
    return float(np.corrcoef(a,b)[0,1])


class PoolCache:
    def __init__(self,folder,size=4):self.folder=Path(folder);self.size=size;self.data=OrderedDict()
    def get(self,pid):
        p=self.folder/(pid+'.json.gz')
        if not p.exists():return None
        stamp=(p.stat().st_mtime_ns,p.stat().st_size)
        if pid in self.data and self.data[pid][0]==stamp:
            self.data.move_to_end(pid);return self.data[pid][1]
        try:obj=gs.read(p)
        except (EOFError,OSError,json.JSONDecodeError):return None
        rows={r['team_key']:r for r in obj['teams']}
        self.data[pid]=(stamp,rows);self.data.move_to_end(pid)
        while len(self.data)>self.size:self.data.popitem(last=False)
        return rows


def new_acc():
    return dict(counts=Counter(),status_a=Counter(),status_b=Counter(),status_joint=Counter(),
        values={k+suffix:[] for k in FIELDS for suffix in ['_a','_b']},
        joint_bev_a=[],joint_bev_b=[],joint_q_a=[],joint_q_b=[],
        q_abs_effect_difference=[],geom_abs_effect_difference=[],
        geom_q_a=[],qmag_a=[],geom_q_b=[],qmag_b=[])


def summarise_acc(z):
    out=dict(z['counts'])
    for k in ['attempted','valid_distance_a_n','valid_distance_b_n','joint_valid_distance_n',
              'same_count_a_n','same_count_b_n','both_same_count_n','different_count_a_n','different_count_b_n',
              'complete_a_comparison_n','complete_b_comparison_n','both_complete_comparisons_n',
              'exact_unchanged_a_n','exact_unchanged_b_n','exact_unchanged_both_n',
              'cyclic_unchanged_a_n','cyclic_unchanged_b_n','cyclic_unchanged_both_n',
              'position_small_both_n','position_a_large_only_n','position_b_large_only_n','position_large_both_n',
              'q_joint_n','same_nonzero_structure_opposite_q_n']:
        out.setdefault(k,0)
    for view in ['a','b','joint']:
        out['status_'+view+'_json']=json.dumps(z['status_'+view],sort_keys=True,separators=(',',':'))
    for key,values in z['values'].items():
        out[key+'_n']=len(values)
        out[key+'_mean']=float(np.mean(values)) if values else None
        out[key+'_p90']=float(np.quantile(values,.9)) if values else None
    for key in ['q_abs_effect_difference','geom_abs_effect_difference']:
        v=z[key];out[key+'_n']=len(v);out[key+'_mean']=float(np.mean(v)) if v else None
        out[key+'_p90']=float(np.quantile(v,.9)) if v else None
    out['bev_effect_crossview_corr']=corr(z['joint_bev_a'],z['joint_bev_b'])
    out['q_effect_crossview_corr']=corr(z['joint_q_a'],z['joint_q_b'])
    out['bev_vs_absolute_q_effect_corr_a']=corr(z['geom_q_a'],z['qmag_a'])
    out['bev_vs_absolute_q_effect_corr_b']=corr(z['geom_q_b'],z['qmag_b'])
    return out


def panel_compute(meta,links,ra,rb,pa,pb):
    ordered=sorted(links,key=lambda x:(int(x['hi_selected']),int(x['selected_mask'])))
    accum={};candidates=[]
    for left,right in itertools.combinations(ordered,2):
        m=(int(left['selected_mask'])^int(right['selected_mask'])).bit_count()//2
        r=int(right['hi_selected'])-int(left['hi_selected'])
        key=(m,r);z=accum.setdefault(key,new_acc());c=z['counts'];c['attempted']+=1
        a0,a1=ra[left['team_key_a']],ra[right['team_key_a']]
        b0,b1=rb[left['team_key_b']],rb[right['team_key_b']]
        ga=compare(pa[left['team_key_a']],pa[right['team_key_a']])
        gb=compare(pb[left['team_key_b']],pb[right['team_key_b']])
        z['status_a'][ga['status']]+=1;z['status_b'][gb['status']]+=1
        z['status_joint'][ga['status']+'||'+gb['status']]+=1
        va=ga['status']=='unique_cyclic_candidate';vb=gb['status']=='unique_cyclic_candidate'
        for suffix,g,valid in [('a',ga,va),('b',gb,vb)]:
            c['same_count_'+suffix+'_n']+=bool(g['same_count'])
            c['different_count_'+suffix+'_n']+=g['status']=='different_corner_count'
            c['complete_'+suffix+'_comparison_n']+=bool(g['complete'])
            if valid:
                c['valid_distance_'+suffix+'_n']+=1
                c['exact_unchanged_'+suffix+'_n']+=g['exact_geometry_equal']
                c['cyclic_unchanged_'+suffix+'_n']+=g['cyclic_geometry_equal']
                for f in FIELDS:z['values'][f+'_'+suffix].append(g[f])
        c['both_same_count_n']+=bool(ga['same_count'] and gb['same_count'])
        c['both_complete_comparisons_n']+=bool(ga['complete'] and gb['complete'])
        if va and vb:
            c['joint_valid_distance_n']+=1
            c['exact_unchanged_both_n']+=bool(ga['exact_geometry_equal'] and gb['exact_geometry_equal'])
            c['cyclic_unchanged_both_n']+=bool(ga['cyclic_geometry_equal'] and gb['cyclic_geometry_equal'])
            da,db=ga['bev_mean_h'],gb['bev_mean_h']
            z['joint_bev_a'].append(da);z['joint_bev_b'].append(db)
            z['geom_abs_effect_difference'].append(abs(db-da))
            small_a,small_b=da<=.02,db<=.02
            if small_a and small_b:state='position_small_both_n'
            elif not small_a and small_b:state='position_a_large_only_n'
            elif small_a and not small_b:state='position_b_large_only_n'
            else:state='position_large_both_n'
            c[state]+=1
        qa,qb=delta(a0,a1,'B8L2'),delta(b0,b1,'B8L2')
        if qa is not None and qb is not None:
            c['q_joint_n']+=1;z['joint_q_a'].append(qa);z['joint_q_b'].append(qb)
            z['q_abs_effect_difference'].append(abs(qb-qa))
            if va:z['geom_q_a'].append(ga['bev_mean_h']);z['qmag_a'].append(abs(qa))
            if vb:z['geom_q_b'].append(gb['bev_mean_h']);z['qmag_b'].append(abs(qb))
            skeys=['nodes','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
            sa=tuple(delta(a0,a1,f) for f in skeys);sb=tuple(delta(b0,b1,f) for f in skeys)
            same_structure=all(x is not None for x in sa+sb) and sa==sb and any(x!=0 for x in sa)
            if same_structure and qa*qb<0 and min(abs(qa),abs(qb))>2:
                c['same_nonzero_structure_opposite_q_n']+=1
                candidate={k:meta[k] for k in META}
                candidate.update(actual_m=m,net_high_count_change=r,source_before=left['team_key_a'],source_after=right['team_key_a'],
                    target_before=left['team_key_b'],target_after=right['team_key_b'],
                    before_members=left['member_set_key'],after_members=right['member_set_key'],
                    before_mask=int(left['selected_mask']),after_mask=int(right['selected_mask']),
                    before_hi=int(left['hi_selected']),after_hi=int(right['hi_selected']),
                    source_q_delta=qa,target_q_delta=qb,
                    source_q_before=a0.get('B8L2'),source_q_after=a1.get('B8L2'),
                    target_q_before=b0.get('B8L2'),target_q_after=b1.get('B8L2'),
                    structure_delta_json=json.dumps(dict(zip(skeys,sa)),separators=(',',':')),
                    source_geometry_status=ga['status'],target_geometry_status=gb['status'],
                    source_bev_mean_h=ga.get('bev_mean_h'),target_bev_mean_h=gb.get('bev_mean_h'),
                    candidate_strength=min(abs(qa),abs(qb)),selection_role='mechanism_candidate_not_effect_denominator')
                for f in ['D10','iou_2d','dir','S_bottom_deg','Hmean','Hcenter','diag_corner_recall_05','diag_wall_coverage_05']:
                    candidate['source_delta_'+f]=delta(a0,a1,f);candidate['target_delta_'+f]=delta(b0,b1,f)
                candidates.append(candidate)
    summary=[dict({k:meta[k] for k in META},actual_m=m,net_high_count_change=r,**summarise_acc(z)) for (m,r),z in sorted(accum.items())]
    candidates=sorted(candidates,key=lambda x:x['candidate_strength'],reverse=True)[:4]
    return dict(panel_id=meta['panel_id'],summary=summary,candidates=candidates,
        attempted=sum(z['counts']['attempted'] for z in accum.values()))


def aggregate(out,expected):
    pieces=[];cases=[];done=set();attempted=0
    for p in sorted((out/'checkpoints').glob('*.json.gz')):
        obj=gs.read(p)
        for panel in obj['panels']:
            assert panel['panel_id'] not in done;done.add(panel['panel_id'])
            pieces.extend(panel['summary']);cases.extend(panel['candidates']);attempted+=panel['attempted']
    summary=pd.DataFrame(pieces)
    save_csv(out/'PANEL_M_R_GEOMETRY_SUMMARY.csv.gz',summary)
    if cases:
        c=pd.DataFrame(cases).sort_values('candidate_strength',ascending=False)
        # A small varied shortlist, not duplicated versions of one image event.
        c=c.drop_duplicates(['source_before','source_after','target_before','target_after'])
        c=c.groupby('pair_key',sort=False,group_keys=False).head(5).head(120)
        save_csv(out/'SAME_STRUCTURE_OPPOSITE_Q_CANDIDATES.csv',c)
    receipt=dict(status='complete' if len(done)==expected else 'partial',expected_panels=expected,
        completed_panels=len(done),summary_rows=len(summary),attempted_exact_adjustments=attempted,
        unique_pairs=int(summary.pair_key.nunique()) if len(summary) else 0,
        position_tolerance_h=.02,quality_case_threshold_points=2.,new_fusions=0,new_scores=0,
        orientation='increasing hi_selected, then increasing selected_mask',
        pair_geometry='within each image only; cyclic corresponding corner distance v2')
    save(out/'GEOMETRY_TRANSFER_RECEIPT.json',receipt)
    return done,receipt


def main():
    p=argparse.ArgumentParser();p.add_argument('--design',required=True);p.add_argument('--native',required=True);p.add_argument('--output',required=True);p.add_argument('--watch',action='store_true');a=p.parse_args()
    design,native,out=map(Path,[a.design,a.native,a.output]);out.mkdir(parents=True,exist_ok=True);(out/'checkpoints').mkdir(exist_ok=True)
    panels=pd.read_csv(design/'PANELS.csv',keep_default_na=False)
    links=pd.read_csv(design/'PANEL_TEAM_LINKS.csv.gz',keep_default_na=False)
    linkmap={pid:g.to_dict('records') for pid,g in links.groupby('panel_id',sort=False)}
    cache=PoolCache(native/'pools',4);start=time.monotonic()
    while True:
        done,receipt=aggregate(out,len(panels));new=0
        if len(done)==len(panels):break
        for pair,group in panels.groupby('pair_key',sort=True):
            todo=[r for r in group.to_dict('records') if r['panel_id'] not in done]
            if not todo:continue
            ra=cache.get(todo[0]['pool_id_a']);rb=cache.get(todo[0]['pool_id_b'])
            if ra is None or rb is None:continue
            ready=[r for r in todo if all(x['team_key_a'] in ra and x['team_key_b'] in rb for x in linkmap[r['panel_id']])]
            if not ready:continue
            # Project once per endpoint used by these ready panels.
            need_a={x['team_key_a'] for r in ready for x in linkmap[r['panel_id']]}
            need_b={x['team_key_b'] for r in ready for x in linkmap[r['panel_id']]}
            pa={k:prepare(ra[k]) for k in need_a};pb={k:prepare(rb[k]) for k in need_b}
            path=out/'checkpoints'/(gs.digest(pair)[:20]+'.json.gz')
            prior=gs.read(path)['panels'] if path.exists() else []
            added=[];t=time.monotonic()
            for meta in ready:
                added.append(panel_compute(meta,linkmap[meta['panel_id']],ra,rb,pa,pb))
            save(path,dict(pair_key=pair,panels=prior+added));new+=len(added);done.update(x['panel_id'] for x in added)
            print(json.dumps(dict(pair=pair,new_panels=len(added),total_done=len(done),pair_seconds=time.monotonic()-t,wall_seconds=time.monotonic()-start)),flush=True)
        done,receipt=aggregate(out,len(panels));print(json.dumps(receipt),flush=True)
        if len(done)==len(panels) or not a.watch:break
        if not new:time.sleep(10)
    save(out/'EXECUTION.json',dict(wall_seconds=time.monotonic()-start,**receipt))


if __name__=='__main__':main()
