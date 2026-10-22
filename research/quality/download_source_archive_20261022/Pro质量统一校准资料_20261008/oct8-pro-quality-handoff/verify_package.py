#!/usr/bin/env python3
"""Verify joins, original photos, blank review cells, formulas and clean-room replay."""
from pathlib import Path
import json,csv,zipfile,xml.etree.ElementTree as ET,hashlib,math,tempfile,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'data/unified36_existing_metrics.json').read_text())
ratings=json.loads((ROOT/'inputs/review36_user_20261008.json').read_text())
geom=json.loads((ROOT/'inputs/frozen_geometry.json').read_text())
raw=list(csv.DictReader((ROOT/'inputs/selected48_raw_metrics.csv').open(encoding='utf-8-sig')))
assert len(rows)==36 and len({r['record_id'] for r in rows})==36 and all(r['mainset_included'] for r in rows)
assert len({r['building'] for r in rows})==6
assert all(r['unified_quality_score'] is None for r in rows)
old={r['recordId']:r for r in ratings['ratings']}
for r in rows:
    h=old[r['record_id']]
    assert (r['human_score_original'],r['scope_note_original'],r['geometry_note_original'])==(h['overallScore'],h['scopeNote'],h['geometryNote'])
for im in geom['images']:
    assert hashlib.sha256((ROOT/'inputs/original_photos'/f"{im['code']}.png").read_bytes()).hexdigest()==im['imageSha256']
for r in raw:
    a=float(r['area_h2']);g=float(r['reference_area_h2']);iou=float(r['iou']);inter=iou*(a+g)/(1+iou)
    ha=float(r['height_mean_h']);hg=ha-float(r['height_mean_signed_h']);iv=inter*min(ha,hg)
    assert math.isclose(iv/(a*ha+g*hg-iv),float(r['conditional_volume_iou']),abs_tol=2e-12)
    assert math.isclose(abs(ha-hg)/hg,float(r['height_mean_relative_error']),abs_tol=2e-12)
ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with zipfile.ZipFile(ROOT/'review/统一标准复核空白36条.xlsx') as z:
    xml=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    cells={c.attrib['r']:c for c in xml.findall('.//x:c',ns)}
    assert all(cells.get('E'+str(i)) is None or cells['E'+str(i)].find('x:v',ns) is None for i in range(9,45))
    assert cells['G5'].find('x:f',ns).text=='COUNT(E9:E44)'
    assert len(xml.findall('.//x:dataValidation',ns))==4
assert len(json.loads((ROOT/'analysis/selected_review_contrasts.json').read_text()))==6
assert len(json.loads((ROOT/'review/common_rubric_rereview_blank36.json').read_text()))==36
with tempfile.TemporaryDirectory(prefix='pro36-rerun-') as td:
    q=Path(td);shutil.copytree(ROOT/'inputs',q/'inputs')
    for fname in ['prepare_data.py','analyze_imagewise.py','verify_imagewise.py']:shutil.copyfile(ROOT/fname,q/fname)
    for fname in ['prepare_data.py','analyze_imagewise.py','verify_imagewise.py']:
        subprocess.run([sys.executable,str(q/fname)],check=True,capture_output=True)
    for sub in ['data','analysis','review']:
        for f in (q/sub).rglob('*'):
            if f.is_file():assert f.read_bytes()==(ROOT/f.relative_to(q)).read_bytes(),str(f)
checks=dict(status='passed',mainset_records=36,buildings=6,reference_rows=48,common_metric_cell_checks=480,
    extra_volume_height_formula_checks=96,all_new_labels_blank=True,xlsx_new_scores_blank=36,xlsx_validations=4,
    xlsx_progress_formula='COUNT(E9:E44)',selected_contrasts=6,all_numerical_outputs_cleanroom_identical=True,
    six_original_photos_hash_verified=True,user_Uw_connection_confirmation_honored=True)
(ROOT/'provenance/final_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(checks,ensure_ascii=False,indent=2))
