"""两个局部窗口的原路径/实际融合边界对照，以及uNb单图来源检查。"""
import json

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from shapely.geometry import LineString, mapping, shape, box

from .local_patch_response_20261006 import ROOT, PRO
from .layout_reliability_20261005.arc_consensus import paired_wall_proxy, project

OUT = ROOT/'analysis_results/consensus_response_20261006/boundary_followup'
SPECS = {
    'rPc6DW4iMge-06': dict(records=['R01557','R01905','R02452'], erp=(180,245,180,360), bev=(-3.1,-1.95,.3,1.05)),
    'yqstnuAEVhm-32': dict(records=['R02256','R01095','R00157'], erp=(875,1015,150,380), bev=(.15,2.1,1.2,3.4)),
}


def draw_erp(ax, xyz, color, label, style='-'):
    for i,(a,b) in enumerate(zip(xyz,xyz[1:])):
        t=np.linspace(0,1,129)[:,None]
        xy=project(a*(1-t)+b*t)
        for part in np.split(xy,np.flatnonzero(np.abs(np.diff(xy[:,0]))>512)+1):
            ax.plot(part[:,0],part[:,1],color=color,ls=style,lw=1.6,label=label if i==0 else None)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','DejaVu Sans']
    plt.rcParams['axes.unicode_minus']=False
    data=json.loads((PRO/'inputs/cases.json').read_text(encoding='utf-8'))
    ims={r['code']:r for r in data['images']}
    regions={(f['properties']['image'],f['properties']['method']):shape(f['geometry'])
             for f in json.loads((PRO/'results/full_consensus.geojson').read_text(encoding='utf-8'))['features']}
    features=[]
    for code,s in SPECS.items():
        im=ims[code]; records={r['id']:r for r in im['annotations']}
        photo=Image.open(PRO/'inputs'/im['image_file'])
        fig,axes=plt.subplots(2,3,figsize=(15,10))
        for col,rid in enumerate(s['records']):
            r=records[rid]; top,bottom=paired_wall_proxy(r)
            assert np.max(abs(project(bottom)-np.asarray(r['points'])[1::2]))<1e-8
            xy=np.asarray(r['footprint']); ring=np.vstack((xy,xy[0]))
            ax=axes[0,col]; ax.imshow(photo,extent=(0,1024,512,0))
            for p in (top,bottom): draw_erp(ax,np.vstack((p,p[0])),'#1975b5','原作答' if p is top else None)
            axes[1,col].plot(ring[:,0],ring[:,1],color='#1975b5',lw=2,label='原作答')
            for method,color,style,label in [('mv50','#c52b2b','-','全员MV50'),('mv_strict','#803cb0','--','全员严格多数')]:
                region=regions[code,method]; coords=np.asarray(region.exterior.coords)
                floor=np.column_stack((coords[:,0],-np.ones(len(coords)),coords[:,1]))
                draw_erp(ax,floor,color,label,style)
                axes[1,col].plot(coords[:,0],coords[:,1],color=color,ls=style,lw=1.7,label=label)
            x0,x1,y0,y1=s['erp']; ax.set(xlim=(x0,x1),ylim=(y1,y0),xlabel='C画布 x',ylabel='C画布 y',title=f'{rid} / {r["worker"]}')
            a,b,c,d=s['bev']; ba=axes[1,col]; ba.set(xlim=(a,b),ylim=(c,d),xlabel='x / h',ylabel='z / h'); ba.set_aspect('equal')
            for j,p in enumerate(xy):
                if a<=p[0]<=b and c<=p[1]<=d:
                    ba.annotate(f'p{j}',p,xytext=(4,4),textcoords='offset points',fontsize=8)
            ba.legend(fontsize=8)
            clip=LineString(ring).intersection(box(a,c,b,d)); assert not clip.is_empty
            features.append(dict(type='Feature',properties=dict(image=code,object=rid,worker=r['worker'],role='observed_boundary_window'),geometry=mapping(clip)))
        for method in ('mv50','mv_strict'):
            a,b,c,d=s['bev']
            features.append(dict(type='Feature',properties=dict(image=code,object=method,role='actual_full_consensus_boundary_window'),geometry=mapping(regions[code,method].boundary.intersection(box(a,c,b,d)))))
        fig.suptitle(code+'｜同一实际全员边界，分别对照三份现有作答\n上：原图及上下原路径（融合仅底边）；下：未平滑的实际底面边界；p为处理后零基点号',fontsize=13)
        fig.tight_layout(); fig.savefig(OUT/f'{code}_comparison.png',dpi=170); plt.close(fig)
    json_dump=lambda path,value: path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    json_dump(OUT/'boundary_windows.geojson',dict(type='FeatureCollection',features=features))
    # Wider room view keeps the user's alternative target visible; it adds no vote.
    im=ims['rPc6DW4iMge-06']; lookup={r['id']:r for r in im['annotations']}
    fig,axes=plt.subplots(1,2,figsize=(12,7))
    for ax,rid,title in zip(axes,['R01557','R00020'],['P023：用户确认玻璃外侧较标准','P002／来源W002：待核对的内侧墙面观察']):
        ax.imshow(Image.open(PRO/'inputs'/im['image_file']),extent=(0,1024,512,0))
        for xyz in paired_wall_proxy(lookup[rid]): draw_erp(ax,np.vstack((xyz,xyz[0])),'#1975b5',None)
        ax.set(xlim=(0,390),ylim=(480,60),xlabel='C画布 x',ylabel='C画布 y',title=rid+'\n'+title)
    fig.suptitle('rPc-06 两种边界目标的原作答；不选择更像GT的一份作为融合答案')
    fig.tight_layout(); fig.savefig(OUT/'rPc_outer_inner.png',dpi=170); plt.close(fig)
    code='uNb9QFRL6hY-47'; im=ims[code]; stem=im['image_id']
    png=ROOT/'data/mp3d_layout/test/img'/f'{stem}.png'
    jpg=ROOT/'data/mp3d_layout/img_v'/f'{stem}.jpg'
    a=np.asarray(Image.open(png).convert('RGB').resize((1024,512)),float)
    b=np.asarray(Image.open(jpg).convert('RGB').resize((1024,512)),float)
    raw=ROOT/'data/mp3d_layout/test/label_cor'/f'{stem}.txt'
    original=next(r for r in im['references'] if r['version']=='original')
    assert np.array_equal(np.loadtxt(raw),original['points'])
    changed=next(r for r in im['references'] if r['version']=='manual_revision')
    gt=json.loads((ROOT/'export_label/groudTruth.json').read_text(encoding='utf-8'))
    task=next(t for t in gt if stem in t['data']['image'])
    annotation=task['annotations'][0]
    values=[r['value'] for r in annotation['result'] if r['type']=='keypointlabels']
    parsed=np.array([[r['x']*10.24,r['y']*5.12] for r in values])[changed['source_point_indices']]
    revision_error=float(np.max(abs(parsed-np.asarray(changed['points']))))
    json_dump(OUT/'source_trace.json',dict(image=code,original_source=str(raw.relative_to(ROOT)),
        original_canonical_max_diff=0.,reference_revision_source='export_label/groudTruth.json',
        revision_export_percent_rounding_max_px=revision_error,
        revision_task=task['id'],revision_annotation=annotation['id'],
        revision_image_rotation=sorted({r.get('image_rotation') for r in annotation['result'] if r['type']=='keypointlabels'}),
        display_png=str(png.relative_to(ROOT)),labeling_jpg=str(jpg.relative_to(ROOT)),
        image_MAE_uint8={'no_shift':float(np.mean(abs(a-b))),'png_plus_256':float(np.mean(abs(np.roll(a,256,axis=1)-b))),'png_minus_256':float(np.mean(abs(np.roll(a,-256,axis=1)-b)))},
        interpretation='Local PNG/JPG have matching orientation; original GT retained exactly; no proof of upstream quarter-turn transform or permission to correct GT. Live COS image not fetched.'))
    yq={r['id']:r for r in ims['yqstnuAEVhm-32']['annotations']}
    json_dump(OUT/'field_contract.json',dict(schema='local_boundary_followup_v1',specs=SPECS,
        figures='Existing observations and actual saved all-pool boundaries; no resampling of people, smoothing, snapping or new vote.',
        geometry='Clipped to fixed display boxes only; no structure recovery score or semantic identity inferred.',
        duplicate_display_geometry={'records':['R01095','R01029'],'exact_full_points_equal':yq['R01095']['points']==yq['R01029']['points'],'action':'One shown path; existing independent-vote eligibility unchanged.'},
        checks='Bottom projection roundtrip <1e-8 pixels; selected clipped paths nonempty; original reference equals source TXT.'))
    print(json.dumps(dict(boundary_features=len(features),revision_rounding_px=revision_error)))


if __name__=='__main__': run()
