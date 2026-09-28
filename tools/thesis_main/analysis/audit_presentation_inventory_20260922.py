"""盘点汇报资产；只读已有数据/模型输出，不推理、不改研究资格。"""
import collections
import csv
import gzip
import json
from pathlib import Path
import subprocess
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/presentation_inventory_20260922'
HUMAN = ROOT / 'analysis_results/new_manual_reviewed_20260921'
PORTRAIT = ROOT / 'output/image_portrait_20260914_v1'
BRANCH = 'codex/image-portrait-20260914'
PREFIX = 'analysis_results/image_portrait_20260914_v1/'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')


def coverage(name, available, pool, human, prediction):
    return dict(asset=name, available_images=len(available), pool_images=len(available & pool),
        pool_denominator=len(pool), human_images=len(available & human), human_denominator=len(human),
        prediction_images=len(available & prediction), prediction_denominator=len(prediction),
        image_ids=sorted(available), missing_pool_ids=sorted(pool-available),
        missing_human_ids=sorted(human-available), missing_prediction_ids=sorted(prediction-available))


def counts(rows):
    return dict(responses=len(rows), images=len({r['image_id'] for r in rows}),
        workers=len({r['worker_id'] for r in rows}), buildings=len({r['building_id'] for r in rows}))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with gzip.open(HUMAN / 'responses.jsonl.gz', 'rt', encoding='utf8') as f:
        rows = [json.loads(line) for line in f]
    accepted = [r for r in rows if r['calculation_included'] and r['worker_id'] not in {'W019', 'W026'}]
    per_image = read(HUMAN / 'per_image.json')
    human = {r['image_id'] for r in accepted}
    prediction = {r['identity'] for r in per_image if r['unaided_prediction']['responses']}
    assert counts(accepted) == read(HUMAN / 'SUMMARY.json')['views']['all_accepted']
    by_condition = {c: counts([r for r in accepted if r['raw_condition']==c])
                    for c in sorted({r['raw_condition'] for r in accepted})}
    sets = {c: {r['image_id'] for r in accepted if r['raw_condition']==c} for c in by_condition}
    human_summary = dict(version='终审20260921，W006补交已接入', all_accepted=counts(accepted),
        conditions=by_condition, condition_image_ids={k: sorted(v) for k,v in sets.items()},
        manual_semi_overlap_images=len(sets['manual'] & sets['semi']),
        current_views=read(HUMAN / 'SUMMARY.json')['views'],
        source='analysis_results/new_manual_reviewed_20260921/responses.jsonl.gz',
        note='当前已接收的规范化研究视图，非全仓库历轮导出条数；多条件图片可重叠。')
    dump('human_coverage.json', human_summary)
    image_paths = {s: {p.stem:p for p in (ROOT/'data/mp3d_layout'/s/'img').glob('*.png')}
                   for s in ['train','valid','test']}
    pool = set(image_paths['valid']) | set(image_paths['test'])
    assert len(pool)==648
    assets=[]; file_audit=[]

    def add(name, ids, source, validation, **extra):
        assets.append(dict(**coverage(name, set(ids), pool, human, prediction), source=source,
                           validation=validation, **extra))

    # 文本数值逐份校验；存在不等于适用范围/语义质量通过。
    def corners(paths):
        ids=[]
        for iid,p in paths.items():
            a=np.loadtxt(p, ndmin=2)
            valid=a.ndim==2 and a.shape[1]==2 and len(a)>=4 and len(a)%2==0 and np.isfinite(a).all()
            file_audit.append(dict(path=str(p),image_id=iid,numeric_valid=bool(valid),points=len(a)))
            if valid:ids.append(iid)
        return ids

    for s in ['train','valid','test']:
        paths={p.stem:p for p in (ROOT/'data/mp3d_layout'/s/'label_cor').glob('*.txt')}
        add('公共GT_'+s,corners(paths),str(ROOT/'data/mp3d_layout'/s/'label_cor'),
            '逐文件有限数值、二维坐标和偶数点检查；未重新验收GT范围', split=s)
    gt=set().union(*(set(a['image_ids']) for a in assets))
    add('公共GT_全部split',gt,'data/mp3d_layout/{train,valid,test}/label_cor',
        '各split逐文件数值检查后并集，不能等同唯一正确答案')
    no_occ={p.stem:p for s in ['train_no_occ','valid_no_occ','test_no_occ']
            for p in (ROOT/'data/mp3d_layout'/s/'label_cor').glob('*.txt')}
    add('公共GT_no_occ目录版本',corners(no_occ),'data/mp3d_layout/{train,valid,test}_no_occ/label_cor',
        '另一目录版本逐文件数值检查；不与原GT合并计数，未重新核验生成语义')
    hh={}
    for s in ['test','validation']:
        base=ROOT/f'analysis_results/model_initialization_{s}_ep300_replay_20260823_v1/prediction_txt'
        hh.update({p.name.removesuffix('.layout.txt'):p for p in base.glob('*.layout.txt')})
    add('HoHoNet_ep300重放布局',corners(hh),'analysis_results/model_initialization_{test,validation}_ep300_replay_20260823_v1/prediction_txt',
        '逐文件坐标数值检查；此版本不冒充每次Semi实际初始化')
    bi=Path('D:/Work/Manhattan_3D/Bi_layout/exports/mp3d_dual_predictions')
    bi_rows=[]
    for s in ['test','val']:
        with (bi/s/'manifest.csv').open(encoding='utf-8-sig',newline='') as f:bi_rows.extend(csv.DictReader(f))
    add('Bi-Layout_历史清单全部', {r['pano_id'] for r in bi_rows},str(bi),
        'manifest逐图登记，包含退化输出',manifest_status_counts=dict(collections.Counter(r['status'] for r in bi_rows)))
    add('Bi-Layout_历史清单ok', {r['pano_id'] for r in bi_rows if r['status']=='ok'},str(bi),
        'manifest原status=ok；不是人工正确性验收',non_ok_ids=[r['pano_id'] for r in bi_rows if r['status']!='ok'])
    for head in ['enclosed','extended']:
        paths={r['pano_id']:bi/r[head+'_corners_px_path'] for r in bi_rows}
        ids=corners(paths)
        add('Bi-Layout_'+head+'_历史导出',ids,str(bi),'逐文件坐标数值检查；manifest状态保留',
            manifest_status_counts=dict(collections.Counter(r['status'] for r in bi_rows)),
            manifest_ok_images=sum(r['status']=='ok' for r in bi_rows),same_model_two_heads=True)
    faces=['front','right','back','left','up','down']
    expected={
        'hohonet':{'encoder_stage2','encoder_stage4','compressed','refined','shared'},
        'bilayout':{'fc','fg_enclosed','fg_extended'},
        'dinov3':{f'{v}_block{b}_patch' for v in ['panorama',*faces] for b in [3,6,9,11,12]} |
                 {f'{v}_block12_cls' for v in ['panorama',*faces]} | {'source_shape_hw'},
        'da3':{f'{v}_view0_out_layer_{b}' for v in faces for b in [5,7,9,11]} |
              {f'{v}_{k}' for v in faces for k in ['depth','depth_conf','extrinsics','intrinsics','reference_view_index']} | {'source_shape_hw'},
        'ulayout':{f'yaw{y}_{k}' for y in [0,90,180,270] for k in ['compressed','transformer','boundary_radians',
                    'boundary_pixels_float','boundary_pixels_official_round','corner_logits']} | {'source_shape_hw'}}
    for model, keys in expected.items():
        base=PORTRAIT/model if model in ['hohonet','bilayout'] else PORTRAIT/'raw'/model
        files=sorted(base.glob('*.npz')); good=collections.defaultdict(set); problems=[]
        for p in files:
            try:
                with zipfile.ZipFile(p) as z:
                    actual={x.removesuffix('.npy') for x in z.namelist()}
                    valid=actual==keys and all(i.file_size>0 for i in z.infolist())
                if not valid:problems.append(dict(file=p.name,missing=sorted(keys-actual),extra=sorted(actual-keys)))
            except zipfile.BadZipFile:
                valid=False;problems.append(dict(file=p.name,error='BadZipFile'))
            if valid:
                if model in ['hohonet','bilayout']:
                    iid,phase=p.stem.rsplit('_yaw',1);good[iid].add(phase)
                else:good[p.stem].add('single')
        required={'0','90','180','270'} if model in ['hohonet','bilayout'] else {'single'}
        ids={i for i,v in good.items() if v==required}
        add(model+'_本地原始特征',ids,str(base),'全文件NPZ目录和预期键集合检查，未重读全部高维张量或验证语义质量',
            files=len(files),expected_keys=sorted(keys),problems=problems,
            incomplete_phase_ids=sorted(set(good)-ids))
    # 归档版本仅从git读取，避免切换工作区或覆盖本地数据。
    archive_files=subprocess.check_output(['git','ls-tree','-r','--name-only',BRANCH,'--',PREFIX+'models'],cwd=ROOT,text=True).splitlines()
    for name in ['README.md','output_coverage.json','local_validation.json']:
        payload=subprocess.check_output(['git','show',BRANCH+':'+PREFIX+name],cwd=ROOT)
        (OUT/('historical_'+name)).write_bytes(payload)
    for model in expected:
        files={Path(p).name for p in archive_files if str(Path(p).parent).replace('\\','/')==PREFIX+'models/'+model}
        suffixes=['.npz'] if model in ['hohonet','bilayout'] else ['.features.npz','.geometry.npz']
        ids={iid for iid in pool if all(iid+s in files for s in suffixes)}
        add(model+'_归档模型包',ids,BRANCH+':'+PREFIX+'models/'+model,
            '当前核对git文件清单；历史数值验收另存historical_local_validation.json，未重新全量校验')
    pair_files=sorted((PORTRAIT/'raw/da3/multiview').glob('*.npz'))
    dump('asset_coverage.json',dict(schema='presentation_inventory_v1',assets=assets,
        auxiliary_pairs=dict(asset='DA3同房辅助',local_pair_files=len(pair_files),unit='配对资产',
            source=str(PORTRAIT/'raw/da3/multiview'),
            validation='仅核对当前NPZ数量；历史验收316对且相机一致性有问题，非已验证房间重建'),
        image_pool=dict(images=len(pool),test=len(image_paths['test']),valid=len(image_paths['valid']),
                        train=len(image_paths['train']),image_ids=sorted(pool)),
        denominators=dict(human_images=len(human),prediction_images=len(prediction)),
        source_boundaries='648模型池、259人工作答图、240无辅助预测图分别核对；旋转/透视面不增加独立图片。'))
    dump('numeric_file_audit.json',file_audit)
    parts=[r for r in read(HUMAN/'partitions.json') if r['method']=='complete']
    semi=[dict(**r,singleton_mass=r['singletons']/r['N']) for r in parts if r['condition']=='semi']
    manual={r['image_id']:r for r in parts if r['condition']=='manual'}
    pairs=[dict(image_id=r['image_id'],manual_N=manual[r['image_id']]['N'],semi_N=r['N'],
                manual_singleton_mass=manual[r['image_id']]['singletons']/manual[r['image_id']]['N'],
                semi_singleton_mass=r['singleton_mass'],manual_largest_share=manual[r['image_id']]['largest_share'],
                semi_largest_share=r['largest_share']) for r in semi if r['image_id'] in manual]
    dump('semi_descriptive.json',dict(version='当前终审有效点；完整链接25.6px',per_image=semi,
        manual_semi_same_image=pairs,summary=dict(images=len(semi),responses=sum(r['N'] for r in semi),
          overlapping_computable_images=len(pairs)),
        limitation='描述性结果，人员和人数未匹配，非随机化处理效应；单人占比/最大簇占比不是准确率。',
        source='analysis_results/new_manual_reviewed_20260921/partitions.json'))
    print(json.dumps(human_summary,ensure_ascii=False)[:650])
    for a in assets:print(a['asset'],a['available_images'],a['human_images'],a['prediction_images'])
    print('semi',len(semi),sum(r['N'] for r in semi),'overlap',len(pairs))


if __name__=='__main__':main()
