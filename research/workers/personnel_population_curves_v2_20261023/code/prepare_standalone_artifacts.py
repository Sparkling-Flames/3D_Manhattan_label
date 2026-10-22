"""Readable/downloadable copies of existing report and key result tables."""
from pathlib import Path
import json, re, shutil
from urllib.parse import quote

ROOT=Path('/workspace/scratch/fe955c3c772c')
REPO=ROOT/'HOHONET_population_latest'
R=REPO/'research/workers/personnel_population_curves_v2_20261023'
D=ROOT/'population_deliverables'
COMMIT='72a44e80c344975962e1071bd54d894dd86bb4b4'
specs=[
 ('natural/SECTION6_KEY_CURVES.csv','HOHONET_v2人数过程_自然曲线关键表_20261023.csv','sheet'),
 ('natural/SECTION6_KEY_INTERVALS.csv','HOHONET_v2人数过程_自然区间与图楼支持_20261023.csv','sheet'),
 ('policies/ADOPTION_TABLE.csv','HOHONET_v2人数过程_进入顺序采用表_20261023.csv','sheet'),
 ('policies/POLICY_MAIN_FIXED_N20.csv','HOHONET_v2人数过程_四方向80项完整条件_20261023.csv','sheet'),
 ('design/POLICY_POOL_CAPACITY.csv','HOHONET_v2人数过程_逐池角色与实际成员_20261023.csv','sheet'),
 ('design/LOBO_PRIORITY_ROLE_DEFINITIONS.csv','HOHONET_v2人数过程_楼外角色定义与历史中心_20261023.csv','sheet'),
 ('natural/NATURAL_FIXED_PANEL_CURVES.png','HOHONET_v2人数过程_自然24顺序主图_20261023.png','image'),
 ('natural/NATURAL_GEOMETRY_VARIATION.png','HOHONET_v2人数过程_同人数几何波动_20261023.png','image'),
 ('policies/POLICY_PROCESS_DIFFERENCES.png','HOHONET_v2人数过程_四方向成对效果_20261023.png','image'),
 ('policies/POLICY_Q_CURVES.png','HOHONET_v2人数过程_四方向质量曲线_20261023.png','image'),
 ('cases/final_context/NATURAL_CASE_CURVES.png','HOHONET_v2人数过程_五案自然24顺序_20261023.png','image'),
 ('cases/final_context/LOCAL_OPPORTUNITY_POLICY_CURVES.png','HOHONET_v2人数过程_局部结构正反作用_20261023.png','image')]
mapping={};uploads=[]
for relative,name,typ in specs:
    src=R/relative;dst=D/name
    assert src.exists(),src
    shutil.copy2(src,dst);mapping[str(src.resolve())]=dst
    uploads.append({'local_path':str(dst),'purpose':'create_library_file','library_artifact_type':typ})

def standalone(src,dst):
    def repl(m):
        marker,label,target=m[1],m[2],m[3]
        if target.startswith(('http:','https:','#','sandbox:')):return m[0]
        target_path=(src.parent/target.split('#')[0]).resolve()
        if str(target_path) in mapping:
            url='sandbox:'+str(mapping[str(target_path)])
        elif target_path.is_relative_to(R.resolve()):
            assert target_path.exists(),target_path
            url='sandbox:'+str(target_path)
        else:
            rel=target_path.relative_to(REPO.resolve()).as_posix()
            host=('https://raw.githubusercontent.com/Sparkling-Flames/3D_Manhattan_label/'+COMMIT+'/'
                  if marker else 'https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/'+COMMIT+'/')
            url=host+quote(rel,safe='/')
        return marker+'['+label+']('+url+')'
    s=re.sub(r'(!?)\[([^\]]+)\]\(([^)]+)\)',repl,src.read_text())
    s+='\n\n---\n\n本文件是同一报告的独立阅读副本，正文结论与仓库版一致，仅将引用改为附件及冻结提交链接。可移植的仓库相对链接版本随阶段04D保存；全部数据分包位置见下载清单。\n'
    dst.write_text(s)
    uploads.append({'local_path':str(dst),'purpose':'create_library_file','library_artifact_type':'report'})

standalone(REPO/'docs/thesis_main/人员分类与构成不确定性_研究组织与比较清单_20261022.md',D/'人员分类与构成不确定性_研究组织与比较清单_20261022.md')
standalone(R/'cases/final_context/CASE_CURVE_BACKGROUND.md',D/'HOHONET_v2人数过程_五案完整顺序背景_20261023.md')
(ROOT/'population_work/final_standalone_upload_request.json').write_text(json.dumps({'uploads':uploads},ensure_ascii=False,indent=2))
(ROOT/'population_work/STANDALONE_SOURCE_MAP.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2,default=str))
print('Prepared',len(uploads),'standalone copies')
