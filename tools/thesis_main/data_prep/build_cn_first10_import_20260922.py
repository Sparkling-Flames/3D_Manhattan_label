"""将已核对的9人首批清单转为任务8导入包，沿用任务7数据字段。"""
import json
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

from tools.thesis_main.analysis.build_stage1_image_packages_20260913 import chinese_names
from tools.thesis_main.analysis.plan_cn_first10_20260922 import prepare, ROOT

OUT = ROOT/'import_json/cn_first10_20260922'
PLAN = ROOT/'analysis_results/cn_first10_20260922/分配明细.json'


def build():
    plan=json.loads(PLAN.read_text(encoding='utf8'))
    _,seen,profiles,sources=prepare()
    rows=plan['assignments']
    assert Counter(r['worker'] for r in rows)=={w:10 for w in profiles}
    assert len({(r['worker'],r['image_id']) for r in rows})==90
    assert all(r['worker'] not in seen[r['image_id']] for r in rows)
    ids=sorted({r['image_id'] for r in rows})
    urls={}
    # 只取已记录的原图地址；绝不复制GT、点集或预标注。
    for filename in ['export_label/groudTruth.json',
                     'import_json/mp3d_validation_gt_audit_20260809/mp3d_validation_all_gt_import.json']:
        for task in json.loads((ROOT/filename).read_text(encoding='utf-8-sig')):
            url=task['data']['image'];iid=Path(unquote(urlparse(url).path)).stem
            if iid in ids: urls.setdefault(iid,url)
    template=json.loads((ROOT/'import_json/scene_stability_stage1_20260913_v2/label_studio_import/任务7.json').read_text(encoding='utf8'))[0]['data']
    assert set(urls)==set(ids)
    codes={iid:f'{n:03d}' for n,iid in enumerate(ids,1)}
    tasks=[]
    for iid in ids:
        data=dict(template,image=urls[iid],base_task_id=iid,title=Path(unquote(urlparse(urls[iid]).path)).name,
                  package_task_code=codes[iid],project_display_name='任务8')
        assert set(data)==set(template) and data['condition']=='manual'
        assert '?' not in data['vis_3d']
        tasks.append({'data':data})
    names=chinese_names()
    registry=json.loads((ROOT/'analysis_results/scene_image_exploration_20260910_v1/same_room_selection_registry_v2_20260912.json').read_text(encoding='utf8'))
    meta={r['image_id']:r for r in registry['images']}
    assignments=[]
    for r in sorted(rows,key=lambda r:(r['worker'],r['order'])):
        w=int(r['worker'][1:]);iid=r['image_id']
        assignments.append(dict(worker_id=w,image_id=iid,tier='required',language='zh',batch=r['room'],
            source_groups=r['room'],code=r['code'],number=meta[iid]['number'],image_path=r['image_path'],
            order=r['order'],project_key='zh_required',package_task_code=codes[iid],display_task_code='任务8-'+codes[iid]))
    project=dict(project_key='zh_required',project_display_name='任务8',language='zh',images=len(tasks),
        import_file='import_json/cn_first10_20260922/label_studio_import/任务8.json',
        project_id=None,project_binding_status='pending_post_import',release_status='ready_for_runtime_binding',
        image_urls_status='observed_in_repository_not_network_checked',selection_mode='required_manifest')
    workbook=dict(project_display_name='任务8',workers=[dict(worker_id=int(w[1:]),name=names[int(w[1:])]) for w in profiles],
                  assignments=assignments)
    return tasks,assignments,project,workbook,sources


def main():
    tasks,assignments,project,workbook,sources=build()
    (OUT/'label_studio_import').mkdir(parents=True,exist_ok=True)
    for path,data in [('label_studio_import/任务8.json',tasks),('required_assignments.json',assignments),
                      ('projects.json',[project]),('workbook_input.json',workbook),('source_exports.json',sources)]:
        (OUT/path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (OUT/'使用说明.md').write_text('''# 任务8：中文9人首批各10张

只将 `label_studio_import/任务8.json` 导入一个新的中文Manual项目，建议名称“任务8”。19张图对应90个人图任务，不是给每个人都标19张。

工作簿“任务8.xlsx”沿用任务7的一份文件、9个姓名sheet、个人顺序／包内编号／图片编号三列。每人仅按本人sheet做10张。包内编号001—019与JSON一致，不是LS自动生成的task ID；导入后用base_task_id核对运行时任务并绑定项目入口，再分发。

其余JSON均是管理资料，不导入LS。required_assignments.json是本批人员—图片分配依据，project_id尚未绑定。CE项目可见性不等于逐人权限隔离，个人清单用于流程分发。

沿用任务7的Manual字段、图像地址与空白3D入口，无predictions、annotations、参考点、GT或人员分类。图像URL已核对仓库记录，本轮未逐一验证网络可达；XML/userscript/服务器未改。新建项目时沿用已测试的中文Manual配置，不使用Semi初始化。

未调用LS API、未线上导入、未给标注者发送任务。原任务7、原导出和首批90份人员—图片对应关系均不改。
''',encoding='utf8')
    print(f'19张导入图，{len(assignments)}个人图分配；{OUT}')


if __name__=='__main__': main()
