"""Six-case endpoint study. No person selection by GT, no refitting or new votes.
Usage: python src/analyze.py --input PATH_TO_EXTRACTED_HANDOFF --out results
"""
from pathlib import Path
from itertools import combinations
import argparse, json, math, sys
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union
from lee_excerpt import tile_consensus

SPECIAL=['x8F5xyUWy9e-01','x8F5xyUWy9e-09','uNb9QFRL6hY-47','jtcxE69GiFV-12']
DETAIL=['rPc6DW4iMge-06','yqstnuAEVhm-32']
CODES=SPECIAL+DETAIL

def roster(im):
    gate='stable_nonorthogonal_separate' if im['code'].startswith('x8F') else 'main_candidate'
    return [r for r in im['annotations'] if r['independent'] and r['consensus_eligible']
            and r['condition']=='manual' and r['main_consensus_gate']['status']==gate]

def area_metrics(a,b):
    overlap=a.intersection(b).area
    omission=b.area-overlap; extension=a.area-overlap
    return dict(iou=overlap/(a.area+b.area-overlap),area_h2=a.area,ref_area_h2=b.area,
                omission_h2=omission,extension_h2=extension,
                omission_ref=omission/b.area,extension_ref=extension/b.area,
                error_ref=(omission+extension)/b.area)

def boundary_distances(a,b,n=512):
    # Equal-arclength midpoint sampling of each boundary. Not vertex matching.
    t=(np.arange(n)+.5)/n
    ab=shapely.distance(shapely.line_interpolate_point(a.boundary,t,normalized=True),b.boundary)
    ba=shapely.distance(shapely.line_interpolate_point(b.boundary,t,normalized=True),a.boundary)
    both=np.r_[ab,ba]
    return dict(boundary_mean_h=float(np.mean(both)),boundary_p95_h=float(np.quantile(both,.95)),
                boundary_sampled_max_h=float(max(both)),boundary_samples_each=n)

def main(input_path,out_path):
    source=Path(input_path); dest=Path(out_path);dest.mkdir(parents=True,exist_ok=True)
    data=json.loads((source/'cases.json').read_text());ims={i['code']:i for i in data['images']}
    saved=json.loads((source/'analysis_results/consensus_response_20261006/common10_all_consensus.geojson').read_text())
    saved_geom={(f['properties']['image'],f['properties']['method']):f for f in saved['features']}
    old_pair=pd.read_csv(source/'pairwise_distances.csv')
    old_ind=pd.read_csv(source/'individual_reference.csv')
    old_end=pd.read_csv(source/'analysis_results/consensus_response_20261006/all_pool_summary.csv')
    features=[];pairs=[];individual=[];ends=[];summaries=[];rosters=[];display={};notes=[]
    for code in CODES:
        im=ims[code];records=roster(im);n=len(records)
        assert n==dict(zip(CODES,[5,24,23,9,24,24]))[code]
        polys=[Polygon(r['footprint']) for r in records];u=unary_union(polys)
        for r in im['annotations']:
            rosters.append(dict(image=code,record=r['id'],worker=r['worker'],included=r in records,
                condition=r['condition'],independent=r['independent'],consensus_eligible=r['consensus_eligible'],
                gate=r['main_consensus_gate']['status'],quality_gate=r['main_quality_gate']['status'],
                quality_candidate=r['quality_candidate'],order_used=r['order_used'],cleaning=r['cleaning']))
        if code in SPECIAL:
            run=tile_consensus(records);regions=run['regions'];notes+=run['warnings']
            provenance='new_four_case_endpoint_using_supplied_module'
            pairrows=[]
            for ia,ib in combinations(range(n),2):
                a,b=polys[ia],polys[ib];delta=a.symmetric_difference(b).area
                row=dict(image=code,record_a=records[ia]['id'],record_b=records[ib]['id'],
                    worker_a=records[ia]['worker'],worker_b=records[ib]['worker'],
                    distance_h2=delta,distance_union=delta/u.area,
                    iou=a.intersection(b).area/a.union(b).area,
                    **boundary_distances(a,b))
                pairs.append(row);pairrows.append(row)
            R=float(np.mean([r['distance_union'] for r in pairrows]))
            med=float(np.median([r['distance_union'] for r in pairrows]))
            # A real representative selected solely from within-person range distances.
            D=np.zeros((n,n))
            for r in pairrows:
                ia=next(j for j,x in enumerate(records) if x['id']==r['record_a'])
                ib=next(j for j,x in enumerate(records) if x['id']==r['record_b'])
                D[ia,ib]=D[ib,ia]=r['distance_union']
            rep=int(D.sum(1).argmin());far=int(D[rep].argmax())
            display[code]=dict(representative=records[rep]['id'],farthest_from_representative=records[far]['id'],
                 selection='minimum_sum_fixed_union_pairwise_distance_and_farthest; no GT')
            pd.DataFrame(D,index=[r['id'] for r in records],columns=[r['id'] for r in records]).to_csv(dest/f'{code}_pairwise_matrix.csv')
        else:
            regions={m:shape(saved_geom[code,m]['geometry']) for m in ['mv50','mv_strict']}
            provenance='reused_supplied_common10_all_consensus_geojson'
            pp=old_pair[old_pair.image==code];R=float(pp.distance_union.mean());med=float(pp.distance_union.median())
            # No rerun of B endpoint or pairwise matrix.
            pairrows=pp.to_dict('records');pairs+=pairrows
        info=dict(image=code,n=n,room=im['room'],union_area_h2=u.area,raw_R=R,
            pairwise_median=med,pairwise_p10=float(np.quantile([r['distance_union'] for r in pairrows],.1)),
            pairwise_p90=float(np.quantile([r['distance_union'] for r in pairrows],.9)),
            pairwise_mean_h2=R*u.area,pairwise_min=float(min(r['distance_union'] for r in pairrows)),
            pairwise_max=float(max(r['distance_union'] for r in pairrows)),
            pair_count=len(pairrows),pair_numbers=[len(r['points'])//2 for r in records],
            source=provenance,policy_difference_h2=regions['mv50'].symmetric_difference(regions['mv_strict']).area)
        if code in SPECIAL:
            info['pairwise_boundary_mean_h']=float(np.mean([r['boundary_mean_h'] for r in pairrows]))
            info['pairwise_iou_median']=float(np.median([r['iou'] for r in pairrows]))
        summaries.append(info)
        for m,g in regions.items():
            assert g.is_valid and not g.is_empty
            features.append(dict(type='Feature',properties=dict(image=code,method=m,n=n,
                threshold=(n+1)//2 if m=='mv50' else n//2+1,condition='manual',
                records=[r['id'] for r in records],workers=[r['worker'] for r in records],
                output_type='BEV_region_only_no_ceiling',coordinate_unit='camera_height_h_not_geographic',
                quality_eligibility_unchanged=True,source=provenance),geometry=mapping(g)))
            for ref in im['references']:
                gp=Polygon(ref['footprint']);v=ref['version']
                row=dict(image=code,method=m,n=n,version=v,reference_id=ref['id'],
                    geometry_type=g.geom_type,holes=len(g.interiors) if g.geom_type=='Polygon' else None,
                    **area_metrics(g,gp))
                if code in SPECIAL:
                    ir=[area_metrics(a,gp) for a in polys]
                    row.update(individual_mean_error_ref=float(np.mean([i['error_ref'] for i in ir])),
                               individual_median_error_ref=float(np.median([i['error_ref'] for i in ir])))
                    if m=='mv50':
                        for r,x in zip(records,ir):individual.append(dict(image=code,record=r['id'],worker=r['worker'],version=v,**x))
                else:
                    old=old_end[(old_end.image==code)&(old_end.method==m)&(old_end.version==v)].iloc[0]
                    row.update(individual_mean_error_ref=float(old.individual_mean_error_ref),
                               individual_median_error_ref=float(old.individual_median_error_ref))
                    if m=='mv50':individual+=old_ind[(old_ind.image==code)&(old_ind.version==v)].to_dict('records')
                row['all_minus_individual_mean']=row['error_ref']-row['individual_mean_error_ref'];ends.append(row)
    for fn,rows in [('pairwise_distances',pairs),('individual_reference',individual),('endpoint_metrics',ends),('roster',rosters)]:
        pd.DataFrame(rows).to_csv(dest/f'{fn}.csv',index=False)
    (dest/'full_consensus.geojson').write_text(json.dumps(dict(type='FeatureCollection',features=features),ensure_ascii=False,indent=2))
    (dest/'case_summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2))
    (dest/'display_selection.json').write_text(json.dumps(display,ensure_ascii=False,indent=2))
    (dest/'execution.json').write_text(json.dumps(dict(special_endpoint_calls=4,detail_endpoint_calls=0,
        total_included=sum(x['n'] for x in summaries),warnings=notes,numpy=np.__version__,shapely=shapely.__version__,
        coordinate_frame='C continuous 1024x512; PNG is 2048x1024; figure axis maps 2:1',
        no_sha_audit=True,no_global_replay=True),ensure_ascii=False,indent=2))
    print(pd.DataFrame(summaries).drop(columns=['pair_numbers','source']).to_string(index=False))
    print(pd.DataFrame(ends)[['image','method','version','iou','omission_ref','extension_ref','error_ref','individual_mean_error_ref','all_minus_individual_mean']].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();main(a.input,a.out)
