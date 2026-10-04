import json

import pytest
from shapely.geometry import box

from tools.thesis_main.analysis.lee_tile_precision_20261003 import run
from tools.thesis_main.analysis.lee_difficulty_20261003 import summarize


def test_new_collection_rejects_stale_difficulty_and_accepts_corrected_inventory(tmp_path):
    from pathlib import Path
    from tools.thesis_main.analysis.lee_difficulty_20261003 import collect
    stale = tmp_path/'stale'; stale.mkdir()
    with pytest.raises(ValueError, match='image_or_label_drift:B6ByNegPMKs-40'):
        collect(stale, chosen=['B6ByNegPMKs-40'])
    current = tmp_path/'current'; current.mkdir()
    inventory = Path(__file__).parents[1]/'analysis_results/review_source_audit_20261004/corrected_inventory'
    data = collect(current, chosen=['B6ByNegPMKs-40'], inventory_dir=inventory)
    assert data['images'][0]['difficulty'] == '简单'
    assert json.loads((current/'source_binding.json').read_text(encoding='utf-8'))['status'] == 'passed'


def test_bounded_run_preserves_population_and_exact_votes(tmp_path):
    records = [dict(id=str(i), worker=str(i), condition='manual', independent=True,
                    consensus_eligible=True, main_consensus_gate={'status':'main_candidate'},
                    footprint=list(box(i,0,i+2,2).exterior.coords)[:-1]) for i in range(3)]
    data = dict(schema='lee_tile_stage1_input_v1', images=[dict(code='image', annotations=records+[dict(records[0],id='semi',condition='semi')],
        references=[dict(version='original', footprint=records[0]['footprint'])])])
    source=tmp_path/'input.json'; source.write_text(json.dumps(data),encoding='utf-8')
    result=run(source,tmp_path/'result',max_k=2,stratum=('manual','main_candidate'),make_plot=False)
    assert len(result)==4 and {r['n'] for r in result}=={3}
    assert {r['k'] for r in result}=={1,2}
    assert all(r['estimator']=='exact' for r in result)
    assert next(r for r in result if r['k']==1)['iou_mean']==pytest.approx(4/9)
    # 两人MV50为并集；三个组合分别得到2/3、1/2、1/4。
    assert next(r for r in result if r['k']==2 and r['method']=='mv50')['iou_mean']==pytest.approx((2/3+1/2+1/4)/3)
    with pytest.raises(ValueError,match='insufficient_roster_for_fixed_k'):
        run(source,tmp_path/'invalid',max_k=4,make_plot=False)


def test_group_means_keep_images_fixed_and_propagate_only_mc_error():
    meta={'a':dict(difficulty='简单',building='uNb9QFRL6hY'),
          'b':dict(difficulty='困难',building='other')}
    rows=[]
    for image,values in [('a',[.8,.9]),('b',[.2,.4])]:
        for method in ['mv50','mv_strict']:
            for k,q in enumerate(values,1):
                rows.append(dict(image=image,method=method,version='original',k=k,n=8,
                    iou_mean=q,mc_error_bound=0 if k==1 else .02,
                    expected_intersection_h2=1,expected_omission_h2=1,expected_extension_h2=.5))
    enriched,groups=summarize(rows,meta)
    group=next(r for r in groups if r['cohort']=='全部' and r['method']=='mv50' and r['k']==2)
    assert group['image_n']==2 and group['iou_mean']==pytest.approx(.65)
    assert group['gain_from_one']==pytest.approx(.15)
    assert group['mc_error_bound']==pytest.approx(.02)
    assert group['omission_fraction']==pytest.approx(.5)
    assert all(r['gain_from_one']==0 for r in enriched if r['k']==1)
    assert {r['image_n'] for r in groups if r['cohort']=='非困难'}=={1}
    with pytest.raises(ValueError,match='nonconstant_image_panel'):
        summarize(rows[:-1],meta)
    with pytest.raises(ValueError,match='duplicate_curve_point'):
        summarize(rows+[rows[0]],meta)
