"""Latest-data numerical baseline. Inputs are explicit derived records, never raw exports.

No GT enters aggregation. Reconstruction does not delete, reorder or fit points.
The explicit prepare_record helper applies the existing confirmed/default-x rule;
historical callers remain unchanged. Lengths use camera height one, not metres.
"""
from __future__ import annotations
import argparse
import copy
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from tools.label_studio.panorama_studio.geometry import analyze
from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask, aggregate
from tools.thesis_main.analysis.layout_metric_probe_20260926 import compare_regions, polygon_metrics, bev_range_metrics

REQUIRED = {'id','worker','condition','points','cleaning','independent','consensus_eligible',
            'quality_candidate','order_status','geometry_status'}
METHODS = ('mv50','mv_strict','medoid')


def validate_panel(panel):
    if panel['schema'] != 'layout_research_panel_v1':
        raise ValueError('unsupported_panel_schema')
    ids=set(); images=set()
    for im in panel['images']:
        if im['code'] in images:raise ValueError('duplicate_image')
        images.add(im['code']); votes=set()
        for r in im['annotations']:
            if REQUIRED-set(r):raise ValueError('missing_record_fields:'+str(sorted(REQUIRED-set(r))))
            if r['id'] in ids:raise ValueError('duplicate_record_id')
            ids.add(r['id'])
            for field in ('independent','consensus_eligible','quality_candidate'):
                if type(r[field]) is not bool:raise ValueError('nonboolean_eligibility:'+field)
            if r['independent'] and r['consensus_eligible']:
                key=(r['worker'],r['condition'])
                if key in votes:raise ValueError('duplicate_independent_person')
                votes.add(key)
        versions=[r['version'] for r in im['references']]
        if len(versions)!=len(set(versions)):raise ValueError('duplicate_reference_version')


def prepare_record(record):
    """沿用10/2探针：确认环保留，未确认环按预处理共享x排序，原始GT不改序。"""
    r = copy.deepcopy(record)
    if r.get('points') is None:
        r['order_used'] = 'unavailable'
        return r
    if r.get('ring_confirmed') or r.get('version') == 'original':
        r['order_used'] = 'human_confirmed' if r.get('ring_confirmed') else 'original_gt_reference'
        return r
    p = np.asarray(r['points'], float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) % 2 or not np.isfinite(p).all():
        raise ValueError('invalid_preprocessed_points')
    pairs = p.reshape(-1, 2, 2)
    if not np.allclose(pairs[:, 0, 0], pairs[:, 1, 0], rtol=0, atol=1e-9):
        raise ValueError('preprocessed_shared_x_mismatch')
    order = np.argsort(pairs[:, 0, 0], kind='stable').tolist()
    r['points'] = pairs[order].reshape(-1, 2).tolist()
    for key in ('source_pair_indices', 'source_point_indices', 'source_point_labels'):
        if r.get(key) is not None:
            stride = 1 if key == 'source_pair_indices' else 2
            if len(r[key]) != stride*len(order):
                raise ValueError('source_identity_length_mismatch')
            r[key] = [r[key][stride*i+j] for i in order for j in range(stride)]
    r['order_used'] = 'default_x_unreviewed'
    return r


def reconstruct(record, *, coordinate_convention='continuous'):
    """声明环；历史默认连续x/W。表示状态独立于审核和人员资格。"""
    def unavailable(reason):
        return dict(status='unavailable',reason=reason,floor=None,heights=None,
                    polygon_valid=None,camera_relation='unavailable',camera_in_visible_kernel=None,
                    wall_top_available=False,order_status=record.get('order_status'),ring_confirmed=record.get('ring_confirmed'),
                    coordinate_convention=coordinate_convention,
                    source_point_indices=record.get('source_point_indices'),source_pair_indices=record.get('source_pair_indices'),
                    source_point_labels=record.get('source_point_labels'),
                    representations={k:dict(status='unavailable',reason=reason) for k in
                                     ('declared_footprint','declared_column_wall_band')})
    if coordinate_convention not in ('continuous','pixel_center'):raise ValueError('unknown_coordinate_convention')
    if record['points'] is None:return unavailable('pairing_unavailable')
    p=np.asarray(record['points'],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        return unavailable('invalid_point_array')
    pairs=p.reshape(-1,2,2)
    identities=record.get('source_pair_indices')
    if identities is not None and (len(identities)!=len(pairs) or len(set(identities))!=len(identities)):
        return unavailable('invalid_source_pair_identity')
    payload=dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=[
        dict(source_pair_id=str(identities[i] if identities is not None else i),
             top=dict(zip(('x','y'),a)),bottom=dict(zip(('x','y'),b))) for i,(a,b) in enumerate(pairs)])
    try:raw=analyze(payload,compute_fit=False,coordinate_convention=coordinate_convention)['raw']
    except ValueError as e:return unavailable(str(e))
    floor=np.asarray(raw['declared_floor'])[:,[0,2]] if all(p is not None for p in raw['declared_floor']) else None
    height=np.asarray(raw['ceiling'])[:,1]+1 if all(p is not None for p in raw['ceiling']) else None
    return dict(status='ok' if raw['surface_valid'] else 'unavailable',
                reason=None if raw['surface_valid'] else ';'.join(raw['issues']),
                floor=floor,heights=height,metrics=raw['metrics'],issues=raw['issues'],pair_count=len(pairs),
                polygon_valid=raw['polygon_valid'],camera_relation=raw['camera_relation'],
                camera_in_visible_kernel=raw['camera_in_visible_kernel'],
                wall_top_available=height is not None and 'vertical_pair_mismatch' not in raw['issues'],
                bottom_horizon_margin_deg=raw['bottom_horizon_margin_deg'],top_horizon_margin_deg=raw['top_horizon_margin_deg'],
                coordinate_convention=coordinate_convention,order_status=record.get('order_status'),ring_confirmed=record.get('ring_confirmed'),
                source_point_indices=record.get('source_point_indices'),source_pair_indices=record.get('source_pair_indices'),
                source_point_labels=record.get('source_point_labels'),
                representations=raw['representations'])


def candidate_geometry(record, geometry=None):
    g=reconstruct(record) if geometry is None else geometry
    state={k:g[k] for k in ('polygon_valid','camera_relation','camera_in_visible_kernel','wall_top_available','representations')}
    if g['status']!='ok':return dict(status=g['status'],reason=g['reason'],**state)
    p,h=g['floor'],g['heights'];poly=Polygon(p)
    lengths=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    angles=np.arctan2(*(np.roll(p,-1,axis=0)-p)[:,::-1].T)
    axis=np.radians(g['metrics']['heading_frame_deg'])
    residual=np.degrees(np.abs((angles-axis+np.pi/4)%(np.pi/2)-np.pi/4))
    return dict(status='ok',reason=None,pair_count=len(p),area_h2=float(poly.area),
                camera_inside=bool(poly.contains(Point(0,0))),
                direction_length_weighted_deg=float(np.average(residual,weights=lengths)),
                height_mad_relative=float(np.median(abs(h-np.median(h)))/np.median(h)),
                **g['metrics'],**state)


def declared_column_wall_mask(g,width=512,height=256):
    """声明底环首交＋线性墙顶的列式墙带；不声明一般屋顶真实可见性。"""
    if not isinstance(width,int) or not isinstance(height,int) or min(width,height)<2:
        raise ValueError('invalid_resolution')
    state=g['representations']['declared_column_wall_band']
    if state['status']!='ok':raise ValueError(state['reason'])
    p,h=g['floor'],g['heights']
    if not Polygon(p).contains(Point(0,0)):raise ValueError('camera_not_strictly_inside')
    longitude=2*np.pi*((np.arange(width)+.5)/width-.5)
    rays=np.c_[np.sin(longitude),-np.cos(longitude)]
    distance=np.full(width,np.inf);top_height=np.full(width,np.nan)
    cross=lambda a,b:a[...,0]*b[...,1]-a[...,1]*b[...,0]
    for i,(a,b) in enumerate(zip(p,np.roll(p,-1,axis=0))):
        edge=b-a;den=cross(rays,edge);good=abs(den)>1e-12
        radius=np.full(width,np.inf);fraction=np.full(width,np.inf)
        radius[good]=cross(a,edge)/den[good];fraction[good]=cross(a,rays[good])/den[good]
        hit=good & (radius>0) & (fraction>=-1e-10) & (fraction<=1+1e-10) & (radius<distance)
        distance[hit]=radius[hit]
        top_height[hit]=h[i]+fraction[hit]*(h[(i+1)%len(h)]-h[i])-1
    if not np.isfinite(distance).all():raise ValueError('uncovered_ray')
    lat=np.pi*(.5-(np.arange(height)+.5)/height)
    return (lat[:,None]<=np.arctan2(top_height,distance)) & (lat[:,None]>=-np.arctan2(1,distance))


visible_wall_mask = declared_column_wall_mask  # 历史导入名保留；新的调用点显式命名表示。


def iou(a,b):
    union=np.count_nonzero(a|b)
    return float(np.count_nonzero(a&b)/union) if union else None


def stats(values):
    v=np.asarray([x for x in values if x is not None and np.isfinite(x)],float)
    return dict(n=len(v),mean=float(v.mean()) if len(v) else None,
                median=float(np.median(v)) if len(v) else None,
                p05=float(np.quantile(v,.05)) if len(v) else None,
                p95=float(np.quantile(v,.95)) if len(v) else None)


def summarize_replays(group,masks,refs,seeds=100):
    """Fixed seeds; GT used only after each mask is formed. Missing votes stay in k."""
    group=sorted(group,key=lambda r:r['id']);available=[r for r in group if r['id'] in masks]
    if not available:return []
    stack=np.stack([masks[r['id']] for r in available]);position={r['id']:i for i,r in enumerate(available)}
    affinity=np.array([[iou(a,b) if np.any(a|b) else 1. for b in stack] for a in stack])
    samples=defaultdict(list)
    for seed in range(seeds):
        order=np.random.default_rng(290929+seed).permutation(len(group))
        counts=np.zeros(stack.shape[1:],np.int16);selected=[];previous={}
        for k,j in enumerate(order,1):
            key=group[j]['id']
            if key in position:
                pos=position[key];selected.append(pos);counts+=stack[pos]
            used=len(selected)
            if not used:
                for method in METHODS:
                    for version in refs or {'unavailable':None}:
                        samples[k,method,version].append((None,None,0))
                continue
            # Stable ID tie-breaking prevents input-order artefacts at identical membership.
            best=min(selected,key=lambda pos:(-float(affinity[pos,selected].sum()),available[pos]['id']))
            outputs={'mv50':2*counts>=used,'mv_strict':2*counts>used,'medoid':stack[best]}
            for method,mask in outputs.items():
                last=previous.get(method)
                change=None if last is None else (1-iou(mask,last) if np.any(mask|last) else 0.)
                previous[method]=mask.copy()
                for version,ref in (refs or {'unavailable':None}).items():
                    samples[k,method,version].append((iou(mask,ref) if ref is not None else None,change,used))
    return [dict(k=k,method=method,reference=version,replicates=len(v),
                 **{'iou_'+a:b for a,b in stats([x[0] for x in v]).items()},
                 change_mean=stats([x[1] for x in v])['mean'],
                 used_k_mean=float(np.mean([x[2] for x in v])),used_k_min=min(x[2] for x in v),
                 used_k_max=max(x[2] for x in v)) for (k,method,version),v in sorted(samples.items())]


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def write_csv(path,rows):
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def coverage(panel):
    workers=defaultdict(list);images=[];rows=[]
    for im in panel['images']:
        for r in im['annotations']:
            row=dict(image=im['code'],building=im['building'],scene=im['scene'],**r)
            rows.append(row);workers[r['worker']].append(row)
        for condition in sorted({r['condition'] for r in im['annotations']}):
            subset=[r for r in im['annotations'] if r['condition']==condition]
            images.append(dict(image=im['code'],building=im['building'],condition=condition,
                               total=len(subset),retained=sum(r['cleaning']=='retained' for r in subset),
                               independent_consensus=sum(r['independent'] and r['consensus_eligible'] for r in subset),
                               quality_candidates=sum(r['quality_candidate'] for r in subset),**im['scene']))
    people=[dict(worker=w,records=len(rs),images=len({r['image'] for r in rs}),
                 buildings=len({r['building'] for r in rs}),
                 cleaning=dict(Counter(r['cleaning'] for r in rs)),
                 conditions=dict(Counter(r['condition'] for r in rs))) for w,rs in sorted(workers.items())]
    summary=dict(annotations=len(rows),images=sum(bool(i['annotations']) for i in panel['images']),
                 reference_only_images=sum(not i['annotations'] for i in panel['images']),workers=len(workers),
                 buildings=len({im['building'] for im in panel['images']}),
                 cleaning=dict(Counter(r['cleaning'] for r in rows)),
                 conditions=dict(Counter(r['condition'] for r in rows)),
                 independent_consensus=sum(r['independent'] and r['consensus_eligible'] for r in rows),
                 quality_candidates=sum(r['quality_candidate'] for r in rows))
    return summary,images,people


def run(panel,out,seeds=100,width=512, *, include_legacy_proxy=False):
    validate_panel(panel);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    height=width//2
    summary,image_rows,people=coverage(panel)
    write_csv(out/'image_coverage.csv',image_rows);write_csv(out/'worker_coverage.csv',people)
    quality=[];geometry=[];endpoints=[];replays=[];failures=[]
    for number,im in enumerate(panel['images'],1):
        gs={};mask_failures={};masks={'declared_column_wall_band':{},'legacy_x_envelope_continuous':{},'legacy_x_envelope_pixel_center':{}}
        relevant=[r for r in im['annotations'] if r['cleaning'] in ('retained','retained_pending')]
        objects=relevant+im['references']
        for r in objects:
            g=reconstruct(r);gs[r['id']]=g
            geometry.append(dict(image=im['code'],id=r['id'],kind='annotation' if 'worker' in r else r['version'],
                                 **candidate_geometry(r,g)))
            for representation in masks:
                try:
                    if representation=='declared_column_wall_band':mask=declared_column_wall_mask(g,width,height)
                    else:
                        if r['points'] is None:raise ValueError('pairing_unavailable')
                        convention='continuous' if representation.endswith('_continuous') else 'pixel_center'
                        mask=wall_mask(np.asarray(r['points']).reshape(-1,2,2),width,height,coordinate_convention=convention)
                    masks[representation][r['id']]=mask
                except ValueError as e:
                    mask_failures[representation,r['id']]=str(e)
                    failures.append(dict(image=im['code'],id=r['id'],representation=representation,reason=str(e)))
        for r in relevant:
            for ref in im['references']:
                base=dict(image=im['code'],building=im['building'],id=r['id'],worker=r['worker'],
                          condition=r['condition'],reference=ref['version'],quality_candidate=r['quality_candidate'],
                          independent=r['independent'],order_status=r['order_status'])
                for representation,cache in masks.items():
                    ok=r['id'] in cache and ref['id'] in cache
                    metrics=compare_regions(cache[r['id']],cache[ref['id']]) if ok else dict(iou=None,
                        reason=';'.join(key+':'+mask_failures[representation,key] for key in (r['id'],ref['id']) if key not in cache))
                    metrics={k:v for k,v in metrics.items() if not k.startswith('scores_')}
                    if representation=='declared_column_wall_band':metrics['declared_column_wall_band_iou']=metrics.get('iou')
                    quality.append(dict(**base,representation=representation,status='ok' if ok else 'unavailable',**metrics))
                a,b=gs[r['id']],gs[ref['id']]
                available=all(g['representations']['declared_footprint']['status']=='ok' for g in (a,b))
                metrics=bev_range_metrics(a['floor'],b['floor']) if available else dict(
                    status='unavailable',bev_range_iou=None,
                    reason=';'.join(g['representations']['declared_footprint']['reason'] for g in (a,b)
                                    if g['representations']['declared_footprint']['reason']))
                quality.append(dict(**base,representation='bev_range',**metrics))
                if include_legacy_proxy:
                    metrics=polygon_metrics(a['floor'],b['floor'],float(np.median(a['heights'])),float(np.median(b['heights']))) if a['status']==b['status']=='ok' else dict(
                        status='unavailable',volume_iou=None,reason='surface_reconstruction_unavailable')
                    proxy=metrics['volume_iou']
                    quality.append(dict(**base,representation='historical_vertex_median_prism_proxy',
                        status=metrics['status'],reason=metrics.get('reason'),prism_surrogate_iou=proxy))
        for condition in sorted({r['condition'] for r in relevant}):
            group=sorted([r for r in relevant if r['condition']==condition and r['independent'] and r['consensus_eligible']],key=lambda r:r['id'])
            if not group:continue
            for representation,cache in masks.items():
                available=[r for r in group if r['id'] in cache]
                for method in ('mv50','mv_strict','medoid','em_correct_probability','greedy_empirical','staple'):
                    result=aggregate(np.stack([cache[r['id']] for r in available]),method) if available else dict(status='unavailable',mask=None,reason='no_available_masks')
                    for ref in im['references']:
                        ok=result.get('mask') is not None and ref['id'] in cache
                        metrics=compare_regions(result['mask'],cache[ref['id']]) if ok else {}
                        metrics={k:v for k,v in metrics.items() if not k.startswith('scores_')}
                        endpoints.append(dict(image=im['code'],condition=condition,representation=representation,
                                              method=method,reference=ref['version'],k=len(group),used_k=len(available),
                                              algorithm_status=result['status'],evaluation_status='ok' if ok else 'unavailable',
                                              reason=result.get('reason'),**metrics))
                if representation=='declared_column_wall_band' and seeds:
                    refs={r['version']:cache[r['id']] for r in im['references'] if r['id'] in cache}
                    replays.extend(dict(image=im['code'],building=im['building'],condition=condition,representation=representation,
                                        **row) for row in summarize_replays(group,{r['id']:cache[r['id']] for r in available},refs,seeds))
        if number%10==0:print(f'images {number}/{len(panel["images"])}',flush=True)
    for name,rows in [('individual_quality',quality),('geometry_diagnostics',geometry),('consensus_endpoints',endpoints),
                      ('replay_summary',replays),('representation_failures',failures)]:write_csv(out/(name+'.csv'),rows)
    summary.update(schema='research_round_baseline_v2',raster=[width,height],replay_seeds=seeds,
                   historical_vertex_median_proxy_requested=include_legacy_proxy,
                   quality_rows=len(quality),endpoint_rows=len(endpoints),replay_rows=len(replays),
                   quality_status=dict(Counter((r['representation']+':'+r['status']) for r in quality)),
                   endpoint_status=dict(Counter(r['algorithm_status'] for r in endpoints)),
                   failures=dict(Counter(r['representation']+':'+r['reason'] for r in failures)),
                   interpretation='GT-relative diagnostics; not worker ability, semantic correctness, difficulty labels or an identified noise decomposition',
                   coordinate_conventions={'declared_column_wall_band':'continuous x/W viewer candidate; raster cell centres; unknown roof',
                                           'legacy_x_envelope_continuous':'continuous x/W and x sorting',
                                           'legacy_x_envelope_pixel_center':'historical +0.5 pixel-centre convention and x sorting'},
                   source_manifest=panel.get('source_manifest'))
    write_json(out/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=100);parser.add_argument('--width',type=int,default=512)
    parser.add_argument('--include-legacy-proxy',action='store_true',help='历史顶点中位墙高代理，非真实体积或主分数')
    args=parser.parse_args()
    if args.seeds<0 or args.width<4 or args.width%2:parser.error('nonnegative seeds and positive even width required')
    panel=json.loads(args.input.read_text(encoding='utf-8'))
    print(json.dumps(run(panel,args.out,args.seeds,args.width,include_legacy_proxy=args.include_legacy_proxy),ensure_ascii=False))


if __name__=='__main__':main()
