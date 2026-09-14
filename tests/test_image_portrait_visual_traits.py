"""Small contract check for the blinded 648-image visual review."""
import json
from tools.thesis_main.analysis.image_portrait.visual_traits import ROOT, images

def test_visual_traits_identity_and_contract():
    source=images()
    records=json.loads((ROOT/'analysis_results/image_portrait_20260914_v1/visual/visual_traits.json').read_text(encoding='utf-8'))
    assert len(records)==648
    for original, row in zip(source,records):
        assert row['image_id']==original['image_id'] and row['index']==original['index']
        assert (ROOT/original['path']).is_file()
        assert row['reviewed'] and row['evidence'].strip()
        assert row['reviewer']=='AI_image_only'
        for field in ('floor_boundary','ceiling_boundary'):
            assert row[field] in {'present','partial','unknown'}
        for field in ('corner_occlusion','connected_space','reflection_glass','low_contrast'):
            assert row[field] in {'present','absent','unknown'}
        assert not {'worker_id','quality','difficulty','active_time','prediction'} & row.keys()

def test_visual_resolution_recheck_is_separate_and_recomputable():
    data=json.loads((ROOT/'analysis_results/image_portrait_20260914_v1/visual/resolution_recheck.json').read_text(encoding='utf-8'))
    rows=data['images']
    assert [r['index'] for r in rows]==list(range(0,648,32))
    old=json.loads((ROOT/'analysis_results/image_portrait_20260914_v1/visual/visual_traits.json').read_text(encoding='utf-8'))
    for row in rows:
        assert row['image_id']==old[row['index']]['image_id']
        assert row['source_dimensions'][0]>=1024 and row['source_dimensions'][1]>=512
        assert row['evidence'] and row['reviewed']
        assert row['thumbnail_traits']=={f:old[row['index']][f] for f in row['thumbnail_traits']}
    for field, stat in data['summary']['agreement'].items():
        assert stat['denominator']==len(rows)
        assert stat['matches']==sum(r['thumbnail_traits'][field]==r['reviewed_traits'][field] for r in rows)
