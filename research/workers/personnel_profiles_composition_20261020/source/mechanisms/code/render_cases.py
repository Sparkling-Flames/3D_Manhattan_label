"""Render selected personnel-composition mechanisms from frozen states.

This script only displays supplied points; it never selects members, alters
reference bindings, refits scoring, repairs geometry, or changes fusion.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import textwrap

os.environ.setdefault('MPLCONFIGDIR','/tmp/personnel_profile_mechanism_mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image

COLORS={'H':'#2dc9fa','L':'#ff9b38','F':'#2dc9fa','S':'#ff9b38','other':'#bfc3cb'}
REF_COLOR='#e5ffae'
FUSION_COLOR='#f22c74'


def read(path):
    p=Path(path)
    return json.loads((gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes()).decode('utf-8-sig'))


def visual_module(repo, font=None):
    path=repo/'research/workers/personnel_composition_study_20261019/analysis/composition/case_visuals.py'
    spec=importlib.util.spec_from_file_location('frozen_case_visuals',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    here=Path(__file__).resolve().parent
    candidates=[here/'fonts/NotoSansSC-Regular.ttf',here.parent/'fonts/NotoSansSC-Regular.ttf',here/'NotoSansSC-Regular-full.ttf']
    font=Path(font) if font else next((p for p in candidates if p.exists()),candidates[0])
    font_manager.fontManager.addfont(str(font))
    name=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams.update({'font.family':name,'font.size':10,'axes.unicode_minus':False,
                         'figure.facecolor':'#ffffff','savefig.facecolor':'#ffffff'})
    return module


def extract_photo(image_id, index_path, archive_dir, output):
    import zipfile
    rows=list(csv.DictReader(Path(index_path).open(encoding='utf-8-sig')))
    row=next(r for r in rows if r['image_id']==image_id)
    dest=Path(output)/row['archive_path']
    if not dest.exists():
        with zipfile.ZipFile(Path(archive_dir)/row['archive']) as z:z.extract(row['archive_path'],output)
    return dest,row


def render(case, repo, photo_path, destination, font=None):
    v=visual_module(repo, font)
    photo=np.asarray(Image.open(photo_path).convert('RGB'))
    panels=case['panels'];ncols=len(panels)
    ref=case['reference']['points_1024x512']
    records={r['object_id']:r for r in case['records']}
    group_map=case.get('history_groups',{})
    bounds=case['zoom_bounds']
    fig=plt.figure(figsize=(5.4*ncols,12.4))
    grid=fig.add_gridspec(4,ncols,height_ratios=[1.1,1.55,1.2,.7],
                         left=.035,right=.985,bottom=.09,top=.825,wspace=.14,hspace=.28)
    geoms=[v.viewer_geometry(p['state']['candidate']['points'],p['state']['candidate'].get('footprint')) for p in panels]
    refgeom=v.viewer_geometry(ref,case['reference'].get('floor_xz_h'))
    arr=np.concatenate([g['floor'] for g in geoms+[refgeom] if g['floor'] is not None])
    lo,hi=arr.min(axis=0),arr.max(axis=0);pad=np.maximum(.09*(hi-lo),.1)
    bev_bounds=(lo[0]-pad[0],hi[0]+pad[0],lo[1]-pad[1],hi[1]+pad[1])
    diagnostics=[]
    for j,panel in enumerate(panels):
        st=panel['state'];sc=panel['score'];team_records=[records[oid] for oid in panel['object_ids']]
        ids=panel.get('focus_group_ids',[])
        groups=[g for g in st['identity_groups'] if g['feature_id'] in ids]
        points=st['candidate']['points']
        ax=fig.add_subplot(grid[0,j]);v._erp_background(ax,photo)
        for r in team_records:v._erp_edges(ax,r['points_1024x512'],COLORS.get(group_map.get(r['worker_id']),COLORS['other']),linewidth=.72,alpha=.35)
        v._erp_edges(ax,ref,REF_COLOR,linewidth=1.05,reference=True)
        v._erp_edges(ax,points,FUSION_COLOR,linewidth=1.9,markers=True)
        q='不可用' if sc.get('B8L2') is None else f"{sc['B8L2']:.2f}"
        ax.set_title(f"{panel['label']}\n{len(team_records)}人 · {len(points)//2}节点 · B8L2 {q}",fontsize=12,pad=8)
        from matplotlib.patches import Rectangle
        ax.add_patch(Rectangle((bounds[0],bounds[2]),bounds[1]-bounds[0],bounds[3]-bounds[2],fill=False,edgecolor='white',lw=1.1,linestyle='--'))
        ax=fig.add_subplot(grid[1,j]);v._erp_background(ax,photo,bounds)
        if groups:
            for g in groups:
                for m in g['members']:
                    pp=np.asarray(m['points']);ax.plot(pp[:,0],pp[:,1],color=COLORS.get(group_map.get(m['worker']),COLORS['other']),lw=1,alpha=.7)
        else:
            for r in team_records:v._erp_edges(ax,r['points_1024x512'],COLORS.get(group_map.get(r['worker_id']),COLORS['other']),linewidth=.8,alpha=.4)
        v._erp_edges(ax,ref,REF_COLOR,linewidth=1.2,reference=True)
        v._erp_edges(ax,points,FUSION_COLOR,linewidth=2,markers=True)
        for gi,g in enumerate(groups):
            pp=np.asarray(g['center']);mid=pp.mean(axis=0)
            label=f"{g['feature_id'].replace('node_','G')}  {g['support']}/{st['minimum_support']} {'保留' if g['selected'] else '未入选'}"
            ax.annotate(label,xy=mid,xytext=(.025,.94-gi*.12),textcoords='axes fraction',fontsize=8,color='white',va='top',
                        bbox=dict(facecolor='#202836',alpha=.86,edgecolor='none',pad=2),
                        arrowprops=dict(arrowstyle='-',color='white',lw=.65))
            counts={h:sum(group_map.get(m['worker'])==h for m in g['members']) for h in sorted(set(group_map.values()))}
            diagnostics.append(dict(case_id=case['case_id'],panel=panel['label'],team_key=panel['team_key'],
                                    node_id=g['feature_id'],support=g['support'],threshold=st['minimum_support'],selected=g['selected'],
                                    group_counts=counts,workers=sorted(m['worker'] for m in g['members'])))
        ax.set_title('局部原观察、投票与最终连接',fontsize=10,pad=5)
        ax=fig.add_subplot(grid[2,j]);v._bev_ring(ax,refgeom['floor'],'#283946',linewidth=1.5,reference=True)
        v._bev_ring(ax,geoms[j]['floor'],FUSION_COLOR,linewidth=2)
        v._style_bev(ax,bev_bounds);ax.set_title('底面：相机高度归一化，未做配准',fontsize=10)
        ax=fig.add_subplot(grid[3,j]);ax.axis('off')
        member_ids=[r['worker_id'] for r in team_records]
        members='\n'.join(('人员：' if i==0 else '')+'、'.join(member_ids[i:i+6]) for i in range(0,len(member_ids),6))
        d='不可用' if sc.get('D10') is None else f"{sc['D10']:.2f}"
        info=f"D10 {d}；门槛 {st['minimum_support']} 票\n"+panel.get('notes','')+'\n'+members
        if panel.get('labor_seconds') is not None:info=f"总活动耗时 {panel['labor_seconds']/60:.1f} 分钟\n"+info
        ax.text(0,1,'\n'.join(textwrap.fill(x,41) for x in info.splitlines()),va='top',fontsize=8.7,linespacing=1.35)
    fig.suptitle(case['title'],fontsize=17,y=.978)
    fig.text(.035,.933,case['subtitle'],fontsize=10.5,va='top')
    labels=case.get('group_labels',{'H':'历史较高Q','L':'历史较低Q'})
    legend=[Line2D([0],[0],color=COLORS[k],lw=2,label=t+'原标注') for k,t in labels.items()]
    legend.extend([Line2D([0],[0],color=FUSION_COLOR,lw=2,label='融合'),Line2D([0],[0],color=REF_COLOR,lw=3,label='已绑定参考（ERP）'),Line2D([0],[0],color='#283946',ls='--',lw=1.5,label='已绑定参考（底面）')])
    fig.legend(handles=legend,loc='upper left',bbox_to_anchor=(.03,.91),ncol=(3 if ncols==2 else len(legend)),frameon=False,fontsize=9)
    fig.text(.035,.042,case.get('footer','组号仅在本团队内有效；原标注线使用当前研究处理点，按既定环序绘制球面短弧；参考不参与选人、对应和投票。'),fontsize=9,va='top')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(destination,dpi=155);plt.close(fig)
    return diagnostics


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,type=Path)
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--photo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--font',type=Path)
    args=parser.parse_args();case=read(args.case)
    rows=render(case,args.repo,args.photo,args.out,args.font)
    args.out.with_suffix('.votes.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'case':case['case_id'],'figure':str(args.out),'traced_groups':len(rows)},ensure_ascii=False))

if __name__=='__main__':main()
