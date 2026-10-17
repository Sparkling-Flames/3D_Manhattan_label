"""Frozen B8L2/D10 diagnostics with explicit partial-reference handling."""
import importlib.util
import sys
import tempfile
import zipfile
from dataclasses import replace
import numpy as np
from shapely.geometry import Polygon

from . import simulate_annotators as base
from .difficulty_wild_inputs import QUALITY, DIFFICULTY, read

ARCHIVE = base.ROOT / 'research/quality_joint_closeout_review_20261015/pro_closeout_delta.zip'
MODEL_SOURCE = 'research/quality/quality_ab_feedback_handoff_20261015/prior_AB/src/working_models.py'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Evaluator:
    def __init__(self, sources):
        self.sources = sources
        self.temp = tempfile.TemporaryDirectory(prefix='wild_quality_')
        from pathlib import Path
        root = Path(self.temp.name).resolve()
        with zipfile.ZipFile(ARCHIVE) as z:
            for name in z.namelist():
                if (name.startswith('engine/') and name.endswith('.py')) or name in ('src/quality.py', 'configs/WQ_LS08_UNCHANGED.json'):
                    if not (root / name).resolve().is_relative_to(root):
                        raise ValueError('invalid_engine_archive_member')
                    z.extract(name, root)
        # Do not silently reuse a different engine loaded by another evaluator.
        for name in ('audit_geometry', 'geometric_components', 'strict_geometry', 'height_revision',
                     'centered_height', 'traditional_metrics', 'prepare_inputs'):
            if name in sys.modules:
                raise ValueError('metric_engine_already_loaded:' + name)
        self.engine = module_at('wild_frozen_quality', root / 'src/quality.py')
        self.models = module_at('wild_working_models', sources['directory'] / MODEL_SOURCE)
        self.parameters = (self.models.B, replace(self.models.B, version='B8L2-D10-20261016', direction_scale_deg=10.))
        self.refs = {}

    def close(self):
        from pathlib import Path
        root = str(Path(self.temp.name).resolve())
        for name, module in list(sys.modules.items()):
            if str(getattr(module, '__file__', '')).startswith(root):
                del sys.modules[name]
        sys.path[:] = [p for p in sys.path if not p.startswith(root)]
        self.temp.cleanup()

    def score_metrics(self, metrics):
        values = [metrics[k] for k in ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')]
        return {name: float(self.models.score(*values, p)) for name, p in zip(('B8L2', 'D10'), self.parameters)}

    def evaluate(self, points, difficulty):
        tid = difficulty['difficulty_target_id']
        result = dict(reference_id=tid, B8L2=None, D10=None, floor_iou=None, status='unavailable', reasons=[])
        if difficulty['gt_error_excluded']:
            result.update(status='gt_error_excluded', reasons=['bad_gt_not_used'])
            return result
        ref = self.sources['v6_references'].get(tid)
        if ref is None:
            result['reasons'] = ['v6_reference_missing']; return result
        try:
            floor = ref.get('floor_xz_h')
            if floor:
                rays = base.rays(np.asarray(points)[1::2])
                polygon = Polygon(-rays[:, (0, 2)] / rays[:, 1, None])
                reference_polygon = Polygon(floor)
                if polygon.is_valid and reference_polygon.is_valid:
                    result['floor_iou'] = float(polygon.intersection(reference_polygon).area / polygon.union(reference_polygon).area)
            if not difficulty['reference_full_available'] or not ref.get('full_reference_available'):
                result.update(status='floor_only', reasons=['top_boundary_not_confirmed'])
                return result
            if tid not in self.refs:
                self.refs[tid] = self.engine.geometry(ref['points_1024x512'])
            m = self.engine.measure(self.engine.geometry(points), self.refs[tid])
            result['status'] = m['status']; result['reasons'] = m.get('reasons', [])
            if m['status'] == 'complete':
                result.update(self.score_metrics(m['metrics']), metrics=m['metrics'])
        except (ValueError, ArithmeticError, TypeError) as exc:
            result.update(status='measurement_failed', reasons=[str(exc)])
        return result

    def parity(self):
        """Check the actual frozen score formula against all scored real rows."""
        errors = []
        for row in self.sources['shared']:
            if row['quality_usable'] != 'True':
                continue
            metrics = {k: float(row[k]) for k in ('iou_2d', 'S_bottom_deg', 'dir', 'Hmean', 'Hcenter')}
            scores = self.score_metrics(metrics)
            errors.append(max(abs(scores[k] - float(row[k])) for k in scores))
        if not errors or max(errors) > 1e-7:
            raise ValueError('frozen_score_formula_parity_failed')
        return dict(records=len(errors), max_absolute_error=max(errors), passed=True)
