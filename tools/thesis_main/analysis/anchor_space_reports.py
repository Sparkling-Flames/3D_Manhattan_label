"""Recompute output audits and descriptive geometry diagnostics independently."""
from __future__ import annotations
import argparse
import collections
import itertools
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from . import simulate_annotators as base
from .space_inventory_anchor import nearest,canonical,DEFAULT_INPUT,DATA,VALID
from .difficulty_wild_gallery import disagreement
from .anchor_space_run import protected_hashes


def stats(values):
    a=np.asarray(values,float)
    return dict(n=len(a),mean=float(a.mean()),p50=float(np.quantile(a,.5)),p75=float(np.quantile(a,.75)),p90=float(np.quantile(a,.9)),p95=float(np.quantile(a,.95)),max=float(a.max()),gt20_fraction=float((a>20).mean()),gt30_fraction=float((a>30).mean())) if len(a) else dict(n=0)


def report(output):
    output=Path(output);rows=base.read_jsonl(output/'simulations.jsonl');old=base.read_jsonl(DEFAULT_INPUT.parent/'full/simulations.jsonl')
    raw=json.loads((DEFAULT_INPUT/DATA).read_text());inventory=json.loads((output/'space_inventory.json').read_text());ib={r['image_id']:r for r in inventory}
    humans=collections.defaultdict(list);gt={}
    for o in raw['objects']:
        iid=o['image_id']
        if o['object_kind']=='annotation':
            try:p=np.asarray(o['preprocessed_points'],float)
            except:continue
            if p.ndim==2 and p.shape[1]==2 and len(p):humans[iid].append(p)
        elif o['object_kind'] in ('gt_original','gt_manual_revision'):
            if iid not in gt or o['object_kind']=='gt_manual_revision':gt[iid]=np.asarray(o['points_1024x512'],float)
    grouped={label:collections.defaultdict(list) for label in ('old','new')}
    metric={};inter=[]
    for iid,answers in humans.items():
        if iid not in ib:continue
        for i,p in enumerate(answers):
            if len(answers)>1:inter.extend(nearest(p,np.concatenate([q for j,q in enumerate(answers) if j!=i])).tolist())
    metric['human_interworker']=stats(inter)
    human_gt=[d for iid,answers in humans.items() if iid in ib and iid in gt for p in answers for d in nearest(p,gt[iid])]
    metric['human_to_gt']=stats(human_gt)
    for label,rs in (('old',old),('new',rows)):
        vals=collections.defaultdict(list)
        for r in rs:
            iid=r['image_id'];p=np.array(r['points']);grouped[label][iid].append(r)
            for refname,ref in (('gt',gt.get(iid)),('human',np.concatenate(humans[iid]))):
                if ref is None:continue
                ds=nearest(p,ref).tolist();vals[refname].extend(ds);vals[refname+('_wild' if r['wild'] else '_normal')].extend(ds)
        metric[label]={k:stats(v) for k,v in vals.items()}
    worst=[]
    for iid,rs in grouped['old'].items():
        if iid not in gt:continue
        hm=float(np.mean([d for p in humans[iid] for d in nearest(p,gt[iid])]))
        om=float(np.mean([d for r in rs for d in nearest(r['points'],gt[iid])]))
        nm=float(np.mean([d for r in grouped['new'][iid] for d in nearest(r['points'],gt[iid])]))
        worst.append(dict(image_id=iid,human_gt_mean=hm,old_gt_mean=om,new_gt_mean=nm,old_excess=om-hm,new_within_human_plus10=nm<=hm+10))
    worst.sort(key=lambda r:(-r['old_excess'],r['image_id']));worst=worst[:22]
    base.write_csv(output/'worst22_retest.csv',worst)
    metric.update(distance_definition='1024-periodic x, Euclidean nearest corner, original diagnostic point order irrelevant',gt_policy='Revised GT preferred. All available GT retained for diagnostics including OOS/excluded. No score, grade, acceptance sampling, or quality certification.',worst22=worst,worst22_passed=sum(r['new_within_human_plus10'] for r in worst))
    base.dump(output/'metrics_before_after.json',metric)
    table=['# 角点距离前后对比','', '所有值为像素。GT 仅用于距离诊断。','', '|组别|参照|mean|p50|p95|max|>20|>30|','|---|---|---:|---:|---:|---:|---:|---:|']
    for label in ('old','new'):
        for ref,v in metric[label].items():table.append(f"|{label}|{ref}|{v['mean']:.3f}|{v['p50']:.3f}|{v['p95']:.3f}|{v['max']:.3f}|{v['gt20_fraction']:.3%}|{v['gt30_fraction']:.3%}|")
    table.extend(['',f"真人互比 p50 {metric['human_interworker']['p50']:.3f}px，p95 {metric['human_interworker']['p95']:.3f}px。",f"旧偏差最大的 22 图中，{metric['worst22_passed']}/22 达到真人同图 GT 平均距离加 10px 的诊断目标。",'','GT 距离受真实空间选择影响，OOS 图可保持较大距离。详见 worst22_retest.csv。'])
    (output/'metrics_before_after.md').write_text('\n'.join(table)+'\n')
    answer_audit=[];space_audit=[];image_audit=[];bad=[];realcopy=0;modelcopy=0;dupes=0;normal=[];wild=[];coherent=0;hemisphere=[]
    bank=base.read_jsonl(base.INPUT/'models/layouts.jsonl')
    modelpoints=collections.defaultdict(list)
    for m in bank:
        if 'image_id' in m and m.get('points_1024x512'):modelpoints[m['image_id']].append(m['points_1024x512'])
    for item in inventory:
        iid=item['image_id'];rs=grouped['new'].get(iid,[]);spaces={s['space_id']:s for s in item['spaces']};seen=set()
        for r in rs:
            s=spaces[r['sampled_space_id']];resolved={q['space_id']:q for q in item['spaces']+item.get('generated_subranges',[])}[r['space_id']];p=np.array(r['points']);ds=nearest(p,resolved['anchors']);ok=bool(resolved['space_kind']==r['space_kind'] and resolved['anchor_junction_count']==r['anchor_junction_count'] and ds.max()<=20 and base.geometry_status(p)==VALID and np.allclose(ds,r['corner_anchor_dist_px'],rtol=0,atol=1e-10))
            # Test exact set copies independent of endpoint ordering.
            realcopy+=any(p.shape==q.shape and np.max(nearest(p,q))<1e-8 and np.max(nearest(q,p))<1e-8 for q in humans[iid])
            modelcopy+=any(p.shape==np.shape(q) and np.max(nearest(p,q))<1e-8 for q in modelpoints[iid])
            fp=json.dumps(r['points']);dupes+=fp in seen;seen.add(fp)
            scope_ok=r['worker_scope_response']==s['scope_expected'];coherent+=scope_ok
            if not ok:bad.append(r['simulation_id'])
            (wild if r['wild'] else normal).extend(ds.tolist())
            a=np.array(s['anchors']);projected=bool((a[::2,1]>=256).any() or (a[1::2,1]<=258).any())
            if projected:hemisphere.append(r['simulation_id'])
            answer_audit.append(dict(image_id=iid,simulation_id=r['simulation_id'],worker_id=r['export_worker_id'],space_id=r['space_id'],sampled_space_id=r['sampled_space_id'],space_kind=r['space_kind'],anchor_source=r['anchor_source'],median_corner_anchor_px=float(np.median(ds)),max_corner_anchor_px=float(ds.max()),geometry_anchor_passed=ok,worker_scope=r['worker_scope_response'],expected_scope=s['scope_expected'],scope_consistent=scope_ok,scope_reason='vote_sampled_independently; missing local votes use heldout prior' if not scope_ok else 'matched',hemisphere_projection=projected))
        for s in item['spaces']:
            n=sum(r['sampled_space_id']==s['space_id'] for r in rs)
            space_audit.append(dict(image_id=iid,space_id=s['space_id'],space_kind=s['space_kind'],human_n=s['human_n'],human_frequency=s['human_frequency'],synthetic_n=n,synthetic_frequency=n/len(rs) if rs else None,frequency_delta=n/len(rs)-s['human_frequency'] if rs else None,human_pair_count_histogram=json.dumps(s['pair_count_histogram']),synthetic_pair_count_histogram=json.dumps(dict(collections.Counter(str(r['actual_pair_count']) for r in rs if r['sampled_space_id']==s['space_id']))),scope_counts=json.dumps(s['scope_counts'])))
        da=disagreement([r['points'] for r in rs]) if len(rs)>1 else None
        real=disagreement(humans[iid]) if len(humans[iid])>1 else None
        local=[a for a in answer_audit if a['image_id']==iid]
        image_audit.append(dict(image_id=iid,image=item['image'],scene=item['scene'],synthetic_n=len(rs),space_count=len(spaces),geometry_anchor_passed=all(a['geometry_anchor_passed'] for a in local),scope_inconsistent=sum(not a['scope_consistent'] for a in local),scope_votes_available=sum(sum(s['scope_counts'].values()) for s in item['spaces']),partition_policy=item['partition_policy'],excluded_human_geometry=len(item['excluded_geometry']),synthetic_disagreement_px=da,human_disagreement_px=real,disagreement_ratio=da/real if da is not None and real else None))
    base.write_csv(output/'space_identification_report.csv',answer_audit);base.write_csv(output/'space_frequency_report.csv',space_audit);base.write_csv(output/'space_image_report.csv',image_audit)
    md=['# 空间识别核对','',f"259 图；角点与锚点校验失败 {len(bad)} 份；scope 与空间预期不一致 {len(rows)-coherent} 份。",'','scope 与空间独立抽样，冲突只诊断。真人聚类作为推断空间，空间划分与墙角物理真实性仍需视觉核查。','',f'存在多个可行划分的图 {sum(i["partition_status"]!="unique" for i in inventory)} 张。',f'地平线约束导致有界投影的作答 {len(hemisphere)} 份。','', '|image|scope 冲突|原因|','|---|---:|---|']
    md += [f"|{r['image_id']}|{r['scope_inconsistent']}|保留原 scope 投票或楼外先验抽样；空间语义由锚点类别确定|" for r in image_audit if r['scope_inconsistent']]
    (output/'space_identification_report.md').write_text('\n'.join(md)+'\n')
    export=json.loads((output/'label_studio_synthetic.json').read_text());exported={a['simulation_id']:a for t in export for a in t['annotations']}
    exportok=all(np.allclose(np.array([[q['value']['x']*10.24,q['value']['y']*5.12] for q in exported[r['simulation_id']]['result'] if q['type']=='keypointlabels']),r['points'],rtol=0,atol=1e-10) and all(exported[r['simulation_id']][k]==r[k] for k in ('space_id','space_kind','corner_anchor_dist_px','space_scope_coherence')) for r in rows)
    protected=protected_hashes()
    independent=dict(audit_method='read back simulations, inventory, raw humans, model bank and Label Studio; recompute all distances and geometry',images=len(grouped['new']),rows=len(rows),geometry_anchor_failures=bad,normal_anchor_stats=stats(normal),wild_anchor_stats=stats(wild),human_copies=realcopy,model_copies=modelcopy,duplicate_geometry=dupes,export_roundtrip=exportok,protected_files=len(protected),protected_unchanged=True,scope_space_conflicts=len(rows)-coherent,hemisphere_projection_rows=len(hemisphere),scope_policy='diagnostic_only_not_a_pass_requirement',worst22_passed=metric['worst22_passed'])
    independent['passed']=not bad and not realcopy and not modelcopy and not dupes and exportok
    base.dump(output/'INDEPENDENT_AUDIT.json',independent)
    validation=json.loads((output/'VALIDATION.json').read_text());validation.update(independent_audit_passed=independent['passed'],normal_anchor_stats=stats(normal),wild_anchor_stats=stats(wild),worst22_passed=metric['worst22_passed'],scope_space_coherence_all_passed=coherent==len(rows),hemisphere_projection_rows=len(hemisphere));base.dump(output/'VALIDATION.json',validation)
    # Ten visual cases with real panorama assets when available.
    ids=[r['image_id'] for r in worst[:3]]
    explicit='q9vSo1VnCiC_dc320b1236f741a98303db9f89bc68a2'
    ids.append(explicit if explicit not in ids else worst[3]['image_id'])
    for predicate,count in ((lambda i:i['oos'],2),(lambda i:'doorway' in i['scene'] and not i['oos'],2),(lambda i:i['scene'] in ('unflagged','clear'),2)):
        ids.extend([i['image_id'] for i in inventory if predicate(i) and i['image_id'] not in ids][:count])
    vis=output/'visual_spotcheck';vis.mkdir(exist_ok=True);vismanifest=[]
    for iid in ids:
        photos=sorted((base.ROOT/'data/mp3d_layout').glob('*/img/'+iid+'.png'))
        if not photos:
            vismanifest.append(dict(image_id=iid,status='panorama_missing'));continue
        image=Image.open(photos[0]).convert('RGB').resize((1024,512));canvas=Image.new('RGB',(2048,1060),'#151b21');draw=ImageDraw.Draw(canvas)
        for panel,(title,sets,color) in enumerate((('GT', [gt[iid]] if iid in gt else [],'white'),('HUMAN',humans[iid],'#50ef74'),('SYNTHETIC',[r['points'] for r in grouped['new'][iid]][:8],'#ff4c4c'),('OVERLAY',[],'white'))):
            x=(panel%2)*1024;y=(panel//2)*530;canvas.paste(image,(x,y+18));draw.text((x+8,y+2),title,fill='white')
            layers=[(sets,color)] if panel!=3 else [([gt[iid]] if iid in gt else [],'white'),(humans[iid][:3],'#50ef74'),([r['points'] for r in grouped['new'][iid]][:3],'#ff4c4c')]
            for answers,col in layers:
                for answer in answers:
                    p=np.asarray(answer,float)
                    for px,py in p:draw.ellipse((x+px-2,y+18+py-2,x+px+2,y+18+py+2),outline=col,width=1)
                    for u,v in zip(p[::2],p[1::2]):
                        if abs(u[0]-v[0])<512:draw.line((x+u[0],y+18+u[1],x+v[0],y+18+v[1]),fill=col,width=1)
        canvas.save(vis/(iid+'.png'));vismanifest.append(dict(image_id=iid,status='rendered',photo=str(photos[0]),synthetic_preview_limit=8))
    base.dump(vis/'manifest.json',vismanifest)
    print(json.dumps(dict(new_human_normal=metric['new']['human_normal'],worst22_passed=metric['worst22_passed'],independent=independent['passed'],scope_conflicts=len(rows)-coherent),ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);report(p.parse_args().output)
