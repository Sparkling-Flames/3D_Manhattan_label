"""阶段1：完整审核输入的表示可计算性清点及少量反例，不执行研究算法。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from tools.label_studio.panorama_studio.geometry import pixel_ray, project_pixel, triangulate
from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask
from tools.thesis_main.analysis.layout_metric_probe_20260926 import bev_range_metrics, polygon_metrics
from tools.thesis_main.analysis.research_round_20260929 import (
    reconstruct, declared_column_wall_mask, iou, validate_panel, write_csv, write_json,
)

SCHEMA = 'layout_foundation_census_v1'


def synthetic_record(floor, heights=2.7):
    """仅为已知合成几何生成投影输入；不包含任何真实重建适配器。"""
    heights=np.broadcast_to(heights,(len(floor),))
    points=[[project_pixel([x,h-1,z],1024,512),project_pixel([x,-1,z],1024,512)]
            for (x,z),h in zip(floor,heights)]
    return dict(id='synthetic',points=np.array(points).reshape(-1,2).tolist(),
                source_pair_indices=list(range(len(floor))),order_status='synthetic_known',ring_confirmed=True)


def synthetic_cases():
    """选择性吸收已核验 Pro 反例，身份和环不作化简。"""
    square=[[-2,-2],[2,-2],[2,2],[-2,2]]
    hidden=[unary_union([box(-2,-2,2,2),box(2,.5,4,1.5),box(3,1.5,4,length)])
            for length in (4,20)]
    return dict(
        different_ring=(synthetic_record([[-3,-3],[3,-3],[3,3],[1,.7],[-3,3]]),
                        synthetic_record([[-3,-3],[3,-3],[1,.7],[3,3],[-3,3]])),
        hidden_extension=tuple(synthetic_record(np.array(p.exterior.coords)[:-1]) for p in hidden),
        collinear_height_proxy=(synthetic_record(square,[1.5,3.5,3.5,1.5]),
            synthetic_record([[-2,-2],[2,-2],[2,0],[2,2],[-2,2]],[1.5,3.5,3.5,3.5,1.5])))


def synthetic_mesh_wall_mask(floor, heights, roof_triangles, width=128):
    """已知合成实体的独立首交对照。屋顶必须显式给出，不用于真实数据封顶。"""
    if roof_triangles is None:raise ValueError('explicit_roof_required')
    p,h=np.asarray(floor,float),np.asarray(heights,float)
    n=len(p);poly=Polygon(p);roof=np.asarray(roof_triangles)
    if (not poly.is_valid or h.shape!=(n,) or not np.isfinite(h).all() or (h<=1).any()
            or roof.ndim!=2 or roof.shape[1]!=3 or not np.issubdtype(roof.dtype,np.integer)
            or (roof<0).any() or (roof>=n).any() or not isinstance(width,int) or width<4 or width%2):
        raise ValueError('invalid_synthetic_mesh')
    parts=[Polygon(p[t]) for t in roof]
    if (unary_union(parts).symmetric_difference(poly).area>1e-8
            or abs(sum(t.area for t in parts)-poly.area)>1e-8):
        raise ValueError('roof_triangulation_not_a_partition')
    # 面积覆盖不能发现遗漏的抬高折点。边界索引必须逐段连接原墙顶 3D 顶点；
    # 即使某点真正 3D 共线，也保留原始边界分段，不静默化简。
    edges=Counter(tuple(sorted((t[k],t[(k+1)%3]))) for t in roof for k in range(3))
    boundary={tuple(sorted((i,(i+1)%n))) for i in range(n)}
    if ({e for e,count in edges.items() if count==1}!=boundary
            or any(count not in (1,2) for count in edges.values()) or any(t.area<=0 for t in parts)):
        raise ValueError('roof_boundary_not_wall_top_boundary')
    vertices=np.r_[np.c_[p[:,0],-np.ones(n),p[:,1]],np.c_[p[:,0],h-1,p[:,1]]]
    faces=[];labels=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([[i,j,n+j],[i,n+j,n+i]]);labels.extend([1,1])
    base=triangulate(p)
    faces.extend(base);labels.extend([2]*len(base))
    faces.extend((roof+n).tolist());labels.extend([3]*len(roof))
    # Pro 的双面 Moller–Trumbore 首交核；射线使用仓库坐标函数。
    rays=np.array([pixel_ray(x+.5,y+.5,width,width//2)
                   for y in range(width//2) for x in range(width)])
    best=np.full(len(rays),np.inf);classes=np.zeros(len(rays),np.int8)
    for face,label in zip(faces,labels):
        a,b,c=vertices[face];e1,e2=b-a,c-a
        pv=np.cross(rays,e2);det=pv@e1;good=abs(det)>1e-12
        inv=np.zeros_like(det);inv[good]=1/det[good]
        tv=-a;u=(pv@tv)*inv;qv=np.cross(tv,e1);v=(rays@qv)*inv;t=(qv@e2)*inv
        hit=good&(u>=-1e-10)&(v>=-1e-10)&(u+v<=1+1e-10)&(t>1e-9)&(t<best-1e-10)
        best[hit]=t[hit];classes[hit]=label
    if (classes==0).any():raise ValueError('synthetic_mesh_uncovered_pixels')
    return (classes==1).reshape(width//2,width)


def _counts(rows):
    representations=('bev_range','declared_column_wall_band','legacy_x_envelope_continuous','legacy_x_envelope_pixel_center')
    return dict(records=len(rows),annotations=sum(r['kind']=='annotation' for r in rows),
        workers=len({r['worker'] for r in rows if r['worker'] is not None}),
        images=len({r['image'] for r in rows}),
        **{key+'_available':sum(r[key+'_status']=='ok' for r in rows) for key in representations},
        failures={key:dict(Counter(r[key+'_reason'] for r in rows if r[key+'_status']!='ok'))
                  for key in representations})


def inspect_panel(panel, width=512):
    """清点全部记录，包括排除/历史版本；可计算性不重新定义资格。"""
    validate_panel(panel)
    if not isinstance(width,int) or width<4 or width%2:raise ValueError('invalid_resolution')
    rows=[]
    for im in panel['images']:
        for r in im['annotations']+im['references']:
            g=reconstruct(r,coordinate_convention='continuous')
            annotation='worker' in r
            row=dict(image=im['code'],id=r['id'],kind='annotation' if annotation else r['version'],
                worker=r.get('worker'),condition=r.get('condition'),cleaning=r.get('cleaning'),
                order_status=r['order_status'],ring_confirmed=r.get('ring_confirmed'),
                upstream_geometry_status=r['geometry_status'],polygon_valid=g['polygon_valid'],
                camera_relation=g['camera_relation'],camera_in_visible_kernel=g['camera_in_visible_kernel'],
                wall_top_available=g['wall_top_available'],source_point_indices=g['source_point_indices'],
                source_pair_indices=g['source_pair_indices'],
                source_point_labels=g['source_point_labels'],
                independent=r.get('independent'),quality_candidate=r.get('quality_candidate'),
                consensus_eligible=r.get('consensus_eligible'),scene_category=r.get('scene_category'),
                oos_status=im['scene'].get('oos_status'),doorway_status=im['scene'].get('doorway_status'),
                quality_gate=r.get('main_quality_gate',{}).get('status'),
                consensus_gate=r.get('main_consensus_gate',{}).get('status'),
                bottom_horizon_margin_deg=g.get('bottom_horizon_margin_deg'),
                top_horizon_margin_deg=g.get('top_horizon_margin_deg'),
                coordinate_convention='continuous',scope_closure_status='cyclic_ring_model_not_visual_verification',
                roof_model_status='not_observed_not_assumed',
                **{k+'_mark':'marked' if (r.get('review') or {}).get(k) is True else 'no_recorded_mark'
                   for k in ('scope_annotation','detail_annotation')})
            for key,state in g['representations'].items():
                name='bev_range' if key=='declared_footprint' else key
                row[name+'_status']=state['status'];row[name+'_reason']=state['reason']
            if row['declared_column_wall_band_status']=='ok':
                try:declared_column_wall_mask(g,width,width//2)
                except ValueError as exc:
                    row.update(declared_column_wall_band_status='unavailable',declared_column_wall_band_reason=str(exc))
            for convention in ('continuous','pixel_center'):
                key='legacy_x_envelope_'+convention
                try:
                    if r['points'] is None:raise ValueError('pairing_unavailable')
                    wall_mask(np.asarray(r['points']).reshape(-1,2,2),width,width//2,coordinate_convention=convention)
                    row[key+'_status']='ok';row[key+'_reason']=None
                except ValueError as exc:
                    row[key+'_status']='unavailable';row[key+'_reason']=str(exc)
            rows.append(row)
    strata=[]
    for population,subset in (('all_objects',rows),('annotations',[r for r in rows if r['kind']=='annotation'])):
        for dimension in ('kind','order_status','cleaning','oos_status','doorway_status','scene_category',
                          'quality_gate','consensus_gate','independent','scope_annotation_mark','detail_annotation_mark'):
            groups=defaultdict(list)
            for r in subset:groups[r[dimension]].append(r)
            for value,group in sorted(groups.items(),key=lambda kv:str(kv[0])):
                strata.append(dict(population=population,dimension=dimension,value=value,**_counts(group)))
    summary=dict(schema=SCHEMA,raster=[width,width//2],**_counts(rows),
        ring_review=dict(Counter(r['order_status'] for r in rows)),
        camera_relation=dict(Counter(r['camera_relation'] for r in rows)),
        camera_in_visible_kernel=dict(Counter(str(r['camera_in_visible_kernel']) for r in rows)),
        annotation_population=_counts([r for r in rows if r['kind']=='annotation']),
        mark_semantics='no_recorded_mark means unknown/absence of recorded mark, never verified negative',
        scope='representation computability only; no quality, clustering, consensus, search or weights',
        coordinate_status='original GT production verified continuous; final LS percent maps to continuous canvas; native HoHoNet pixel_center; same numeric C/P is mismatch or unknown-source sensitivity; physical ERP sampling/gravity calibration unresolved')
    return rows,strata,summary


def examples(panel,out,width=512):
    """只比较受控代表样例，不计算全量两两差异。"""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    cases=synthetic_cases();rows=[]
    fig,axes=plt.subplots(3,2,figsize=(11,10))
    for (name,(a,b)),ax in zip(cases.items(),axes):
        ga,gb=reconstruct(a),reconstruct(b)
        ma,mb=[declared_column_wall_mask(g,width,width//2) for g in (ga,gb)]
        m=bev_range_metrics(ga['floor'],gb['floor'])
        proxy=polygon_metrics(ga['floor'],gb['floor'],float(np.median(ga['heights'])),float(np.median(gb['heights'])))['volume_iou']
        rows.append(dict(case=name,**m,declared_column_wall_band_iou=iou(ma,mb),historical_vertex_median_prism_proxy_iou=proxy))
        for g,color,label in ((ga,'#2474b5','A'),(gb,'#dc7f28','B')):
            p=np.r_[g['floor'],g['floor'][:1]];ax[0].plot(p[:,0],p[:,1],'.-',color=color,label=label)
        ax[0].plot(0,0,'k+');ax[0].axis('equal');ax[0].legend();ax[0].set_title(name+' / BEV')
        ax[1].imshow(ma.astype(int)+2*mb.astype(int),vmin=0,vmax=3,interpolation='nearest',cmap='viridis')
        ax[1].set_title(f'Column wall band IoU={iou(ma,mb):.6f}')
    fig.tight_layout();fig.savefig(out/'synthetic_representations.png',dpi=130);plt.close(fig)
    write_csv(out/'synthetic_examples.csv',rows)
    chosen={'R02503','R03288','R03286'}
    selected=[(im,r) for im in panel['images'] for r in im['annotations']+im['references'] if r['id'] in chosen]
    if {r['id'] for _,r in selected}!=chosen:raise ValueError('representative_source_missing')
    fig,axes=plt.subplots(2,3,figsize=(14,7));factorial=[]
    for (im,r),axs in zip(sorted(selected,key=lambda item:item[1]['id']),axes.T):
        masks={};geometries={}
        for convention in ('continuous','pixel_center'):
            g=reconstruct(r,coordinate_convention=convention);geometries[convention]=g
            for kind in ('sorted','declared'):
                key=kind+'_'+convention
                try:
                    masks[key]=(declared_column_wall_mask(g,width,width//2) if kind=='declared' else
                        wall_mask(np.array(r['points']).reshape(-1,2,2),width,width//2,coordinate_convention=convention))
                except ValueError as exc:
                    factorial.append(dict(id=r['id'],image=im['code'],comparison=key,status='unavailable',reason=str(exc),iou=None))
        for a,b in (('sorted_continuous','declared_continuous'),('sorted_pixel_center','declared_pixel_center'),
                    ('sorted_continuous','sorted_pixel_center'),('declared_continuous','declared_pixel_center')):
            ok=a in masks and b in masks
            factorial.append(dict(id=r['id'],image=im['code'],comparison=a+' vs '+b,
                status='ok' if ok else 'unavailable',reason=None if ok else 'see_representation_failure',
                iou=iou(masks[a],masks[b]) if ok else None))
        g=geometries['continuous'];p=g['floor'];q=p[np.argsort(np.array(r['points'])[::2,0])]
        for points,color,label in ((p,'#2474b5','declared ring'),(q,'#dc7f28','x sorted')):
            points=np.r_[points,points[:1]];axs[0].plot(points[:,0],points[:,1],'.-',color=color,label=label)
        axs[0].plot(0,0,'k+');axs[0].axis('equal');axs[0].legend()
        axs[0].set_title(r['id']+' / '+r['order_status'])
        if 'declared_continuous' in masks and 'sorted_continuous' in masks:
            axs[1].imshow(masks['sorted_continuous'].astype(int)+2*masks['declared_continuous'].astype(int),
                vmin=0,vmax=3,interpolation='nearest',cmap='viridis')
        else:axs[1].text(.05,.5,'Column wall band unavailable:\n'+g['representations']['declared_column_wall_band']['reason'],transform=axs[1].transAxes)
        axs[1].set_title('Same coordinate interpretation: sorted / declared')
    fig.tight_layout();fig.savefig(out/'real_coordinate_vs_adjacency.png',dpi=130);plt.close(fig)
    write_csv(out/'real_factorial.csv',factorial)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--width',type=int,default=512)
    args=parser.parse_args()
    from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
    from tools.thesis_main.data_prep.project_public_research_20260929 import project_bundle
    bundle=load_current_bundle();panel,mapping=project_bundle(bundle)
    source={mapping['records'][o['object_id']]:o for o in bundle['data']['objects']}
    for im in panel['images']:
        for r in im['annotations']+im['references']:
            r['source_pair_indices']=source[r['id']]['ordered_source_pair_indices']
    print('Validated complete manifest bundle; inspecting all records',flush=True)
    rows,strata,summary=inspect_panel(panel,args.width)
    args.out.mkdir(parents=True,exist_ok=True)
    write_csv(args.out/'records.csv',rows);write_csv(args.out/'strata.csv',strata)
    summary.update(source_entry='analysis_results/research_input_20260929/manifest.json',
                   source_validation=bundle['validation'],contract_version=bundle['data']['contract_version'])
    write_json(args.out/'summary.json',summary)
    write_json(args.out/'field_contract.json',dict(schema=SCHEMA,record_fields=list(rows[0]),
        region_kinds={'bev_range':'declared footprint in shared camera-height units',
                      'declared_column_wall_band':'nearest bottom edge and linear wall top; unknown roof',
                      'legacy_x_envelope_continuous':'x sorted, continuous input',
                      'legacy_x_envelope_pixel_center':'historical x sorted and +0.5 convention'},
        unavailable='status unavailable with reason; no score zero; polygon_valid/kernel may be null when not assessed',
        eligibility='copied upstream candidates/gates; failures do not alter eligibility',
        strata='population annotations/all_objects separately; one dimension per row; null not applicable; do not sum across dimensions',
        marks=summary['mark_semantics'],identity='public record/person aliases; source point/pair indices retained',
        historical_proxy='only synthetic examples; vertex-median prism is not true volume or a main score'))
    examples(panel,args.out,args.width)
    print(f"Completed {summary['records']} records / {summary['annotations']} annotations / {summary['workers']} workers",flush=True)


if __name__=='__main__':main()
