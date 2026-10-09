"""DINO缓存两轴：视觉距离和局部视觉异质性；近邻参照在内外折重建。"""
from collections import Counter
import json

import numpy as np

from .research_artifact_io import ROOT, read_csv, write_csv, write_json
from .difficulty_score_20261009 import LABELS, empirical_percentiles, weight_grid, evaluate_subjective
from .difficulty_model_comparison_20261009 import NEW_FEATURES, numeric

BASE = ROOT/'analysis_results/objective_difficulty_20261009'
OUT = BASE/'dino_probe'
CACHE = ROOT/'output/image_portrait_20260914_v1/raw/dinov3'
FACES = ('front','right','back','left','up','down')
FEATURES = (*NEW_FEATURES, 'dino_other_building_5nn_cosine', 'dino_horizontal_patch_dispersion')


def summarize_patches(arrays):
    faces, dispersion = [], []
    for face in FACES:
        a = np.asarray(arrays[face], dtype=np.float32)
        if a.ndim != 3 or not np.isfinite(a).all():
            raise ValueError('nonfinite_or_invalid_dino_patch')
        mean = a.mean(axis=(1,2))
        norms = np.linalg.norm(a, axis=0)
        norm = np.linalg.norm(mean)
        if norm == 0 or np.any(norms == 0):
            raise ValueError('zero_dino_patch_or_mean')
        unit = mean/norm
        faces.append(unit)
        if face in FACES[:4]:
            dispersion.append(float(np.clip(1-np.mean(np.sum(a*unit[:,None,None],axis=0)/norms),0,2)))
    vector = np.mean(faces, axis=0)
    norm = np.linalg.norm(vector)
    if norm == 0:
        raise ValueError('zero_dino_cube_mean')
    return vector/norm, float(np.mean(dispersion))


def fold_features(base, distances, buildings, train, neighbours=5, audit=None, image_ids=None, context=None, query_mask=None):
    novelty = []
    for i, building in enumerate(buildings):
        reference = np.asarray(train) & (buildings != building)
        ref_indices = np.flatnonzero(reference)
        values = distances[i,ref_indices]
        if len(values) < neighbours:
            raise ValueError('insufficient_other_building_neighbours')
        nearest = ref_indices[np.argsort(values,kind='stable')[:neighbours]]
        novelty.append(float(distances[i,nearest].mean()))
        if audit is not None and (query_mask is None or query_mask[i]):
            audit.append(dict(**context,image_id=image_ids[i],query_building=building,
                reference_images=len(ref_indices),reference_buildings=len(set(buildings[ref_indices])),
                nearest_image_ids=json.dumps([image_ids[j] for j in nearest]),
                nearest_buildings=json.dumps(buildings[nearest].tolist())))
    return np.column_stack((base[:,:3], novelty, base[:,3]))


def nested_predictions(rows, base, distances, indices, audit=None):
    buildings = np.asarray([r['building'] for r in rows])
    labels = np.asarray([np.nan if r['subjective_label'] not in LABELS else LABELS[r['subjective_label']] for r in rows])
    grid = weight_grid(len(indices))
    uniform = np.full(len(indices),1/len(indices))
    outputs = []
    image_ids = [r['image_id'] for r in rows]
    for heldout in sorted(set(buildings)):
        train = buildings != heldout
        x = fold_features(base, distances, buildings, train, audit=audit, image_ids=image_ids,
                          context=dict(level='outer_all_queries',outer_heldout=heldout,inner_heldout=''))[:,indices]
        errors = []
        for inner in sorted(set(buildings[train])):
            inner_train = train & (buildings != inner)
            inner_test = train & (buildings == inner) & np.isfinite(labels)
            if not inner_test.any():
                continue
            inner_x = fold_features(base, distances, buildings, inner_train, audit=audit, image_ids=image_ids,
                context=dict(level='inner_labelled_validation_queries',outer_heldout=heldout,inner_heldout=inner),
                query_mask=inner_test)[:,indices]
            ranks = empirical_percentiles(inner_x[inner_test], inner_x[inner_train])
            errors.append(np.mean((ranks @ grid.T-labels[inner_test,None]/2)**2,axis=0))
        if len(errors)<2:
            weights, status = uniform, 'insufficient_inner_buildings_uniform'
        else:
            losses = np.mean(errors,axis=0)
            best = min(range(len(grid)),key=lambda i:(round(float(losses[i]),12),float(np.sum((grid[i]-uniform)**2)),tuple(grid[i])))
            weights, status = grid[best], 'inner_building_selected'
        ranks = empirical_percentiles(x[~train],x[train])
        for i,p in zip(np.flatnonzero(~train),ranks):
            outputs.append(dict(image=rows[i]['image'],building=heldout,
                label=None if not np.isfinite(labels[i]) else int(labels[i]),
                weights=weights.tolist(),baseline_score=float(100*p @ uniform),
                calibrated_score=float(100*p @ weights),component_scores=(100*p).tolist(),
                training_buildings=sorted(set(buildings[train])),inner_validation_buildings=len(errors),
                calibration_status=status))
    return outputs


def run():
    rows = read_csv(BASE/'model_comparison/joined_features.csv')
    metadata_path = ROOT/'output/links/repo/analysis_results/image_portrait_20260914_v1/metadata/images.jsonl'
    metadata = {r['image_id']:r for r in [json.loads(line) for line in metadata_path.read_text(encoding='utf-8').splitlines()]}
    hoho = {r['image_id']:r for r in read_csv(BASE/'hohonet_probe/per_image.csv')}
    summaries, vectors = [], {}
    for r in rows:
        meta = metadata[r['image_id']]
        recorded_path = (ROOT/meta['path']).resolve()
        if str(recorded_path) != hoho[r['image_id']]['image_path'] or meta['building'] != r['building']:
            raise ValueError('dino_recorded_source_mismatch:' + r['image_id'])
        path = CACHE/(r['image_id']+'.npz')
        with np.load(path) as data:
            patches = {f:data[f+'_block12_patch'] for f in FACES}
            if any(a.shape != (768,32,32) for a in patches.values()):
                raise ValueError('dino_cache_patch_shape_mismatch:' + r['image_id'])
            vector, dispersion = summarize_patches(patches)
            shape = data['source_shape_hw'].tolist()
        vectors[r['image_id']] = vector
        summaries.append(dict(image=r['image'],image_id=r['image_id'],building=r['building'],
            source=str(path),source_shape_hw=json.dumps(shape),status='finite_final_patches',
            recorded_image_source=str(recorded_path),source_record_matches_current_path=True,
            dino_horizontal_patch_dispersion=dispersion,
            calibration_panel=r['calibration_panel']))
        for k in NEW_FEATURES:
            r[k] = numeric(r[k])
        r['dino_horizontal_patch_dispersion'] = dispersion
    ordinary = [r for r in rows if r['calibration_panel']=='ordinary_historical_panel'
                and all(r[k] is not None for k in NEW_FEATURES)]
    matrix = np.stack([vectors[r['image_id']] for r in ordinary]).astype(float)
    distances = np.clip(1-matrix @ matrix.T,0,2)
    base = np.asarray([[r[k] for k in (*NEW_FEATURES,'dino_horizontal_patch_dispersion')] for r in ordinary])
    sets = {'point_only':(0,), 'current_three':(0,1,2), 'dino_novelty_only':(3,),
            'dino_dispersion_only':(4,), 'three_plus_novelty':(0,1,2,3),
            'three_plus_dispersion':(0,1,2,4), 'all_five':(0,1,2,3,4)}
    metrics, predictions, audit = [], [], []
    for name, indices in sets.items():
        pred = nested_predictions(ordinary,base,distances,indices,audit if name=='all_five' else None)
        features = tuple(FEATURES[i] for i in indices)
        metrics += [dict(candidate=name,**m) for m in evaluate_subjective(pred,features)
                    if m['score'] in ('baseline_score','calibrated_score')]
        predictions += [dict(candidate=name,features=features,**p) for p in pred]
    OUT.mkdir(parents=True,exist_ok=True)
    write_csv(OUT/'features.csv',summaries)
    np.savez_compressed(OUT/'cube_mean_descriptors.npz',**vectors)
    write_csv(OUT/'metrics.csv',metrics)
    write_csv(OUT/'neighbour_reference_audit.csv',audit)
    write_json(OUT/'holdout_predictions.json',predictions)
    contract = dict(schema='difficulty_dino_probe_20261009_v1', cache=str(CACHE),
        layer='fixed block12 norm=True patch, float16 cache -> float32 summary; no CLS/register mixing',
        descriptor='each of six cube faces mean patch vector L2-normalized, mean six then L2-normalized; 768 dims',
        dispersion='four horizontal faces separately mean cosine distance of patch token to that face mean vector, average four; pixel patches equal weight',
        novelty='mean five nearest cosine distances to ordinary training images of other buildings; recomputed within each outer AND inner fold',
        primary_panel=len(ordinary), all_images=len(rows), labels=sum(r['subjective_label'] in LABELS for r in ordinary),
        role='visual distribution deviation and within-view visual heterogeneity; NOT structure/occlusion/difficulty ground truth',
        source_boundary='cached recorded paths match HoHo research source; historical extraction bytes not frozen, not certified current-byte-identical',
        validation='retrospective design; mixed subjective labels; building nested only separates this run refs/ranks/weight tuning; no checkpoint training independence proof',
        directions='both larger as exploratory hypothesis; directions/layer/neighbour5 fixed before current DINO subjective evaluation',
        fitting='same nonnegative .25 weight grid plus equal weight; simple/middle/hard working targets0/.5/1; building equal MSE',
        exclusions='OOS/doorway/pending retain individual dispersion/descriptors only; excluded from ordinary references and calibration',
        source_metadata=str(metadata_path), neighbour_audit='outer all queries; inner labelled validation queries; reference sizes and exact5 identities/buildings',
        deployment='does not overwrite earlier scores or establish three-class cutoffs', candidates=sets)
    write_json(OUT/'field_contract.json',contract)
    write_json(OUT/'summary.json',dict(all_images=len(rows),ordinary=len(ordinary),metrics=metrics,
        evaluated_weight_frequencies={name:dict(Counter({p['building']:json.dumps(p['weights']) for p in predictions
            if p['candidate']==name and p['label'] is not None}.values())) for name in sets}))
    building_losses = []
    for name in sets:
        for building in sorted({p['building'] for p in predictions if p['label'] is not None}):
            group = [p for p in predictions if p['candidate']==name and p['building']==building and p['label'] is not None]
            for score in ('baseline_score','calibrated_score'):
                building_losses.append(dict(candidate=name,building=building,score=score,n=len(group),
                    mse=float(np.mean([(p[score]/100-p['label']/2)**2 for p in group]))))
    write_csv(OUT/'building_losses.csv',building_losses)
    evaluated_five = [p for p in predictions if p['candidate']=='all_five' and p['label'] is not None]
    dino_zero = all(p['weights'][3:]==[0.0,0.0] for p in evaluated_five)
    point_loss = next(m['building_equal_mse'] for m in metrics if m['candidate']=='point_only' and m['score']=='calibrated_score')
    five_loss = next(m['building_equal_mse'] for m in metrics if m['candidate']=='all_five' and m['score']=='calibrated_score')
    lines=['# DINOv3：视觉距离与视觉异质性候选','',
        f"全研究图{len(rows)}的固定最后层缓存已读取；普通共同面板{len(ordinary)}图、{contract['labels']}份历史三档标签。全景/六面不是新增独立图片。",'',
        '两轴定义、内外折近邻隔离及来源限制见field_contract.json；不训练、下载或按案例选择层。保留点数和当前三轴基线；逐一加轴与五轴同时对照，禁止只挑最好结果。','',
        '|候选|评分|标签图|建筑|Spearman|异档对排序一致率|建筑等权MSE|','|---|---|---:|---:|---:|---:|---:|']
    for m in metrics:
        rho='N/A' if m['spearman'] is None else f"{m['spearman']:.4f}"
        concordance='N/A' if m['concordance'] is None else f"{m['concordance']:.4f}"
        lines.append(f"|{m['candidate']}|{m['score']}|{m['n']}|{m['buildings']}|{rho}|{concordance}|{m['building_equal_mse']:.4f}|")
    lines += ['', '## 本轮采用判断', '',
        '两轴按固定正向标准检查，单轴相关与误差、逐一加入的等权／选权和五轴全部并列。逐建筑误差见building_losses.csv，有标签建筑的选权频次见summary.json；不能仅凭汇总相关挑选轴或改计分方向。',
        f"五轴校准建筑等权MSE{five_loss:.5f}，同折点数{point_loss:.5f}；{'DINO两轴在有标签外折中全部零权重' if dino_zero else 'DINO两轴在部分有标签外折有非零权重'}。",
        '当前候选不自动加入评分；本轮组合或单轴表现不推论DINO或其它预先定义的视觉测量普遍无用。']
    lines += ['', '数值比较仍是回顾性主观一致程度，不是新盲验证；单轴或组合较好也不认证固有难度。两轴可受家具、纹理、照明和构图影响，未直接测量边界可见性、遮挡或非正交。','',
        '源缓存记录与研究PNG路径一致，缓存为历史float16：未证明历史提取时源文件字节与当前完全一致。上游预训练/模型选择是否接触目标未知。特殊图不因DINO距离大而自动困难或不可标。','',
        '复算：`.venv/Scripts/python.exe -m tools.thesis_main.analysis.difficulty_dino_20261009`。','']
    (OUT/'REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(images=len(rows),ordinary=len(ordinary),metrics=metrics)),flush=True)


if __name__=='__main__':
    run()
