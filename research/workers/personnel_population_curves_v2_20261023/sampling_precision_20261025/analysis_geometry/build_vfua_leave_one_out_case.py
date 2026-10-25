"""Explain an already registered exact N-1 margin; no extra endpoint evaluation."""
from __future__ import annotations
import argparse
import gzip
import io
import json
import os
from pathlib import Path
import pickle
import numpy as np
import pandas as pd
from population_paths import add_population_root_argument,resolve_population_root
from safe_io import install_safe_csv_writer
install_safe_csv_writer()

PID='VFuaQ6m2Qom-04__manual__fbe40a551f'
FOCAL_ABSENT=['W103','W113','W134']


def json_clean(x):
    if isinstance(x,dict):return {str(k):json_clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [json_clean(v) for v in x]
    if isinstance(x,np.generic):return json_clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x


def raw_floor(points):
    a=np.asarray(points,float)[1::2]
    r=1/np.tan(np.pi*(a[:,1]/512-.5));t=2*np.pi*(a[:,0]/1024-.5)
    return np.c_[r*np.sin(t),-r*np.cos(t)]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--study',required=True);ap.add_argument('--out',required=True);add_population_root_argument(ap);a=ap.parse_args()
    root=Path(a.study).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    base=resolve_population_root(root,a.population_root)
    design=pd.read_csv(root/'design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz')
    own=design[design.pool_id.eq(PID) & design.k.isin([34,35])].copy()
    assert len(own)==36 and own.team_key.nunique()==36
    wanted=set(own.team_key)
    snapshot=json.load(gzip.open(base/'inputs/INPUT_SNAPSHOT.json.gz','rt'))
    pool=next(p for p in snapshot['images'] if p['pool_id']==PID)
    workers={r['worker_id'] for r in pool['records']}
    byworker={r['worker_id']:r for r in pool['records']}
    old_cache=out/'OLD_EXACT_ENDPOINT_SCALARS.csv.gz'
    if old_cache.exists():old=pd.read_csv(old_cache,low_memory=False)
    else:
        frames=[]
        for d in pd.read_csv(base/'results/ENDPOINT_SCALARS.csv.gz',chunksize=25000,low_memory=False):
            q=d[d.team_key.isin(wanted)]
            if len(q):frames.append(q)
        old=pd.concat(frames,ignore_index=True);old.to_csv(old_cache,index=False)
    scalar={r['team_key']:r for r in old.to_dict('records')}
    geom=pickle.load(open(root/f'analysis_geometry/results/old_pool_geometry_cache/{PID}.pkl','rb'))
    geometry={k:geom[k].get('geometry') for k in wanted if k in geom}
    states={};pointers={};origin={k:'inherited_population_20261023' for k in scalar}
    for directory in [root/'new_endpoints',root/'engine/benchmark']:
        parts=directory/'parts'/PID
        for receipt_path in sorted(parts.glob('part_*.receipt.json')):
            receipt=json.loads(receipt_path.read_text())
            intersection=wanted & set(receipt['team_keys'])
            if not intersection:continue
            d=pd.read_csv(parts/receipt['scalar_file'],low_memory=False)
            scalar.update({r['team_key']:r for r in d[d.team_key.isin(wanted)].to_dict('records')})
            line_numbers={int(r['geometry_line_1based']):r['team_key'] for r in d[d.team_key.isin(wanted)].to_dict('records')}
            with gzip.open(parts/receipt['geometry_file'],'rt') as f:
                for number,line in enumerate(f,1):
                    if number not in line_numbers:continue
                    r=json.loads(line);key=r['team_key']
                    states[key]=r.get('full_state');geometry[key]=r.get('geometry');origin[key]='new_native_20261025'
                    pointers[key]=str((parts/receipt['geometry_file']).relative_to(root))+'#L'+str(number)
    absent_keys=wanted-scalar.keys()
    if absent_keys:
        (out/'PENDING_CASE.json').write_text(json.dumps(dict(missing_keys=sorted(absent_keys),requested=36,available=len(wanted&scalar.keys())),indent=2))
        raise SystemExit(f'Exact N-1 case not complete: {len(absent_keys)} keys pending')
    if (out/'PENDING_CASE.json').exists():(out/'PENDING_CASE.json').unlink()
    scalar_rows=[];groups=[];assignments=[];rings=[];georecords=[]
    for d in own.to_dict('records'):
        key=d['team_key'];r=scalar[key]
        members=str(d['member_workers']).split('|');absent='|'.join(sorted(workers-set(members)))
        record=dict(d,**{k:v for k,v in r.items() if k not in d})
        record.update(absent_worker=absent or 'FULL35',endpoint_source=origin[key],full_state_available=key in states,exact_probability=1/35 if int(d['k'])==34 else 1,geometry_state_pointer=pointers.get(key,'results/ENDPOINT_GEOMETRY.json.gz#team_key='+key))
        scalar_rows.append(record)
        georecords.append(dict(team_key=key,absent_worker=absent or 'FULL35',geometry=geometry.get(key)))
        state=states.get(key)
        if not state:continue
        selected=set((geometry.get(key) or {}).get('feature_ids') or [])
        for g in state.get('identity_groups',[]):
            center=np.asarray(g.get('center'),float)
            groups.append(dict(team_key=key,absent_worker=absent,feature_id=g['feature_id'],selected=g['feature_id'] in selected,
                support=g.get('support'),joint_support=g.get('joint_support'),top_support=g.get('top_support'),bottom_support=g.get('bottom_support'),
                minimum_support=state['minimum_support'],top_x=float(center[0,0]),top_y=float(center[0,1]),bottom_x=float(center[1,0]),bottom_y=float(center[1,1]),
                member_workers='|'.join(sorted({m['worker'] for m in g['members']})),member_object_ids='|'.join(str(m['id']) for m in g['members'])))
        for x in state.get('assignments',[]):
            assignments.append(dict(team_key=key,absent_worker=absent,worker_id=x['worker'],object_id=x['id'],feature_ids='|'.join(x['feature_ids'])))
        ring=state.get('ring_diagnostics') or {}
        for e in ring.get('edges',[]):
            rings.append(dict(team_key=key,absent_worker=absent,edge='|'.join(e['feature_ids']),direct_support=e.get('direct_support'),projected_support=e.get('projected_support'),direct_workers='|'.join(e.get('direct_workers',[])),projected_workers='|'.join(e.get('projected_workers',[]))))
    allrows=pd.DataFrame(scalar_rows)
    allrows.to_csv(out/'VFUA_35_LEAVE_ONE_OUT_AND_FULL.csv',index=False)
    pd.DataFrame(groups).to_csv(out/'VFUA_SAVED_GROUP_VOTES.csv',index=False)
    pd.DataFrame(assignments).to_csv(out/'VFUA_SAVED_RAW_ASSIGNMENTS.csv',index=False)
    pd.DataFrame(rings).to_csv(out/'VFUA_SAVED_CONNECTION_EDGES.csv',index=False)
    g=allrows[allrows.k.eq(34)]
    q=pd.to_numeric(g.B8L2,errors='coerce').dropna()
    outcome=g.groupby(['score_available','nodes'],dropna=False).agg(teams=('team_key','size'),q_mean=('B8L2','mean'),q_min=('B8L2','min'),q_max=('B8L2','max'),absent_workers=('absent_worker',lambda s:'|'.join(sorted(s)))).reset_index()
    outcome['probability']=outcome.teams/35;outcome.to_csv(out/'VFUA_EXACT_OUTCOME_COUNTS.csv',index=False)
    old_links=pd.read_csv(base/'results/PREFIX_TEAM_LINKS.csv.gz',low_memory=False)
    old_links=old_links[old_links.pool_id.eq(PID)&old_links.k.eq(34)&old_links.policy.eq('natural_random')].copy();old_links['batch']='old24'
    added=pd.read_csv(root/'design/NEW_PREFIX_TEAM_LINKS.csv.gz',low_memory=False,dtype={'seed':str,'master_seed':str})
    added=added[added.pool_id.eq(PID)&added.k.eq(34)&added.policy.eq('natural_random')].copy()
    added['batch']=added.batch.replace({'balanced_new24':'new24','focus_new48':'focus48'})
    sampled=pd.concat([old_links,added],ignore_index=True).merge(g[['team_key','B8L2','score_failure_nonpolicy','absent_worker','nodes']],on='team_key',validate='many_to_one')
    sampled.to_csv(out/'VFUA_N34_EXACT_SAMPLED_PATHS.csv',index=False)
    summaries=[]
    for name,batches in {'old24':['old24'],'new24':['new24'],'combined48':['old24','new24'],'focus48':['focus48'],'combined96':['old24','new24','focus48']}.items():
        x=sampled[sampled.batch.isin(batches)];qs=x.B8L2.dropna()
        summaries.append(dict(sample=name,paths=len(x),unique_teams=x.team_key.nunique(),scorable=len(qs),failures=int(x.score_failure_nonpolicy.sum()),failure_rate=x.score_failure_nonpolicy.mean(),q_mean=qs.mean(),q_mean_error_from_exact=qs.mean()-q.mean(),q_p10=qs.quantile(.1),q_sd_sample=qs.std(ddof=1),mean_mcse=qs.std(ddof=1)/np.sqrt(len(qs))))
    summaries.append(dict(sample='exact35_teams',paths=35,unique_teams=35,scorable=len(q),failures=int(g.score_failure_nonpolicy.sum()),failure_rate=g.score_failure_nonpolicy.mean(),q_mean=q.mean(),q_mean_error_from_exact=0.,q_p10=q.quantile(.1),q_sd_sample=q.std(ddof=0),mean_mcse=0.))
    pd.DataFrame(summaries).to_csv(out/'VFUA_N34_SAMPLING_COMPARISON.csv',index=False)
    from geometry_sampling_precision import distance_matrices,ustat
    geometry_rows={r['team_key']:dict(r,geometry=geometry.get(r['team_key'])) for r in g.to_dict('records')}
    exact_geometry=[]
    for metric,matrix in distance_matrices(g.team_key.tolist(),geometry_rows).items():
        summary,_=ustat(matrix,exact_population=True)
        exact_geometry.append(dict(pool_id=PID,k=34,metric=metric,finite_team_space=35,exact_mean=summary['mean'],exact_valid_teams=summary['valid_paths'],valid_fraction=summary['valid_paths']/35,exact_pair_denominator=summary['valid_pairs']))
    eg=pd.DataFrame(exact_geometry);eg.to_csv(out/'VFUA_N34_EXACT_GEOMETRY.csv',index=False)
    point_file=root/'analysis_geometry/results/completed_pool_checkpoints'/(PID+'.precision.csv.gz')
    if not point_file.exists():
        point_file=root/'analysis_geometry/results/GEOMETRY_PATH_PRECISION.csv.gz'
    if point_file.exists():
        sampled_geo=pd.read_csv(point_file);sampled_geo=sampled_geo[sampled_geo.pool_id.eq(PID)&sampled_geo.k.eq(34)].merge(eg[['metric','exact_mean','exact_valid_teams','valid_fraction']],on='metric',validate='many_to_one')
        sampled_geo['estimate_minus_exact']=sampled_geo['mean']-sampled_geo.exact_mean
        sampled_geo.to_csv(out/'VFUA_N34_GEOMETRY_SAMPLING.csv',index=False)
    # The illustrative absent workers were fixed after observing their saved
    # contrasting states, before waiting for the remaining exact margin. This
    # case is a mechanism illustration, not independent confirmatory selection.
    selected=allrows[allrows.absent_worker.isin(FOCAL_ABSENT+['FULL35'])]
    selected.to_csv(out/'VFUA_SELECTED_ENDPOINTS.csv',index=False)
    package=dict(pool_id=PID,meta=pool['meta'],reference=pool['reference'],selected_endpoints=[json_clean(r) for r in selected.to_dict('records')],geometries=[r for r in georecords if r['absent_worker'] in FOCAL_ABSENT+['FULL35']],selected_raw_answers={w:byworker[w] for w in FOCAL_ABSENT},selected_full_states={r['team_key']:states[r['team_key']] for r in selected.to_dict('records') if r['team_key'] in states})
    with gzip.open(out/'VFUA_MECHANISM_GEOMETRY.json.gz','wt') as f:json.dump(json_clean(package),f,ensure_ascii=False,separators=(',',':'))
    receipt=dict(pool_id=PID,exact_leave_one_out_teams=35,full_team=1,scorable=int(g.B8L2.notna().sum()),failures=int(g.score_failure_nonpolicy.sum()),q_mean=float(q.mean()),q_p10=float(q.quantile(.1)),q_population_sd=float(q.std(ddof=0)),q_min=float(q.min()),q_max=float(q.max()),full_team_scorable=bool(allrows[allrows.k.eq(35)].score_available.iloc[0]),full_state_rows=len(states),new_fusions_by_case_script=0)
    (out/'VFUA_CASE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    # Publication-ready exact-coordinate BEV; failed candidates are shown as
    # nodes only and never rendered as a valid closed consensus footprint.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(1,4,figsize=(15,4.5),constrained_layout=True)
    ref=np.asarray(pool['reference']['floor_xz_h']);rr=np.r_[ref,ref[:1]]
    for ax,who in zip(axes,FOCAL_ABSENT+['FULL35']):
        row=allrows[allrows.absent_worker.eq(who)].iloc[0];gg=geometry[row.team_key];floor=np.asarray(gg['footprint'])
        ax.fill(rr[:,0],rr[:,1],color='#f0f0f0',zorder=0);ax.plot(rr[:,0],rr[:,1],color='#333333',lw=1.7,label='Frozen reference')
        if who!='FULL35':
            raw=raw_floor(byworker[who]['points']);raw=np.r_[raw,raw[:1]];ax.plot(raw[:,0],raw[:,1],':',color='#7856a3',lw=1.2,alpha=.85,label='Absent worker raw answer')
        if row.complete_floor_evaluable:
            ff=np.r_[floor,floor[:1]];ax.plot(ff[:,0],ff[:,1],'-o',color='#d45d25',lw=2,ms=4,label='Consensus')
        else:ax.scatter(floor[:,0],floor[:,1],c='#bd3030',marker='x',s=55,label='Incomplete selected nodes')
        ax.scatter([0],[0],c='#267a9c',marker='^',s=35,label='Camera')
        label='Full N=35' if who=='FULL35' else 'N=34, absent '+who
        score=f'Q={row.B8L2:.2f}' if pd.notna(row.B8L2) else 'Q unavailable (failure)'
        ax.set_title(f'{label}\n{int(row.nodes)} nodes; {score}')
        ax.set_aspect('equal');ax.set_xlim(-2.25,2.85);ax.set_ylim(-2.7,1.0);ax.set_xlabel('x / camera height');ax.grid(alpha=.15)
    axes[0].set_ylabel('z / camera height');handles,labels=axes[0].get_legend_handles_labels();h2,l2=axes[-1].get_legend_handles_labels()
    allleg=dict(zip(labels+ l2,handles+h2));fig.legend(allleg.values(),allleg.keys(),loc='outside lower center',ncol=3,frameon=False)
    fig.suptitle('VFuaQ6m2Qom-04: one absent member changes which 17-vote group survives',fontsize=14)
    png=out/'VFUA_LEAVE_ONE_OUT_BEV.png';pdf=out/'VFUA_LEAVE_ONE_OUT_BEV.pdf'
    png_tmp=out/'VFUA_LEAVE_ONE_OUT_BEV.tmp.png';pdf_tmp=out/'VFUA_LEAVE_ONE_OUT_BEV.tmp.pdf'
    png_buf=io.BytesIO();pdf_buf=io.BytesIO()
    fig.savefig(png_buf,format='png',dpi=180);fig.savefig(pdf_buf,format='pdf');plt.close(fig)
    for path,body in [(png_tmp,png_buf.getvalue()),(pdf_tmp,pdf_buf.getvalue())]:
        with path.open('wb') as stream:
            n=stream.write(body);stream.flush();os.fsync(stream.fileno())
        assert n==len(body) and path.read_bytes()==body
    from PIL import Image
    with Image.open(png_tmp) as im:im.load()
    png_tmp.replace(png);pdf_tmp.replace(pdf)
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':main()
