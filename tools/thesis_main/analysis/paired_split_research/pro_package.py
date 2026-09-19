"""Whitelist cloud numeric evidence; no raw exports, logs, credentials or local UI runtime."""
import argparse
import gzip
import json
import zipfile
from pathlib import Path

from . import study

REPO = Path(__file__).resolve().parents[4]
DELIVERY = REPO / 'analysis_results/pro_next_round_20260920'


def verify(root):
    paired = root / 'analysis_results/paired_split_research_received_20260920'
    rows = [json.loads(line) for line in gzip.open(paired/'inputs/responses.jsonl.gz', 'rt', encoding='utf-8')]
    by = {r['canonical_annotation_id']: r for r in rows}
    assert len(rows) == len(by) == 2501
    note = json.loads((root/'analysis_results/pro_next_round_20260920/uNb21_用户局部对应.json').read_text(encoding='utf-8'))
    a, b = by[note['id_a']], by[note['id_b']]
    assert a['image_id'] == b['image_id'] == note['image_id']
    assert (a['worker_id'], b['worker_id']) == ('W006', 'W013')
    assert a['raw_condition'] == b['raw_condition'] == 'manual'
    assert note['confirmed_statement'] == {'a_display_ordinal':3, 'b_display_ordinal':4}
    for projection in note['coordinate_projection_not_additional_user_confirmation']:
        for side, row, ordinal in [('a',a,3),('b',b,4)]:
            points = row['effective_points_1024x512']
            candidates = [i for i,p in enumerate(points) if (p[1]<255.5 if projection['role']=='top' else p[1]>255.5)]
            ordered = sorted(candidates, key=lambda i:(points[i][0]%1024,points[i][1],i))
            index = projection[side+'_point_index_1based']-1
            assert ordered[ordinal-1] == index
            assert all(abs(v-w)<.00051 for v,w in zip(points[index],projection[side+'_xy']))
    assert note['full_correspondence_override_applied'] is False and note['final_cluster_decision'] is None
    history = paired/'history_visual_review'
    queue = json.loads((history/'all_history_queue.json').read_text(encoding='utf-8'))
    findings = json.loads((history/'visual_findings.json').read_text(encoding='utf-8'))
    assert len(queue)==239 and len({q['image_id'] for q in queue})==214 and len(findings)==8
    assert all(f['user_decision'] is None for f in findings)  # User update is a separate partial relation.
    print('Verified: 2501 records, 214 images / 239 units, 8 visual notes and partial user anchor.')


def build():
    files = set()
    def add(p):
        if p.is_dir():
            files.update(f for f in p.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
        else:
            assert p.is_file(), p
            files.add(p)
    paired = study.ROOT
    local = REPO/'analysis_results/local_point_research_received_20260919'
    for name in ['inputs','received_results','received_min_horizontal','source_code','report',
                 'history_visual_review','visual_checked','README.md','REPORT_ZH.md',
                 '独立审查与研究方向.md','RECEIPT.json','local_recheck/REPRODUCTION_CHECK.json',
                 'local_recheck/results/SCOPE.json','local_recheck/results/TESTS.json']:
        add(paired/name)
    for name in ['inputs','received_results','source_code','previous_pairing_time','INPUT_MANIFEST.json',
                 'README.md','REPORT_ZH.md','独立审查与研究方向.md','RECEIPT.json',
                 'pair_pilot/README.md','pair_pilot/evidence.json','pair_pilot/用户_六图点对审核_原始.json',
                 'pro_followup_20260920/README.md','pro_followup_20260920/visual_review.json',
                 'pro_followup_20260920/evidence.json','local_recheck/REPRODUCTION_CHECK.json',
                 'local_recheck/INDEPENDENT_CHECK.json']:
        add(local/name)
    for folder in ['paired_split_research','local_point_research']:
        for p in (REPO/'tools/thesis_main/analysis'/folder).glob('*.py'):
            add(p)
    add(REPO/'analysis_results/full_corpus_research_received_20260918/full_study_20260918/code/legacy_reproduction.py')
    for name in ['Pro下一轮_分簇定稿与分析准备_20260920.md','真人标注不确定性研究_当前状态.md',
                 '相似场景标注稳定性分析SOP.md','图片分类与同房间收敛预测研究SOP.md',
                 '用户研究要求核对清单_20260913.md','研究主线与新增标注验证说明_20260909.md']:
        add(REPO/'docs/thesis_main'/name)
    for name in ['用户_39图文字审核_原始.json','一正_39图审核_原始.json','用户_39图最终裁决_原始.json']:
        add(REPO/'analysis_results/human_review_reconciliation_20260918'/name)
    for name in ['用户_12图审核_原始.json','用户审核接收与研究澄清.md']:
        add(REPO/'analysis_results/cluster_review_extra_20260919'/name)
    for name in ['test_paired_split_research.py','test_local_point_research.py','test_point_pair_pilot.py']:
        add(REPO/'tests'/name)
    for name in ['README.md','来源核对与最新要求.md','uNb21_用户局部对应.json']:
        add(DELIVERY/name)
    if (DELIVERY/'DELIVERY_CHECK.json').exists():add(DELIVERY/'DELIVERY_CHECK.json')
    manifest = dict(schema='pro_cloud_numeric_delivery_v1',
                    entry='docs/thesis_main/Pro下一轮_分簇定稿与分析准备_20260920.md',
                    files=[dict(path=p.relative_to(REPO).as_posix(),bytes=p.stat().st_size) for p in sorted(files)],
                    excludes=['raw runtime exports','raw time logs','credentials','full original panoramas','local UI runtime','regenerable caches'],
                    old_relative_links='Historical reports may reference nonbundled UI/assets; use the delivery README.')
    study.dump(DELIVERY/'MANIFEST.json',manifest)
    files.add(DELIVERY/'MANIFEST.json')
    assert not any(p.relative_to(REPO).parts[0] in ['export_label','active_logs','.git','.codex'] for p in files)
    archive = DELIVERY/'pro_next_round_20260920.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files):z.write(p,p.relative_to(REPO).as_posix())
        z.writestr('START_HERE.md','# Pro下一轮\n\n先读 analysis_results/pro_next_round_20260920/README.md，再读 docs/thesis_main/Pro下一轮_分簇定稿与分析准备_20260920.md。\n')
    verify(REPO)
    print(f'Packaged {len(files)} files, {archive.stat().st_size} bytes: {archive.name}')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify-root',type=Path);args=parser.parse_args()
    verify(args.verify_root.resolve()) if args.verify_root else build()
