"""Build and verify portable result archive; never commit a ZIP into the repo."""
from __future__ import annotations
import hashlib,json,os,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
from tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core import ROOT,B,OLD,MAINSPACE,OUT,BASE,js


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(destination='/tmp/history_difficulty_delivery'):
    dest=Path(destination);dest.mkdir(parents=True,exist_ok=True)
    stage=dest/'portable';stage.mkdir(exist_ok=True);repo=stage/'repo';repo.mkdir(exist_ok=True)
    req='numpy==1.26.4\npandas==2.2.3\nscipy==1.14.1\nscikit-learn==1.5.2\nshapely==2.0.7\npillow==10.4.0\nopencv-python-headless==4.10.0.84\nPyYAML==6.0.2\npytest==8.3.5\nmatplotlib==3.9.4\nmarkdown==3.7\ntabulate==0.9.0\n'
    relative=str(OUT.relative_to(ROOT))
    commands='''# 历史粗分类研究复算\n\n本包包含本轮全部新代码、逐图结果、精确数值核、实际输入来源、原评论、失败日志和必要历史过程。没有原图、权重或视觉模型推理。旧实验difficulty只存在于不可变原始证据中，不进入白名单分析字段。\n\n解压后先打开根目录START_HERE.html。命令在repo目录运行，Python3.11：\n\n```bash\npython -m pip install -r requirements-history.txt\nexport OPENBLAS_NUM_THREADS=1\nexport OMP_NUM_THREADS=1\npython -m pytest tests/test_history_difficulty_v1.py tests/test_history_difficulty_v1_followup.py -q\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_core prepare\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_targets\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_predict\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_associations\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_transfer\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_people_conditioned\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_diagnostics\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_finalize\npython -m tools.thesis_main.analysis.image_portrait.history_difficulty_v1_report\n```\n\nWindows在PowerShell使用 `$env:OPENBLAS_NUM_THREADS="1"` 与 `$env:OMP_NUM_THREADS="1"`，其余python命令相同。\n\n预测脚本已有对应候选CSV时会复用，完整重拟合应将新OUT/prediction备份并移出后运行；不删除原始数据或旧mainspace结果。仅重算汇总使用`history_difficulty_v1_predict --summarize-only`。\n\n本包省略重复原始模型NPZ，但保留全部70种205图精确Gram矩阵，足以复算本轮L2数值核、训练侧中心化/PCA/Ridge/kNN。不可据此恢复原空间张量，也不能宣称包含648张原数组。重新导出核须在原仓库取得相应原始数值数组后运行`history_difficulty_v1_models`；该命令只读导出数组，不推理。两张Bi extended预测不可用，反馈表和失败表均保留。\n\n训练/检验使用包内固定隔离；目标人类人数、簇数、分歧不进入纯图片预测。E_conditioned是Manual/Semi分别训练的主人员结果；E/早期混合Q/T画像记录仅保留审计，不作为主结果。A_B/associations_verified.csv取代首次none控制标志错误的临时表。原专家评论空字符串计数修正见expert/COMMENT_COUNT_CORRECTION.json。\n\n所有图、真实子集和定义版本都不会增加独立样本。历史重排不是日历到达顺序，累计到19在实际n较小时是观察范围截断值。粗类不是正式最终收敛判据。\n'''
    # Files needed for all declared stages; no arbitrary large source/results sweep.
    inputs=[B/'metadata',B/'evaluation',B/'human',B/'visual',OLD/'process',OLD/'foundation/human',MAINSPACE/'images/metadata_all648.csv',ROOT/'analysis_results/candidate_selection_review_20260913_v2/用户审查原始记录.json']
    code_roots=[ROOT/'tools/thesis_main/analysis/image_portrait',ROOT/'tools/thesis_main/analysis/geometry_consensus',ROOT/'tools/thesis_main/analysis/quality_core',ROOT/'lib/misc']
    files=[]
    for p in inputs+[OUT]:
        files.extend([p] if p.is_file() else [q for q in p.rglob('*') if q.is_file() and '__pycache__' not in q.parts])
    for p in code_roots:files.extend(p.rglob('*.py'))
    for p in ROOT.glob('tools/**/__init__.py'):files.append(p)
    for name in ['lib/__init__.py','tests/test_history_difficulty_v1.py','tests/test_history_difficulty_v1_followup.py','pytest.ini']:
        p=ROOT/name
        if p.exists():files.append(p)
    oldreports=[MAINSPACE/'REPORT_ZH.md',OLD/'REPORT_ZH.md']
    files.extend(p for p in oldreports if p.exists())
    banned={'.jpg','.jpeg','.png','.webp','.pth','.pkl','.safetensors','.zip'}
    manifest=[]
    for p in sorted(set(files)):
        if not p.is_file():continue
        # Numerical figures generated in this run are permitted, original-image folders not selected.
        if p.suffix.lower() in banned and not (p.suffix=='.png' and p.is_relative_to(OUT/'figures')):continue
        relative_path=p.relative_to(ROOT);out=repo/relative_path;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,out)
        manifest.append(dict(path='repo/'+str(relative_path),bytes=p.stat().st_size,sha256=sha(p)))
    (repo/'requirements-history.txt').write_text(req);(stage/'REPRODUCE.md').write_text(commands,encoding='utf-8');(OUT/'REPRODUCE.md').write_text(commands,encoding='utf-8')
    start='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>历史作答粗分类研究</title><style>body{font-family:system-ui;line-height:1.9;max-width:900px;margin:50px auto;padding:0 20px}</style><body><h1>历史作答粗分类、不确定性与图片特质</h1><p>本轮实际执行结果。先阅读中文报告，再核对逐图证据；粗类不是永久难度真值。</p><p><a href="repo/'+relative+'/REPORT_ZH.html">打开完整中文报告（内嵌数值图）</a></p><p><a href="repo/'+relative+'/targets/primary_with_robustness.csv">逐图粗类、实际人数与定义一致性</a></p><p><a href="repo/'+relative+'/prediction/compact_primary_scores.csv">留楼预测比较</a></p><p><a href="repo/'+relative+'/local_image_review_queue.csv">本地审图队列</a></p><p><a href="REPRODUCE.md">复算说明</a>；代码在repo/tools/thesis_main/analysis/image_portrait/。</p><p>完整性与独立解压测试见DELIVERY_VERIFICATION.json；原图、权重和新视觉推理均不在交付中。主源基线 '+BASE+'。</p></body></html>'
    (stage/'START_HERE.html').write_text(start,encoding='utf-8')
    # A minimal local git record allows source-preparation provenance commands after extraction.
    subprocess.run(['git','init',str(repo)],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['git','-C',str(repo),'config','user.name','Portable research snapshot'],check=True)
    subprocess.run(['git','-C',str(repo),'config','user.email','snapshot@example.invalid'],check=True)
    subprocess.run(['git','-C',str(repo),'commit','--allow-empty','-m','Portable execution anchor; real input commit recorded in manifests'],check=True,stdout=subprocess.DEVNULL)
    # Only the tiny empty git metadata is packed; original source history is not copied.
    inventory=[]
    for p in sorted(stage.rglob('*')):
        if p.is_file():inventory.append(dict(path=str(p.relative_to(stage)),bytes=p.stat().st_size,sha256=sha(p)))
    (stage/'FILE_MANIFEST.json').write_text(json.dumps({'input_commit':BASE,'source_execution_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),'files':inventory,'note':'Hashes cover all payload files before manifest/verification itself. Portable .git is an empty local execution anchor, not upstream history.'},ensure_ascii=False,indent=2))
    archive=dest/'history_difficulty_study.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in stage.rglob('*'):
            if p.is_file():z.write(p,p.relative_to(stage))
    verification=dict(status='not_yet_verified',archive=archive.name,archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),input_commit=BASE)
    with tempfile.TemporaryDirectory(prefix='history_verify_') as tmp:
        with zipfile.ZipFile(archive) as z:assert z.testzip() is None;z.extractall(tmp)
        tmp=Path(tmp);mf=json.loads((tmp/'FILE_MANIFEST.json').read_text());bad=[]
        for rec in mf['files']:
            if sha(tmp/rec['path'])!=rec['sha256']:bad.append(rec['path'])
        assert not bad
        env=os.environ.copy();env['OPENBLAS_NUM_THREADS']='1';env['OMP_NUM_THREADS']='1';env['PYTHONPATH']=str(tmp/'repo')
        command=[sys.executable,'-m','pytest','tests/test_history_difficulty_v1.py','tests/test_history_difficulty_v1_followup.py','-q']
        result=subprocess.run(command,cwd=tmp/'repo',env=env,text=True,capture_output=True)
        verification.update(status='verified' if result.returncode==0 else 'tests_failed',files_verified=len(mf['files']),zip_integrity='passed',hash_mismatches=bad,extracted_test_command=command,extracted_tests_returncode=result.returncode,extracted_test_output=result.stdout+result.stderr,full_nested_cv_refitted_in_extract=False,exact_kernel_numerics_tested=True)
        assert result.returncode==0,result.stdout+result.stderr
    (dest/'DELIVERY_VERIFICATION.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8');js('execution/DELIVERY_VERIFICATION.json',verification)
    shutil.copy2(OUT/'REPORT_ZH.html',dest/'REPORT_ZH.html');shutil.copy2(OUT/'targets/primary_with_robustness.csv',dest/'per_image_historical_tiers.csv');shutil.copy2(OUT/'local_image_review_queue.csv',dest/'local_image_review_queue.csv')
    # Artifact download contains the verified ZIP plus a directly readable report and key CSVs.
    print(json.dumps(verification,ensure_ascii=False,indent=2),flush=True)
    return verification

if __name__=='__main__':run()
