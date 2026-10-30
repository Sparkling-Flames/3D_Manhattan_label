"""Replay cached collection/capacity/case paths with all Git subprocesses forbidden."""
from pathlib import Path
import json,runpy,subprocess
ROOT=Path(__file__).resolve().parents[1];old=subprocess.check_output;calls=[]
def forbidden(*args,**kwargs):
    calls.append(str(args[0]) if args else 'unspecified')
    raise AssertionError('A packaged-input replay attempted an archive subprocess')
subprocess.check_output=forbidden
scripts=['same_room_extract_events.py','same_room_endpoint_status.py','same_room_capacity.py','same_room_evidence.py','same_room_case_viewer.py'];completed=[]
try:
    for script in scripts:
        try:runpy.run_path(str(ROOT/'scripts'/script),run_name='__main__')
        except SystemExit as exc:
            if exc.code not in [None,0]:raise
        completed.append(script)
finally:subprocess.check_output=old
(ROOT/'stage02_same_room/PACKAGED_INPUT_PORTABILITY_CHECK.json').write_text(json.dumps(dict(completed_scripts=completed,archive_subprocess_attempts=calls,all_passed=len(completed)==len(scripts) and not calls,old_repository_not_needed_for_these_paths=True,full_ABC_aggregation_cache_priority='EXISTING_GEOMETRY_SOURCE.csv.gz is checked before original repository fallback',prediction_uses_only_packaged_source_files=True),ensure_ascii=False,indent=2))
print('PACKAGED_INPUT_PORTABILITY_OK',len(completed),flush=True)
