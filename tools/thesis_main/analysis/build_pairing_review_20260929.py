"""34份独立上下配对工作台；坐标只读，连接顺序不在本轮确认。"""
import csv
from .finalize_review_20260928 import read, dump
from .build_order_studio_20260926 import ROOT, encode
from tools.label_studio.panorama_studio.build import data_image

OUT=ROOT/'analysis_results/pairing_review_20260929'


def build():
    objects={o['object_id']:o for o in read(ROOT/'analysis_results/shared_x_baseline_20260928/preprocessed_source.json')['objects']}
    with (ROOT/'analysis_results/order_completion_audit_20260929/下一阶段_配对及表示核查.csv').open(encoding='utf-8-sig') as f:items=list(csv.DictReader(f))
    registry=read(ROOT/'analysis_results/consensus_research_20260923/inputs/room_registry.json.gz')
    meta={r['image_id']:r for r in registry['images']};images={};cases=[]
    for item in items:
        o=objects[item['object_id']];points=o['before_preprocessing_points']
        if not points or len(points)!=len(o['point_labels']):raise ValueError('invalid_points:'+o['object_id'])
        if o['image_id'] not in images:images[o['image_id']]=data_image(ROOT/meta[o['image_id']]['path'],texture=True)
        cases.append(dict(object_id=o['object_id'],image_id=o['image_id'],image_code=o['image_code'],worker_id=o['worker_id'],condition=o['condition'],
            points=points,labels=o['point_labels'],initial_pairs=o['links_zero_based'] or [],source=o['source'],
            coordinate_source='before_preprocessing_points',note=item['note'],problem_sources=item['sources'],
            pairing_basis=o['pairing_basis'],doorway=o['scene_doorway_status'],oos=o['scene_oos_status']))
    if len(cases)!=34 or len({r['object_id'] for r in cases})!=34:raise ValueError('queue_drift')
    OUT.mkdir(exist_ok=True)
    data=dict(schema='pairing_only_review_20260929_v1',cases=cases,images=images)
    (OUT/'data.js').write_text('window.PAIRING_DATA='+encode(data)+';',encoding='utf-8')
    here=ROOT/'tools/thesis_main/analysis'
    (OUT/'index.html').write_text((here/'pairing_review_20260929.html').read_text(encoding='utf-8'),encoding='utf-8')
    dump(OUT/'source_objects.json',dict(objects=[objects[r['object_id']] for r in cases]))
    dump(OUT/'field_contract.json',dict(schema=data['schema'],primary_key='object_id',coordinate_source='平均x前有效点；原坐标与标签不改',
        pairs='corrections_only仅记录用户修正的零基[上端点,下端点]，允许局部或空集合，不表达完整配对或环序；legacy_full_pairing保留旧版完整/草稿记录语义',
        statuses=['draft','checked','paired','deferred'],confirmation='checked表示本图检查完成，untouched_points=accepted_without_correction；未出现在修正中的点无需逐一配对。未审/草稿不作无问题判定；旧paired仍要求完整覆盖',
        scope='pairing_only；order_confirmed=false；坐标修订、删除补点和连接顺序留后续；保存不自动跳转',
        binding='object_id、points、labels、coordinate_source的完整JSON绑定；未知身份、坐标漂移、冲突导入拒绝覆盖'))
    return dict(objects=len(cases),images=len(images),odd_point_objects=sum(len(c['points'])%2 for c in cases))


if __name__=='__main__':print(build())
