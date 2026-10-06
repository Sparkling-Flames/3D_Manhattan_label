"""Data-faithful PNG overlays. One axes per figure; no synthesized pixels.
ERP axes use the input continuous 1024 x 512 canvas. Actual PNGs are 2048 x 1024.
All declared edges, including longitude backtracking, are preserved.
"""
from pathlib import Path
import json
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from shapely.geometry import shape
from arc_excerpt import project, paired_wall_proxy
from analyze import CODES, SPECIAL, DETAIL, roster

plt.rcParams['font.family']=['Noto Sans CJK JP','DejaVu Sans']
plt.rcParams['axes.unicode_minus']=False


def polygon_paths(g):
    if g.geom_type=='Polygon':
        return [np.asarray(g.exterior.coords)]+[np.asarray(x.coords) for x in g.interiors]
    return [x for part in g.geoms for x in polygon_paths(part)]


def joined(paths):
    return np.vstack([np.vstack([x,np.full((1,2),np.nan)]) for x in paths])


def projected_edges(paths,top=False):
    result=[]
    for xyz in paths:
        for a,b in zip(xyz[:-1],xyz[1:]):
            t=np.linspace(0.,1.,129)
            xy=project(a[None,:]*(1-t[:,None])+b[None,:]*t[:,None])
            cuts=np.flatnonzero(np.abs(np.diff(xy[:,0]))>512)+1
            for p in np.split(xy,cuts):
                if len(p)>1:result.append(p)
    return result


def record_erp(r):
    t,b=paired_wall_proxy(r)
    return projected_edges([np.vstack([v,v[0]]) for v in (t,b)])


def region_erp(g):
    paths=[np.column_stack([xy[:,0],-np.ones(len(xy)),xy[:,1]]) for xy in polygon_paths(g)]
    return projected_edges(paths)


def render(source,result_dir,fig_dir):
    source=Path(source);rd=Path(result_dir);fd=Path(fig_dir);fd.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'cases.json').read_text());ims={i['code']:i for i in data['images']}
    saved=json.loads((rd/'full_consensus.geojson').read_text())
    regs={(f['properties']['image'],f['properties']['method']):shape(f['geometry']) for f in saved['features']}
    files=[]
    for code in CODES:
        im=ims[code];recs=roster(im)
        for view in ['bev','erp']:
            fig,ax=plt.subplots(figsize=(10.6,6.4) if view=='bev' else (14,7))
            if view=='erp':ax.imshow(Image.open(source/im['image_file']),extent=(0,1024,512,0))
            paths=[]
            for r in recs:
                if view=='bev':
                    xy=np.array(r['footprint']);paths.append(np.vstack([xy,xy[0]]))
                else:paths+=record_erp(r)
            xy=joined(paths);ax.plot(xy[:,0],xy[:,1],lw=.75,alpha=.32,label=f'{len(recs)}人原作答（非共识上界）' if view=='erp' else f'{len(recs)}人完整原作答')
            for m,ls,label in [('mv50','-','全员 MV50'),('mv_strict','--','全员严格多数')]:
                g=regs[code,m];xy=joined(polygon_paths(g) if view=='bev' else region_erp(g))
                ax.plot(xy[:,0],xy[:,1],lw=2.2,ls=ls,label=label+(' · 仅底边' if view=='erp' else ''))
            for ref in im['references']:
                lab=('原GT ' if ref['version']=='original' else '修订GT ')+ref['id']
                if view=='bev':
                    xy=np.array(ref['footprint']);xy=np.vstack([xy,xy[0]])
                else:xy=joined(record_erp(ref))
                ax.plot(xy[:,0],xy[:,1],lw=1.55,ls=':' if ref['version']=='original' else '-.',label=lab)
            if view=='bev':
                ax.plot(0,0,'+',ms=10,label='相机');ax.set_aspect('equal');ax.set(xlabel='x / h',ylabel='z / h')
            else:ax.set(xlim=(0,1024),ylim=(512,0),xlabel='原C画布 x（PNG坐标÷2）',ylabel='原C画布 y')
            ax.set_title(f'{code} | 全部{len(recs)}名纳入人员 · '+('声明足迹与全员范围' if view=='bev' else '实际原PNG＋声明连线；Lee无上界'),fontsize=12)
            ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=2,fontsize=9)
            fig.tight_layout();file=fd/f'{code}_{view}_full.png';fig.savefig(file,dpi=170,bbox_inches='tight');plt.close(fig);files.append(file)
    return files


def render_focus(source,result_dir,fig_dir,spec_file):
    source=Path(source);rd=Path(result_dir);fd=Path(fig_dir)
    ims={i['code']:i for i in json.loads((source/'cases.json').read_text())['images']}
    fs=json.loads((rd/'full_consensus.geojson').read_text())['features']
    regs={(f['properties']['image'],f['properties']['method']):shape(f['geometry']) for f in fs}
    specs=json.loads(Path(spec_file).read_text());written=[]
    choices={'rPc6DW4iMge-06':['R01557','R01905','R02452'],
             'yqstnuAEVhm-32':['R02256','R01095','R00157']}
    for code,s in specs.items():
        im=ims[code];lookup={r['id']:r for r in roster(im)}
        for view in ['bev','erp']:
            fig,ax=plt.subplots(figsize=(10,7.5))
            if view=='erp':ax.imshow(Image.open(source/im['image_file']),extent=(0,1024,512,0))
            for rid in choices[code]:
                r=lookup[rid]
                if view=='bev':
                    xy=np.asarray(r['footprint']);xy=np.vstack([xy,xy[0]])
                else:xy=joined(record_erp(r))
                ax.plot(xy[:,0],xy[:,1],lw=1.8,alpha=.85,label=f"{rid} / {r['worker']} 原作答")
            for m,ls,label in [('mv50','-','MV50 · 仅底面'),('mv_strict','--','严格多数 · 仅底面')]:
                xy=joined(polygon_paths(regs[code,m]) if view=='bev' else region_erp(regs[code,m]))
                ax.plot(xy[:,0],xy[:,1],ls=ls,lw=2.2,label=label)
            for ref in im['references']:
                if view=='bev':
                    xy=np.asarray(ref['footprint']);xy=np.vstack([xy,xy[0]])
                else:xy=joined(record_erp(ref))
                ax.plot(xy[:,0],xy[:,1],ls=':' if ref['version']=='original' else '-.',lw=1.7,
                        label=('原GT ' if ref['version']=='original' else '修订GT ')+ref['id'])
            target=lookup[s['id']]
            pts=np.asarray(target['footprint']) if view=='bev' else np.asarray(target['points'])[1::2]
            for idx in s['indices']:
                ax.annotate(f'p{idx}',pts[idx],xytext=(5,6),textcoords='offset points',fontsize=9)
            if view=='bev':
                patch_indices=s['indices'] if code.startswith('rPc') else [10,11,12]
                patch=pts[patch_indices]
                ax.fill(patch[:,0],patch[:,1],fill=False,hatch='///',lw=.7,
                        alpha=.35,label='只读诊断面片（非GT、非投票）')
                a,b,c,d=s['bev_box'];ax.set(xlim=(a,b),ylim=(c,d),xlabel='x / h',ylabel='z / h');ax.set_aspect('equal')
            else:
                a,b,c,d=s['erp_box'];ax.set(xlim=(a,b),ylim=(d,c),xlabel='C画布 x（实际PNG坐标÷2）',ylabel='C画布 y')
            ax.set_title(f"{code}｜{s['label']}\np为{s['id']}处理后零基点对号；原图叠线非语义金标准",fontsize=11)
            ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=2,fontsize=9)
            fig.tight_layout();path=fd/f'{code}_{view}_detail.png';fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig);written.append(path)
    # A second yq window: the large fireplace is a retained positive control.
    code='yqstnuAEVhm-32';im=ims[code];lookup={r['id']:r for r in roster(im)}
    fig,ax=plt.subplots(figsize=(10.5,7));ax.imshow(Image.open(source/im['image_file']),extent=(0,1024,512,0))
    for rid in ['R02256','R01439']:
        xy=joined(record_erp(lookup[rid]));ax.plot(xy[:,0],xy[:,1],lw=1.6,label=f'{rid} 原作答')
    for m,ls in [('mv50','-'),('mv_strict','--')]:
        xy=joined(region_erp(regs[code,m]));ax.plot(xy[:,0],xy[:,1],lw=2,ls=ls,label=m+' · 仅底面')
    ax.set(xlim=(510,700),ylim=(405,90),xlabel='C画布 x',ylabel='C画布 y',title='yq-32｜壁炉的大轮廓被保留：不要把所有细节都称为融合遗漏')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.12),ncol=2,fontsize=9);fig.tight_layout()
    path=fd/'yqstnuAEVhm-32_fireplace_retained.png';fig.savefig(path,dpi=180,bbox_inches='tight');plt.close(fig);written.append(path)
    return written
