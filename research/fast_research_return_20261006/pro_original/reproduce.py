#!/usr/bin/env python3
"""Reproduce only the selected endpoints and the small diagnostic calculations.
No k/composition replay, source edits, point repair, threshold search or GT-based
candidate selection. Requires NumPy and Shapely >=2.
"""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np
from shapely.geometry import Polygon, Point, shape, mapping
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from arc_excerpt import Ring, Unsupported, footprint, TAU
from lee_excerpt import tile_consensus

N_COLUMNS=8192

def load(name: str) -> dict:
    return json.loads((ROOT/'inputs'/name).read_text(encoding='utf-8'))

def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def save_csv(path: Path, rows: list[dict]) -> None:
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys); writer.writeheader();writer.writerows(rows)

def compare_region(a, g) -> dict:
    inter=a.intersection(g).area
    return dict(iou=inter/(a.area+g.area-inter),missing_over_gt=g.difference(a).area/g.area,
                excess_over_gt=a.difference(g).area/g.area)

def angular_split(a: dict, g: dict) -> dict:
    try:
        ra,rg=Ring(a),Ring(g)
        u=(np.arange(N_COLUMNS)+.5)*TAU/N_COLUMNS
        d=(ra.evaluate(u)-rg.evaluate(u))*180/512
        return dict(status='ok',upper_mae_deg=float(abs(d[0]).mean()),
                    lower_mae_deg=float(abs(d[1]).mean()),
                    upper_signed_deg=float(d[0].mean()),lower_signed_deg=float(d[1].mean()),
                    upper_p95_deg=float(np.quantile(abs(d[0]),.95)),
                    lower_p95_deg=float(np.quantile(abs(d[1]),.95)))
    except Unsupported as e:
        return dict(status='unavailable',reason=str(e))

def valid_description(p) -> dict:
    return dict(valid=bool(p.is_valid),camera_inside=bool(p.contains(Point(0,0))),
                geometry_type=p.geom_type,
                hole_count=len(p.interiors) if p.geom_type=='Polygon' else None,
                boundary_node_count=len(p.exterior.coords)-1 if p.geom_type=='Polygon' else None)

def formula_control() -> dict:
    """One connected orthogonal footprint pair; integer unit cubes count volumes independently."""
    A={(0,0),(0,1),(1,0),(1,1)}
    G={(0,0),(0,1),(1,0),(2,0)}
    results=[]
    for ha,hg in [(2,2),(2,3)]:
        va={(x,y,z) for x,y in A for z in range(ha)}
        vg={(x,y,z) for x,y in G for z in range(hg)}
        direct=len(va&vg)/len(va|vg)
        inter=len(A&G)*min(ha,hg)
        formula=inter/(len(A)*ha+len(G)*hg-inter)
        assert direct==formula
        results.append(dict(height_a=ha,height_g=hg,bev_iou=len(A&G)/len(A|G),
                            direct_unit_cube_iou=direct,prism_formula_iou=formula))
    assert results[0]['bev_iou']==results[0]['direct_unit_cube_iou']
    return dict(status='passed',scope='one footprint pair, common floor, two height settings',
                formula='I*min(Ha,Hg)/(Aa*Ha+Ag*Hg-I*min(Ha,Hg))',results=results)

def run(out: Path) -> None:
    out.mkdir(parents=True,exist_ok=True)
    j=load('2t7_selected.json');g=footprint(j['reference'])[1]
    rows=[]; feats=[]
    for method in ['lee','exact','point']:
        p=shape(j['lee']['geometry']) if method=='lee' else footprint(j[method])[1]
        assert p.is_valid and p.contains(Point(0,0))
        d=compare_region(p,g)
        row=dict(method=method,area_h2=p.area,bev_iou=d['iou'],
                 missing_over_gt=d['missing_over_gt'],excess_over_gt=d['excess_over_gt'],
                 **valid_description(p))
        if method!='lee':
            row.update(angular_split(j[method],j['reference']))
            row['pair_count']=len(j[method]['points'])//2
        rows.append(row)
        feats.append(dict(type='Feature',properties={'method':method,'unit':'h'},geometry=mapping(p)))
    dump(out/'2t7_comparison.json',dict(image=j['image'],sampling_columns=N_COLUMNS,results=rows))
    dump(out/'2t7_complete.geojson',dict(type='FeatureCollection',features=feats))

    s=load('e9z19_selected.json'); rs=s['records'];ps=[Polygon(r['footprint']) for r in rs]
    assert len(rs)==24
    full=tile_consensus(rs)  # ONE existing full-pool endpoint, not a replay experiment.
    mv=full['regions']['mv50']
    # GT is not passed to this selection. Exactly one original complete response is selected.
    scores=np.array([np.mean([compare_region(a,b)['iou'] for k,b in enumerate(ps) if k!=i])
                     for i,a in enumerate(ps)])
    im=int(scores.argmax());ci=[r['id'] for r in rs].index('R01301');candidate=ps[ci]
    refs={r['version']:Polygon(r['footprint']) for r in s['references']}
    scope_rows=[]
    for name,p in [('observed_medoid',ps[im]),('MV50',mv),('scope_R01301',candidate)]:
        assert p.is_valid and p.contains(Point(0,0))
        scope_rows.append(dict(name=name,area_h2=p.area,geometry=mapping(p),**valid_description(p),
                               references={k:compare_region(p,g) for k,g in refs.items()}))
    outside=candidate.difference(mv);support=full['mesh']['votes'].sum(0)
    hist={int(k):0. for k in sorted(set(support))}
    for t,k in zip(full['mesh']['tiles'],support):hist[int(k)]+=t.intersection(outside).area
    result=dict(image=s['image'],n=24,threshold=12,rule='2*support >= N',
                medoid_id=rs[im]['id'],medoid_worker=rs[im]['worker'],
                medoid_rule='maximum mean pairwise BEV IoU to the other 23 observed submissions; no GT input',
                medoid_mean_iou=float(scores[im]),
                medoid_ranking=[dict(id=rs[i]['id'],mean_iou=float(scores[i])) for i in np.argsort(-scores)],
                results=scope_rows,candidate_outside_consensus_area_h2=outside.area,
                candidate_outside_consensus_support_area=hist,
                candidate_outside_consensus_single_vote_share=hist[1]/outside.area,
                candidate_iou_to_consensus=compare_region(candidate,mv)['iou'],warnings=full['warnings'])
    dump(out/'e9z19_comparison.json',result)
    dump(out/'e9z19_complete.geojson',dict(type='FeatureCollection',features=[
        dict(type='Feature',properties={'method':r['name'],'unit':'h'},geometry=r['geometry']) for r in scope_rows]))
    dump(out/'e9z19_complete_layouts.json',dict(observed_medoid=rs[im],scope_candidate=rs[ci],
         mv50_range=mapping(mv),mv50_upper_boundary_status='not_provided_by_BEV_route',
         note='Original complete responses retained. No original polygon was edited. No height or corner was added to MV.'))

    o=load('e9z16_selected.json')
    split=[dict(reference=g['version'],**angular_split(o['record'],g)) for g in o['references']]
    dump(out/'e9z16_boundary_split.json',dict(image=o['image'],sampling_columns=N_COLUMNS,
         metric='shared-longitude vertical angular displacement; NOT matched-corner error',results=split))
    dump(out/'formula_control.json',formula_control())

    q=load('quality_selected.json')['rows']
    for r in q:
        a,g,j2=r['area_a_h2'],r['area_g_h2'],r['bev_iou']
        inter=j2*(a+g)/(1+j2)
        r.update(missing_over_gt=(g-inter)/g,excess_over_gt=(a-inter)/g,
                 height_reference_mean_h=r['height_mean_h']-r['height_bias_h'])
    save_csv(out/'quality_selected_rows.csv',q)
    save_csv(out/'table1_quality.csv',[
        {'案例':'jtc-12 / R03398（Manual）','问题类型':'细节标记＋执行问题标记',
         '已有数值':'BEV 0.828；墙带0.958；边界均值/P95=0.123/0.589h；体积0.793',
         '解释与取舍':'全局覆盖不能代替细节审核；边界尾部定位差异，但未建立点对应，不能称角点定位精度。原主质量资格暂缓。'},
        {'案例':'e9z-19 / R01301（Manual）','问题类型':'明确范围差异',
         '已有数值':'原/修BEV=0.450/0.150；原参考双向边界=0.080/0.928h；内部墙高RMS=0.012h',
         '解释与取舍':'主要是范围选择及参考口径；恒高自洽不等于范围正确。不用GT分数抹去已标记scope分支。'},
        {'案例':'B6-42 / R03325（Manual）','问题类型':'近地平线＋难标门洞',
         '已有数值':'面积200.342 vs17.504h²；GT完全包含；BEV/体积=0.087/0.086',
         '解释与取舍':'外扩/参考面积1044.5%；条件反投影放大量不能自动变成真实三维标错幅度，体积无新增定位解释。'},
        {'案例':'e9z-16 / R00087（Semi）','问题类型':'参考变化与上边界偏移',
         '已有数值':'原→修BEV 0.864→0.954；墙高偏差+0.045→+0.066h；新增修订参考上/下MAE=1.931°/0.560°',
         '解释与取舍':'上下拆分保留。低墙高RMS=0.007h不能排除上边界偏移；不从Semi单例推个人能力或模型纠正效果。'}])
    completed=[]
    for row in rows:
        names={'lee':'Lee MV50','exact':'精确上下弧','point':'点方法（未确认基线）'}
        product={'lee':'11个BEV表示节点；区域票≥2/3','exact':'25个上下弧表示节点；上下分别达票','point':'4角点对；各点簇3人，不等于整环3票'}
        completed.append({'案例':'2t7-06','输出':names[row['method']],'完整产物与支持口径':product[row['method']],
            'BEV原GT':f"{row['bev_iou']:.6f}",'BEV修订GT':'—',
            '上/下MAE(度)':f"{row['upper_mae_deg']:.3f}/{row['lower_mae_deg']:.3f}" if 'upper_mae_deg' in row else '—（只输出范围）',
            '结论':'范围与Lee相同；不是25个实体墙角' if row['method']=='exact' else '保留基线，不作跨图优越性结论'})
    for row in scope_rows:
        names={'observed_medoid':'完整原作答 R02122','MV50':'Lee MV50（24人）','scope_R01301':'观测scope候选 R01301'}
        prod={'observed_medoid':'6对；不看GT选出的几何medoid','MV50':'完整Polygon，122表示节点；区域票≥12/24','scope_R01301':'5对；原作答未编辑；不是已确认多空间共识'}
        completed.append({'案例':'e9z-19','输出':names[row['name']],'完整产物与支持口径':prod[row['name']],
            'BEV原GT':f"{row['references']['original']['iou']:.6f}",
            'BEV修订GT':f"{row['references']['manual_revision']['iou']:.6f}",
            '上/下MAE(度)':'—（不强制单值化原环）',
            '结论':'对两版参考均未超过原作答代表' if row['name']=='MV50' else '保留实际完整观测，不把来源升级为合理性证明'})
    save_csv(out/'table2_complete.csv',completed)
    print('Completed: saved 2t7 outputs; one e9z-19 endpoint; one boundary split; one prism-formula control.')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=ROOT/'recomputed')
    args=p.parse_args();run(args.out)
