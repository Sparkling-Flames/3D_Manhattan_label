"""图片难度候选特征：标签盲提取；模型输出、历史暴露及缺失分别保存。"""
from __future__ import annotations

import csv
import json
from math import isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FEATURE_SOURCE = 'analysis_results/c2b_validation_static_20260802_v16/static/c2b_static_model_risk.csv'
FEATURE_MANIFEST = 'analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json'
BILAYOUT_SOURCE = 'analysis_results/independent_direction_worker_review_20260908_v1/recomputed/bilayout_recomputed_per_image.csv'
MODEL_SOURCE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/layouts.jsonl'
MODEL_PROVENANCE = 'analysis_results/uncertainty_cloud_inputs_20260906_v1/models/MODEL_PROVENANCE.json'
GEOMETRY_SOURCE = 'analysis_results/uncertainty_visual_review_20260907_v1/reproduced_numerical/measurement/layout_audit.csv'
SCORE_FEATURES = ('hohonet_offline_pair_count', 'd_model_feat_static', 'bilayout_floor_gap')
FEATURE_DEFINITIONS = {
    'hohonet_offline_pair_count': {
        'meaning': 'HoHoNet ep300离线重放原数组中的上下点对数，未经新的人为修正；不是历史实际预标注暴露点数。',
        'source': MODEL_SOURCE, 'source_role': 'offline_ep300_replay',
        'limitation': '约束后处理和四角回退可能简化输出；不等同真实角数、几何复杂度或已验证难度。',
        'training_overlap_status': 'not_independently_verified',
        'checkpoint_selection_target_gt_use': 'unknown_not_verified',
    },
    'd_model_feat_static': {
        'meaning': '历史global图像描述符经冻结reference PCA与scale变换后，到reference描述符5近邻的平均欧氏距离；图像分布偏离。',
        'source': FEATURE_SOURCE, 'manifest': FEATURE_MANIFEST,
        'definition_code': 'tools/thesis_main/analysis/c2b_static_evidence.py:materialize_static_model_risk',
        'limitation': '历史reference图像池与尺度；不是几何失败、人员质量或当前任务已验证难度。',
        'reference_pool': '冻结历史reference，1647图；原审计路径/内容不重合通过，但本次未证明建筑独立。',
        'target_building_overlap_status': 'unknown_not_verified',
        'evaluation_limit': '固定历史特征下的回顾性留建筑评估，不能声称整个PCA/5NN/模型链条在新建筑上独立泛化。',
    },
    'bilayout_floor_gap': {
        'meaning': '同一BiLayout模型enclosed/extended头，按源点序、相机高度归一化声明底面之间的1-IoU；只接floor_status=computable。',
        'source': BILAYOUT_SOURCE, 'upstream_layouts': MODEL_SOURCE,
        'definition_code': 'tools/thesis_main/analysis/review_bilayout_logic_20260908.py + archive audit.footprint/dp',
        'limitation': '双头差异可反映范围差异；不是模型到GT误差；原顺序不可计算保留None，不做x排序修补。',
        'training_overlap_status': 'not_independently_verified_do_not_infer_from_split_name',
        'checkpoint_selection_target_gt_use': 'unknown_not_verified',
    },
    'bilayout_legacy_band': {
        'meaning': '历史球面投影ERP墙带1-IoU；与BEV floor分别存储，未进入基线评分。',
        'source': BILAYOUT_SOURCE,
    },
    'hohonet_floor_valid': {
        'meaning': '已有审计中源点序声明底面是否有效且包含相机；未知None，不代表曼哈顿正交性或人类可标性。',
        'source': GEOMETRY_SOURCE,
    },
    'hohonet_fallback_used': {
        'meaning': '原模型资料未逐图记录回退，全部None；不能由四点输出猜测。',
        'source': MODEL_PROVENANCE,
    },
    'hohonet_legacy_pair_count': {
        'meaning': 'candidate_prescreen_legacy_output原数组点对数，保持与ep300重放独立；不假定等于所有阶段实际暴露。',
        'source': MODEL_SOURCE,
    },
}


def _indexed_csv(relative, key='image_id'):
    with (ROOT / relative).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError('duplicate_feature_source_key:' + relative + ':' + value)
        result[value] = row
    return result


def _number(row, key):
    if row is None or row[key] == '':
        return None
    value = float(row[key])
    if not isfinite(value):
        raise ValueError('nonfinite_model_field:' + key)
    return value


def _pair_count(model):
    if model is None or not model['source_exists'] or not model['points_1024x512']:
        return None
    points = model['points_1024x512']
    if len(points) % 2 or any(len(p) != 2 or not all(isfinite(v) for v in p) for p in points):
        raise ValueError('invalid_model_point_array:' + model['layout_id'])
    if (model['coordinate_width'], model['coordinate_height']) != (1024, 512):
        raise ValueError('model_coordinate_frame_mismatch:' + model['layout_id'])
    return len(points) // 2


def extract_features(bundle=None):
    """259研究图为主名单；不读取人工标签、人员作答或GT坐标来生成特征。"""
    if bundle is None:
        from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
        bundle = load_current_bundle()
    static = _indexed_csv(FEATURE_SOURCE)
    bilayout = _indexed_csv(BILAYOUT_SOURCE)
    geometry = _indexed_csv(GEOMETRY_SOURCE, 'layout_id')
    models = {}
    with (ROOT / MODEL_SOURCE).open(encoding='utf-8-sig') as stream:
        for line in stream:
            model = json.loads(line)
            if model['model_family'] != 'HoHoNet':
                continue
            key = model['image_id'], model['source_role']
            if key in models:
                raise ValueError('duplicate_model_role:' + str(key))
            models[key] = model
    rows = []
    image_ids = set()
    for image in bundle['research']['images']:
        iid = image['image_id']
        if iid in image_ids:
            raise ValueError('duplicate_research_image:' + iid)
        image_ids.add(iid)
        offline = models.get((iid, 'offline_ep300_replay'))
        legacy = models.get((iid, 'candidate_prescreen_legacy_output'))
        bi = bilayout.get(iid)
        audited = geometry.get(offline['layout_id']) if offline else None
        floor_valid = None
        if audited and audited['floor_ok'] != '':
            if audited['floor_ok'] not in ('True', 'False'):
                raise ValueError('unknown_geometry_boolean:' + iid)
            floor_valid = audited['floor_ok'] == 'True'
        row = dict(image_id=iid, image=image['image_code'], building=image['building_id'],
            room=image['room_id'],
            hohonet_offline_pair_count=_pair_count(offline),
            hohonet_legacy_pair_count=_pair_count(legacy),
            d_model_feat_static=_number(static.get(iid), 'd_model_feat_static'),
            bilayout_floor_gap=_number(bi, 'floor') if bi and bi['floor_status'] == 'computable' else None,
            bilayout_floor_status=bi['floor_status'] if bi else 'missing_source',
            bilayout_legacy_band=_number(bi, 'band') if bi and bi['band_status'] == 'computable' else None,
            bilayout_source_present=bi is not None,
            hohonet_floor_valid=floor_valid,
            hohonet_floor_failure=audited['floor_failure'] if audited else 'unknown_not_audited',
            hohonet_fallback_used=None, hohonet_fallback_status='unknown_not_recorded',
            hohonet_offline_source=offline['source_path'] if offline else None,
            hohonet_legacy_source=legacy['source_path'] if legacy else None,
            static_feature_source=FEATURE_SOURCE if iid in static else None,
            bilayout_source=BILAYOUT_SOURCE if bi else None,
            model_layout_source=MODEL_SOURCE if offline or legacy else None,
            provenance=dict(model=MODEL_PROVENANCE, static=FEATURE_MANIFEST,
                geometry=GEOMETRY_SOURCE, model_training_overlap='not_independently_verified',
                static_reference_building_overlap='unknown_not_verified',
                checkpoint_selection_target_gt_use='unknown_not_verified'))
        row['model_available'] = any(row[name] is not None for name in SCORE_FEATURES)
        rows.append(row)
    return rows
