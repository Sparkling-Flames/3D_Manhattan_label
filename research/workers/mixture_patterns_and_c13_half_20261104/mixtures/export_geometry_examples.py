#!/usr/bin/env python3
"""Extract existing exact geometry for three explicitly posthoc illustrations."""
from pathlib import Path
import argparse,gzip,hashlib,json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from plot_style import configure_cjk_font

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
BASE=ROOT/'research/data/releases/v2.1/closeout_20261030/alliance_completion_20261031'

def main():
    a=pd.read_csv(HERE/'DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz')
    g=a[a.from_classes.eq('C3')&a.to_classes.eq('C2|C3')&a.B8L2.notna()]
    cases=[]
    specifications=[('遮挡层中位附近负向例','occluded_median_effect',g[g.structural_condition.eq('boundary_self_occlusion')],None),
        ('遮挡层反向例','occluded_reverse_example',g[g.structural_condition.eq('boundary_self_occlusion')&g.B8L2.gt(0)],'highest'),
        ('无短段／遮挡近零例','nonoccluded_near_zero',g[g.structural_condition.eq('no_short_turns_or_boundary_occlusion')],'zero')]
    for label,selection,z,how in specifications:
        val=0 if how=='zero' else z.B8L2.median()
        r=z.loc[z.B8L2.idxmax()] if how=='highest' else z.iloc[np.argmin(abs(z.B8L2-val))]
        cases.append(dict(label=label,selection=selection,row=r.to_dict()))
    wanted={c['row'][k] for c in cases for k in ['from_team_key','to_team_key']}
    endpoints={};sources=[]
    reused=BASE/'REUSED_ENDPOINTS.jsonl.gz'
    for line in gzip.open(reused,'rt',encoding='utf-8'):
        e=json.loads(line)
        if e['team_key'] in wanted:
            endpoints[e['team_key']]=e
    sources.append(reused)
    for key in wanted-set(endpoints):
        p=BASE/'new_endpoints'/f'{key}.json.gz'
        endpoints[key]=json.load(gzip.open(p,'rt',encoding='utf-8'));sources.append(p)
    snap=ROOT/'research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json';sources.append(snap)
    pools={p['pool_id']:p for p in json.loads(snap.read_text())['images']}
    rows=[];bundle=[]
    fig,axes=plt.subplots(3,3,figsize=(12,11),layout='constrained')
    colors=['#59616c','#087f8c','#cf6a26']
    for ri,c in enumerate(cases):
        r=c['row'];p=pools[r['pool_id']];ref=p['reference'];e1=endpoints[r['from_team_key']];e2=endpoints[r['to_team_key']]
        assert abs(e1['B8L2']-r['Q_from'])<1e-7 and abs(e2['B8L2']-r['Q_to'])<1e-7
        assert e1['member_workers']==sorted(e1['member_workers']) and len(e1['member_workers'])==r['n_from']
        assert set(e1['member_workers'])<set(e2['member_workers'])
        assert e1['reference_id']==e2['reference_id']==ref['target_id']
        assert e1['reference_version']==e2['reference_version']==ref['reference_version']
        pts=[np.array(ref['floor_xz_h']),np.array(e1['geometry']['footprint']),np.array(e2['geometry']['footprint'])]
        allp=np.vstack(pts);lo=allp.min(axis=0);hi=allp.max(axis=0);center=(lo+hi)/2
        span=max(hi-lo)*1.17;limits=[(center[i]-span/2,center[i]+span/2) for i in [0,1]]
        titles=['当前采用参考',f"纯 C3   n={e1['k']}   Q={e1['B8L2']:.2f}",f"C2+C3   n={e2['k']}   Q={e2['B8L2']:.2f}"]
        for ci,(v,title,col) in enumerate(zip(pts,titles,colors)):
            ax=axes[ri,ci]
            refp=np.vstack([pts[0],pts[0][0]])
            if ci:ax.plot(refp[:,0],refp[:,1],color='#9da4ad',ls='--',lw=1.1,alpha=.9,zorder=1)
            poly=np.vstack([v,v[0]])
            ax.plot(poly[:,0],poly[:,1],color=col,lw=1.8,marker='o',ms=3.5,zorder=3)
            ax.scatter([0],[0],marker='+',s=40,color='#303740',zorder=4)
            ax.set(xlim=limits[0],ylim=limits[1],aspect='equal',xlabel='x / 相机高度',ylabel='z / 相机高度')
            ax.grid(color='#e4e8ec',lw=.6);ax.set_title(title,loc='left',fontsize=11)
            if ci:
                ep=e1 if ci==1 else e2
                ax.text(.02,.02,f"节点 {ep['nodes']}  转折 {ep['fusion_turn_n']}  短转折边 {ep['fusion_short_turn_edges']}",
                    transform=ax.transAxes,fontsize=9,color=col,bbox=dict(facecolor='white',alpha=.8,edgecolor='none',pad=2))
            else:
                ax.set_title(f"{c['label']} · {r['image']}\n{r['official_difficulty']} / {r['purpose']} · 混合减纯类 ΔQ={r['B8L2']:+.3f}\n当前采用参考",loc='left',fontsize=10)
        bundle.append(dict(image=r['image'],pool_id=r['pool_id'],selection=c['selection'],selection_label=c['label'],
            status='posthoc_mechanism_illustration',official_difficulty=r['official_difficulty'],purpose=r['purpose'],
            structural_condition=r['structural_condition'],Q_difference=r['B8L2'],reference=ref,
            pure_C3=e1,mixed_C2_C3=e2,accepted_reference_id=r['reference_id'],
            accepted_reference_version=r['reference_version']))
        for arm,e in [('C3',e1),('C2|C3',e2)]:
            rows.append(dict(image=r['image'],selection=c['selection'],classes=arm,team_key=e['team_key'],n=e['k'],
                Q=e['B8L2'],nodes=e['nodes'],turns=e['fusion_turn_n'],short_turn_edges=e['fusion_short_turn_edges'],
                reference_id=e['reference_id'],reference_version=e['reference_version'],
                source=str(reused.relative_to(ROOT)) if e['team_key'] not in [p.stem.removesuffix('.json') for p in sources if p.parent.name=='new_endpoints']
                    else str((BASE/'new_endpoints'/f"{e['team_key']}.json.gz").relative_to(ROOT))))
    fig.suptitle('同一张图内统一底面坐标范围：纯 C3 与加入 C2 后的完整几何',fontsize=15)
    fig.supxlabel('虚线为当前采用参考，加号为相机位置。三例均为事后机制说明；总体结论使用预定义分层的全部图片。',fontsize=9)
    fig.savefig(HERE/'FIG04_GEOMETRY_ILLUSTRATIONS.png',dpi=200,bbox_inches='tight')
    fig.savefig(HERE/'FIG04_GEOMETRY_ILLUSTRATIONS.svg',bbox_inches='tight');plt.close(fig)
    (HERE/'GEOMETRY_ILLUSTRATIONS.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n')
    pd.DataFrame(rows).to_csv(HERE/'GEOMETRY_ILLUSTRATION_ENDPOINTS.csv',index=False,encoding='utf-8-sig')
    manifest=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size) for p in sources]
    (HERE/'GEOMETRY_ILLUSTRATION_SOURCES.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    (HERE/'GEOMETRY_ILLUSTRATION_CHECKS.json').write_text(json.dumps(dict(cases=3,endpoints=6,
        score_parity_tolerance=1e-7,nodes_and_coordinates_unchanged=True,
        reference_and_members_verified=True,new_fusion=0,per_image_equal_axis_ranges=True,status='passed'),indent=2)+'\n')
    print('Exported 3 cases, 6 unchanged endpoint geometries; Q/reference/member parity passed.',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--font');args=parser.parse_args()
    configure_cjk_font(args.font);main()
