"""Offline review of preserved and diagnostic flat ceilings using existing viewer."""
import json
import os
import pandas as pd
from .diagnose_scope_ceiling_20261028 import OUT,ROOT


def main():
    candidates=json.loads((OUT/'CANDIDATES.json').read_text(encoding='utf-8'))
    heights=pd.read_csv(OUT/'HEIGHT_AUDIT.csv').set_index('target_id')
    scores=pd.read_csv(OUT/'SCORE_SUMMARY.csv').set_index('target_id')
    adoption=pd.read_csv(OUT.parent/'GEOMETRY_ACCEPTANCE.csv').set_index('target_id')
    catalog={r['target_id']:r for r in json.loads((OUT.parent/'REFERENCE_CATALOG.json').read_text(encoding='utf-8'))}
    rows=[];excluded=[]
    for r in candidates:
        r=dict(r);h=heights.loc[r['target_id']];a=adoption.loc[r['target_id']]
        reference=catalog[r['target_id']]
        reasons=list(reference['image_analysis_hold_reasons'])
        if reference['image_analysis_blocked']:reasons.append('image_analysis_blocked')
        if not reference['current_target']:reasons.append('historical_not_current')
        if reasons:
            excluded.append(dict(image=r['image'],target_id=r['target_id'],reasons=reasons))
            continue
        photo=ROOT/'data/mp3d_layout/img_v'/(r['image_id']+'.jpg');assert photo.exists()
        r.update(photo=os.path.relpath(photo,OUT).replace('\\','/'),height_range=float(h.height_range_h),max_pixel_move=float(h.max_top_y_move_px),
                 use_status='既有暂停：不因本次复核解除' if pd.notna(a.hold_reasons) else '当前参考' if a.current_target else '历史／非当前：不新增资格')
        r['max_q_delta']=float(scores.loc[r['target_id'],'B8L2_max_abs_delta']) if r['target_id'] in scores.index else None
        rows.append(r)
    rows.sort(key=lambda r:r['height_range'],reverse=True)
    viewer=os.path.relpath(ROOT/'research/statistics/research_explorer_v1_r2_20261017',OUT).replace('\\','/')
    template=__file__.replace('.py','.html')
    from pathlib import Path
    page=Path(template).read_text(encoding='utf-8').replace('__VIEWER__',viewer).replace('__CASE_COUNT__',str(len(rows)))
    (OUT/'ceiling-review-data.js').write_text('window.CEILING_REVIEW='+json.dumps(dict(schema='ceiling_review_20261028_v1',cases=rows),ensure_ascii=False,allow_nan=False)+';',encoding='utf-8')
    (OUT/'ceiling-review.html').write_text(page,encoding='utf-8')
    assert len(rows)==30 and len({r['target_id'] for r in rows})==30
    qa=json.loads((OUT/'REVIEW_PAGE_QA.json').read_text(encoding='utf-8'))
    qa.update(cases=len(rows),excluded_from_review=excluded,selection_source='../REFERENCE_CATALOG.json',selection_rule='current_target and not image_analysis_blocked and no image_analysis_hold_reasons')
    qa['logic_checks']=[x.replace('34-record','30-record') for x in qa['logic_checks']]
    (OUT/'REVIEW_PAGE_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Built',len(rows),'cases:',OUT/'ceiling-review.html')


if __name__=='__main__':main()
