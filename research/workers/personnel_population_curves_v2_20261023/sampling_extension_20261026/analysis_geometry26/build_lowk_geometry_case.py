"""One observed low-k sampling-change case, using saved raw answers and geometry.

Selection, when requested, is the largest absolute old48/new208 V_floor change
among comparable ordinary Manual k=3..10, N>=30. It is explanatory selection,
not an independent confirmation. No new fusion or altered eligibility.
"""
from __future__ import annotations
import argparse,gzip,io,json,math,os,pickle
from pathlib import Path
import numpy as np
import pandas as pd
from geometry_extension import COHORTS,META,read_new_pool,registered_links,save_json
from safe_io import install_safe_csv_writer,atomic_bytes
install_safe_csv_writer()

def read_quality(study,pid,wanted):
    keep=['team_key','pool_id','k','B8L2','D10','score_status','geometry_status','nodes','complete_evaluable',
          'complete_floor_evaluable','member_workers','member_object_ids','reference_id','reference_version',
          'iou_2d','S_bottom_deg','dir','Hmean','Hcenter','minimum_support','height_mean_h','floor_turn5_n']
    paths=[study/'inputs_cache26/ENDPOINT_SCALARS_20261023.csv.gz',study/'inputs_cache26/precision25/NEW_ENDPOINT_SCALARS.csv.gz']
    paths+=sorted((study/'new_endpoints26/stage1/parts'/pid).glob('part_*.scalars.csv.gz'))
    paths+=sorted((study/'new_endpoints26/stage2/parts'/pid).glob('part_*.scalars.csv.gz'))
    frames=[]
    for path in paths:
        for d in pd.read_csv(path,usecols=lambda c:c in keep,chunksize=40000,low_memory=False):
            x=d[d.team_key.isin(wanted)].copy()
            if len(x):x['scalar_source']=str(path.relative_to(study));frames.append(x)
    result=pd.concat(frames,ignore_index=True)
    assert set(result.team_key)==wanted and not result.team_key.duplicated().any()
    return result

def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not np.isfinite(x):return None
    return x

def main(study,pid,k,select_largest):
    root=study/'analysis_geometry26';stats=pd.read_csv(root/'results_stage2/GEOMETRY_PATH_PRECISION.csv.gz')
    selection={}
    if select_largest:
        old=stats[stats.cohort.eq('old48')&stats.metric.eq('V_floor')&stats.k.between(3,10)&stats.pool_n.ge(30)&stats.layer.eq('ordinary_manual')]
        new=stats[stats.cohort.eq('new208')&stats.metric.eq('V_floor')]
        x=old.merge(new,on=['pool_id','k','metric'],suffixes=('_old','_new'))
        x['delta']=x['mean_new']-x['mean_old'];x=x[x.delta.notna()].copy();x['abs_delta']=x.delta.abs()
        x=x.sort_values(['abs_delta','pool_id','k'],ascending=[False,True,True])
        chosen=x.iloc[0];pid=str(chosen.pool_id);k=int(chosen.k)
        selection=dict(rule='largest absolute old48/new208 V_floor change; ordinary Manual; N>=30; k3..10; both point estimates available',
            candidate_pool_k=len(x),candidate_images=x.pool_id.nunique(),rank=1,actual_delta=float(chosen.delta),
            interpretation='exploratory mechanism/example selection using observed outcomes; not validation')
        x.to_csv(root/'LOW_K_CASE_SELECTION_SCAN.csv.gz',index=False)
    if pid is None or k is None:raise ValueError('provide --pool and --k, or --select-largest')
    out=root/'low_k_cases'/f'{pid}__k{k}';out.mkdir(parents=True,exist_ok=True)
    with (root/'cache/baseline'/(pid+'.pkl')).open('rb') as f:rows=pickle.load(f)
    additional,parts=read_new_pool(study,pid,2);assert not set(rows)&set(additional);rows.update(additional)
    oldlinks=pd.read_csv(root/'BASELINE_NATURAL_LINKS.csv.gz');links=pd.concat([oldlinks[oldlinks.pool_id.eq(pid)],registered_links(study,[pid],2)],ignore_index=True)
    own=links[links.k.eq(k)].copy();quality=read_quality(study,pid,set(own.team_key))
    if 'k' in quality:
        assert quality.k.dropna().eq(k).all()
        quality=quality.drop(columns='k')
    own=own.merge(quality,on=['pool_id','team_key'],validate='many_to_one')
    selected=[];summary=[]
    for cohort in ['old48','stage1_104','stage2_104','new208','pooled256']:
        d=own[own.batch.isin(COHORTS[cohort])];q=d[d.B8L2.notna()].sort_values(['B8L2','team_key','path_id'])
        summary.append(dict(pool_id=pid,k=k,cohort=cohort,attempted=len(d),scorable=len(q),
            Q_mean=q.B8L2.mean(),Q_P10_linear=q.B8L2.quantile(.1),Q_P10_inverse_cdf=float(np.quantile(q.B8L2,.1,method='inverted_cdf')) if len(q) else np.nan,
            Q_SD=q.B8L2.std(ddof=1),D10_mean=q.D10.mean(),below_four_count=int(d.nodes.lt(4).sum()),
            quality_missing_count=int(d.B8L2.isna().sum()),
            score_status_counts_json=json.dumps(d.score_status.fillna('missing_source_status').value_counts().to_dict(),ensure_ascii=False),
            geometry_status_counts_json=json.dumps(d.geometry_status.fillna('missing_source_status').value_counts().to_dict(),ensure_ascii=False)))
        if cohort in ['old48','new208'] and len(q):
            levels=[.1] if cohort=='old48' else [.1,.5]
            for level in levels:
                r=q.iloc[max(0,math.ceil(level*len(q))-1)].to_dict();r.update(example_role=f'{cohort}_inverseCDF_{level:g}',quantile_level=level)
                selected.append(r)
    with gzip.open(study/'repo/research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz','rt') as f:snapshot=json.load(f)
    pool=next(p for p in snapshot['images'] if p['pool_id']==pid);raw={r['worker_id']:r for r in pool['records']}
    for r in selected:
        key=r['team_key'];r['geometry']=rows[key].get('geometry');r['raw_answers']=[raw[w] for w in r['member_workers'].split('|')]
        r['geometry_complete_eligible']=rows[key]['complete_floor_evaluable']
    own.to_csv(out/'CASE_ALL_PATHS_AND_ENDPOINTS.csv.gz',index=False)
    pd.DataFrame(summary).to_csv(out/'CASE_QUALITY_AND_SUPPORT.csv',index=False)
    precision=stats[stats.pool_id.eq(pid)];precision.to_csv(out/'CASE_FULL_GEOMETRY_CURVE.csv.gz',index=False)
    pd.DataFrame([{key:value for key,value in r.items() if key not in ['geometry','raw_answers']} for r in selected]).to_csv(out/'CASE_SELECTED_ACTUAL_TEAMS.csv',index=False)
    package=clean(dict(pool_id=pid,k=k,meta=pool['meta'],reference=pool['reference'],selection=selection,selected_endpoints=selected))
    atomic_bytes(out/'CASE_RAW_FUSION_REFERENCE.json.gz',gzip.compress(json.dumps(package,ensure_ascii=False,allow_nan=False).encode(),mtime=0))
    save_json(out/'CASE_RECEIPT.json',dict(pool_id=pid,k=k,selection=selection,source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        actual_paths=len(own),distinct_teams=own.team_key.nunique(),selected_endpoints=len(selected),new_fusions=0,
        input_native_parts_read=parts,presentation_selection='actual empirical inverse-CDF endpoints; no interpolated geometry'))
    render(out,package,own,precision)
    print(out,flush=True)

def raw_floor(points):
    bottom=np.asarray(points,float)[1::2];r=1/np.tan(np.pi*(bottom[:,1]/512-.5));t=2*np.pi*(bottom[:,0]/1024-.5)
    return np.c_[r*np.sin(t),-r*np.cos(t)]

def render(out,package,paths,precision):
    os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_geometry_matplotlib26')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    root=out.parents[1];font=root.parent/'assets/NotoSansCJKsc-Regular.otf'
    if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(2,3,figsize=(12.5,8.0),constrained_layout=True)
    colors={'old48':'#66717e','new208':'#247ba0','pooled256':'#28784b'}
    labels={'old48':'原48','new208':'独立新208','pooled256':'主256'}
    for cohort,color in colors.items():
        d=precision[precision.cohort.eq(cohort)&precision.metric.eq('V_floor')].sort_values('k')
        axes[0,0].plot(d.k,d['mean'],color=color,label=labels[cohort],lw=1.7)
        x=paths[paths.batch.isin(COHORTS[cohort])].B8L2.dropna().sort_values().to_numpy()
        if len(x):axes[0,1].step(np.r_[0,x,100],np.r_[0,np.arange(1,len(x)+1)/len(x),1],where='post',color=color,lw=1.7,label=labels[cohort])
    axes[0,0].axvline(package['k'],ls=':',color='#333333');axes[0,0].set_title('该池完整几何波动曲线',loc='left');axes[0,0].set_ylabel('V_floor');axes[0,0].set_xlabel('人数 k');axes[0,0].legend(frameon=False,fontsize=9)
    axes[0,1].axhline(.1,ls=':',color='#777777');axes[0,1].set_title(f"{package['k']} 人的可评分 Q 分布",loc='left');axes[0,1].set_ylabel('条件累计概率');axes[0,1].set_xlabel('B8L2 Q')
    q=pd.read_csv(out/'CASE_QUALITY_AND_SUPPORT.csv');lines=['同一固定人员池 / 同一冻结参考','完整路径抽样，重复队保留频数','']
    for cohort in colors:
        r=q[q.cohort.eq(cohort)].iloc[0];lines.append(f"{labels[cohort]}：{int(r.scorable)}/{int(r.attempted)} 可评分\n均Q {r.Q_mean:.2f}；linear P10 {r.Q_P10_linear:.2f}")
    axes[0,2].axis('off');axes[0,2].text(0,.95,'\n'.join(lines),va='top',fontsize=11)
    reference=np.asarray(package['reference']['floor_xz_h'],float);rr=np.r_[reference,reference[:1]]
    allcoords=[reference]
    for r in package['selected_endpoints']:
        floor=(r.get('geometry') or {}).get('footprint')
        if floor:allcoords.append(np.asarray(floor))
    points=np.concatenate(allcoords);lo=points.min(axis=0);hi=points.max(axis=0);pad=.08*max((hi-lo).max(),1)
    for ax,r in zip(axes[1],package['selected_endpoints']):
        ax.fill(rr[:,0],rr[:,1],color='#eeeeee');ax.plot(rr[:,0],rr[:,1],color='#333333',lw=2,label='固定参考')
        for i,answer in enumerate(r['raw_answers']):
            xy=raw_floor(answer['points']);xy=np.r_[xy,xy[:1]];ax.plot(xy[:,0],xy[:,1],color='#99a6b3',lw=.9,alpha=.7,label='成员原答' if i==0 else None)
        xy=np.asarray(r['geometry']['footprint']);xy=np.r_[xy,xy[:1]]
        ax.plot(xy[:,0],xy[:,1],color='#c64c38',lw=2.2,marker='o',ms=3,label='实际融合')
        label='原48的低尾实际队' if r['example_role'].startswith('old48') else '新208的低尾实际队' if r['quantile_level']==.1 else '新208的中位实际队'
        ax.set_title(f"{label}\nQ={r['B8L2']:.2f}；节点={int(r['nodes'])}",loc='left',fontsize=10)
        ax.set_aspect('equal');ax.set_xlim(lo[0]-pad,hi[0]+pad);ax.set_ylim(lo[1]-pad,hi[1]+pad);ax.set_xlabel('x / 相机高度');ax.set_ylabel('z / 相机高度')
        ax.text(.02,.01,r['member_workers'],transform=ax.transAxes,fontsize=7,ha='left',va='bottom',wrap=True)
    if package['selected_endpoints']:axes[1,0].legend(frameon=False,fontsize=8)
    for ax in axes.ravel():ax.spines[['top','right']].set_visible(False)
    fig.suptitle(package['meta']['image']+f"：低人数 k={package['k']} 的新旧抽样与实际几何",fontsize=14)
    for ext in ['png','pdf']:
        memory=io.BytesIO();fig.savefig(memory,format=ext,dpi=190);atomic_bytes(out/('CASE_CURVE_Q_RAW_FUSION_BEV.'+ext),memory.getvalue())
    plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);p.add_argument('--pool');p.add_argument('--k',type=int);p.add_argument('--select-largest',action='store_true');a=p.parse_args();main(a.study.resolve(),a.pool,a.k,a.select_largest)
