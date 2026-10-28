"""复用原同房分析，只替换已复算端点和明确指定的当前楼外标签。"""
import argparse
import json
import subprocess
import sys
import types
from .prepare_v21_same_room_analysis_20261028 import CURRENT,LARGE,TARGET
from .rebuild_v21_20261028 import ROOT,OUT


def load_without_file_hash(path,old,new):
    source=path.read_text(encoding='utf8');assert source.count(old)==1
    module=types.ModuleType(path.stem);module.__file__=str(path)
    exec(compile(source.replace(old,new),str(path),'exec'),module.__dict__)
    return module


def main(stage,current=False):
    design=OUT/('same_room_current_extended_design' if current else 'same_room_current_labels_design')
    endpoint=OUT/'same_room_current_results/finite/native' if current else TARGET/'current_classes/native'
    destination=OUT/('same_room_current_results/finite' if current else 'same_room_current_labels_results')
    labels=OUT/'same_room_current_capacity/CURRENT_MANUAL_LABELS_LOBO.csv' if current else design/'LABELS_AND_HISTORIES.csv.gz'
    if stage=='response':
        path=CURRENT/'code/taxonomy_response/analyze_response.py'
        native=load_without_file_hash(path,'signature={str(p.name):hashlib.sha256(p.read_bytes()).hexdigest() for p in immutable_inputs}','signature={} # No input hashes or stale-cache reuse in this release run.')
        out=destination/'response'
        native.analyze(argparse.Namespace(repo=ROOT,labels=labels,design=design,native=endpoint,out=out,partial=False,reuse_existing=False))
        p=out/'ANALYSIS_RECEIPT.json';r=json.loads(p.read_text(encoding='utf8'))
        r.update(data_release='v2.1',label_input='current_v21_LOBO',existing_structure_labels_and_actual_teams_unchanged=True,additional_panels_from_existing_relations=current,joint_labels_and_Q_histories_updated=True)
        p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    elif stage=='exact':
        subprocess.run([sys.executable,'-X','utf8','-B',str(CURRENT/'code/analysis/analyze_exact_changes.py'),'--design',str(design),'--native',str(endpoint),'--out',str(destination/'exact_changes')],check=True)
        p=destination/'exact_changes/ANALYSIS_RECEIPT.json';r=json.loads(p.read_text(encoding='utf8'))
        r.update(data_release='v2.1',current_LOBO_labels=True,additional_panels_from_existing_relations=current)
        p.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf8')
    elif stage=='large':
        out=OUT/'same_room_current_results/large' if current else TARGET/'large_block'
        design=OUT/'same_room_current_large_design' if current else LARGE/'design'
        geometry=out/'geometry' if current else LARGE/'geometry'
        native=load_without_file_hash(LARGE/'analysis/build_events.py',"'design_sha256':hashlib.sha256(Path(design).read_bytes()).hexdigest()","'data_release':'v2.1'")
        native.main(design/'STRICT_ABC_EVENTS.csv.gz',out/'native/ENDPOINT_SCALARS.csv.gz',out/'results')
        calls=[
            ['summarize_conditions.py','--events',out/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--out',out/'results'],
            ['member_sensitivity.py','--events',out/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--out',out/'sensitivity'],
            ['summarize_geometry.py','--events',out/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--geometry',geometry/'EVENT_GEOMETRY_RESULTS.csv.gz','--out',out/'geometry_summary'],
            ['history_q_common_support.py','--events',out/'results/EVENT_Q_STRUCTURE_EFFECTS.csv.gz','--geometry',out/'geometry_summary/EVENT_GEOMETRY_COMMON_SUPPORT.csv.gz','--out',out/'history_q'],
            ['analyze_anchor_paths.py','--design-dir',design,'--native',out/'native/ENDPOINT_SCALARS.csv.gz','--out',out/'anchor_paths'],
        ]
        for script,*args in calls:
            print(script,flush=True)
            subprocess.run([sys.executable,'-X','utf8','-B',str(LARGE/'analysis'/script),*map(str,args)],check=True)
        recovered=sum(p['recovered_geometries'] for p in json.loads((geometry/'CHECKS.json').read_text(encoding='utf8'))['pools']) if current else 0
        (out/'ANALYSIS_COMPLETE.json').write_text(json.dumps(dict(data_release='v2.1',actual_teams_and_labels='current_v21' if current else 'frozen_v2',current_reference_scores=True,geometry_reused=recovered==0,geometry_comparisons_recomputed=current,geometry_recoveries=recovered,complete=True)),encoding='utf8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['response','exact','large']);p.add_argument('--current',action='store_true');a=p.parse_args();main(a.stage,a.current)
