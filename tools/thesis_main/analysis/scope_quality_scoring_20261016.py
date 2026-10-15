"""按指定完整参考重算冻结质量版本；不选参考、不改标注、不授予资格。"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import zipfile

import numpy as np

from .worker_wq_integration_20261015 import frozen_engine

ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT / 'research/quality/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'
MODEL_SOURCE = ROOT / 'research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py'
IDENTITY = ('object_id', 'image_id', 'worker_id', 'condition', 'current_target_id', 'reference_version')
METRICS = ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter',
           'height_mean_ratio', 'iou_3d_corner_mean')


@contextmanager
def scoring_engine():
    """一次打开冻结引擎，适合对整批queue复用；临时文件自动清理。"""
    spec = importlib.util.spec_from_file_location('scope_frozen_working_models', MODEL_SOURCE)
    models = importlib.util.module_from_spec(spec)
    # dataclass解析类型时需要可查到其定义模块。
    import sys
    sys.modules[spec.name] = models
    try:
        spec.loader.exec_module(models)
        with zipfile.ZipFile(ARCHIVE) as archive, frozen_engine(archive) as engine:
            yield engine, models
    finally:
        del sys.modules[spec.name]


def score_task(task, engine, models):
    """points为1024×512、top/bottom交替的最终环；调用方负责完整参考资格。"""
    result = {key: task[key] for key in IDENTITY}
    result.update({key: None for key in (*METRICS, 'IoU3D100', 'WQ', 'A10', 'B8L2')})
    result.update(score_status='unavailable', reasons=[],
        score_versions={name: params.version for name, params in models.MODELS.items()},
        metric_engine='pro_closeout_delta_20261015_frozen_geometry',
        iou_3d_definition='mean_height_prism_corner_mean_0_to_100',
        annotation_changed=False, reference_selection='caller_supplied_no_optimization')
    if task['reference_points'] is None or not task.get('reference_full_available', True):
        result['reasons'] = ['reference_full_points_missing']
        return result
    try:
        annotation = engine.geometry(task['annotation_points'])
    except (ValueError, TypeError, ArithmeticError) as exc:
        result['reasons'] = ['annotation:' + str(exc)]
        return result
    try:
        reference = engine.geometry(task['reference_points'])
    except (ValueError, TypeError, ArithmeticError) as exc:
        result['reasons'] = ['reference:' + str(exc)]
        return result
    try:
        measured = engine.measure(annotation, reference)
    except (ValueError, ArithmeticError) as exc:
        result['reasons'] = ['frozen_measurement:' + str(exc)]
        return result
    if measured['status'] != 'complete':
        result['reasons'] = measured.get('reasons', ['frozen_measurement_not_complete'])
        return result
    metrics = measured['metrics']
    result.update({key: metrics.get(key) for key in METRICS})
    values = [metrics[key] for key in ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')]
    scores = {name: float(models.score(*values, params)) for name, params in models.MODELS.items()}
    assert np.isclose(scores['WQ'], measured['scores']['WQ'], rtol=0, atol=1e-10), 'frozen WQ parity drift'
    result.update(scores)
    result.update(IoU3D100=100 * metrics['iou_3d_corner_mean'], score_status='complete')
    return result


def score_records(tasks):
    """完整批量接口；返回每条任务身份、状态、原因、分项、IoU及三版完整Q。"""
    with scoring_engine() as (engine, models):
        return [score_task(task, engine, models) for task in tasks]
