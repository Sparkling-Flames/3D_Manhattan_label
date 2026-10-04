"""定向只读复核。原件只读；仅把结果写入本脚本所在目录。

字段：checks.json 记录验证范围、计数与最大绝对误差；CSV 是固定池描述。
prediction_* 的 gain_sse = baseline_sse - model_sse，允许负值；
去掉两人的 evaluation_only 行仅重汇总既有预测，绝不删除人员重训。
运行：D:/anaconda/python.exe <此文件> [--pro <归档根>] [--dot <dot根>]
"""
from pathlib import Path
import argparse
import itertools
import json
import math
import platform

import numpy as np
import pandas as pd
import scipy
from scipy.cluster.hierarchy import linkage, cut_tree
import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[2]
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--pro', type=Path, default=REPO/'research/worker_subtype_returns_20261004/pro')
ap.add_argument('--dot', type=Path, default=REPO/'research/worker_subtype_returns_20261004/dot')
args = ap.parse_args()
PRO, DOT = args.pro, args.dot
PANEL = REPO/'analysis_results/worker_profiles_20261003'
DOT_TEN = DOT/'ten_image_subtype_check'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def save(name, rows):
    pd.DataFrame(rows).to_csv(OUT/name, index=False, encoding='utf-8-sig')

def supplied_equal(original, supplied):
    if isinstance(supplied, dict):
        return isinstance(original, dict) and all(k in original and supplied_equal(original[k],v) for k,v in supplied.items())
    return original == supplied

def fit(x, method):
    if method == 'no_worker':
        return np.zeros_like(x), np.zeros(len(x), int)
    if method == 'individual':
        return x.copy(), np.arange(len(x))
    if method == 'median2':
        med = np.median(x)
        if np.any(x == med):
            return None, None
        lab = (x > med).astype(int)
    else:
        raw = cut_tree(linkage(x[:, None], method='ward'), n_clusters=[int(method[-1])]).ravel()
        order = sorted(set(raw), key=lambda n: x[raw == n].mean())
        lab = np.array([order.index(n) for n in raw])
    return np.array([x[lab == n].mean() for n in lab]), lab

def hyper(N, c, k, j):
    if j < 0 or j > c or k-j < 0 or k-j > N-c:
        return 0.
    return math.comb(c, j)*math.comb(N-c, k-j)/math.comb(N, k)

def inclusion(c, k, rule):
    threshold = (k+1)//2 if rule == 'mv50' else k//2+1
    return sum(hyper(12, c, k, j) for j in range(threshold, k+1))

def iou(a, b):
    inter = a.intersection(b).area
    return inter/(a.area+b.area-inter)

checks = {'scope': '当前保存的24×10面板、两政策480单人分数、重训嵌套预测、十图80稳定性行；两图六人NPZ全量重汇总及每图19组重新几何积分；两图35校准传播。不是完整外包复跑，不视觉裁决。',
          'sources': {'pro': str(PRO), 'dot': str(DOT), 'panel': str(PANEL)},
          'environment': {'python': platform.python_version(), 'numpy': np.__version__,
                          'scipy': scipy.__version__, 'shapely': shapely.__version__,
                          'geos': shapely.geos_version_string}}
images = {im['code']: im for im in read(PANEL/'input.json')['images']}
matrices = {}
matrix_identity = {}
for policy in ['original', 'revised_where_available']:
    file = 'matrix_'+policy+'_iou.csv'
    matrix_identity[policy] = (PANEL/file).read_bytes() == (PRO/'inputs'/file).read_bytes()
    assert matrix_identity[policy]
    matrices[policy] = pd.read_csv(PANEL/file)
workers = list(matrices['original'].columns[2:])
assert len(workers) == 24 and len(images) == 10
checks['matrix_bytes_equal_repo'] = matrix_identity
checks['dot_original_matrix_bytes_equal_repo'] = (DOT_TEN/'inputs/matrix_original_iou.csv').read_bytes() == (PANEL/'matrix_original_iou.csv').read_bytes()
assert checks['dot_original_matrix_bytes_equal_repo']
refs = pd.read_csv(PANEL/'reference_policy.csv').set_index(['policy', 'image']).version
binding = []; score_rows = []; excluded = []
records_by_image = {}
for code, im in images.items():
    records = {r['worker']: r for r in im['annotations'] if r['worker'] in workers}
    assert len(records) == 24 and len(im['annotations']) == 26
    records_by_image[code] = [records[w] for w in workers]
    for r in im['annotations']:
        if r['worker'] not in workers:
            assert r['independent'] is False and r['consensus_eligible'] is False and r['quality_candidate'] is False
            excluded.append({'image': code, 'worker': r['worker'], 'id': r['id'], 'restored': False})
    for r in records.values():
        assert r['condition'] == 'manual' and r['independent'] and r['consensus_eligible'] and r['quality_candidate']
        assert not r['borrowed_points'] and r['footprint_state']['status'] == 'ok'
        for policy, matrix in matrices.items():
            ref = next(x for x in im['references'] if x['version'] == refs.loc[policy, code])
            expected = float(matrix.set_index('image').loc[code, r['worker']])
            actual = iou(Polygon(r['footprint']), Polygon(ref['footprint']))
            score_rows.append({'policy': policy, 'image': code, 'worker': r['worker'], 'record': r['id'],
                               'reference': ref['id'], 'saved': expected, 'recomputed': actual,
                               'absolute_error': abs(actual-expected)})
for im in read(DOT_TEN/'inputs/footprints_240.json')['images']:
    original = {r['id']: r for r in images[im['code']]['annotations']}
    for r in im['annotations']:
        for key, value in r.items():
            assert original[r['id']][key] == value, (im['code'], r['id'], key)
        binding.append({'source': 'dot240', 'image': im['code'], 'record': r['id'], 'fields': len(r), 'equal': True})
for file in ['one_image_geometry.json', 'rpc_geometry.json']:
    compact = read(PRO/'inputs'/file)
    original = {r['id']: r for r in images[compact['image']]['annotations']}
    for r in compact['records']:
        for key, value in r.items():
            assert supplied_equal(original[r['id']][key], value), (file, r['id'], key)
        binding.append({'source': file, 'image': compact['image'], 'record': r['id'], 'fields': len(r), 'equal': True})
    original_ref = next(r for r in images[compact['image']]['references'] if r['id'] == compact['reference']['id'])
    assert all(original_ref[k] == v for k, v in compact['reference'].items())
checks['binding'] = {'dot_records': 240, 'pro_records': 48, 'pro_references': 2, 'excluded_not_restored': len(excluded),
                     'all_supplied_record_fields_equal': True, 'omitted_fields_not_certified': True}
checks['single_iou'] = {'n': len(score_rows), 'max_absolute_error': max(r['absolute_error'] for r in score_rows)}
assert checks['single_iou']['max_absolute_error'] < 1e-12
save('input_binding.csv', binding); save('single_iou_check.csv', score_rows); save('excluded_records.csv', excluded)
print('input binding and 480 single scores complete', flush=True)

# Independent nested re-fit, and signed improvement attribution of the fixed predictions.
method_menu = ['no_worker', 'median2', 'ward2', 'ward3', 'ward4', 'individual']
saved_predictions = pd.read_csv(PRO/'results/nested_prediction_cells.csv').set_index(['policy', 'image', 'worker'])
saved_choices = pd.read_csv(PRO/'results/nested_method_choices.csv').set_index(['policy', 'target'])
prediction_rows = []; fold_rows = []; concentration = []
max_prediction_error = 0.
for policy, df in matrices.items():
    y = df[workers].to_numpy(); residual = y-y.mean(axis=1, keepdims=True)
    b = df.building.to_numpy(); buildings = sorted(set(b))
    for outer in buildings:
        train, test = b != outer, b == outer
        losses = {}
        for method in method_menu:
            inner_losses = []
            for inner in buildings:
                if inner == outer:
                    continue
                pred, _ = fit(residual[train & (b != inner)].mean(axis=0), method)
                inner_losses.append(np.inf if pred is None else np.mean((residual[b == inner]-pred)**2))
            losses[method] = np.mean(inner_losses)
        chosen = min(method_menu, key=lambda m: (losses[m], method_menu.index(m)))
        assert chosen == saved_choices.loc[policy, outer].selected_method
        pred, _ = fit(residual[train].mean(axis=0), chosen)
        baseline = float((residual[test]**2).sum()); model = float(((residual[test]-pred)**2).sum())
        fold_rows.append({'policy': policy, 'building': outer, 'method': chosen,
                          'image_n': int(test.sum()), 'baseline_sse': baseline, 'model_sse': model, 'gain_sse': baseline-model})
        for i in np.flatnonzero(test):
            for j, worker in enumerate(workers):
                old = saved_predictions.loc[policy, df.image.iloc[i], worker]
                error = max(abs(old.prediction-pred[j]), abs(old.centered_target-residual[i,j]))
                max_prediction_error = max(max_prediction_error, float(error))
                base = residual[i,j]**2; loss = (residual[i,j]-pred[j])**2
                prediction_rows.append({'policy': policy, 'image': df.image.iloc[i], 'building': outer, 'worker': worker,
                                        'baseline_sse': base, 'model_sse': loss, 'gain_sse': base-loss})
predictions = pd.DataFrame(prediction_rows)
worker_gain = predictions.groupby(['policy', 'worker'])[['baseline_sse', 'model_sse', 'gain_sse']].sum().reset_index()
for policy in matrices:
    p = predictions[predictions.policy == policy]; f = pd.DataFrame(fold_rows).query('policy == @policy')
    baseline, total = p.baseline_sse.sum(), p.gain_sse.sum()
    wg = worker_gain[worker_gain.policy == policy].set_index('worker')
    other = p[~p.worker.isin(['P002', 'P017'])]
    concentration.append({'policy': policy, 'relative_sse_improvement': total/baseline,
                          'building_equal_relative_improvement': (f.gain_sse/f.image_n).sum()/(f.baseline_sse/f.image_n).sum(),
                          'improved_buildings': int((f.gain_sse > 0).sum()), 'total_buildings': len(f),
                          'p017_signed_gain_fraction': wg.loc['P017'].gain_sse/total,
                          'p002_and_p017_signed_gain_fraction': wg.loc[['P002','P017']].gain_sse.sum()/total,
                          'evaluation_only_other22_relative_improvement': other.gain_sse.sum()/other.baseline_sse.sum(),
                          'positive_worker_count': int((wg.gain_sse > 0).sum()), 'total_workers': len(wg)})
checks['nested_prediction'] = {'cells': len(predictions), 'outer_choices_match': True,
                               'max_absolute_prediction_or_target_error': max_prediction_error}
assert max_prediction_error < 1e-12
save('prediction_building_contributions.csv', fold_rows); save('prediction_worker_contributions.csv', worker_gain)
save('prediction_concentration.csv', concentration)
print('nested prediction and concentration complete', flush=True)

# Rebuild polygon partitions from repository footprints. No GT enters vote partition.
labels_frozen = pd.read_csv(DOT_TEN/'inputs/frozen_labels.csv')
dot_raw = pd.read_csv(DOT_TEN/'results/raw_dispersion.csv').set_index(['image', 'subtype'])
dot_shape = pd.read_csv(DOT_TEN/'results/same_k_shape.csv').set_index(['image', 'subtype', 'k', 'rule'])
raw_rows = []; shape_rows = []; basis_by_image = {}; tile_rows = []
matrix = matrices['original']
for code, im in images.items():
    records = records_by_image[code]
    polygons = [Polygon(r['footprint']) for r in records]
    assert all(p.is_valid and p.area > 0 for p in polygons)
    tiles = []; votes = []
    for tile in polygonize(unary_union([p.boundary for p in polygons])):
        v = np.array([p.covers(tile.representative_point()) for p in polygons], bool)
        if v.any():
            tiles.append(tile); votes.append(v)
    area = np.array([t.area for t in tiles]); votes = np.array(votes)
    union_area = float(area.sum()); actual_union = unary_union(polygons).area
    individual_error = float(np.max(np.abs(area@votes - [p.area for p in polygons])))
    assert abs(union_area-actual_union) < 1e-9 and individual_error < 1e-9
    train = matrix.loc[matrix.building != im['building'], workers].to_numpy()
    _, labels = fit((train-train.mean(axis=1, keepdims=True)).mean(axis=0), 'median2')
    frozen = labels_frozen[(labels_frozen.policy == 'original') & (labels_frozen.method == 'median2') & (labels_frozen.target == im['building'])]
    assert all(int(frozen.set_index('worker').loc[w].subtype) == int(z) for w,z in zip(workers, labels))
    basis_by_image[code] = (tiles, area, votes, polygons)
    tile_rows.append({'image': code, 'tiles': len(tiles), 'union_area': union_area, 'individual_area_error': individual_error})
    for group in [0,1]:
        ids = np.flatnonzero(labels == group)
        raw = float(np.mean([1-iou(polygons[i], polygons[j]) for i,j in itertools.combinations(ids,2)]))
        raw_common_union = float(np.mean([area@(votes[:,i] != votes[:,j])/union_area for i,j in itertools.combinations(ids,2)]))
        raw_rows.append({'image': code, 'subtype': group, 'mean_pair_1_minus_iou': raw,
                         'mean_pair_symdiff_union': raw_common_union,
                         'saved_error': abs(raw-dot_raw.loc[code,group].mean_pair_1_minus_iou)})
        supports = votes[:, ids].sum(axis=1)
        for k in [4,6]:
            for rule in ['mv50','mv_strict']:
                threshold = (k+1)//2 if rule == 'mv50' else k//2+1
                probability = np.array([inclusion(int(c), k, rule) for c in supports])
                independent = float(area@(2*probability*(1-probability))/union_area)
                dj = {c: sum(hyper(12,c,k,j)*hyper(12-k,c-j,k,l) for j in range(k+1) for l in range(k+1) if (j>=threshold) != (l>=threshold)) for c in range(13)}
                disjoint = float(area@np.array([dj[int(c)] for c in supports])/union_area)
                saved = dot_shape.loc[code,group,k,rule]
                shape_rows.append({'image': code, 'subtype': group, 'k': k, 'rule': rule,
                                   'independent': independent, 'disjoint': disjoint,
                                   'saved_error': max(abs(independent-saved.same_k_independent_symdiff_union), abs(disjoint-saved.same_k_disjoint_symdiff_union))})
    print(code, len(tiles), 'tiles complete', flush=True)
save('raw_dispersion_recomputed.csv',raw_rows); save('same_k_shape_recomputed.csv',shape_rows); save('tile_checks.csv',tile_rows)
checks['ten_image'] = {'raw_rows': len(raw_rows), 'shape_rows': len(shape_rows),
                       'max_raw_error': max(r['saved_error'] for r in raw_rows),
                       'max_shape_error': max(r['saved_error'] for r in shape_rows)}
assert max(checks['ten_image']['max_raw_error'], checks['ten_image']['max_shape_error']) < 1e-10
direction = []
raw_frame = pd.DataFrame(raw_rows)
for metric, df, grouping in [('raw',raw_frame,[]),('raw_common_union',raw_frame,[]),('independent',pd.DataFrame(shape_rows),['k','rule']),('disjoint',pd.DataFrame(shape_rows),['k','rule'])]:
    groups = [((),df)] if not grouping else df.groupby(grouping)
    for key, group in groups:
        name = {'raw':'mean_pair_1_minus_iou', 'raw_common_union':'mean_pair_symdiff_union'}.get(metric, metric)
        pivot = group.pivot(index='image', columns='subtype', values=name)
        delta = pivot[1]-pivot[0]
        direction.append({'metric':metric, 'k': key[0] if key else '', 'rule': key[1] if key else '',
                          'high_more_variable': int((delta>0).sum()), 'high_less_variable': int((delta<0).sum()),
                          'mean_high_minus_low': delta.mean(), 'images': len(delta)})
save('ten_image_directions.csv', direction)

# Saved six-person arrays: full arithmetic checks, selected independent geometry integrals.
six_rows = []; selected_rows = []; propagation_rows = []; propagation_summary = []
assignments = pd.read_csv(PRO/'results/profile_assignments.csv')
for code in ['7y3sRwLe3Va-04','rPc6DW4iMge-06']:
    z = np.load(PRO/'results'/f'{code}_six_person_all_sets.npz')
    assert list(z['worker']) == workers
    assert list(z['record_id']) == [r['id'] for r in records_by_image[code]]
    subsets = z['subsets']; assert np.array_equal(subsets, np.array(list(itertools.combinations(range(24),6)),dtype=np.uint8))
    tiles, area, votes, _ = basis_by_image[code]
    ref = Polygon(next(r for r in images[code]['references'] if r['version']=='original')['footprint'])
    inside = np.array([t.intersection(ref).area for t in tiles])
    indices = np.unique(np.linspace(0, len(subsets)-1, 19, dtype=int))
    for ix in indices:
        count = votes[:,subsets[ix]].sum(axis=1)
        for rule,t in [('mv50',3),('mv_strict',4)]:
            mask = count>=t; inter = float(inside@mask); size = float(area@mask)
            val = inter/(ref.area+size-inter)
            selected_rows.append({'image':code,'subset_index':int(ix),'rule':rule,'saved':float(z['iou_'+rule][ix]),'recomputed':val,'absolute_error':abs(val-z['iou_'+rule][ix]),'area_error':abs(size-z['area_'+rule][ix])})
    old_var = pd.read_csv(PRO/'results'/f'{code}_six_person_variance.csv').set_index(['policy','method','rule'])
    old_comp = pd.read_csv(PRO/'results'/f'{code}_six_person_compositions.csv').set_index(['policy','method','rule','higher_n'])
    for policy, matrix in matrices.items():
        for method in ['median2','ward2']:
            train = matrix.loc[matrix.building != images[code]['building'],workers].to_numpy()
            _,labels = fit((train-train.mean(axis=1,keepdims=True)).mean(axis=0),method)
            nh = int(labels.sum()); count = labels[subsets].sum(axis=1)
            for rule in ['mv50','mv_strict']:
                values = z['iou_'+rule]; total = values.var(); mean = values.mean(); between=within=0.
                for c in np.unique(count):
                    values_c = values[count==c]; n = len(values_c)
                    assert n == math.comb(nh,int(c))*math.comb(24-nh,6-int(c))
                    saved = old_comp.loc[policy,method,rule,c]
                    assert n == saved.sets_n and abs(values_c.mean()-saved.mean_iou)<1e-12
                    between += n/len(values)*(values_c.mean()-mean)**2
                    within += n/len(values)*values_c.var()
                old = old_var.loc[policy,method,rule]
                err = max(abs(between/total-old.between_share),abs(within/total-old.within_share),abs(total-between-within))
                six_rows.append({'image':code,'policy':policy,'method':method,'rule':rule,'sets':len(subsets),
                                 'between_share':between/total,'within_share':within/total,'saved_error':err})
        # All 35 calibration sets, no target building, 924 six-member sets per high list.
        qs = {rule:[] for rule in ['mv50','mv_strict']}
        rows_by_rule = {rule:[] for rule in qs}
        other_buildings = sorted(set(matrix.building)-{images[code]['building']})
        for calibration in itertools.combinations(other_buildings,4):
            qx = matrix.loc[matrix.building.isin(calibration),workers].to_numpy().mean(axis=0)
            _,labels = fit(qx-qx.mean(),'median2'); assert labels is not None
            subset_mask = labels[subsets].sum(axis=1)==6
            assert int(subset_mask.sum()) == 924
            supports = votes[:,labels==1].sum(axis=1)
            for rule in qs:
                q = np.array([inclusion(int(c),6,rule) for c in supports])
                val = z['iou_'+rule][subset_mask]
                row={'image':code,'policy':policy,'rule':rule,'calibration':'|'.join(calibration),
                     'higher_workers':'|'.join(w for w,l in zip(workers,labels) if l==1),'mean_iou':float(val.mean()),
                     'within_team_iou_variance':float(val.var()),'same_k_shape':float(area@(2*q*(1-q))/area.sum())}
                propagation_rows.append(row); rows_by_rule[rule].append(row); qs[rule].append(q)
        for rule, bag in qs.items():
            q=np.array(bag); rr=rows_by_rule[rule]; means=np.array([r['mean_iou'] for r in rr])
            shape_within=float(np.mean([r['same_k_shape'] for r in rr])); shape_between=float(2*area@q.var(axis=0)/area.sum())
            shape_total=float(2*area@(q.mean(axis=0)*(1-q.mean(axis=0)))/area.sum())
            propagation_summary.append({'image':code,'policy':policy,'rule':rule,'valid_calibrations':len(rr),
                'distinct_higher_lists':len({r['higher_workers'] for r in rr}),
                'minimum_conditional_mean_iou':float(means.min()),'maximum_conditional_mean_iou':float(means.max()),
                'iou_variance_due_to_list_fraction':float(means.var()/(means.var()+np.mean([r['within_team_iou_variance'] for r in rr]))),
                'shape_within_fixed_list':shape_within,'shape_between_calibration_lists':shape_between,
                'shape_total':shape_total,'shape_between_fraction':shape_between/shape_total})
checks['six_person']={'images':2,'sets_each':134596,'all_members_arrays_validated':True,'full_saved_array_decomposition_rows':len(six_rows),
                      'selected_geometry_sets_each':19,'selected_geometry_score_checks':len(selected_rows),
                      'max_decomposition_error':max(r['saved_error'] for r in six_rows),
                      'max_selected_geometry_iou_error':max(r['absolute_error'] for r in selected_rows)}
old_details=pd.read_csv(PRO/'results/calibration_propagation_details.csv').set_index(['image','policy','rule','calibration'])
max_detail_error=0.
for row in propagation_rows:
    old=old_details.loc[row['image'],row['policy'],row['rule'],row['calibration']]
    assert old.higher_workers==row['higher_workers']
    max_detail_error=max(max_detail_error,*(abs(row[k]-old[k]) for k in ['mean_iou','within_team_iou_variance','same_k_shape']))
old_summary=pd.read_csv(PRO/'results/calibration_propagation_summary.csv').set_index(['image','policy','rule'])
max_summary_error=0.
for row in propagation_summary:
    old=old_summary.loc[row['image'],row['policy'],row['rule']]
    max_summary_error=max(max_summary_error,*(abs(row[k]-old[k]) for k in row if k not in ['image','policy','rule']))
checks['calibration_propagation']={'details':len(propagation_rows),'summary_rows':len(propagation_summary),
                                   'max_detail_error':max_detail_error,'max_summary_error':max_summary_error}
assert max(checks['six_person']['max_decomposition_error'],checks['six_person']['max_selected_geometry_iou_error'],max_detail_error,max_summary_error)<1e-10
save('six_person_decomposition_recheck.csv',six_rows);save('six_person_selected_geometry.csv',selected_rows)
save('calibration_propagation_recomputed.csv',propagation_rows);save('calibration_propagation_summary_recomputed.csv',propagation_summary)
inventory_path=REPO/'analysis_results/review_source_audit_20261004/corrected_inventory'
current=pd.read_csv(inventory_path/'groups.csv').set_index(['image','condition','consensus_gate'])
excerpt=pd.read_csv(PRO/'inputs/high_support_inventory_excerpt.csv')
inventory_rows=[]
for old in excerpt.to_dict('records'):
    row=current.loc[old['image'],old['condition'],old['consensus_gate']]
    for key in ['candidate_n','candidate_bev_failed_n','reference_quality_compatible','building','curve_ready']:
        assert old[key] == row[key], (old['image'],key)
    inventory_rows.append({'image':old['image'],'condition':old['condition'],'consensus_gate':old['consensus_gate'],
                           'candidate_n':old['candidate_n'],'pro_difficulty':old['difficulty'],
                           'current_difficulty':row.difficulty,'non_difficulty_fields_equal':True})
save('inventory_version_binding.csv',inventory_rows)
groups=current.reset_index()
manual=groups[(groups.condition=='manual') & (groups.candidate_n>=20)]
quality=manual[(manual.candidate_bev_failed_n==0) & (manual.consensus_gate=='main_candidate') & manual.reference_quality_compatible]
held=manual[(manual.candidate_bev_failed_n==0) & (manual.consensus_gate=='main_candidate') & ~manual.reference_quality_compatible]
flat=read(inventory_path/'input.json')['records']; hold_rows=[]
for code in held.image:
    rr=[r for r in flat if r['image']==code and r['condition']=='manual' and r['consensus_candidate']]
    hold_rows.append({'image':code,'quality_gates':'|'.join(sorted({r['quality_gate'] for r in rr})),
                      'quality_reasons':'|'.join(sorted({r['quality_reasons'] for r in rr})), 'candidate_records':len(rr)})
save('six_main_consensus_quality_holds.csv',hold_rows)
checks['inventory_version']={'matched_excerpt_rows':len(inventory_rows),'high_support_manual_n':len(manual),
 'computable_manual_n':int((manual.candidate_bev_failed_n==0).sum()),'quality_main_n':len(quality),
 'current_quality_main_difficulty':quality.difficulty.value_counts().to_dict(),
 'difficulty_changes_in_excerpt':sum(r['pro_difficulty']!=r['current_difficulty'] for r in inventory_rows),
 'quality_hold_main_n':len(hold_rows), 'quality_hold_reasons':pd.Series([r['quality_reasons'] for r in hold_rows]).value_counts().to_dict()}
checks['status']='targeted_checks_passed'
(OUT/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(checks,ensure_ascii=True,indent=2),flush=True)
