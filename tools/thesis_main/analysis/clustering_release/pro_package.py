"""Bundle only version-bound research inputs, numerical results and textual reviews."""
from pathlib import Path
import zipfile
from .pipeline import REPO,BASE,verify,read,sha


def main():
    root=BASE/'current';m=verify(root)
    result=read(root/'results/RESULT_MANIFEST.json')
    assert result['run_id']==m['run_id']
    files={REPO/name:name for name in m['code_files']}
    for name,expected in m['input_files'].items():
        assert sha(root/name)==expected
        files[root/name]='study/'+name
    for name,expected in result['files'].items():
        assert sha(root/'results'/name)==expected
        files[root/'results'/name]='study/results/'+name
    for name in ['RUN_MANIFEST.json','DATA_AUDIT.json','results/RESULT_MANIFEST.json']:
        files[root/name]='study/'+name
    for p in (BASE/'visual_review').glob('*.json'):
        files[p]='visual_review/'+p.name
    files[BASE/'README.md']='README.md'
    files[BASE/'PRO_TASK.md']='PRO_TASK.md'
    # Historical hypotheses/results, not freshly validated classifications.
    for folder in ['worker_four_block_exploration_20260910_v1','worker_rule_triad_20260910_v1','worker_coarse_validation_20260910_v1']:
        for p in (REPO/'analysis_results'/folder).rglob('*'):
            if p.is_file() and p.suffix in {'.md','.csv'}:
                files[p]='personnel_history/'+str(p.relative_to(REPO/'analysis_results')).replace('\\','/')
    for name in ['worker_four_block_exploration_20260910.py','worker_rule_triad_20260910.py','validate_worker_coarse_20260910.py']:
        files[REPO/'tools/thesis_main/analysis'/name]='personnel_history/source_code/'+name
    target=BASE/'pro_consistency_20260920.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for p,name in sorted(files.items(),key=lambda item:item[1]):
            z.write(p,name)
    print(target)


if __name__=='__main__':main()
