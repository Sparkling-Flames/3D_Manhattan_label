"""Restore submitted axes; refine only supported offsets, never rotate from a door leaf."""
import copy
import json
import zipfile
from pathlib import Path

import build_doorframe_alignment_20261031 as display

BASE=display.BASE
PREP=display.PREP
OUT=PREP/'manhattan_correction_20261031'


def axis(cut):
    a,b=cut['line']
    fixed=[k for k in range(2) if a[k]==b[k]]
    if len(fixed)!=1 or cut['side'] not in (-1,1):
        raise ValueError('停止边必须平行于当前空间主轴且具有有效方向')
    return fixed[0]


def main():
    OUT.mkdir(exist_ok=True)
    original=json.loads((BASE/'data.js').read_text(encoding='utf8').split('=',1)[1][:-1])['cases']
    submitted=display.read(PREP/'USER_REVIEW_FINAL_RECEIVED.json')['cases']
    archived=display.read(BASE/'first_review_audit/review_result_v2.json')['cases']
    archive_path=Path('C:/Users/ASUS/Downloads/门洞审核.zip')
    with zipfile.ZipFile(archive_path) as archive:
        member=next(n for n in archive.namelist() if n.endswith('/review_result_v2.json'))
        zip_cases=json.loads(archive.read(member))['cases']
    assert zip_cases==archived
    zipped={c['image_id']:c for c in zip_cases}
    decisions=[]; comparisons=[]
    for c in original:
        key=c['image_id'];image=c['image'];baseline=submitted[key]['cuts'];cuts=copy.deepcopy(baseline)
        assert axis(cuts[0])==axis(cuts[1])
        source='ZIP初审切分，与最新用户导出一致'
        note='保留既有方向与位置；门框宽度仍为工作候选，不以模糊端点旋转或扩大切分。'
        evidence=[]
        if image=='B6ByNegPMKs-42':
            source='最新用户导出覆盖ZIP旧横切；保留用户纵切与已再确认分类'
            note='固定x=0.022453955495470402与x=0.125；第二面仍保留原暂拟身份。禁止用上一轮门扇/斜线候选覆盖。'
            assert axis(cuts[0])==0 and cuts[0]['line'][0][0]==0.022453955495470402
            assert cuts[1]['line'][0][0]==0.125
        elif image=='7y3sRwLe3Va-10':
            note='以固定墙口和顶部轨道方向定位；中央伸出的门扇及拉手不是空间止边。撤回上轮自由斜线，保留ZIP两条平行x停止边。'
        elif image=='7y3sRwLe3Va-18':
            source='ZIP初审与最新用户切分；复核固定柱角和侧板外端'
            evidence=[dict(points=[[230,397],[797,397]],role='近侧柱角'),dict(points=[[171,380],[856,380]],role='侧板外端；不能只取柱前脸厚度')]
            note='撤回旧带过宽的结论。近侧柱角支持z约0.145，侧板外端支持z约0.538；保留整个墙口厚度，不收窄为柱子前脸。'
        excluded=image in ['pRbA3pwrgk9-01','pRbA3pwrgk9-11']
        pending=image=='q9vSo1VnCiC-24'
        decisions.append(dict(image=image,image_id=key,status='excluded' if excluded else 'uncertain' if pending else 'manhattan',
            cuts=None if excluded or pending else cuts,provisional_cuts=cuts if pending else None,
            source=source,notes=note,evidence_pixels=evidence,needs_human=False,
            scope_pending=pending,reference_adopted=False,manhattan_axis='x' if axis(cuts[0])==0 else 'z',
            human_answer_labels_preserved=True))
        comparisons.append(dict(image=image,zip_cuts=zipped[key]['cuts'],user_cuts=baseline,current_cuts=cuts,
            user_differs_from_zip=baseline!=zipped[key]['cuts'],offset_refined=cuts!=baseline))
    assert sum(r['user_differs_from_zip'] for r in comparisons)==1
    assert sum(r['offset_refined'] for r in comparisons)==0
    display.main(decisions,OUT)
    display.save('ZIP_USER_CUT_COMPARISON.json',comparisons)
    page=OUT/'index.html';text=page.read_text(encoding='utf8')
    text=text.replace('门框逐图视觉对齐','门洞曼哈顿切分修正')
    text=text.replace('<h1>门洞曼哈顿切分修正</h1>', '<h1>门洞曼哈顿切分修正</h1><p><strong>以ZIP初审和最新用户修改为基准，停止边严格平行于空间主轴。B6-42保留用户纵切；7y-10不用门扇边；7y-18保留包括侧板在内的原厚度范围。灰虚线为最新用户导出的基准线，彩线为当前工作切分。</strong></p>')
    page.write_text(text,encoding='utf8')


if __name__=='__main__':main()
