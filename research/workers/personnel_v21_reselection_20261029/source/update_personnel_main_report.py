"""Update the existing personnel report and export the same document for delivery."""
from pathlib import Path
import difflib,hashlib,json,re

W=Path(__file__).resolve().parents[1]
REPO=W.parent/'HOHONET_v21_20261029'
COMMIT='a476461d7ede8db95da43de4139e612c05e618bc'
NAME='人员分类与构成不确定性_研究组织与比较清单_20261022.md'
REL=Path('docs/thesis_main')/NAME
TOPIC=Path('research/workers/personnel_v21_reselection_20261029')
original=W/'source/ORIGINAL_PERSONNEL_MAIN_REPORT_AT_a476461d.md'
if not original.exists():
    original.write_bytes((REPO/REL).read_bytes())
assert hashlib.sha256(original.read_bytes()).hexdigest()=='8c846853976db8980c281fa433c8103dac678435654aaf1fdf0ff20a547dd1c6'
old=original.read_text()
marker='## 历史v2研究与方法来源'
before,historical=old.split(marker,1)
before='\n'.join(before.splitlines()[1:]).strip()
historical=marker+historical
historical=historical.replace('### 1.0 当前主方法、核心对照与新一轮同图大块结果（2026-10-25）','### 1.0 历史v2采用方法与同图大块结果（2026-10-25）',1)
prior='\n<details>\n<summary>本轮接续前的v2.1基线与任务原文（历史保留，已由顶部结果接续）</summary>\n\n'+before+'\n\n</details>\n\n'+historical
body=(W/'stage07_adoption/code/current_report_sections.md').read_text()
body=body.replace('{{CONDITION_TABLE}}',(W/'stage07_adoption/CONDITION_TABLE_FRAGMENT.md').read_text().strip())
assert '{{' not in body
repo_body=body.replace('{R}','../../'+TOPIC.as_posix())
repo_text=repo_body+prior
(REPO/REL).write_text(repo_text)
dest=W/'integration'/REL;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(repo_text)
patch=''.join(difflib.unified_diff(old.splitlines(keepends=True),repo_text.splitlines(keepends=True),fromfile='a/'+REL.as_posix(),tofile='b/'+REL.as_posix()))
(W/'integration/PERSONNEL_MAIN_REPORT_UPDATE.patch').write_text(patch)
topic=REPO/TOPIC
if not topic.exists():topic.symlink_to(W,target_is_directory=True)

def historical_web_links(s):
    def conv(m):
        href=m.group(1)
        if re.match(r'^[a-z]+:',href) or href.startswith('#'):return m.group(0)
        path,sep,fragment=href.partition('#')
        p=(REPO/REL.parent/path).resolve()
        try:r=p.relative_to(REPO.resolve()).as_posix()
        except ValueError:return m.group(0)
        return ']('+f'https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/{COMMIT}/{r}'+(sep+fragment if sep else '')+')'
    return re.sub(r'\]\(([^)\n]+)\)',conv,s)
export=body.replace('{R}','.')+historical_web_links(prior)
(W/NAME).write_text(export)
receipt={'source_commit':COMMIT,'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
         'repository_document':str(REL),'updated_repository_sha256':hashlib.sha256(repo_text.encode()).hexdigest(),
         'export_file':NAME,'export_sha256':hashlib.sha256(export.encode()).hexdigest(),
         'history_preserved':True,'github_pushed':False,'data_or_scoring_modified':False,
         'export_note':'Same report content; historical relative repository links converted to pinned GitHub links for standalone reading.'}
(W/'integration/REPORT_UPDATE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps(receipt,ensure_ascii=False))
