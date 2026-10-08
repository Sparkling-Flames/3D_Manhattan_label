"""审核回执必须绑定所选原答；切换新版不覆盖旧记录。"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'tools/thesis_main/analysis/wall_identity_review_20261007.html'


def test_review_import_rejects_observation_outside_selected_group():
    source = TEMPLATE.read_text(encoding='utf-8')
    validate = 'function validate' + source.split('function validate', 1)[1].split('function persist', 1)[0]
    obs = [dict(id='a', pair_index=0), dict(id='b', pair_index=0)]
    data = dict(schema='wall_identity_review_20261008_v2', revision=True, images=[dict(
        code='image', image_id='id', observations=obs,
        states={'7.5': [dict(label='G01', members=[0]), dict(label='G02', members=[1])]})])
    review = dict(schema=data['schema'], decisions=[dict(image='image', image_id='id',
        note='', done=False, verdicts={'7.5': '需要少量人工'}, issues=[dict(type='不确定', note='',
        groups=[dict(gap='7.5', label='G01')], selected_members=[obs[0]])])])
    code = f"const D={json.dumps(data)}, v={json.dumps(review)};\n"
    code += "const verdicts=['','可用','需要少量人工','暂不能用','不确定'];const identityTypes=['都想标同一墙线','包含不同墙线','不确定'];\n"
    code += validate + "\nconst assert=require('node:assert/strict');"
    code += "assert.deepEqual(validate(v).image.issues[0].selected_members,[D.images[0].observations[0]]);"
    code += "v.decisions[0].issues[0].selected_members=[D.images[0].observations[1]];assert.throws(()=>validate(v),/具体来源不匹配/);"
    code += "v.schema='wall_identity_review_20261007_v1';assert.throws(()=>validate(v),/请选择本工作台/);"
    result = subprocess.run(['node'], input=code, text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0, result.stderr
    assert '</option value=' not in source


def test_revisit_preserves_old_group_labels_and_keeps_new_answers_blank():
    root = ROOT/'analysis_results/direct_fusion_20261007/gap_sweep/population'
    def data(path):
        text = path.read_text(encoding='utf-8')
        return json.loads(text.split('<script id="source" type="application/json">')[1].split('</script>')[0])
    old = data(root/'review.html'); new = data(root/'refine_20261008/review.html')
    assert old['schema'] != new['schema']
    assert sum(im['priority'] for im in new['images']) == 11
    for a, b in zip(old['images'], new['images']):
        assert a['code'] == b['code']
        for gap in ('7.5', '9'):
            assert a['states'][gap] == b['states'][gap]
        assert 'decisions' not in b and 'prior' in b
        assert (root/'refine_20261008'/b['src']).exists()
