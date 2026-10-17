"""Exclusive-output round1 anchor-space run with frozen-source preservation."""
from __future__ import annotations
import argparse
import collections
import json
import shutil
from pathlib import Path
import numpy as np
from . import simulate_annotators as base
from . import difficulty_wild_run as legacy
from .difficulty_wild_inputs import load_inputs,DEFAULT_INPUT
from .space_inventory_anchor import build_inventory,VERSION,POLICY,nearest,canonical,VALID
from .anchor_space_generation import sample_row
from .export_synthetic_label_studio import export_samples

WORK=base.ROOT.parent
PRESERVATION=WORK/'output/codex_handoff_20261017/PRESERVATION_MANIFEST.json'


def protected_hashes():
    manifest=json.loads(PRESERVATION.read_text());paths={}
    for key,value in manifest['protected'].items():
        if key=='user_edited_export':continue
        if key=='key_workspace_files':entries={p:h for p,h in value.items() if p!='path_scope'}
        elif 'files' in value:entries=value['files']
        elif 'sha256' in value:entries={str(Path(value['path'])/p):h for p,h in value['sha256'].items()}
        else:continue
        for p,h in entries.items():
            actual=base.digest(WORK/p)
            if actual!=h:raise ValueError('preservation_changed:'+p)
            paths[str(WORK/p)]=h
    return paths


def smoke_panel(panel,sources,inventory):
    selected=set()
    for label in ('简单','中等','困难'):
        selected.update(t['image_id'] for t in [t for t in panel if t['difficulty_class']==label][:2])
    def votes(iid):return collections.Counter(r['worker_scope'] for r in sources['scope'] if r['image_id']==iid)
    oos=next(t['image_id'] for t in panel if t['image_id'] not in selected and votes(t['image_id'])['oos']>votes(t['image_id'])['in_scope'])
    selected.add(oos)
    ties=[t['image_id'] for t in panel if t['image_id'] not in selected and votes(t['image_id'])['oos']==votes(t['image_id'])['in_scope'] and votes(t['image_id'])['oos']]
    tie=ties[0] if ties else min((t['image_id'] for t in panel if t['image_id'] not in selected and sum(votes(t['image_id']).values())),key=lambda i:(abs(votes(i)['oos']-votes(i)['in_scope'])/sum(votes(i).values()),i))
    selected.add(tie)
    return [t for t in panel if t['image_id'] in selected]


def run(output,seed=20261017,pilot_only=False,inputs=DEFAULT_INPUT):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    hashes=protected_hashes();sources=load_inputs(inputs)
    inventory,im=build_inventory(inputs);by={r['image_id']:r for r in inventory}
    im['space_sampling']='randomized_systematic_strata_per_image; frequency counts differ from expected by less than one; allocation shuffled across normal/wild slots'
    base.dump(output/'space_inventory.json',inventory);base.dump(output/'space_inventory_manifest.json',im)
    panel=legacy.targets(sources,seed);indices={t['image_id']:i for i,t in enumerate(panel)}
    if pilot_only:panel=smoke_panel(panel,sources,inventory)
    base.write_csv(output/'target_manifest.csv',panel)
    if pilot_only:
        votes={t['image_id']:dict(collections.Counter(r['worker_scope'] for r in sources['scope'] if r['image_id']==t['image_id'])) for t in panel}
        base.dump(output/'smoke_scope_coverage.json',dict(votes=votes,tie_available=any(c.get('oos',0)==c.get('in_scope',0) and c.get('oos',0)>0 for c in votes.values()),fallback='minimum_nonzero_vote_margin_when_no_true_tie_exists'))
    previous=DEFAULT_INPUT.parent/'full';oldrows=base.read_jsonl(previous/'simulations.jsonl');oldkeys=set().union(*(r.keys() for r in oldrows))
    # Preserve every optional legacy field, with null when that operation is absent.
    blocked_ids={r['export_worker_id'] for r in oldrows}
    blocked_ids.update(r['export_worker_id'] for r in base.read_jsonl(DEFAULT_INPUT.parent/'round2_gallery_144_20261017/simulations.jsonl'))
    humans=collections.defaultdict(list)
    for o in sources['objects'].values():
        if o['object_kind']=='annotation':
            p,g=canonical(o['preprocessed_points'])
            if p is not None:humans[o['image_id']].append(p)
    samples=[];audit=[];calibration={}
    for building in sorted({t['building_id'] for t in panel}):
        print('fit',building,flush=True);fitted=legacy.fit_fold(sources,building)
        base.dump(output/f'fold_{building}.json',dict(profiles=fitted['profiles'],held_out_building=building,training_buildings=fitted['training_buildings'],training_annotation_ids=fitted['training_annotation_ids'],calibration=fitted['calibration']))
        base.dump(output/f'donor_manifest_{building}.json',dict(held_out_building=building,time_annotation_ids=sorted(r['annotation_id'] for r in fitted['times']),time_buildings=sorted({r['building_id'] for r in fitted['times']}),geometry_donors_metadata_only=sorted(r['annotation_id'] for r in fitted['donors'])))
        for t in [t for t in panel if t['building_id']==building]:
            iid=t['image_id'];group=[];seen=set()
            for slot in range(t['need']):
                for nonce in range(128):
                    row=sample_row(sources,t,fitted,by[iid],seed,slot,indices[iid],nonce);p=np.array(row['points'])
                    fingerprint=json.dumps(row['points'],separators=(',',':'))
                    copied=any(p.shape==q.shape and np.allclose(p,q,rtol=0,atol=1e-8) for q in humans[iid]) or any(p.shape==np.shape(v['points']) and np.allclose(p,v['points'],rtol=0,atol=1e-8) for v in sources['models'][iid].values())
                    if fingerprint not in seen and not copied:seen.add(fingerprint);break
                else:raise ValueError('unique_noncopy_exhausted:'+iid)
                for key in oldkeys:row.setdefault(key,None)
                assert row['export_worker_id'] not in blocked_ids
                group.append(row)
            samples.extend(group);calibration[iid]={s['space_id']:s['jitter_calibration'] for s in by[iid]['spaces']}
            audit.append(dict(**t,synthetic_n=len(group),wild_n=sum(r['wild'] for r in group),normal_n=sum(not r['wild'] for r in group),total_n=t['real_manual_n']+len(group),spaces_selected=len({r['sampled_space_id'] for r in group}),scope_space_inconsistent=sum(not r['space_scope_coherence']['consistent'] for r in group)))
            print('generated',t['image'],len(group),'/',t['need'],flush=True)
    # Materialize every generated continuous subregion as an explicit resolvable
    # space. These do not enter the observed-frequency sampling population.
    derived=collections.defaultdict(dict)
    for r in samples:
        if r['space_id']==r['sampled_space_id']:continue
        parent=next(s for s in by[r['image_id']]['spaces'] if s['space_id']==r['sampled_space_id'])
        d=derived[r['image_id']].setdefault(r['space_id'],dict(space_id=r['space_id'],space_kind='subrange',parent_space_id=parent['space_id'],anchor_source=parent['anchor_source'],anchor_annotation_id=parent['anchor_annotation_id'],anchor_junction_count=r['anchor_junction_count'],source_anchor_junction_count=r['source_anchor_junction_count'],anchors=np.asarray(parent['anchors']).reshape(-1,2,2)[r['anchor_pair_indices']].reshape(-1,2).tolist(),parent_pair_indices=r['anchor_pair_indices'],scope_expected=parent['scope_expected'],human_n=0,human_frequency=0.,members=[],synthetic_n=0,scope_counts={},derivation='continuous ordered parent subring; no invented corners'))
        d['synthetic_n']+=1
    for item in inventory:item['generated_subranges']=[derived[item['image_id']][k] for k in sorted(derived[item['image_id']])]
    im['derived_space_resolution']='space_id resolves in spaces or generated_subranges; generated subranges have zero human sampling mass; per-corner distances use their own active subring anchors'
    base.dump(output/'space_inventory.json',inventory);base.dump(output/'space_inventory_manifest.json',im)
    samples.sort(key=lambda r:(r['image_id'],r['simulation_id']));base.write_jsonl(output/'simulations.jsonl',samples)
    _,export=export_samples(samples,sources['images'],output)
    base.write_csv(output/'difficulty_wild_audit.csv',audit);base.dump(output/'image_calibration.json',calibration)
    integrity={p:base.digest(Path(p))==h for p,h in hashes.items()};base.dump(output/'source_integrity.json',integrity)
    code=sorted(Path(__file__).parent.glob('*.py'));code += sorted((Path(__file__).parent/'geometry_consensus').glob('*.py'))
    source_manifest=dict(seed=seed,version=VERSION,policy_change=POLICY,input_sha256=hashes,space_inventory_sources=im['source_sha256'],code_sha256={str(p.relative_to(base.ROOT)):base.digest(p) for p in code},row_contract='round1 field union superset; GT score fields null, legacy donor geometry metadata retained only for provenance',user_edits='archived_only_never_loaded_by_generator',preservation_manifest_sha256=base.digest(PRESERVATION))
    base.dump(output/'source_manifest.json',source_manifest)
    for p in code:
        dest=output/'source_snapshot'/p.relative_to(base.ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    for p in (base.ROOT/'tests').glob('test_*anchor*.py'):
        dest=output/'source_snapshot/tests'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dest)
    dists=[d for r in samples for d in r['corner_anchor_dist_px']];normal=[d for r in samples if not r['wild'] for d in r['corner_anchor_dist_px']]
    validation=dict(all_targets_filled=all(a['total_n']==35 for a in audit),budgets_passed=all(a['wild_n']==a['wild_budget_k'] for a in audit),geometry_issues=sum(r['geometry_status']!=VALID for r in samples),corner_anchor_max_px=max(dists),corner_anchor_gt20=sum(d>20 for d in dists),corner_anchor_gt30=sum(d>30 for d in dists),normal_p50_px=float(np.median(normal)),normal_p95_px=float(np.quantile(normal,.95)),donor_building_isolation=all(all(r[k]!=r['held_out_building'] for k in ('time_donor_building_id','lead_time_donor_building_id','residual_donor_building_id')) for r in samples),unique_synthetic_ids=len({r['export_worker_id'] for r in samples})==len(samples),id_range_disjoint=not blocked_ids.intersection(r['export_worker_id'] for r in samples),source_integrity=all(integrity.values()),model_copies=0,human_copies=0,within_image_duplicate_geometry_rows=0,row_contract_superset=all(oldkeys<=r.keys() for r in samples),scope_space_inconsistent=sum(not r['space_scope_coherence']['consistent'] for r in samples),scope_policy='diagnostic_only_preserved_vote_distribution',export=export,reproducibility='pending_independent_replay')
    validation['functional_passed']=all(validation[k] for k in ('all_targets_filled','budgets_passed','donor_building_isolation','unique_synthetic_ids','id_range_disjoint','source_integrity','row_contract_superset')) and not(validation['geometry_issues'] or validation['corner_anchor_gt20'] or export['rejected']) and validation['normal_p95_px']<=15
    base.dump(output/'VALIDATION.json',validation)
    summary=dict(mode='fill-to-35-anchor-space',seed=seed,target_images=len(panel),generated=len(samples),wild=sum(r['wild'] for r in samples),normal=sum(not r['wild'] for r in samples),functional_passed=validation['functional_passed'],**export)
    base.dump(output/'summary.json',summary)
    if not validation['functional_passed']:raise ValueError('anchor_validation_failed')
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,default=20261017);p.add_argument('--pilot-only',action='store_true');a=p.parse_args();run(a.output,a.seed,a.pilot_only)

if __name__=='__main__':main()
