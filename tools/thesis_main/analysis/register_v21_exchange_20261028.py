"""按原确认网格、随机种子和楼外标签重选严格ABC；不读取目标评分。"""
import gzip
import importlib.util
import json
import sys
import types
import pandas as pd
from .rebuild_v21_20261028 import ROOT, OUT, read
from .recover_v21_composition_20261028 import SOURCE as COMPOSITION
from .prepare_v21_natural_inputs_20261028 import BASE

SOURCE=ROOT/'analysis_results/personnel_exchange_discrimination_audit_20261025/unpacked/03'
TARGET=OUT/'current_exchange_design'


def collect_labels():
    frames=[]
    for name in ['condition_classification/LABELS_ALL_LOBO.csv.gz','scope_axis_classification/AXIS_METHOD_LABELS_ALL_LOBO.csv.gz','scope_axis_classification/SCOPE_INCREMENT_LABELS_ALL_LOBO.csv.gz','fusion_role_classification/LABELS_ALL_LOBO.csv.gz']:
        d=pd.read_csv(OUT/name);d['label_source']=name;d['tier']='specified';frames.append(d)
    old=pd.read_csv(OUT/'joint_history_classification/ALL_METHOD_LABELS_LOBO.csv.gz')
    for method in ['V3_BEHAVIOR','V3_JOINT_QT']:
        for tier in ['coarse','fine']:
            d=old[old.method.eq(method)&old.condition.eq('manual')].copy()
            d['class_id']=d[tier+'_label'];d['method']=method+'_'+tier;d['tier']=tier;d['label_source']='joint_history_classification';frames.append(d)
    labels=pd.concat(frames,ignore_index=True);labels['candidate_origin']='v2.1_refit_or_verified_input_reuse'
    fields=['worker_id','heldout_building','method','class_id','known','condition','tier','candidate_origin','label_source']
    labels=labels[fields].drop_duplicates()
    assert not labels.duplicated(['worker_id','heldout_building','method','condition']).any()
    return labels


def main():
    TARGET.mkdir(exist_ok=True)
    source=types.ModuleType('run_native');source.ROOT=TARGET;source.REPO=ROOT;source.POP=BASE
    def load(path):
        if path==BASE/'inputs/INPUT_SNAPSHOT.json.gz':return read(OUT/'pools/INPUT_SNAPSHOT.json')
        if path.suffix=='.gz':
            with gzip.open(path,'rt',encoding='utf-8') as f:return json.load(f)
        return read(path)
    def save(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        op=gzip.open if path.suffix=='.gz' else open
        with op(path,'wt',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=True)
    def csv(path,frame):
        path.parent.mkdir(parents=True,exist_ok=True);frame.to_csv(path,index=False,encoding='utf-8-sig')
    # The native team identity uses canonical sorted members; retain its digest.
    import hashlib
    source.team_key=lambda pid,ws:pid+'__'+hashlib.sha256(json.dumps(sorted(ws),sort_keys=True,separators=(',',':')).encode()).hexdigest()[:20]
    source.read=load;source.save=save;source.csv=csv;sys.modules['run_native']=source
    spec=importlib.util.spec_from_file_location('v21_registration_native',SOURCE/'register_exchange.py')
    native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
    native.collect_labels=collect_labels
    frozen=pd.read_csv(SOURCE/'design/confirm/IMAGE_PHASE_ASSIGNMENT.csv').set_index('pool_id')
    def partition(pools):
        rows=[]
        for pool in pools:
            meta=pool['meta'];pid=pool['pool_id']
            if pid in frozen.index:
                r=frozen.loc[pid].to_dict();r.update(meta);rows.append(r);continue
            known=frozen[frozen.building.eq(meta['building'])]
            assert len(known)>0 and known.selection_building_group.nunique()==1
            group=known.selection_building_group.iloc[0]
            phase=('within_building_extension' if group=='discovery' else 'selection_heldout_building') if meta['layer']=='ordinary_manual' else 'not_primary'
            rows.append(dict(meta,phase=phase,selection_building_group=group,split_seed=native.SEED))
        return pd.DataFrame(rows)
    native.partition=partition
    history=pd.read_csv(OUT/'condition_classification/HISTORY_FEATURES_ALL_LOBO.csv.gz')
    csv(TARGET/'features/HISTORY_FEATURES_ALL_LOBO.csv.gz',history)
    checks=[]
    for stage in ['confirm','reverse_confirm']:
        old=read(SOURCE/f'design/{stage}/DESIGN.json')
        plan=old.get('method_specific_grid')
        methods=sorted(plan) if plan else ['RFUSE_GEOM_K2','RFUSE_GEOM_K3','RFUSE_GEOMQ_K2','RFUSE_GEOMQ_K3']
        planpath=TARGET/f'{stage}_FROZEN_GRID.json'
        if plan:save(planpath,plan)
        args=types.SimpleNamespace(stage=stage,plan=planpath if plan else None,methods=','.join(methods),grid=','.join(f'{n}:{m}' for n,m in old['grid']),blocks=old['blocks_per_cell'],backgrounds=old['backgrounds_per_level'])
        native.generate(args)
        ev=pd.read_csv(TARGET/f'design/{stage}/EVENTS_EXACT.csv.gz')
        assert ev.actual_m_AB.eq(ev.m).all() and ev.actual_m_AC.eq(ev.m).all() and ev.actual_m_BC.eq(ev.m).all()
        assert ev.A_class_vector.eq(ev.B_class_vector).all()
        receipt=read(TARGET/f'design/{stage}/DESIGN.json');receipt.update(underlying_data='v2.1',selection_plan='frozen_v2_confirmation_grids_no_target_outcome_reselection',phase_assignment='all_existing_images_unchanged_new_images_inherit_building_partition')
        save(TARGET/f'design/{stage}/DESIGN.json',receipt);checks.append(receipt)
    save(TARGET/'CHECKS.json',checks)


if __name__=='__main__':main()
