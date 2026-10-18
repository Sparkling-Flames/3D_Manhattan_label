"""只验证独立包的当前输入、实际融合和冻结评分入口，不改分析结果。"""
import json
from pathlib import Path

from tools.thesis_main.data_prep.consolidate_research_input import load_current_bundle
from tools.thesis_main.analysis.consensus_delivery_20261008 import fuse, WORKING_GAP
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores

root=Path(__file__).resolve().parent
bundle=load_current_bundle(root/'research/data/processed_input_review_20261018/manifest.json')
assert bundle['validation']['status']=='passed'
pools=json.loads((root/'CURRENT_POOLS.json').read_text(encoding='utf-8'))['images']
pool=next(p for p in pools if p['image']=='7y3sRwLe3Va-04' and p['condition']=='manual')
result=fuse(pool['records'][:6],gap=WORKING_GAP)
assert result['automatic'] is not None
with scoring_engine() as (engine,models):
    geometry=engine.geometry(pool['reference']['points_1024x512'])
    measurement=engine.measure(geometry,geometry)
    assert measurement['status']=='complete'
    scores=dual_scores(measurement['metrics'],models)
    assert all(abs(v-100)<1e-8 for v in scores.values()),scores
print(json.dumps(dict(current_bundle='passed',pools=len(pools),fusion_six_real_members='executed',self_scores=scores)))
