"""Assemble immutable evidence exports and an explicit adoption ledger.

This script only copies saved research results and derives presentation tables.
It never changes a reference, scope decision, personnel label, or fusion result.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import io
import json
import shutil
import zipfile
import pandas as pd

OUT = Path(__file__).resolve().parents[1]
WORK = OUT.parent
REPO = WORK / 'repo'
BASE = REPO / 'research/workers/personnel_v21_reselection_20261029'
COMMIT = '519c7447278dd16c3d69f505b807fb5b53792b36'


def dump(obj, p):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def copy(src, dst):
    src = Path(src); dst = Path(dst)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('*.log', '__pycache__', '*.pyc', '*.partial', '*.writing'))
    else:
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)


def checksum(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        while b := f.read(1 << 20): h.update(b)
    return h.hexdigest()


def native_export():
    src = OUT / 'stage03_new_abc'
    out = OUT / 'stage03_completed_abc'; out.mkdir(exist_ok=True)
    for p in src.iterdir():
        if p.is_file() and p.suffix != '.log': copy(p, out / p.name)
    copy(src / 'endpoints/ENDPOINT_SCALARS.csv.gz', out / 'ENDPOINT_SCALARS.csv.gz')
    copy(src / 'endpoints/RUN_RECEIPT.json', out / 'RUN_RECEIPT.json')
    copy(src / 'metrics/EVENT_METRICS.csv.gz', out / 'EVENT_METRICS.csv.gz')
    copy(src / 'metrics/MEASUREMENT_RECEIPT.json', out / 'MEASUREMENT_RECEIPT.json')
    seen = set(); rows = 0
    final = out / 'ENDPOINT_GEOMETRY.jsonl.gz'
    tmp = out / 'ENDPOINT_GEOMETRY.jsonl.gz.partial'
    with gzip.open(tmp, 'wt', encoding='utf-8', compresslevel=6) as dest:
        for p in sorted((src / 'endpoints/pools').glob('*/part_*.jsonl.gz')):
            with gzip.open(p, 'rt', encoding='utf-8-sig') as f:
                for line in f:
                    if not line.strip(): continue
                    obj = json.loads(line)
                    assert obj['team_key'] not in seen, obj['team_key']
                    seen.add(obj['team_key']); rows += 1
                    dest.write(json.dumps(obj, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')
    req = pd.read_csv(out / 'REQUESTS.csv.gz')
    assert seen == set(req.team_key) and rows == 16818
    tmp.replace(final)
    dump({'rows': rows, 'unique_team_keys': len(seen), 'all_requests_found': True,
          'full_geometry_and_failure_status_preserved': True,
          'vote_trace_scope': 'six selected exact ABC events in stage04_cases; not all endpoints',
          'true_new_physical_teams': 16810, 'existing_geometry_replays': 8,
          'source_commit': COMMIT, 'sha256': checksum(final)}, out / 'GEOMETRY_EXPORT_RECEIPT.json')


def decision_for(m):
    if m == 'TARGET_DSTRUCT_K3': return ('主分类', '普通Manual原答结构响应主方法', '目标对齐；直接原答解释、同点数几何区分、楼外稳定性与七人覆盖的综合证据；不按最高Q选择。')
    if m == 'TARGET_DSTRUCT_K2': return ('主分类粗层', '主要结构群与较多转折群', '与K3同树；先展示主要分离，再解释K3增加的简化/近共线差异。')
    if m == 'TARGET_DSTRUCT_K4': return ('条件性细层', '四人小类机制与父内细分', 'K4没有整体原答区分优势；只有明确父内问题时使用，不能因格数更多而自动升级。')
    if m == 'V21_DSTRUCT_RAW3_K3': return ('必要互补', '纯原答定义敏感性与八人替换扩覆盖', '移除参考角点对应轴；八人覆盖与双方向结果有新增价值，七人覆盖、稳定性和共同图结果不支持替代主方法。')
    if m.startswith('V21_DSTRUCT_RAW3_'): return ('参数敏感性', '纯原答定义的粗细层', '全部楼外拟合与原答审计已完成；K4原答区分下降，不作为默认新层。')
    if m.startswith('V21_DSTRUCT_'): return ('参数敏感性', '实际重拟合并保留全部结果', '全维、仅水平、可计算条件、困难域半权重的定向检验；本轮没有形成足够一致的替代证据。')
    if m == 'OPPJOINT_K3': return ('联合画像主层', '结构机会、定位尺度、Q与来源内时间画像；方向性配比', '保留实际替换效果；旧Q二分对照未控制A/D和连续历史Q梯度，不再据此授予总主分类地位。')
    if m == 'OPPJOINT_K4': return ('联合画像细层', '慢小类和时间构成；有证据的父内细分', '主要升质方向已在K3父类存在；时间组织是清楚增量，小类成员与图片支持必须单列。')
    if m == 'OPPJOINT_K2': return ('联合画像粗度对照', '主要联合人群二分', '保留同家族粗度，避免把细分类描述自由度当作方法准确率。')
    if m == 'RFUSE_GEOM_K2': return ('反向机制互补', '自然融合响应反推；三至四人块', '保留原答前向与融合反向互补；原答距离弱、少数类小，不承担七八人纯类主干预。')
    if m == 'TARGET_RFUSE_GEOM_K2': return ('等价复现', '目标等权后的同分区', 'ALL及22楼外折与RFUSE_GEOM_K2完全相同；不能计为第二套独立有效分类。')
    if 'RFUSE' in m: return ('反向敏感性', '反推粒度、加入Q、目标等权', '已有广筛与配比结果保留；K3有较大容量但原答标法区分较弱，现有证据未使其成为普通Manual主分类竞争者。')
    if m == 'OPPSTRUCT_K3': return ('条件定义互补', '不输入Q/T的连续结构机会响应', '机会条件可解释；本轮四格容量已补全，与TARGET相比没有一致的原答、稳定性和容量优势。')
    if m.startswith('OPPSTRUCT'): return ('机会粒度对照', '机会响应的粗细与探索层', '保留已完成结果；K5单人小类不默认作为主方法。')
    if m == 'OPPGEOM_K3': return ('几何机制互补', '位置、面积、高度响应', '用于几何与阈值机制案例，不与原答结构主方法争夺同一解释任务。')
    if m.startswith('OPPGEOM'): return ('几何粒度对照', '位置尺度响应粗细层', '按几何问题使用；不凭单个最大Q差选择。')
    if m == 'MSDGEOM_SCOPE_K4': return ('跨条件与scope补充', 'Manual/Semi历史与空间范围行为', '已有重点ABC与多指标价值；输入域不同，普通Manual研究不以跨条件标签替代主分类。')
    if m.startswith('MSDGEOM'): return ('跨条件敏感性', 'Manual/Semi及scope有无、粗细层', '保留全部比较；不把Manual上的证据写成Semi自身验证。')
    if m.startswith('Q_'): return ('必要基线', '简单历史质量分层', '不要求结构信息完全独立于Q，但使用同候选、同背景、同端点条件比较分清增量。')
    if m.startswith('DSTRUCT'): return ('原路线基线', '旧难度结构路线与连续轴', '正式v2.1已重算数值，但保留历史域的特殊范围辅助记录；普通Manual主采用目标对齐TARGET。')
    if m.startswith('DJOINT'): return ('联合备选', '旧难度域联合结构位置Q/T', 'K4等已有竞争结果保留；不能仅按Q配比解释占比决定主方法。')
    if m.startswith('DBOUNDARY'): return ('定位基线', '边界定位轴及其聚类', '用于区分结构与位置解释；不以是否主文出现判定有效或无效。')
    if m.startswith('V3_JOINT'): return ('整体配比补充', '较多类的历史联合构成', '共同有限面板解释较高；保留Q/T控制后的实测增量，不将其等同预测准确率或通用主分类。')
    if m.startswith('V3_BEHAVIOR'): return ('历史策略对照', '原行为/策略画像', '保留作为历史行为构成解释；细层在ALL人数相同也不自动表示新独立方法。')
    raise ValueError(m)


def synthesis_tables():
    dest = OUT / 'stage05_synthesis'; dest.mkdir(exist_ok=True)
    old = pd.read_csv(BASE/'stage07_adoption/ALL45_METHOD_ADOPTION_DECISIONS.csv')
    old = old.rename(columns={'adoption_status':'prior_adoption_status', 'retained_use_zh':'prior_use_zh', 'adoption_reason_zh':'prior_reason_zh'})
    new = pd.read_csv(WORK/'audit_classification/results/CANDIDATE_REGISTRY.csv')
    new = new[new.heldout_building.eq('ALL') & ~new.method.str.startswith('REPRO_')]
    new = new.rename(columns={'known_workers':'ALL_known_workers','unknown_workers':'ALL_unknown_workers','class_sizes':'ALL_class_sizes','k':'ALL_k'})
    merged = pd.concat([old,new],ignore_index=True)
    assert len(merged)==60 and merged.method.nunique()==60
    for col,idx in [('current_adoption_status',0),('current_use_zh',1),('current_reason_zh',2)]:
        merged[col] = merged.method.map(lambda m: decision_for(m)[idx])
    merged['review_date']='2026-10-29';merged['review_source_commit']=COMMIT
    merged.to_csv(dest/'ALL60_CURRENT_ADOPTION_DECISIONS.csv',index=False,encoding='utf-8-sig')
    methods=['TARGET_DSTRUCT_K2','TARGET_DSTRUCT_K3','TARGET_DSTRUCT_K4','V21_DSTRUCT_RAW3_K3','OPPJOINT_K3','OPPJOINT_K4','RFUSE_GEOM_K2']
    lab = pd.read_csv(BASE/'classification/MAIN45_LABELS_ALL_LOBO.csv.gz',low_memory=False)
    newlab = pd.read_csv(WORK/'audit_classification/results/NEW_LABELS_ALL_LOBO.csv.gz')
    lab = pd.concat([lab[lab.method.isin(methods)],newlab[newlab.method.isin(methods)]],ignore_index=True)
    lab.to_csv(dest/'ADOPTED_METHODS_LABELS_ALL_LOBO.csv.gz',index=False,encoding='utf-8-sig')
    all_lab = lab[lab.heldout_building.eq('ALL')]
    roster = all_lab.pivot(index='worker_id',columns='method',values='class_id').reindex(columns=methods)
    hist = pd.read_csv(BASE/'classification/NEW_PERSONNEL_HISTORY_ALL.csv').set_index('worker_id')
    roster = roster.join(hist[['origin','m_all_images','m_all_buildings','m_easy_images','m_hard_images','m_all_turn_n','m_hard_turn_n','m_all_short_turn_edges','m_all_near_straight_nodes_5deg','m_all_unmatched_ref_9','m_all_B8L2','m_all_log_time']])
    roster['label_scope']='ALL descriptive; use building-specific labels for any event'
    roster.to_csv(dest/'PERSONNEL_ROSTER_ALL_WITH_HISTORY.csv',encoding='utf-8-sig')
    centers = pd.read_csv(BASE/'classification/CLASS_ROLES_ALL.csv')
    ncenters = pd.read_csv(WORK/'audit_classification/results/CLASS_CENTERS_ALL.csv')
    centers = pd.concat([centers[centers.method.isin(methods)],ncenters[ncenters.method.isin(methods)]],ignore_index=True)
    centers.to_csv(dest/'ADOPTED_CLASS_MEMBERS_AND_PROFILES_ALL.csv',index=False,encoding='utf-8-sig')
    dump({'configurations':60,'existing_configurations':45,'new_variant_configurations':15,
          'exact_reproduction_aliases_not_counted_as_new':3,
          'main_method':'TARGET_DSTRUCT_K3','coarse_method':'TARGET_DSTRUCT_K2',
          'conditional_fine_method':'TARGET_DSTRUCT_K4','joint_profile':['OPPJOINT_K3','OPPJOINT_K4'],
          'pure_raw_and_m8_complement':'V21_DSTRUCT_RAW3_K3','reverse_complement':'RFUSE_GEOM_K2',
          'ordinary_manual_first':True,'person_labels_not_permanent_traits':True,
          'adoption_uses_full_existing_and_new_evidence_not_pre_frozen_outcome_confirmation':True},dest/'ADOPTION_DECISION.json')


def source_bundle():
    dest=OUT/'stage06_reproduction';manifest=[]
    paths=[]
    paths += [REPO/p.lstrip('/') for p in (WORK/'engine_paths.txt').read_text().splitlines() if p.strip()]
    paths += [p for p in (REPO/'tools/label_studio').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    for p in [BASE/'classification',BASE/'experiment',BASE/'analysis',BASE/'stage02']:
        paths += [x for x in p.rglob('*') if x.is_file() and x.suffix in ('.py','.json','.md') and '__pycache__' not in x.parts]
    paths += [BASE/'classification'/x for x in ['MAIN45_LABELS_ALL_LOBO.csv.gz','CLASS_ROLES_ALL.csv','CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz','NEW_PERSONNEL_HISTORY_ALL.csv','SEMI_BASE_LABELS_ALL_LOBO.csv.gz']]
    paths += [REPO/'research/data/releases/v2.1'/x for x in ['pools/INPUT_SNAPSHOT.json','admitted_space_extension/pools/INPUT_SNAPSHOT.json','simulated_population_evidence/README.md','simulated_population_evidence/composition/README.md','simulated_population_evidence/exchange/README.md']]
    cp=BASE/'additional_delivery/packages/03B_core/composition'
    for folder in ['primary_panel_inputs','primary_compact_links']:
        paths += [x for x in (cp/folder).rglob('*') if x.is_file() and not x.name.startswith('.')]
    paths += [WORK/'prior_extracted/stage02/classification'/x for x in ['HISTORY_FEATURES_ALL_LOBO.csv.gz','RAW_TARGET_RESPONSE_RECORDS.csv.gz']]
    paths += [WORK/'prior_extracted/stage04/raw_similarity/RAW_PAIR_DISTANCES.csv.gz']
    paths += [WORK/'project_sources/01-scope-.md']
    for p in sorted(set(paths)):
        if not p.exists(): raise FileNotFoundError(p)
        rel=p.relative_to(WORK);target=dest/'inputs_and_source'/rel;copy(p,target)
        manifest.append({'original_workspace_path':str(rel),'export_path':str(target.relative_to(OUT)), 'bytes':p.stat().st_size,'sha256':checksum(p)})
    pd.DataFrame(manifest).to_csv(dest/'SOURCE_FILE_MANIFEST.csv',index=False,encoding='utf-8-sig')
    dump({'source_commit':COMMIT,'files':len(manifest),'all_sources_preserved':True,
          'purpose':'reproduce new classification, native ABC, raw geometry, and fixed-panel Q/QT analyses',
          'previous_full_delivery_not_duplicated':'old 45-method stages and old exact event packages are referenced by commit plus their saved original manifests',
          'runtime':'Python 3.12; numpy/pandas/scipy/scikit-learn/matplotlib; task used shapely 2.2.0; source requirements preserved'},dest/'REPRODUCTION_CONTRACT.json')


def package_stage(stage, name):
    path=OUT/stage;zpath=OUT/'deliverables'/name;zpath.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(path.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.log','.pyc'):
                z.write(p,p.relative_to(OUT))
    with zipfile.ZipFile(zpath) as z:
        assert z.testzip() is None
        nested_gz=0;nested_zip=0
        for name in z.namelist():
            if name.endswith('.gz'):
                with z.open(name) as raw, gzip.GzipFile(fileobj=raw) as f:
                    while f.read(1<<20): pass
                nested_gz+=1
            elif name.endswith(('.zip','.docx')):
                with zipfile.ZipFile(io.BytesIO(z.read(name))) as inner:
                    assert inner.testzip() is None, name
                nested_zip+=1
    result={'path':str(zpath),'bytes':zpath.stat().st_size,'sha256':checksum(zpath),'zip_crc_all_passed':True,'inner_gzip_read_to_EOF':nested_gz,'inner_zip_or_docx_crc_all_passed':nested_zip}
    dump(result,zpath.with_suffix('.validation.json'))
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--native',action='store_true');ap.add_argument('--synthesis',action='store_true');ap.add_argument('--source',action='store_true');ap.add_argument('--package',nargs=2)
    args=ap.parse_args()
    if args.native:native_export()
    if args.synthesis:synthesis_tables()
    if args.source:source_bundle()
    if args.package:package_stage(*args.package)
