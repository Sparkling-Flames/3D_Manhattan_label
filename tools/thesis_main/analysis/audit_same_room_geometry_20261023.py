"""流式独立核对全部原生票账及对应距离；保留逐池结果，避免载入全部票账。"""
from pathlib import Path
from collections import Counter
from statistics import median
import argparse
import gzip
import json
import math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon


def main(root, out):
    out.mkdir(parents=True,exist_ok=True)
    fields=['team_key','pool_id','member_workers','member_object_ids','k','minimum_support','nodes',
            'identity_groups_n','geometry_shard','geometry_line_1based','complete_evaluable','score_status',
            'iou_2d','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
    s=pd.read_csv(root/'native_endpoints/ENDPOINT_SCALARS.csv.gz',usecols=fields).set_index('team_key')
    comparisons=pd.read_csv(root/'geometry/UNIQUE_GEOMETRY_COMPARISONS.csv.gz',low_memory=False)
    snapshot=next((root/'engine/frozen_repo').glob('**/fusion/INPUT_SNAPSHOT.json.gz'))
    with gzip.open(snapshot,'rt',encoding='utf-8') as f:
        pools={p['pool_id']:p for p in json.load(f)['images']}
    checked=set();counts=Counter();pool_results=[];maxerr=Counter()
    for pool_no,(pid,scalar) in enumerate(s.groupby('pool_id',sort=True)):
        scal=scalar.to_dict('index');geom={};pool_count=Counter()
        ref=pools[pid]['reference'];rp=np.array(ref['points_1024x512'],float)
        phi=(rp[1::2,0]/1024-.5)*2*np.pi;r=1/np.tan((rp[1::2,1]/512-.5)*np.pi)
        reference=Polygon(np.c_[r*np.sin(phi),-r*np.cos(phi)])
        for shard in sorted((root/'native_endpoints/parts'/pid).glob('*.jsonl.gz')):
            rel=shard.relative_to(root/'native_endpoints').as_posix()
            with gzip.open(shard,'rt',encoding='utf-8') as f:
                for line_no,line in enumerate(f,1):
                    row=json.loads(line);key=row['team_key'];ss=scal[key]
                    assert key not in checked;checked.add(key)
                    assert row['pool_id']==pid and ss['geometry_shard']==rel and ss['geometry_line_1based']==line_no
                    assert '|'.join(row['member_workers'])==ss['member_workers']
                    assert '|'.join(row['member_object_ids'])==ss['member_object_ids']
                    assert row['complete_evaluable']==ss['complete_evaluable'] and row['score_status']==ss['score_status']
                    st=row['full_state'];n=int(ss['k']);threshold=math.ceil(n/2)
                    assert st['n']==n and st['minimum_support']==ss['minimum_support']==threshold
                    groups=st['identity_groups'];nodes=st['node_consensus']['nodes']
                    assert len(groups)==ss['identity_groups_n'] and len(nodes)==ss['nodes']
                    node_by_id={x['feature_id']:x for x in nodes}
                    assert {g['feature_id'] for g in groups if g['selected']}==set(node_by_id)
                    workers=set(row['member_workers']);objects=set(row['member_object_ids'])
                    assert {a['worker'] for a in st['assignments']}==workers
                    for g in groups:
                        voters={m['worker'] for m in g['members']}
                        assert len(voters)==len(g['members'])==g['support']
                        assert voters<=workers and {m['id'] for m in g['members']}<=objects
                        assert g['selected']==(len(voters)>=threshold)
                        if g['selected']:
                            node=node_by_id[g['feature_id']]
                            assert node['support']==g['support'] and node['points']==g['center']
                        # 每原生分片首队核坐标中位数，其余所有队核票数、入选和几何。
                        if line_no==1 and g['center'] is not None:
                            p=np.array([m['points'] for m in g['members']],float)
                            dx=(p[:,0,0]-p[0,0,0]+512)%1024-512
                            assert np.ptp(dx)<512-1e-9
                            x=(p[0,0,0]+median(dx))%1024
                            center=np.array([[x,median(p[:,0,1])],[x,median(p[:,1,1])]])
                            err=float(np.abs(center-np.array(g['center'])).max())
                            assert err<1e-8,(key,g['feature_id'],err)
                            counts['median_groups_sampled']+=1
                        counts['identity_groups']+=1
                    candidate=st['candidate'];gg=row['geometry']
                    if gg is not None:
                        assert gg==candidate
                    points=(gg or {}).get('points');floor=(gg or {}).get('footprint')
                    if points is not None:
                        assert points==[p for fid in gg['feature_ids'] for p in node_by_id[fid]['points']]
                    geom[key]=(np.array(points,float) if points is not None else None, bool(row['complete_evaluable']))
                    if floor is not None and len(floor)>=3:
                        p=np.asarray(floor,float);edges=np.roll(p,-1,axis=0)-p;lens=np.linalg.norm(edges,axis=1)
                        if (lens>=1e-10).all():
                            angles=np.degrees(np.arctan2(np.abs(np.roll(edges,1,axis=0)[:,0]*edges[:,1]-np.roll(edges,1,axis=0)[:,1]*edges[:,0]),(np.roll(edges,1,axis=0)*edges).sum(1)))
                            values=[int((angles>5).sum()),int(((lens/lens.sum()<.04)&(angles>=15)&(np.roll(angles,-1)>=15)).sum()),int((angles<=5).sum())]
                            for c,v in zip(['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n'],values):
                                assert ss[c]==v,(key,c,ss[c],v)
                            counts['expression_endpoints']+=1
                    if row['complete_evaluable']:
                        pp=np.asarray(points,float);phi=(pp[1::2,0]/1024-.5)*2*np.pi
                        radius=1/np.tan((pp[1::2,1]/512-.5)*np.pi)
                        projected=np.c_[radius*np.sin(phi),-radius*np.cos(phi)]
                        assert np.allclose(projected,floor,atol=1e-8,rtol=1e-10)
                        polygon=Polygon(projected);assert polygon.is_valid
                        iou=polygon.intersection(reference).area/polygon.union(reference).area
                        err=abs(iou-ss['iou_2d']);maxerr['iou_2d']=max(maxerr['iou_2d'],err)
                        assert err<1e-8,(key,'iou_2d',iou,ss['iou_2d'])
                        counts['geometry_IoU_endpoints']+=1
                    pool_count[row['score_status']]+=1
        assert set(geom)==set(scalar.index)
        comp=comparisons[comparisons.pool_id.eq(pid)]
        groups={}
        for row in comp.itertuples():
            p,cp=geom[row.team_key_from];q,cq=geom[row.team_key_to]
            if p is None or q is None:
                assert row.status=='missing_connected_geometry';continue
            if not(cp and cq):assert row.status=='incomplete_geometry';continue
            if len(p)!=len(q):assert row.status=='different_corner_count';continue
            groups.setdefault(len(p)//2,[]).append(row)
        for corners,rows in groups.items():
            a=np.stack([geom[x.team_key_from][0] for x in rows]);b=np.stack([geom[x.team_key_to][0] for x in rows])
            def project(pp):
                rad=1/np.tan(np.pi*(pp[:,1::2,1]/512-.5));ph=2*np.pi*(pp[:,1::2,0]/1024-.5)
                bottom=np.stack([rad*np.sin(ph),-np.ones_like(rad),-rad*np.cos(ph)],axis=-1)
                top=bottom.copy();top[:,:,1]=rad*np.tan(np.pi*(.5-pp[:,::2,1]/512))
                return bottom,top
            ba,ta=project(a);bb,tb=project(b)
            def area(p):return .5*(p[:,:,0]*np.roll(p[:,:,2],-1,axis=1)-p[:,:,2]*np.roll(p[:,:,0],-1,axis=1)).sum(1)
            reverse=np.sign(area(ba))!=np.sign(area(bb));bb[reverse]=bb[reverse,::-1];tb[reverse]=tb[reverse,::-1]
            b=b.copy();b[reverse]=b[reverse].reshape(-1,corners,2,2)[:,::-1].reshape(-1,corners*2,2)
            def angle(p,q):
                dp=((p[:,:,None,0]-q[:,None,:,0]+512)%1024-512)*np.pi/512
                v1=((p[:,:,1]+.5)/512-.5)*np.pi;v2=((q[:,:,1]+.5)/512-.5)*np.pi
                h=np.sin((v1[:,:,None]-v2[:,None,:])/2)**2+np.cos(v1[:,:,None])*np.cos(v2[:,None,:])*np.sin(dp/2)**2
                return np.degrees(2*np.arcsin(np.sqrt(h.clip(0,1))))
            costs=np.maximum(angle(a[:,::2],b[:,::2]),angle(a[:,1::2],b[:,1::2]))
            ix=np.arange(corners);cyclic=np.stack([costs[:,ix,(ix+j)%corners].max(1) for j in ix],axis=1)
            shifts=cyclic.argmin(1);best=cyclic.min(1);gap=np.sort(cyclic,axis=1)[:,1]-best
            for j,row in enumerate(rows):
                assert row.status==('ambiguous_cyclic_match' if gap[j]<=1e-9 else 'unique_cyclic_candidate')
                assert abs(row.angle_deg-best[j])<1e-8 and row.shift==shifts[j] and bool(row.ring_reversed)==reverse[j]
            indices=(ix[None,:]+shifts[:,None])%corners
            bt=bb[np.arange(len(rows))[:,None],indices];tt=tb[np.arange(len(rows))[:,None],indices]
            for name,delta in [('bev',np.linalg.norm(bt-ba,axis=2)),('top',np.linalg.norm(tt-ta,axis=2))]:
                for suffix,values in [('mean_h',delta.mean(1)),('max_h',delta.max(1)),('p95_h',np.quantile(delta,.95,axis=1))]:
                    old=np.array([getattr(r,name+'_'+suffix) for r in rows]);good=gap>1e-9
                    err=np.abs(values[good]-old[good]);assert np.all(err<1e-8)
                    maxerr[name+'_'+suffix]=max(maxerr[name+'_'+suffix],float(err.max()) if len(err) else 0)
            counts['corresponding_pairs_recomputed']+=len(rows)
        counts['all_comparison_pairs']+=len(comp)
        pool_results.append(dict(pool_id=pid,endpoints=len(geom),geometry_pairs=len(comp),**pool_count))
        if pool_no%5==0:print('geometry pools',pool_no+1,'endpoints',len(checked),flush=True)
    assert checked==set(s.index)
    pd.DataFrame(pool_results).to_csv(out/'GEOMETRY_POOL_CHECKS.csv',index=False)
    receipt={'endpoints':len(checked),'geometry_shards':len(list((root/'native_endpoints/parts').rglob('*.jsonl.gz'))),**counts,'max_abs_errors':dict(maxerr)}
    (out/'GEOMETRY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.root,a.out)
