#!/usr/bin/env python3
"""Secondary within-image ordinal diagnostics; the main task is comparable absolute quality calibration preparation.

Python standard library only. Does not recompute or alter geometry, optimize
weights, infer difficulty, calibrate raw score levels, or contact any service.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DISPUTED = 'UwV83HsGsw3-09'
SPECS = {
    'iou': ('范围 IoU', 1, 'reference'),
    'C': ('归一质心距离', -1, 'reference'),
    'U': ('上界经度边界误差 °', -1, 'reference'),
    'B': ('下界经度边界误差 °', -1, 'reference'),
    'T': ('参考墙顶 3D 曲线距离 / h', -1, 'reference'),
    'F': ('参考地面 3D 曲线距离 / h', -1, 'reference'),
    'omission': ('相对参考范围遗漏', -1, 'reference'),
    'extension': ('相对参考范围超出', -1, 'reference'),
    'dir': ('自身墙向残差 °', -1, 'intrinsic'),
    'flat': ('自身平顶残差 °', -1, 'intrinsic'),
    'LC': ('已有固定组合 LC', -1, 'fixed_composite'),
    'LCT': ('已有固定组合 LCT', -1, 'fixed_composite'),
    'LCG': ('已有固定组合 LCG', -1, 'fixed_composite'),
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def finite(x): return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
def sign(x): return (x > 0) - (x < 0)
def mean(xs): return sum(xs) / len(xs) if xs else None
def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ans = [0.] * len(xs)
    for _, pairs in itertools.groupby(enumerate(order, 1), key=lambda p: xs[p[1]]):
        pairs = list(pairs)
        rank = mean([p[0] for p in pairs])
        for _, i in pairs: ans[i] = rank
    return ans

def pearson(xs, ys):
    if len(xs) < 2: return None
    mx, my = mean(xs), mean(ys)
    sxx = sum((x-mx)**2 for x in xs)
    syy = sum((y-my)**2 for y in ys)
    return sum((x-mx)*(y-my) for x,y in zip(xs,ys))/math.sqrt(sxx*syy) if sxx*syy else None

def ordinal(rows, key, version_override=None):
    direction = SPECS[key][1]
    vals = []
    for r in rows:
        version = version_override or r['referenceVersion']
        x = r['metricsByReference'][version]['metrics'].get(key)
        if r['status'] == 'rated' and finite(r['overallScore']) and finite(x):
            vals.append((r, float(x), direction*float(x)))
    counts = Counter(C=0, D=0, metric_tie=0, human_tie_only=0, both_tie=0)
    pairs = []
    # Exact floating values define ties. No learned or post-hoc tolerance.
    for (ra, xa, qa), (rb, xb, qb) in itertools.combinations(vals, 2):
        hs = sign(ra['overallScore']-rb['overallScore'])
        ms = sign(qa-qb)
        label = 'both_tie' if hs == ms == 0 else 'human_tie_only' if hs == 0 else 'metric_tie' if ms == 0 else 'C' if hs == ms else 'D'
        counts[label] += 1
        pairs.append(dict(image=ra['imageCode'], metric=key,
            reference_version=version_override or ra['referenceVersion'],
            a=ra['reviewId'], b=rb['reviewId'],
            human_a=ra['overallScore'], human_b=rb['overallScore'],
            metric_a=xa, metric_b=xb, human_order=hs, metric_quality_order=ms,
            result=label))
    C,D,M,H,Z = [counts[k] for k in ['C','D','metric_tie','human_tie_only','both_tie']]
    n = C+D+M
    den = math.sqrt((C+D+M)*(C+D+H))
    ans = dict(n_metric_records=len(vals), n_all_pairs=len(pairs),
        n_human_distinct_pairs=n, n_human_tied_pairs=H+Z,
        concordant=C, discordant=D, metric_tied_on_human_distinct=M,
        both_tied=Z, strict_concordance=C/n if n else None,
        tie_half_concordance=(C+0.5*M)/n if n else None,
        kendall_tau_b=(C-D)/den if den else None,
        spearman_rho=pearson(ranks([r['overallScore'] for r,_,_ in vals]),ranks([q for _,_,q in vals])))
    return ans, pairs

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n',encoding='utf-8')

def write_csv(path, rows):
    if not rows: return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w = csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs',type=Path,default=ROOT/'inputs')
    ap.add_argument('--out',type=Path,default=ROOT/'analysis/imagewise_ordinal')
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    human_path=args.inputs/'review36_user_20261008.json'
    geometry_path=args.inputs/'frozen_geometry.json'
    selection_path=args.inputs/'selection_manifest.json'
    before={p.name:sha(p) for p in [human_path,geometry_path,selection_path]}
    human=json.loads(human_path.read_text());geometry=json.loads(geometry_path.read_text())
    selection=json.loads(selection_path.read_text())
    assert human['dataSnapshot']==geometry['datasetFingerprintSha256']
    assert human['dataSnapshot']==selection['datasetFingerprintSha256']
    assert len(human['ratings'])==36
    assert len({r['reviewId'] for r in human['ratings']})==36
    assert len({r['recordId'] for r in human['ratings']})==36
    source={a['id']:(im['code'],a) for im in geometry['images'] for a in im['annotations']}
    assert len(source)==36
    joined=[]; groups=defaultdict(list)
    for rating in human['ratings']:
        image,a=source[rating['recordId']]
        assert image==rating['imageCode'] and a['reviewId']==rating['reviewId']
        version=rating['referenceVersion']
        assert a['metricsByReference'][version]['referenceId']==rating['referenceId']
        assert rating['status'] in ['rated','unable','unrated']
        assert rating['status']!='rated' or rating['overallScore'] in [1,2,3,4,5]
        r=dict(rating, metricsByReference=a['metricsByReference'],
            matched_metrics=a['metricsByReference'][version]['metrics'],
            historical_Uw_query_image=image==DISPUTED, pair_count=a['pairCount'],
            source_geometry_status=a['geometryStatus'])
        joined.append(r);groups[image].append(r)
    assert len(groups)==6 and all(len(r)==6 for r in groups.values())
    summaries=[]
    for image,rows in groups.items():
        rated=[r for r in rows if r['status']=='rated']
        dist=Counter(r['overallScore'] for r in rated)
        tied=sum(n*(n-1)//2 for n in dist.values());n=len(rated)
        summaries.append(dict(image=image,n=len(rows),rated=n,
            unable=sum(r['status']=='unable' for r in rows),
            scores_in_review_order=[r['overallScore'] for r in rows],
            review_ids=[r['reviewId'] for r in rows], score_histogram=dict(sorted(dist.items())),
            all_pairs=n*(n-1)//2,human_tied_pairs=tied,human_distinct_pairs=n*(n-1)//2-tied,
            reference_version=rows[0]['referenceVersion'], historical_Uw_query_image=image==DISPUTED))
    per_image=[]; all_pairs=[]; alt_reference=[]
    tie_ranges=[]
    for image,rows in groups.items():
        for score in sorted({r['overallScore'] for r in rows}):
            tied=[r for r in rows if r['overallScore']==score]
            if len(tied)<2:continue
            for key in SPECS:
                values=[r['matched_metrics'].get(key) for r in tied]
                values=[v for v in values if finite(v)]
                tie_ranges.append(dict(image=image,human_score=score,n_records=len(tied),
                    review_ids=[r['reviewId'] for r in tied],metric=key,n_metric_values=len(values),
                    min_value=min(values) if values else None,max_value=max(values) if values else None,
                    span=max(values)-min(values) if values else None,
                    interpretation='same ordinal score; not evidence of metric equivalence or error'))
        for key in SPECS:
            stats,pairs=ordinal(rows,key)
            per_image.append(dict(image=image,metric=key,reference_version=rows[0]['referenceVersion'],historical_Uw_query_image=image==DISPUTED,**stats))
            all_pairs.extend(pairs)
            if 'manual_revision' in rows[0]['metricsByReference']:
                for version in ['original','manual_revision']:
                    stats,_=ordinal(rows,key,version)
                    alt_reference.append(dict(image=image,metric=key,metric_reference=version,
                        actual_rating_reference=rows[0]['referenceVersion'],
                        matched_actual_reference=version==rows[0]['referenceVersion'],**stats))
    aggregates=[]
    scopes={
        'historical_sensitivity_exclude_Uw_5_images':set(groups)-{DISPUTED},
        'main_all36_6_images':set(groups),
        'common_UB_available_3_images':{im for im,rows in groups.items() if all(finite(r['matched_metrics'].get('U')) and finite(r['matched_metrics'].get('B')) for r in rows)},
    }
    for name,images in scopes.items():
        for key in SPECS:
            selected=[s for s in per_image if s['image'] in images and s['metric']==key]
            usable=[s for s in selected if s['n_human_distinct_pairs']]
            C=sum(s['concordant'] for s in usable);D=sum(s['discordant'] for s in usable);M=sum(s['metric_tied_on_human_distinct'] for s in usable);n=C+D+M
            aggregates.append(dict(scope=name,metric=key,n_images_requested=len(images),
                n_images_usable=len(usable),n_records_usable=sum(s['n_metric_records'] for s in usable),
                n_human_distinct_pairs=n,concordant=C,discordant=D,metric_tied_on_human_distinct=M,
                pair_weighted_strict_concordance=C/n if n else None,
                pair_weighted_tie_half_concordance=(C+0.5*M)/n if n else None,
                macro_image_tie_half_concordance=mean([s['tie_half_concordance'] for s in usable]),
                macro_image_spearman_rho=mean([s['spearman_rho'] for s in usable if s['spearman_rho'] is not None]),
                macro_image_kendall_tau_b=mean([s['kendall_tau_b'] for s in usable if s['kendall_tau_b'] is not None]),
                used_images=[s['image'] for s in usable]))
    paired_lookup={(p['image'],p['a'],p['b'],p['metric']):p for p in all_pairs}
    composite_changes=[]
    for image,rows in groups.items():
        for a,b in itertools.combinations(rows,2):
            if a['overallScore']==b['overallScore']:continue
            baseline=paired_lookup[(image,a['reviewId'],b['reviewId'],'LC')]
            for comparison in ['LCT','LCG']:
                other=paired_lookup[(image,a['reviewId'],b['reviewId'],comparison)]
                if baseline['metric_quality_order']!=other['metric_quality_order']:
                    composite_changes.append(dict(image=image,a=a['reviewId'],b=b['reviewId'],
                        human_a=a['overallScore'],human_b=b['overallScore'],comparison=comparison,
                        LC_result=baseline['result'],comparison_result=other['result'],
                        LC_a=baseline['metric_a'],LC_b=baseline['metric_b'],
                        comparison_a=other['metric_a'],comparison_b=other['metric_b']))
    # Textual within-tie preference is NOT introduced into score-based analyses.
    q={r['reviewId']:r for r in joined}
    text_preference=[]
    for key,(_,direction,_) in SPECS.items():
        a,b=q['Q02']['matched_metrics'].get(key),q['Q06']['matched_metrics'].get(key)
        text_preference.append(dict(preferred='Q02',other='Q06',numeric_scores='5 vs 5',
            source_note=q['Q06']['scopeNote'],metric=key,metric_preferred=a,metric_other=b,
            metric_supports_text=(direction*a>direction*b) if finite(a) and finite(b) else None,
            included_in_primary_numeric_pairs=False))
    write_json(args.out/'joined_ratings_metrics.json',joined)
    write_json(args.out/'rating_summary.json',summaries)
    write_csv(args.out/'rating_summary.csv',summaries)
    write_csv(args.out/'ratings_with_notes.csv',[{**{k:v for k,v in r.items() if k not in ['metricsByReference','matched_metrics']},**{f'metric_{k}':v for k,v in r['matched_metrics'].items()}} for r in joined])
    write_csv(args.out/'metric_by_image.csv',per_image)
    write_csv(args.out/'aggregate_imagewise.csv',aggregates)
    write_csv(args.out/'within_image_pairs.csv',all_pairs)
    write_csv(args.out/'reference_sensitivity.csv',alt_reference)
    write_csv(args.out/'fixed_composite_pair_changes.csv',composite_changes)
    write_csv(args.out/'textual_tie_preference_separate.csv',text_preference)
    write_csv(args.out/'human_tie_metric_ranges.csv',tie_ranges)
    after={p.name:sha(p) for p in [human_path,geometry_path,selection_path]}
    assert before==after
    provenance=dict(input_sha256=before,source_preserved=True,
        snapshot_matches=True,snapshot=human['dataSnapshot'],
        source_exported_at=human['exportedAt'],metric_formulas=geometry['formulas'],metric_scales=geometry['scales'],
        metric_specs={k:dict(label=label,quality_direction=d,family=f) for k,(label,d,f) in SPECS.items()},
        counts=dict(ratings=len(joined),images=len(groups),all_imagewise_pairs=sum(s['all_pairs'] for s in summaries),
            human_tied_pairs=sum(s['human_tied_pairs'] for s in summaries),
            human_distinct_pairs=sum(s['human_distinct_pairs'] for s in summaries),
            metrics_seen_true=sum(r['metricsSeen'] for r in joined),gt_visible_true=sum(r['gtVisible'] for r in joined),
            scope_notes=sum(bool(r['scopeNote']) for r in joined),geometry_notes=sum(bool(r['geometryNote']) for r in joined)),
        analysis_contract={
            'unit':'within-image human ordinal comparisons; never raw cross-image score pooling',
            'primary':'all 36 records on 6 images; user confirmed Uw connections at 2026-10-08T08:45:26Z; exclusion is historical sensitivity only',
            'matched_reference':'use the exact version and reference ID recorded for each rating',
            'ties':'Human same-score pairs excluded from directional concordance; metric ties earn 0.5 in tie-half version. No tie is classified as a discordance.',
            'correlations':'Spearman with average tied ranks and Kendall tau-b, computed separately within each image; higher metric utility means better.',
            'aggregation':'Unweighted mean across usable images and pair-count-weighted concordance reported separately; pairs share records and are not independent samples.',
            'missing':'Never impute unavailable metrics; report each candidate usable images, records and pairs. U/B use 3 images only.',
            'uncertainty':'Descriptive selected-panel results only; no p-values, population confidence interval, optimized weights, tuned thresholds or difficulty estimates.',
            'tradeoffs':'Within-image ranks remove cross-image level assumptions but do not identify the weighting of scope, geometry and acceptable simplification.'})
    provenance['analysis_contract']['note_semantics']='User clarification at 2026-10-08T08:36:23Z: scope difference and wall-line omission may have been conflated in later notes. Preserve the original scores and text; do not treat note categories as reliable, separate supervision labels.'
    provenance['panel_selection']=selection['counts']
    provenance['panel_selection_limitations']=selection['limitations']
    write_json(args.out/'provenance.json',provenance)
    print(json.dumps({'status':'ok','inputs_unchanged':True,'summary':provenance['counts'],'outputs':str(args.out)},ensure_ascii=False))

if __name__=='__main__':main()
