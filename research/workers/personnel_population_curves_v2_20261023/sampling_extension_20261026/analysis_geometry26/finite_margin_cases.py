"""New registered path frequencies against two already enumerated N-1 catalogues.

No new endpoint, fusion, image qualification or class is created. Exact cached
teams bind the new path design, retaining all repeated draws and their weight.
"""
from __future__ import annotations
import argparse,gzip,json,pickle
from pathlib import Path
import numpy as np
import pandas as pd
from geometry_extension import COHORTS,distance_matrices,ustat,save_json,file_sha,registered_links
from safe_io import install_safe_csv_writer,atomic_bytes
install_safe_csv_writer()

CASES=['wc2JMjhGNzB-46__manual__ddafdd7484','VFuaQ6m2Qom-04__manual__fbe40a551f','rPc6DW4iMge-06__manual__34216003a1']

def describe(q,exact=False):
    q=np.asarray(q,float);q=q[np.isfinite(q)]
    return dict(valid_quality=len(q),mean_Q=float(np.mean(q)) if len(q) else np.nan,
        P10_linear=float(np.quantile(q,.1,method='linear')) if len(q) else np.nan,
        P10_inverse_cdf=float(np.quantile(q,.1,method='inverted_cdf')) if len(q) else np.nan,
        SD_Q=float(np.std(q,ddof=0 if exact else 1)) if len(q)>(0 if exact else 1) else np.nan,
        mean_Q_mcse=0. if exact else float(np.std(q,ddof=1)/np.sqrt(len(q))) if len(q)>1 else np.nan,
        mean_Q_mcse_method='exact finite distribution' if exact else 'sample SD / sqrt(valid Q paths); conditional valid count',
        SD_Q_denominator='valid finite teams M' if exact else 'valid sampled paths q-1')

def execute(study):
    out=study/'analysis_geometry26/finite_margin_cases';out.mkdir(parents=True,exist_ok=True)
    prior=study/'prior_recovered/research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025'
    prior_exact=prior/'new_endpoints/EXACT_MARGINAL_VALUES.csv.gz'
    source=pd.read_csv(prior_exact,low_memory=False)
    source=source[source.pool_id.isin(CASES)&source.k.eq(source.pool_n-1)].copy()
    old=pd.read_csv(study/'analysis_geometry26/BASELINE_NATURAL_LINKS.csv.gz')
    newpath=study/'design26/REGISTRATION_RECEIPT.json'
    new=registered_links(study,CASES,2)
    links=pd.concat([old,new[['pool_id','path_id','k','team_key','batch']]],ignore_index=True)
    links=links[links.pool_id.isin(CASES)].copy()
    expected_new=links[links.batch.isin(['extension_stage1_104','extension_stage2_104'])].groupby(['pool_id','batch']).path_id.nunique()
    assert len(expected_new)==len(CASES)*2 and expected_new.eq(104).all()
    order_paths=[study/'repo/research/workers/personnel_population_curves_v2_20261023/design/EXACT_ORDER_DESIGN.csv.gz',
        prior/'design/NEW_EXACT_ORDER_DESIGN.csv.gz',study/'design26/NEW_EXACT_ORDER_DESIGN.csv.gz']
    order_frames=[]
    for source_index,path in enumerate(order_paths):
        d=pd.read_csv(path,low_memory=False,dtype={'seed':'string','master_seed':'string'})
        d=d[d.pool_id.isin(CASES)&d.policy.eq('natural_random')].copy()
        if source_index==0:d['batch']='old24'
        if source_index==1:d['batch']=d.batch.replace({'balanced_new24':'prior_new24','focus_new48':'prior_focus48'})
        d['order_source']=str(path.relative_to(study))
        keep=['pool_id','image','path_id','base_path_id','pool_n','policy','batch','replicate','new_index','seed','master_seed',
            'seed_rule','worker_order','pool_input_sha256','order_source']
        order_frames.append(d[[x for x in keep if x in d]])
    orders=pd.concat(order_frames,ignore_index=True)
    assert not orders.path_id.duplicated().any()
    assert orders[orders.batch.isin(['extension_stage1_104','extension_stage2_104'])].path_id.nunique()==len(CASES)*208
    orders.to_csv(out/'EXACT_REGISTERED_ORDERS_AND_SEEDS.csv.gz',index=False)
    teams=[];paths=[];summaries=[];geos=[];outcomes=[];geometry_package=[]
    snapshot_path=study/'repo/research/workers/personnel_population_curves_v2_20261023/inputs/INPUT_SNAPSHOT.json.gz'
    with gzip.open(snapshot_path,'rt') as f:snapshot=json.load(f)
    pools={p['pool_id']:p for p in snapshot['images'] if p['pool_id'] in CASES}
    for pid in CASES:
        exact=source[source.pool_id.eq(pid)].copy()
        N=int(exact.pool_n.iloc[0]);k=N-1
        assert len(exact)==N and not exact.team_key.duplicated().any()
        pool_members=set('|'.join(exact.member_workers).split('|'))
        exact['absent_worker']=['|'.join(sorted(pool_members-set(s.split('|')))) for s in exact.member_workers]
        assert exact.absent_worker.nunique()==N
        exact['exact_natural_probability']=1/N
        validq=exact.B8L2.dropna().sort_values().to_numpy()
        gaps=np.diff(validq);threshold=float((validq[np.argmax(gaps)]+validq[np.argmax(gaps)+1])/2)
        # This static exact-catalogue gap summarizes output outcomes, not people.
        exact['low_score_mode']=exact.B8L2.lt(threshold)&exact.B8L2.notna()
        with (study/'analysis_geometry26/cache/baseline'/(pid+'.pkl')).open('rb') as f:rows=pickle.load(f)
        assert set(exact.team_key)<=set(rows)
        geometry_package.append(dict(pool_id=pid,image=exact.image.iloc[0],image_id=exact.image_id.iloc[0],pool_n=N,k=k,
            reference=pools[pid]['reference'],reference_id=exact.reference_id.iloc[0],
            teams=[dict(team_key=r.team_key,absent_worker=r.absent_worker,member_workers=r.member_workers,
                member_object_ids=r.member_object_ids,complete_floor_evaluable=rows[r.team_key]['complete_floor_evaluable'],
                B8L2=None if pd.isna(r.B8L2) else float(r.B8L2),D10=None if pd.isna(r.D10) else float(r.D10),
                nodes=int(r.nodes),low_score_mode=bool(r.low_score_mode),geometry=rows[r.team_key].get('geometry'),
                height_mean_h=rows[r.team_key].get('height_mean_h'),
                floor_turn5_n=rows[r.team_key].get('floor_turn5_n')) for r in exact.itertuples()]))
        exact['outcome_mode']=np.where(exact.B8L2.isna(),'unscorable',np.where(exact.low_score_mode,'lower_score_mode','upper_score_mode'))
        for (nodes,status,mode),group in exact.groupby(['nodes','score_status','outcome_mode']):
            record=dict(pool_id=pid,image=exact.image.iloc[0],k=k,nodes=nodes,score_status=status,outcome_mode=mode,
                finite_teams=len(group),exact_probability=len(group)/N,absent_workers='|'.join(sorted(group.absent_worker)))
            for field in ['B8L2','D10','iou_2d','S_bottom_deg','dir','height_mean_h','B8_floor_block','B8_direction_block','B8_height_block','floor_turn5_n']:
                record[field+'_mean']=group[field].mean()
            outcomes.append(record)
        eg,_=distance_matrices(exact.team_key.tolist(),rows)
        full=links[links.pool_id.eq(pid)&links.k.eq(k)].copy()
        full=full.merge(exact,on=['pool_id','k','team_key'],validate='many_to_one',how='left')
        assert full.member_workers.notna().all()
        assert not full.duplicated(['path_id','k']).any()
        lookup=orders.set_index('path_id').worker_order.to_dict()
        for r in full.itertuples():assert set(lookup[r.path_id].split('|')[:k])==set(r.member_workers.split('|'))
        full['endpoint_resolution']='reused_exact_finite_catalogue_no_new_fusion'
        paths.extend(full.to_dict('records'))
        for metric,mat in eg.items():
            point,_=ustat(mat,exact=True)
            geos.append(dict(pool_id=pid,image=exact.image.iloc[0],k=k,cohort='exact_uniform_catalogue',metric=metric,**point))
        exactmean=describe(exact.B8L2,True)
        summaries.append(dict(pool_id=pid,image=exact.image.iloc[0],pool_n=N,k=k,cohort='exact_uniform_catalogue',
            paths_or_catalogue_size=N,unique_teams=N,total_variation_to_uniform=0.,max_abs_weight_error=0.,
            low_score_mode_threshold=threshold,low_mode_count=int(exact.low_score_mode.sum()),low_mode_probability=float(exact.low_score_mode.mean()),
            below_four_count=int(exact.below_four.sum()),below_four_probability=float(exact.below_four.mean()),
            score_unavailable_count=int(exact.B8L2.isna().sum()),score_unavailable_probability=float(exact.B8L2.isna().mean()),
            exact_inverse_cdf_Q10=exactmean['P10_inverse_cdf'],exact_linear_Q10=exactmean['P10_linear'],
            error_mean_Q=0.,**exactmean))
        for cohort,batches in COHORTS.items():
            if not batches<=set(full.batch):continue
            x=full[full.batch.isin(batches)].copy();counts=x.team_key.value_counts()
            exact[cohort+'_path_count']=exact.team_key.map(counts).fillna(0).astype(int)
            prob=exact[cohort+'_path_count'].to_numpy()/len(x)
            stat=describe(x.B8L2)
            summaries.append(dict(pool_id=pid,image=exact.image.iloc[0],pool_n=N,k=k,cohort=cohort,
                paths_or_catalogue_size=len(x),unique_teams=x.team_key.nunique(),
                total_variation_to_uniform=float(np.abs(prob-1/N).sum()/2),max_abs_weight_error=float(np.abs(prob-1/N).max()),
                low_score_mode_threshold=threshold,low_mode_count=int(x.low_score_mode.sum()),low_mode_probability=float(x.low_score_mode.mean()),
                below_four_count=int(x.below_four.sum()),below_four_probability=float(x.below_four.mean()),
                score_unavailable_count=int(x.B8L2.isna().sum()),score_unavailable_probability=float(x.B8L2.isna().mean()),
                exact_inverse_cdf_Q10=exactmean['P10_inverse_cdf'],exact_linear_Q10=exactmean['P10_linear'],
                error_mean_Q=stat['mean_Q']-exactmean['mean_Q'],**stat))
            geom,_=distance_matrices(x.team_key.tolist(),rows)
            for metric,mat in geom.items():
                point,_=ustat(mat)
                geos.append(dict(pool_id=pid,image=exact.image.iloc[0],k=k,cohort=cohort,metric=metric,**point))
        teams.extend(exact.to_dict('records'))
    pd.DataFrame(teams).to_csv(out/'EXACT_TEAMS_AND_NEW_PATH_FREQUENCIES.csv',index=False)
    pd.DataFrame(paths).to_csv(out/'REGISTERED_PATH_ENDPOINT_BINDINGS.csv.gz',index=False)
    pd.DataFrame(summaries).to_csv(out/'FINITE_CATALOGUE_SAMPLING_COMPARISON.csv',index=False)
    pd.DataFrame(geos).to_csv(out/'FINITE_CATALOGUE_GEOMETRY_COMPARISON.csv',index=False)
    pd.DataFrame(outcomes).to_csv(out/'FINITE_OUTCOME_CONDITIONS.csv',index=False)
    body=json.dumps(geometry_package,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()
    atomic_bytes(out/'FINITE_TEAM_GEOMETRY_AND_REFERENCES.json.gz',gzip.compress(body,mtime=0))
    save_json(out/'CASE_RECEIPT.json',dict(source_commit='b9bcec809fbaec8ab055931a1abb7baa5db44dac',
        cases=CASES,actual_new_registered_paths=len(CASES)*208,new_fusions=0,
        exact_catalogue_reused_teams=len(teams),new_native_execution_required=False,
        inputs={str(prior_exact):file_sha(prior_exact),str(newpath):file_sha(newpath),str(snapshot_path):file_sha(snapshot_path),**{str(p):file_sha(p) for p in order_paths}},
        main_P10='linear remains preserved',finite_distribution_P10='inverse CDF is asymptotic random-sampling target',
        exact_P10_caution='finite catalogue linear interpolation differs from inverse-CDF target; not all differences are Monte Carlo error'))
    make_figure(out)
    return pd.DataFrame(summaries)

def make_figure(out):
    import os
    os.environ.setdefault('MPLCONFIGDIR','/tmp/hohonet_geometry_matplotlib26')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    from matplotlib.ticker import PercentFormatter
    font=out.parent.parent/'assets/NotoSansCJKsc-Regular.otf'
    if font.exists():
        font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    d=pd.read_csv(out/'EXACT_TEAMS_AND_NEW_PATH_FREQUENCIES.csv')
    s=pd.read_csv(out/'FINITE_CATALOGUE_SAMPLING_COMPARISON.csv')
    fig,axes=plt.subplots(len(CASES),2,figsize=(11.4,3.4*len(CASES)),constrained_layout=True)
    colors={'old48':'#a45726','new208':'#276c9e','pooled256':'#28784b'}
    labels={'old48':'原 48 条','new208':'独立新增 208 条','pooled256':'主样本 256 条'}
    for row,pid in enumerate(CASES):
        x=d[d.pool_id.eq(pid)].sort_values('B8L2');a,b=axes[row];N=int(x.pool_n.iloc[0]);k=N-1
        valid=x.B8L2.notna();q=x.loc[valid,'B8L2'].to_numpy();exactcdf=np.arange(1,len(q)+1)/len(q)
        a.step(np.r_[0,q,100],np.r_[0,exactcdf,1],where='post',color='#242424',lw=2,label='精确均匀目录')
        for cohort,color in colors.items():
            w=x.loc[valid,cohort+'_path_count'].to_numpy();cdf=np.cumsum(w)/w.sum()
            a.step(np.r_[0,q,100],np.r_[0,cdf,1],where='post',color=color,lw=1.5,label=labels[cohort])
        a.axhline(.1,color='#909090',ls='--',lw=.8);a.set_xlim(0,100);a.set_ylim(0,1.02)
        a.set_title(f"{x.image.iloc[0]} | {k}/{N} 人",loc='left',fontweight='bold');a.set_xlabel('B8L2 Q（仅可评分端点）');a.set_ylabel('条件累计概率');a.yaxis.set_major_formatter(PercentFormatter(1))
        # Show every exact team, including generated but incomplete outputs.
        qx=x.reset_index(drop=True);idx=np.arange(N);width=.24
        for offset,(cohort,color) in zip([-.26,0,.26],colors.items()):
            count=qx[cohort+'_path_count'].to_numpy();b.bar(idx+offset,count/count.sum(),width,color=color,label=labels[cohort])
        b.axhline(1/N,color='#242424',lw=1.2,label='每队精确权重 1/N')
        b.set_xticks(idx);b.set_xticklabels(qx.absent_worker.str.replace('W',''),rotation=90,fontsize=7)
        b.set_ylabel('实际路径出现频率');b.set_xlabel('缺席者编号（省略 W；按 Q 排序，末尾保留不可评分）');b.yaxis.set_major_formatter(PercentFormatter(1));b.set_title('见过全部团队，与频率估得准确是两件事',loc='left')
        for ax in [a,b]:ax.spines[['top','right']].set_visible(False);ax.grid(axis='y',alpha=.15)
    axes[0,0].legend(loc='upper left',frameon=False,fontsize=8)
    axes[0,1].legend(loc='upper right',frameon=False,fontsize=8)
    fig.suptitle('新增独立进入顺序与完整有限团队分布',fontsize=14)
    import io
    for ext in ['png','pdf']:
        memory=io.BytesIO();fig.savefig(memory,format=ext,dpi=180);atomic_bytes(out/('F_GEOMETRY_FINITE_FREQUENCY.'+ext),memory.getvalue())
    plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--study',type=Path,required=True);a=p.parse_args()
    print(execute(a.study.resolve()).to_string(index=False),flush=True)
