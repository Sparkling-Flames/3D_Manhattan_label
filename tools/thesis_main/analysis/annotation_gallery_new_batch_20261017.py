"""新增导出的独立库存侧栏；不加入现有人数、资格或评分。"""
import json
from collections import Counter,defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote,urlparse

ROOT=Path(__file__).resolve().parents[3]
REVIEW=Path('C:/Users/ASUS/Documents/xwechat_files/wxid_lvoh11i1addo22_a66c/msg/file/2026-10/任务8_筛选与排序审核.json')
OUT=ROOT/'research/statistics/annotation_gallery_20261017/new_batch.json'


def image_identity(data):
    identities={str(data[k]) for k in ['image_id','base_task_id'] if data.get(k)}
    if data.get('image'):
        identities.add(Path(unquote(urlparse(data['image']).path)).stem)
    if len(identities)!=1:
        raise ValueError(f'image identity conflict or missing: {sorted(identities)}')
    return identities.pop()


def person_id(completed_by):
    return completed_by.get('id') if isinstance(completed_by,dict) else completed_by


def parse_new_batch(exports,review,known_image_ids):
    """exports={source_file: LS task list}; project/task/annotation复合键只去重相同导出。

    人员只在同一源文件内按completed_by去重；跨文件身份未知时n_people=null。
    review只附录审核状态，不过滤提交、执行order或解释note为操作指令。
    """
    if review is not None and review['schema']!='task8_screen_order_review_v1':
        raise ValueError('unsupported review schema')
    reviews=review['records'] if review else {}
    if any(key!=value['source_id'] for key,value in reviews.items()):
        raise ValueError('review key/source_id mismatch')
    rows=[];seen={};tasks={};duplicate_annotations=[];duplicate_tasks=[]
    for filename,items in sorted(exports.items()):
        if not isinstance(items,list):raise ValueError('Label Studio export must be a task list')
        for task in items:
            project=task['project'];taskid=task['id'];image=image_identity(task['data']);tk=(project,taskid)
            if tk in tasks:
                if tasks[tk]!=image:raise ValueError('task identity conflict')
                duplicate_tasks.append(dict(project=project,task_id=taskid,source_file=filename))
            tasks[tk]=image
            for ann in task['annotations']:
                if ann.get('task',taskid)!=taskid or ann.get('project',project)!=project:
                    raise ValueError('annotation task/project mismatch')
                key=f'ls{project}:{taskid}:{ann["id"]}'
                fingerprint=(image,json.dumps(ann,sort_keys=True,ensure_ascii=False))
                duplicate=key in seen
                if duplicate:
                    if seen[key]!=fingerprint:raise ValueError('annotation identity conflict')
                    duplicate_annotations.append(dict(source_id=key,source_file=filename))
                else:seen[key]=fingerprint
                result=ann['result'];cancel=bool(ann.get('was_cancelled',False));gt=bool(ann.get('ground_truth',False))
                submitted=not cancel and bool(result) and not gt
                user=person_id(ann.get('completed_by'));rv=reviews.get(key)
                rows.append(dict(image_id=image,source_file=filename,project_id=project,task_id=taskid,
                    annotation_id=ann['id'],source_id=key,duplicate_occurrence=duplicate,
                    completed_by=user,worker_key=f'{filename}::completed_by:{user}' if user is not None else None,
                    was_cancelled=cancel,ground_truth=gt,result_items=len(result),
                    n_keypoints=sum(r.get('type')=='keypointlabels' for r in result),
                    noncancelled_nonempty=not cancel and bool(result),submitted=submitted,
                    review_status=rv['filter'] if rv else 'unreviewed',review=rv,
                    annotation_updated_at=ann.get('updated_at')))
    byimage=defaultdict(list)
    for row in rows:byimage[row['image_id']].append(row)
    images=[]
    for image,raw in sorted(byimage.items()):
        unique=[r for r in raw if not r['duplicate_occurrence']];submitted=[r for r in unique if r['submitted']]
        files=sorted({r['source_file'] for r in raw})
        people_by_file={f:len({r['worker_key'] for r in raw if r['source_file']==f and r['submitted'] and r['worker_key']}) for f in files}
        unknown=sum(r['worker_key'] is None for r in submitted)
        images.append(dict(image_id=image,matched_known_image=image in known_image_ids,
            n_raw_records=len(raw),n_unique_annotation_records=len(unique),n_submitted_records=len(submitted),
            n_noncancelled_nonempty=sum(r['noncancelled_nonempty'] for r in unique),
            n_people=people_by_file[files[0]] if len(files)==1 and not unknown else None,
            n_unknown_person_submissions=unknown,n_people_by_source_file=people_by_file,
            new_worker_keys=sorted({r['worker_key'] for r in submitted if r['worker_key']}),
            source_files=files,review_counts=dict(Counter(r['review_status'] for r in submitted)),
            analysis_included=False,status='pending_analysis_inclusion'))
    keys=set(seen);later=[]
    for r in rows:
        rv=r['review']
        if rv and r['annotation_updated_at'] and rv.get('updated_at'):
            if datetime.fromisoformat(r['annotation_updated_at'].replace('Z','+00:00'))>datetime.fromisoformat(rv['updated_at'].replace('Z','+00:00')):
                later.append(r['source_id'])
    checks=dict(source_files=sorted(exports),task_occurrences=sum(len(x) for x in exports.values()),
        unique_project_tasks=len(tasks),raw_annotation_records=len(rows),unique_annotation_records=len(keys),
        submitted_records=sum(r['submitted'] and not r['duplicate_occurrence'] for r in rows),
        raw_cancelled_records=sum(r['was_cancelled'] for r in rows),raw_empty_records=sum(r['result_items']==0 for r in rows),
        raw_ground_truth_records=sum(r['ground_truth'] for r in rows),image_count=len(images),
        n_source_local_people=len({r['worker_key'] for r in rows if r['submitted'] and r['worker_key']}),
        matched_image_count=sum(r['matched_known_image'] for r in images),
        unmatched_image_ids=sorted(set(byimage)-set(known_image_ids)),
        duplicate_annotation_occurrences=duplicate_annotations,duplicate_task_occurrences=duplicate_tasks,
        unmatched_review_source_ids=sorted(set(reviews)-keys),unreviewed_annotation_source_ids=sorted(keys-set(reviews)),
        annotation_updated_after_review=sorted(set(later)))
    return dict(version='annotation_gallery_new_batch_20261017_v1',status='pending_analysis_inclusion',
        analysis_included=False,identity_policy='Within-source-file completed_by IDs only; multi-file people count null; no existing W identity mapping.',
        submission_rule='Unique project/task/annotation, noncancelled, result nonempty, not ground_truth; review does not change this inventory count.',
        review_policy='Identity join; full-export content binding is verified separately in the intake audit. Pair-index basis must be established before applying order; this parser never reorders points.',
        review_source_metadata={k:review.get(k) for k in ['schema','source_name','source_sha256','exported_at']} if review else None,
        images=images,records=rows,checks=checks)


def main():
    import csv
    directory=ROOT/'export_label/新增中文标注'
    exports={str(p.relative_to(ROOT)):json.loads(p.read_text(encoding='utf-8-sig')) for p in sorted(directory.glob('*.json'))}
    with (ROOT/'research/statistics/annotation_counts_20261017/image_counts.csv').open(encoding='utf-8-sig',newline='') as stream:
        known={r['image_id'] for r in csv.DictReader(stream)}
    result=parse_new_batch(exports,json.loads(REVIEW.read_text(encoding='utf-8-sig')),known)
    from ..data_prep.consolidate_research_input import load_current_bundle
    bundle=load_current_bundle()
    existing={f'ls{o["source"]["project"]}:{o["source"]["task"]}:{o["source"]["annotation"]}'
              for o in bundle['data']['objects'] if o['object_kind']=='annotation'}
    result['checks']['current_inventory_overlap_source_ids']=sorted(existing & {r['source_id'] for r in result['records']})
    result['review_source_file']=str(REVIEW)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['checks'],ensure_ascii=False,indent=2))


if __name__=='__main__':main()
