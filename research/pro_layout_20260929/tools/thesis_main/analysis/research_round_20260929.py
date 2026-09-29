"""Latest-data numerical baseline. Inputs are explicit derived records, never raw exports.

No GT enters aggregation. No point deletion, reordering, geometric fitting or worker
classification is performed. Lengths use a common camera height of one, not metres.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path

import numpy as np
from shapely.geometry import Point, Polygon

from tools.label_studio.panorama_studio.geometry import analyze
from tools.thesis_main.analysis.consensus_region_20260923 import wall_mask, aggregate
from tools.thesis_main.analysis.layout_metric_probe_20260926 import compare_regions, polygon_metrics

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


def reconstruct(record):
    """Continuous x/W convention used by the reviewed 3D viewer; no simplification."""
    if record['points'] is None:return dict(status='unavailable',reason='pairing_unavailable')
    p=np.asarray(record['points'],float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        return dict(status='unavailable',reason='invalid_point_array')
    pairs=p.reshape(-1,2,2)
    payload=dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=[
        dict(top=dict(zip(('x','y'),a)),bottom=dict(zip(('x','y'),b))) for a,b in pairs])
    try:raw=analyze(payload,compute_fit=False)['raw']
    except ValueError as e:return dict(status='unavailable',reason=str(e))
    if not raw['surface_valid']:
        return dict(status='unavailable',reason=';'.join(raw['issues']))
    floor=np.asarray(raw['floor'])[:,[0,2]];height=np.asarray(raw['ceiling'])[:,1]+1
    return dict(status='ok',reason=None,floor=floor,heights=height,metrics=raw['metrics'],
                issues=raw['issues'],pair_count=len(pairs))


def candidate_geometry(record, geometry=None):
    g=reconstruct(record) if geometry is None else geometry
    if g['status']!='ok':return dict(status=g['status'],reason=g['reason'])
    p,h=g['floor'],g['heights'];poly=Polygon(p)
    lengths=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    angles=np.arctan2(*(np.roll(p,-1,axis=0)-p)[:,::-1].T)
    axis=np.radians(g['metrics']['heading_frame_deg'])
    residual=np.degrees(np.abs((angles-axis+np.pi/4)%(np.pi/2)-np.pi/4))
    return dict(status='ok',reason=None,pair_count=len(p),area_h2=float(poly.area),
                camera_inside=bool(poly.contains(Point(0,0))),
                direction_length_weighted_deg=float(np.average(residual,weights=lengths)),
                height_mad_relative=float(np.median(abs(h-np.median(h)))/np.median(h)),
                **g['metrics'])


def visible_wall_mask(g,width=512,height=256):
    """Nearest positive ray/wall intersection, top linearly interpolated in 3D.

    Walls use the supplied physical ring; non-star-shaped simple polygons work.
    Non-horizontal ceilings are a piecewise wall-top model, not a room volume.
    """
    if g['status']!='ok':raise ValueError(g['reason'])
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


def run(panel,out,seeds=100,width=512):
    validate_panel(panel);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    height=width//2
    summary,image_rows,people=coverage(panel)
    write_csv(out/'image_coverage.csv',image_rows);write_csv(out/'worker_coverage.csv',people)
    quality=[];geometry=[];endpoints=[];replays=[];failures=[]
    for number,im in enumerate(panel['images'],1):
        gs={};masks={'explicit_visible':{},'legacy_x_envelope':{}}
        relevant=[r for r in im['annotations'] if r['cleaning'] in ('retained','retained_pending')]
        objects=relevant+im['references']
        for r in objects:
            g=reconstruct(r);gs[r['id']]=g
            geometry.append(dict(image=im['code'],id=r['id'],kind='annotation' if 'worker' in r else r['version'],
                                 **candidate_geometry(r,g)))
            for representation in masks:
                try:
                    if representation=='explicit_visible':mask=visible_wall_mask(g,width,height)
                    else:
                        if r['points'] is None:raise ValueError('pairing_unavailable')
                        mask=wall_mask(np.asarray(r['points']).reshape(-1,2,2),width,height)
                    masks[representation][r['id']]=mask
                except ValueError as e:
                    failures.append(dict(image=im['code'],id=r['id'],representation=representation,reason=str(e)))
        for r in relevant:
            for ref in im['references']:
                base=dict(image=im['code'],building=im['building'],id=r['id'],worker=r['worker'],
                          condition=r['condition'],reference=ref['version'],quality_candidate=r['quality_candidate'],
                          independent=r['independent'],order_status=r['order_status'])
                for representation,cache in masks.items():
                    ok=r['id'] in cache and ref['id'] in cache
                    metrics=compare_regions(cache[r['id']],cache[ref['id']]) if ok else {}
                    metrics={k:v for k,v in metrics.items() if not k.startswith('scores_')}
                    quality.append(dict(**base,representation=representation,status='ok' if ok else 'unavailable',**metrics))
                a,b=gs[r['id']],gs[ref['id']]
                if a['status']=='ok' and b['status']=='ok':
                    metrics=polygon_metrics(a['floor'],b['floor'],float(np.median(a['heights'])),float(np.median(b['heights'])))
                    metrics.pop('scores',None)
                    metrics['prism_surrogate_iou']=metrics.pop('volume_iou')
                    quality.append(dict(**base,representation='bev_and_prism_proxy',**metrics))
                else:quality.append(dict(**base,representation='bev_and_prism_proxy',status='unavailable'))
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
                if representation=='explicit_visible' and seeds:
                    refs={r['version']:cache[r['id']] for r in im['references'] if r['id'] in cache}
                    replays.extend(dict(image=im['code'],building=im['building'],condition=condition,representation=representation,
                                        **row) for row in summarize_replays(group,{r['id']:cache[r['id']] for r in available},refs,seeds))
        if number%10==0:print(f'images {number}/{len(panel["images"])}',flush=True)
    for name,rows in [('individual_quality',quality),('geometry_diagnostics',geometry),('consensus_endpoints',endpoints),
                      ('replay_summary',replays),('representation_failures',failures)]:write_csv(out/(name+'.csv'),rows)
    summary.update(schema='research_round_baseline_v1',raster=[width,height],replay_seeds=seeds,
                   quality_rows=len(quality),endpoint_rows=len(endpoints),replay_rows=len(replays),
                   quality_status=dict(Counter((r['representation']+':'+r['status']) for r in quality)),
                   endpoint_status=dict(Counter(r['algorithm_status'] for r in endpoints)),
                   failures=dict(Counter(r['representation']+':'+r['reason'] for r in failures)),
                   interpretation='GT-relative diagnostics; not worker ability, semantic correctness, difficulty labels or an identified noise decomposition',
                   coordinate_conventions={'explicit_visible':'continuous x/W as reviewed viewer; raster rays at cell centres',
                                           'legacy_x_envelope':'historical +0.5 pixel-centre convention and x sorting'},
                   source_manifest=panel.get('source_manifest'))
    write_json(out/'summary.json',summary)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--seeds',type=int,default=100);parser.add_argument('--width',type=int,default=512)
    args=parser.parse_args()
    if args.seeds<0 or args.width<4 or args.width%2:parser.error('nonnegative seeds and positive even width required')
    panel=json.loads(args.input.read_text(encoding='utf-8'))
    print(json.dumps(run(panel,args.out,args.seeds,args.width),ensure_ascii=False))


if __name__=='__main__':main()
