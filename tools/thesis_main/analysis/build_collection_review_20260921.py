"""复用 Panorama Studio 样式，生成独立的八组采集采用审核，不派发。"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'analysis_results/collection_review_20260921'
ORDER = ['G180','G124','G155','G051','G201','G130','G234','G235']
QUESTIONS = {
    'G180': '你曾写“疑似oos”。这四张是否值得本轮新增？可作为OOS或范围不明确情景研究，不需要先判成普通样本。',
    'G124': '你曾写“有可能算oos”。是否采用本轮五张？请记录希望研究的差异；OOS不自动等于不采用。',
    'G155': '六图同房已由你确认，不重问。跨三个原子组的可见区域是否有需要保留的差异？是否采用全部六图？',
    'G051': '你曾写“22,19,12有点难标”。这些难点是否值得本轮采集？主空间原选项待定不等于否定同房。',
    'G201': '你提到两个凸起墙难标、有人忽略。这正可能形成局部表达差异：是否采用六图，哪些细节需要重点保留？',
    'G130': '已有同房与范围相近记录。本轮是否采用这五张普通视角？如有例外，只需在对应图片下说明。',
    'G234': '已有同房与范围相近记录。本轮是否采用四张？当前“特殊用途”池仅一个建筑，不据此承诺跨建筑预测。',
    'G235': '你曾提到有人忽略墙体小拐角。本轮是否采用四张来观察这种差异？无需因此把它们定义成不同房间。',
}


def read(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))


def main():
    plan=read('analysis_results/collection_plan_20260921_v3/统计与安排.json')
    base=read('analysis_results/collection_plan_20260921/统计与安排.json')
    registry=read('analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json')
    counts={i['image_id']:i for i in base['images']}
    original={g['review_code']:g for g in registry['groups']}
    candidates={g['candidate_id']:g for g in registry['candidates']}
    registry_images={i['image_id']:i for i in registry['images']}
    groups=[]
    for rank,gid in enumerate(ORDER,1):
        selected=[i for i in plan['images'] if i['phase']==3 and i['room']==gid]
        assert selected, gid
        images=[]
        for item in selected:
            iid=item['image_id']; b=counts[iid]; ri=registry_images[iid]
            assert (ROOT/b['image_path']).is_file(), b['image_path']
            images.append(dict(**item, path='../../'+b['image_path'].replace('\\','/'),
                history_n=b['history_n'],actual_n=b['actual_n'],
                prior_image_record=b['original_decision'], prior_notes=ri['all_user_notes'],
                historical_workers=[f'W{w:03d}' for w in b['history_workers']],
                proposed_workers=[a['slot'] for a in plan['assignments'] if a['image_id']==iid]))
        groups.append(dict(id=gid,priority=rank,question=QUESTIONS[gid],
            previous=original[gid]['raw_current'],holds=candidates[gid]['selection_hold_reasons'],
            images=images,tasks=sum(i['need'] for i in selected),
            other_candidate_codes=[counts[i]['code'] for i in candidates[gid]['image_ids'] if i not in {x['image_id'] for x in selected}]))
    assert len(groups)==8 and sum(len(g['images']) for g in groups)==39
    assert sum(g['tasks'] for g in groups)==528
    binding=dict(plan='collection_plan_20260921_v3',review_version=1,
        members=[dict(group=g['id'],images=[dict(image_id=i['image_id'],base_n=i['base_n'],target=i['target'],need=i['need']) for i in g['images']]) for g in groups])
    payload=dict(schema='collection_adoption_review_v1',binding=binding,groups=groups,
        source_files=['analysis_results/collection_plan_20260921_v3/统计与安排.json',
            'analysis_results/collection_plan_20260921/统计与安排.json',
            'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json'])
    OUT.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'analysis_results/panorama_studio_20260907_v3/studio.css',OUT/'studio.css')
    for source,target in [('collection_review.html','index.html'),('collection_review.js','review.js')]:
        shutil.copyfile(Path(__file__).with_name(source),OUT/target)
    (OUT/'data.js').write_text('window.COLLECTION_REVIEW='+json.dumps(payload,ensure_ascii=False).replace('<','\\u003c')+';\n',encoding='utf8')
    (OUT/'审核输入.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'{OUT}/index.html：8组39图，528份候选；原页、原图与采用决定均未修改。')


if __name__=='__main__':
    main()
