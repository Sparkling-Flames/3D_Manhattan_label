#!/usr/bin/env python3
"""Independent finite-roster geometry and risk audit; no source algorithm imports.
Reuses frozen JSON coordinates/eligibility and source LOBO assignments. No repair,
reprojection, deduplication, requalification or stochastic sampling is performed.
"""
from pathlib import Path
from itertools import combinations
from math import comb
from collections import defaultdict
import argparse, hashlib, json, platform, shutil, sys, warnings
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize

ROOT = Path(__file__).resolve().parent
METHODS = {'mv50':2, 'mv_strict':3}
POLICIES = ['original','revised_where_available']


def write_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def hash_file(p):
    b=p.read_bytes()
    return {'name':p.name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
            'git_blob_sha1':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}


def cyclic_key(coords):
    p=tuple(tuple(c) for c in coords)
    if len(p)>1 and p[0]==p[-1]:p=p[:-1]
    return min(p[i:]+p[:i] for p in (p,p[::-1]) for i in range(len(p)))


def duplicate_check(im,rs):
    polys=[Polygon(r['footprint']) for r in rs]
    exact=defaultdict(list); point=defaultdict(list); cyc=defaultdict(list)
    for r in rs:
        exact[json.dumps(r['footprint'],separators=(',',':'))].append(r['worker'])
        point[json.dumps(r['points'],separators=(',',':'))].append(r['worker'])
        cyc[cyclic_key(r['footprint'])].append(r['worker'])
    pairs=[]
    for i,j in combinations(range(len(rs)),2):
        a,b=rs[i],rs[j]
        peq=a['points']==b['points']; feq=a['footprint']==b['footprint']
        pseteq=sorted(map(tuple,a['points']))==sorted(map(tuple,b['points']))
        pairs.append(dict(image=im['code'],worker_a=a['worker'],worker_b=b['worker'],
          record_a=a['id'],record_b=b['id'],footprint_array_equal=feq,
          points_array_equal=peq,points_multiset_equal=pseteq,
          ring_rotation_reversal_equal=cyclic_key(a['footprint'])==cyclic_key(b['footprint']),
          shapely_topological_equal=bool(polys[i].equals(polys[j])),
          symdiff_area_h2=float(polys[i].symmetric_difference(polys[j]).area),
          source_indices_equal=a['source_point_indices']==b['source_point_indices'],
          source_labels_equal=a['source_point_labels']==b['source_point_labels'],
          source_pair_indices_equal=a['source_pair_indices']==b['source_pair_indices'],
          order_used_equal=a['order_used']==b['order_used']))
    summary=dict(image=im['code'],building=im['building'],candidate_n=len(rs),
      unique_exact_footprints=len(exact),unique_exact_points=len(point),unique_cyclic_rings=len(cyc),
      duplicate_footprint_groups=[x for x in exact.values() if len(x)>1],
      duplicate_points_groups=[x for x in point.values() if len(x)>1],
      exact_equal_pair_n=sum(p['footprint_array_equal'] for p in pairs),
      topological_equal_pair_n=sum(p['shapely_topological_equal'] for p in pairs),
      raw_unprocessed_coordinates_embedded=False,
      note='points are saved preprocessed coordinates; original unprocessed submission geometry is not in this input')
    return summary,pairs


def common_basis(rs):
    polys=[Polygon(r['footprint']) for r in rs]
    assert all(p.is_valid and p.area>0 for p in polys),'No geometry repair permitted'
    faces=list(polygonize(unary_union([p.boundary for p in polys])))
    probes=np.asarray([f.representative_point().coords[0] for f in faces])
    votes=np.asarray([shapely.contains_xy(p,probes[:,0],probes[:,1]) for p in polys])
    inside=votes.any(0); faces=[f for f,v in zip(faces,inside) if v]; votes=votes[:,inside]
    area=np.asarray([p.area for p in faces]); domain=unary_union(polys)
    assert abs(area.sum()-domain.area)<1e-9
    assert np.max(abs(votes@area-np.asarray([p.area for p in polys])))<1e-9
    return faces,votes,area,domain


def q_hypergeom(votes,higher,h,threshold):
    """Exact integer combinatorial count / finite composition size, not SciPy PMFs."""
    mh=votes[higher].sum(0); ml=votes[~higher].sum(0)
    counts=np.stack([mh,ml],axis=1); unq,inv=np.unique(counts,axis=0,return_inverse=True)
    l=4-h; den=comb(12,h)*comb(12,l); q=[]
    def choose(n,k):return comb(n,k) if 0<=k<=n else 0
    for a,b in unq:
        a,b=int(a),int(b); num=0
        for x in range(h+1):
            for y in range(l+1):
                if x+y>=threshold:
                    num+=choose(a,x)*choose(12-a,h-x)*choose(b,y)*choose(12-b,l-y)
        q.append(num/den)
    return np.asarray(q)[inv],den


def pure_current_subset_region(rs,indices,threshold):
    # Fresh arrangement contains only these four candidates, independent of all-24 basis.
    p=[Polygon(rs[j]['footprint']) for j in indices]
    faces=list(polygonize(unary_union([g.boundary for g in p])))
    selected=[f for f in faces if sum(g.covers(f.representative_point()) for g in p)>=threshold]
    return unary_union(selected)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,default=ROOT/'inputs');args=parser.parse_args()
    source=args.source; out=ROOT/'results';out.mkdir(parents=True,exist_ok=True)
    names=['input.json','rosters.json','lobo_assignments.csv','composition_exact.csv','subsets.npz','source_binding.json','reference_policy.csv']
    manifest=[hash_file(source/n) for n in names];write_json(ROOT/'input_manifest.json',manifest)
    data=json.loads((source/'input.json').read_text());roster=json.loads((source/'rosters.json').read_text())
    workers=roster['workers'];images={im['code']:im for im in data['images']}
    ass=pd.read_csv(source/'lobo_assignments.csv');published=pd.read_csv(source/'composition_exact.csv');saved=np.load(source/'subsets.npz')
    members=np.asarray(list(combinations(range(24),4)),dtype=np.uint8)
    assert np.array_equal(members,saved['members'])
    rows=[]; dup=[];pairs=[];checks=[];direct=[];basis_rows=[];notices=[]
    for group in roster['groups']:
        im=images[group['image']];byid={r['id']:r for r in im['annotations']};rs=[byid[r] for r in group['record_ids']]
        assert [r['worker'] for r in rs]==workers
        assert all(r['condition']=='manual' and r['independent'] and r['consensus_eligible'] and r['main_consensus_gate']['status']=='main_candidate' for r in rs)
        ds,ps=duplicate_check(im,rs);dup.append(ds);pairs.extend(ps)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always');faces,votes,area,domain=common_basis(rs)
            refs={r['version']:Polygon(r['footprint']) for r in im['references']}
            assert all(g.is_valid and g.area>0 for g in refs.values())
            ints={v:np.asarray([f.intersection(g).area for f in faces]) for v,g in refs.items()}
        notices.extend({'image':im['code'],'message':str(w.message)} for w in caught)
        count=votes[members].sum(1)
        basis_rows.append(dict(image=im['code'],tile_n=len(faces),union_area_h2=domain.area,
                               original_gt_area_h2=refs['original'].area,
                               manual_revision_gt_area_h2=refs.get('manual_revision').area if 'manual_revision' in refs else None))
        for method,threshold in METHODS.items():
            keep=count>=threshold; pred_area=keep@area
            scores={v:(keep@ints[v])/(g.area+pred_area-keep@ints[v]) for v,g in refs.items()}
            for v,score in scores.items():
                err=float(np.max(abs(score-saved[f"{group['key']}_{method}_{v}"])))
                checks.append(dict(image=im['code'],check='all_10626_source_scores',method=method,version=v,policy='',higher_n='',max_abs=err))
                assert err<1e-10
            for policy in POLICIES:
                a=ass[(ass.policy==policy)&(ass.target_building==im['building'])].set_index('worker')
                higher=np.asarray([a.loc[w,'relative_half']=='higher' for w in workers]);assert higher.sum()==12
                hcount=higher[members].sum(1)
                for h in range(5):
                    q,n=q_hypergeom(votes,higher,h,threshold);selected=hcount==h;assert selected.sum()==n
                    qenum=keep[selected].mean(0); qerr=float(np.max(abs(q-qenum)));assert qerr<1e-14
                    V=float(np.sum(area*q*(1-q))); D=float(domain.area)
                    for version,G in refs.items():
                        I=ints[version];garea=float(G.area)
                        EI=float(I@q);EO=float((area-I)@q);EU=garea-EI
                        R=EU+EO
                        # Integrate inside and outside GT separately, plus uncovered GT.
                        outside_gt=garea-float(I.sum())
                        B=float(np.sum(I*(1-q)**2+(area-I)*q*q)+outside_gt)
                        decomp_err=abs(R-B-V)
                        direct_risk=float((garea+pred_area[selected]-2*(keep[selected]@I)).mean())
                        assert decomp_err<1e-9 and abs(R-direct_risk)<1e-9
                        sc=scores[version][selected]
                        row=dict(image=im['code'],building=im['building'],calibration_policy=policy,method=method,version=version,
                         k=4,higher_n=h,lower_n=4-h,subset_n=n,gt_area_h2=garea,union_area_h2=D,
                         expected_under_h2=EU,expected_over_h2=EO,R_h2=R,B_h2=B,V_h2=V,pair_symdiff_h2=2*V,
                         R_gt=R/garea,B_gt=B/garea,V_gt=V/garea,pair_symdiff_gt=2*V/garea,
                         R_union=R/D,B_union=B/D,V_union=V/D,pair_symdiff_union=2*V/D,
                         iou_mean=float(sc.mean()),iou_sd=float(sc.std()),
                         ratio_expected_intersection_union=EI/(garea+EO),q_enum_max_abs=qerr,
                         risk_enum_abs=abs(R-direct_risk),decomposition_abs=decomp_err,
                         gt_outside_all_candidate_union_h2=outside_gt)
                        rows.append(row)
                        p=published[(published.image==im['code'])&(published.calibration_policy==policy)&(published.method==method)&(published.version==version)&(published.higher_n==h)]
                        assert len(p)==1
                        for field,ours in [('iou_mean',row['iou_mean']),('iou_sd',row['iou_sd']),('member_symdiff_h2',2*V),('member_symdiff_union',2*V/D)]:
                            err=abs(ours-float(p.iloc[0][field]));assert err<1e-10
                            checks.append(dict(image=im['code'],check=field,method=method,version=version,policy=policy,higher_n=h,max_abs=err))
                # Three fresh four-only arrangements per policy and rule.
                for h in [0,2,4]:
                    si=int(np.flatnonzero(hcount==h)[0]); region=pure_current_subset_region(rs,members[si],threshold)
                    reconstructed=unary_union([f for f,k in zip(faces,keep[si]) if k])
                    geom_delta=region.symmetric_difference(reconstructed).area;assert geom_delta<1e-9
                    for version,G in refs.items():
                        iou=region.intersection(G).area/region.union(G).area
                        err=abs(iou-scores[version][si]);assert err<1e-10
                        direct.append(dict(image=im['code'],policy=policy,method=method,higher_n=h,version=version,
                          members='|'.join(workers[int(j)] for j in members[si]),iou_abs_difference=err,
                          region_symdiff_h2=geom_delta))
        print(im['code'],len(faces),'tiles;',len(rows),'decomposition rows',flush=True)
    f=pd.DataFrame(rows);f.to_csv(out/'risk_decomposition_all10.csv',index=False)
    pd.DataFrame(pairs).to_csv(out/'geometry_all_pairs.csv',index=False)
    pd.DataFrame([p for p in pairs if p['worker_a']=='P002' and p['worker_b']=='P012']).to_csv(out/'P002_P012_all10.csv',index=False)
    write_json(out/'duplicate_summary.json',dup)
    pd.DataFrame(checks).to_csv(out/'source_comparisons.csv',index=False)
    pd.DataFrame(direct).to_csv(out/'current_subset_direct_checks.csv',index=False)
    pd.DataFrame(basis_rows).to_csv(out/'basis_summary.csv',index=False)
    write_json(out/'warnings.json',notices)
    # End-to-end policies: original GT for original; revision where available for mixed.
    policy_selected=f[(f.calibration_policy=='original')&(f.version=='original')|((f.calibration_policy=='revised_where_available')&(f.version==np.where(f.image.isin([im['code'] for im in data['images'] if any(r['version']=='manual_revision' for r in im['references'])]),'manual_revision','original')))]
    deltas=[]
    for keys,g in f.groupby(['image','building','calibration_policy','method','version']):
        g=g.set_index('higher_n'); a,b=g.loc[0],g.loc[4]
        deltas.append(dict(zip(['image','building','calibration_policy','method','version'],keys)),)
        deltas[-1].update({f'delta_{c}':float(b[c]-a[c]) for c in ['iou_mean','iou_sd','R_h2','B_h2','V_h2','pair_symdiff_h2','R_gt','B_gt','V_gt','pair_symdiff_gt','pair_symdiff_union']})
    df=pd.DataFrame(deltas);df.to_csv(out/'all_upper_minus_all_lower.csv',index=False)
    cols=['iou_mean','iou_sd','R_gt','B_gt','V_gt','pair_symdiff_gt','pair_symdiff_union']
    policy_selected.groupby(['calibration_policy','method','higher_n'])[cols].mean().reset_index().to_csv(out/'matched_policy_image_means.csv',index=False)
    policy_selected.groupby(['calibration_policy','method','higher_n','building'])[cols].mean().groupby(['calibration_policy','method','higher_n']).mean().reset_index().to_csv(out/'matched_policy_building_means.csv',index=False)
    summary=dict(source_commit='405f3041fdd76977f625d50c558c63dbf342699d',images=10,workers=24,k=4,
      calibration_policies=POLICIES,gt_versions='original on all 10; manual_revision additionally on 4; crossed with both calibration policies',
      decomposition_rows=len(rows),pair_comparisons=len(pairs),subset_scores_per_rule_per_image=len(members),
      total_source_subset_score_comparisons=len(members)*sum(len(im['references']) for im in data['images'])*2,
      source_field_checks=len(checks),source_max_abs=max(c['max_abs'] for c in checks),
      q_hypergeom_enum_max_abs=float(f.q_enum_max_abs.max()),risk_enum_max_abs=float(f.risk_enum_abs.max()),
      decomposition_max_abs=float(f.decomposition_abs.max()),fresh_subset_reference_checks=len(direct),
      fresh_subset_geometry_max_abs=max(x['region_symdiff_h2'] for x in direct),
      unique_footprints_total=sum(d['unique_exact_footprints'] for d in dup),exact_equal_within_image_pairs=sum(d['exact_equal_pair_n'] for d in dup),
      P002_P012_exact_equal_images=sum(p['footprint_array_equal'] for p in pairs if p['worker_a']=='P002' and p['worker_b']=='P012'),
      assumptions='uniform sampling without replacement within fixed disjoint 12+12 halves; independent repeat group draws may overlap or coincide',
      area_units='h^2 from saved BEV projection, not measured square metres',
      upstream_raw_generation='not independently verified; frozen input and declared source-binding statuses only',
      warning_count=len(notices),python=sys.version,platform=platform.platform(),numpy=np.__version__,pandas=pd.__version__,shapely=shapely.__version__)
    write_json(out/'summary.json',summary);print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
