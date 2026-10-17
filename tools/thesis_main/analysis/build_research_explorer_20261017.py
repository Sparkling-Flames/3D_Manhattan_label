#!/usr/bin/env python3
"""Build a read-only, columnar research explorer bundle from a pinned checkout.

CSV source hashes identify the original bytes. Display data omit direct personal
contact/name fields, redact email-like strings, and never include raw input blobs.
Inputs are read from pinned Git objects or a SHA-256-verified export. Generated
JSON is local and ignored by Git. Python 3.10+ standard library only.
"""
import argparse, csv, hashlib, io, json, math, re, subprocess, tempfile
from collections import Counter
from pathlib import Path

MODULES = {
    'quality': ('质量与资格', 'research/quality/quality_b8l2_d10_20261017'),
    'difficulty': ('图片难度', 'research/difficulty/difficulty_current_20261017'),
    'statistics': ('全量统计与覆盖', 'research/statistics/b8l2_d10_statistics_20261017'),
    'workers': ('人员画像', 'research/workers/worker_b8l2_d10_20261017'),
    'fusion': ('融合人数过程', 'research/fusion/wall_consensus_d10_20261017'),
    'same_room': ('同房跨视角', 'research/same_room/same_room_update_20261017'),
    'historical_rdv': ('历史：原作答R/D/V与构成', 'analysis_results/consensus_response_20261006'),
    'historical_lee': ('历史：Lee底面全库曲线', 'analysis_results/difficulty_full_20261007'),
    'historical_patterns': ('历史：四图整份标法演示', 'analysis_results/lee_consensus_demos_20261003'),
    'historical_image_features': ('历史：客观图片与离线模型特征', 'analysis_results/objective_difficulty_20261009'),
    'historical_sb': ('历史：S/B与四轴证据', 'research/workers/worker_four_axis_update_20261015'),
    'historical_same_room': ('历史：同房Lee曲线', 'research/same_room/same_room_quality_curves_20261015'),
}
COMMIT='090883fab97298fb18033638487b0f4a84bf0d54'
MANIFEST='analysis_results/research_input_20261017/manifest.json'
DOC_NAMES={
    'CHECKS.json','FIELD_CONTRACT.json','INPUTS.json','MODEL_PARAMETERS.json',
    'VALIDATION.json','VERIFICATION.json','ROUTING_AUDIT.json','INDEPENDENT_CHECK.json',
    'SUMMARY.json','AUXILIARY_STATUS.json','CROSS_MODULE_INPUTS.json','INPUT_BRIDGE.json',
    'SOURCE_HANDOFF.json','CURVE_INPUTS.json','Q_T_INPUTS.json','README.md','HANDOFF.md',
    'REPORT.md','field_contract.json','summary.json','checks.json','pattern_checks.json','projection_checks.json','design.json','FIGURES.md',
}
PERSONAL_FIELDS=re.compile(r'(^|_)(email|e_mail|phone|telephone|password|username|user_name|full_name|real_name|worker_name|annotator_name|display_name)(_|$)',re.I)
EMAIL=re.compile(r'(?<![\w.])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?!\w)')
NUM=re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')
ID_FIELD=re.compile(r'(^|_)(id|ids|code|codes|version|revision|sha|hash)(_|$)',re.I)
GRAINS={
 'shared_records':'one annotation object; complete inventory',
 'record_lookup':'one annotation object; complete inventory',
 'quality_records':'one quality-eligible annotation object',
 'record_audit':'one annotation object with difficulty/target eligibility',
 'record_reason_audit':'one annotation object; overlapping reason fields retained',
 'shared_bindings':'one annotation object and its pre-score target routing evidence',
 'binding_changes':'one annotation object; old/new routing comparison',
 'new_batch_records':'one new-batch annotation object',
 'new_measurements':'one newly measured annotation object; population separates new batch/old routing gap',
 'image_metadata':'one research image',
 'image_inventory':'one research image',
 'worker_inventory':'one pseudonymous source worker',
 'image_condition_stats':'one image × collection condition',
 'worker_condition_stats':'one worker × condition × analysis layer',
 'worker_difficulty':'one worker × condition × comparison stratum',
 'time_quality_focus':'one worker × condition × comparison stratum; exact nonmissing time intersections',
 'worker_special_axes':'one worker × condition × analysis layer × scene axis × level',
 'difficulty_overview':'one condition × comparison stratum',
 'difficulty_by_condition':'one collection condition × difficulty category',
 'difficulty_by_quality_use':'one collection condition × difficulty category × quality use',
 'difficulty_scene_by_condition':'one condition × difficulty × doorway/OOS intersection',
 'scene_by_condition':'one condition × doorway/OOS intersection',
 'image_by_condition':'one image × collection condition',
 'cleaning_summary':'one condition × cleaning disposition',
 'calculation_summary':'one condition × calculation status × quality use',
 'exclusion_reason_hits':'one annotation object × reason kind × reason; not additive people',
 'exclusion_time_summary':'one condition × analysis layer × quality use',
 'time_missing_records':'one annotation object missing at least one tracked time scope',
 'diagnostic_quality_stats':'one condition × scene bucket × quality use; diagnostic only',
 'room_group_registry':'one adopted working group',
 'room_group_memberships':'one working group × image membership; groups overlap',
 'user_original_group_memberships':'one original user group × image membership; groups overlap',
 'room_group_summary':'one working group × condition × analysis layer',
 'user_original_group_summary':'one original user group × condition × analysis layer',
 'room_worker_groups':'one working group × worker × condition × analysis layer',
 'user_original_worker_groups':'one original user group × worker × condition × analysis layer',
 'room_group_views':'one working group × image × condition × analysis layer',
 'user_original_group_views':'one original user group × image × condition × analysis layer',
 'room_direct_pair_registry':'one directly recorded image pair; no transitive room inference',
 'room_direct_pair_summary':'one direct image pair × condition × analysis layer',
 'room_worker_direct_pairs':'one direct image pair × worker × condition × analysis layer',
 'room_unlinked_images':'one image without recorded relationship; not evidence of a different room',
 'trajectory_scores':'one image × real member-order path × member count; repeated subsets possible',
 'subset_scores':'one unique image/member subset; not an independent experiment',
 'by_image_k':'one image × member count; denominator changes across counts',
 'automatic_endpoints':'one image automatic all-member endpoint; failures retained',
 'assisted_endpoints':'one existing human-assisted endpoint; separate from automatic paths',
 'pool_bridge':'one frozen fusion image pool',
 'member_bridge':'one frozen fusion input annotation',
 'matched_changes':'one image × fixed member-count interval on matched valid paths',
 'current_pairs':'one image pair × metric × condition/relationship layer',
 'current_people':'one paired worker observation × image pair × metric',
 'worker_group_image_records':'one annotation × user group membership; overlapping groups repeat annotations',
 'worker_group_difficulty':'one worker × user group × difficulty × condition',
 'frozen_analysis_records':'one annotation in the module analysis source snapshot',
 'quality_panel':'one ordinary Manual training annotation; module-admitted, not all quality eligible',
 'personnel_ledger':'one annotation with personnel-module use gates',
 'shared_input_snapshot':'one annotation object; complete common inventory snapshot',
 'new_admission_review':'one new-batch annotation; training/holdout adjudication',
 'replacement_pairs':'one overlapping real-team single-member replacement pair; not independent trials',
 'team_scores':'one frozen real team; metric columns share geometry and historical use boundary',
}
CAUTIONS={
 'quality':['B8L2 primary; D10 changes direction scale 8°→10° only, not A10.', 'A computed diagnostic is not quality eligibility; OOS never enters quality.', 'Blank means missing, never zero.'],
 'difficulty':['Only quality-eligible records with matching score and difficulty target may enter difficulty-quality summaries.', 'Conditions and ordinary/doorway/special uses remain separate.', 'Human coarse labels are not independently validated by their own outcome means.'],
 'statistics':['Answer-equal and image-equal means use different denominators.', 'Conditions are not pooled; overlapping relationship groups/reasons are not additive.', 'Source activity time and audited same-target time are separate and use real nonmissing intersections.'],
 'workers':['1048 ordinary Manual training annotations are not all 1911 quality-eligible annotations.', 'Preserve scenario, metric, leave-building-out fold and minimum-support gates.', 'Raw means and relative zero-line crossings are not stable worker ability categories.'],
 'fusion':['18 frozen images, 7320 path states, 6693 unique member subsets; not all 261 images.', 'Non-OOS numeric scores still require primary_comparison_eligible/use/holdout gates.', 'Repeated states/subsets are dependent; compare matched paths, not changing valid-state means.', 'D10 changes scoring only; geometry is unchanged.'],
 'same_room':['Image pairs, directions, workers and overlapping user groups are dependent.', 'Current pair/metric/condition/relationship layer must remain explicit; valid metric pairing uses n_paired, not source-overlap n_common_workers.', 'Unrecorded relationship does not certify different rooms; no cross-group transitive inference.', 'Same-room full quality-usable real fusion-curve coverage remains zero.'],
}

def dump(path,obj):
    s=json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(s,encoding='utf-8')
    return len(s.encode())
def sha(b): return hashlib.sha256(b).hexdigest()
def ptr(b): return b.startswith(b'version https://git-lfs.github.com/spec/v1')
def parse_cell(value,column):
    if value is None or value=='': return None
    s=value.strip()
    if s.lower()=='true': return True
    if s.lower()=='false': return False
    if ID_FIELD.search(column): return EMAIL.sub('[redacted email]',value) if '@' in value else value
    if NUM.match(s) and not re.match(r'^[+-]?0\d+$',s):
        try:
            n=float(s)
            if math.isfinite(n):
                if '.' not in s and 'e' not in s.lower():
                    i=int(s)
                    return i if abs(i)<2**53 else s
                return n
        except ValueError: pass
    return EMAIL.sub('[redacted email]',value) if '@' in value else value
def field_map(columns):
    candidates={'object':['object_id','inventory_record_id','record_id'], 'worker':['worker_id','worker'],
        'image':['image_id','image','image_code'],'building':['building_id','building'],
        'condition':['condition'],'target':['rescore_target_id','current_target_id','target_id'],
        'group':['group_id','user_group_id'],'metric':['metric','quality_metric'],'scenario':['scenario','panel']}
    return {k:next((v for v in vs if v in columns),None) for k,vs in candidates.items()}
def infer_grain(stem,columns):
    if stem in GRAINS:return GRAINS[stem]
    key=[c for c in columns if c in {'worker_id','image_id','condition','metric','scenario','panel','heldout_building','target_building','group_id','user_group_id','comparison','axis','level','k','path_id','pair_id'}]
    return 'Declared table row; likely '+(' × '.join(key) if key else stem.replace('_',' '))+'; consult FIELD_CONTRACT and source README.'

def build(repo, out, source_manifest):
    actual = COMMIT
    permitted = {item['path'] for item in source_manifest['files']}
    index={'schema_version':'research_explorer_v1','source_commit':actual,'source_manifest':MANIFEST,
        'source_repository':'Sparkling-Flames/3D_Manhattan_label','modules':[],'tables':[],'documents':[],
        'overview_path':'overview.json','warnings':[], 'privacy':{'audience':'existing owner-private research audience only',
        'raw_research_and_comment_blobs_included':False,'personal_name_contact_fields_omitted':True,
        'note':'Source hashes are hashes of original CSV bytes, before display redaction.', 'input_manifest_embedded':False}}
    cache={};dedup={}; inventory=[]
    for mid,(label,rel) in MODULES.items():
        root=repo/rel
        if not root.is_dir():
            if mid.startswith('historical_'):
                index['warnings'].append({'path':rel,'issue':'Historical supplementary source not materialized; source linked only'});continue
            raise SystemExit(f'Missing module {root}')
        module_status='historical' if mid.startswith('historical_') else 'current'
        index['modules'].append({'id':mid,'label':label,'path':rel,'status':module_status})
        for f in sorted(root.rglob('*.csv')):
            if f.relative_to(repo).as_posix() not in permitted: continue
            relative=f.relative_to(root).as_posix();tid=mid+'__'+relative[:-4].replace('/','__')
            b=f.read_bytes();h=sha(b)
            if ptr(b):
                index['warnings'].append({'path':f.relative_to(repo).as_posix(),'issue':'Git LFS pointer; no data parsed'});continue
            status='superseded' if 'provisional' in relative else module_status
            text=b.decode('utf-8-sig');reader=csv.reader(io.StringIO(text,newline=''))
            original_columns=next(reader,[])
            omit=[c for c in original_columns if PERSONAL_FIELDS.search(c)]
            keep=[i for i,c in enumerate(original_columns) if c not in omit]
            cols=[original_columns[i] for i in keep];rows=[];redacted=0
            for raw in reader:
                if len(raw)!=len(original_columns):raise ValueError(f'{f}: row length {len(raw)} != {len(original_columns)}')
                redacted+=sum(bool(EMAIL.search(v)) for v in raw if '@' in v)
                rows.append([parse_cell(raw[i],original_columns[i]) for i in keep])
            types=[]
            for j,c in enumerate(cols):
                ts={type(r[j]).__name__ for r in rows if r[j] is not None}
                types.append('null' if not ts else 'number' if ts<={'int','float'} else 'boolean' if ts=={'bool'} else 'string' if ts=={'str'} else 'mixed')
            parts=[]
            if h in dedup and dedup[h]['columns']==cols:
                parts=dedup[h]['parts']
            else:
                chunk=[];start=0;size=0;partnum=0
                def write_part():
                    nonlocal start,partnum,chunk,size
                    relpart=f'tables/{tid}.{partnum}.json';nbytes=dump(out/relpart,{'table_id':tid,'columns':cols,'rows':chunk})
                    if nbytes>=20*1024*1024:raise ValueError('Part over 20 MiB')
                    parts.append({'path':relpart,'row_start':start,'row_count':len(chunk),'bytes':nbytes})
                    start+=len(chunk);partnum+=1;chunk=[];size=0
                for row in rows:
                    n=len(json.dumps(row,ensure_ascii=False,separators=(',',':')).encode())+1
                    if chunk and size+n>14*1024*1024:write_part()
                    chunk.append(row);size+=n
                if chunk or not rows:write_part()
                dedup[h]={'columns':cols,'parts':parts,'table_id':tid}
            caveats=list(CAUTIONS.get(mid,['Historical frozen analysis: source population, reference, metric and method differ from current B8L2/D10 modules.', 'Do not merge into current denominators or rename Lee/OSPA results as current wall-line/B8L2 outputs.']))
            if status=='superseded':caveats.insert(0,'Superseded preparation snapshot, retained for traceability; not current totals.')
            entry={'id':tid,'module':mid,'path':f.relative_to(repo).as_posix(),'label':relative,'columns':cols,
                'column_types':types,'row_count':len(rows),'grain':infer_grain(f.stem,cols),'caveats':caveats,
                'sha256':h,'status':status,'parts':parts,'field_map':field_map(cols),
                'condition_fields':[c for c in cols if c in {'condition','analysis_layer','quality_use','scene_bucket','scenario','metric','panel','comparison','use_panel','room_layer','relation_tier','scope_comparable'}],
                'validity_fields':[c for c in cols if any(s in c for s in ['eligible','usable','status','holdout','calculation','missing','n_common','n_paired','support','target_relation'])],
                'redacted_columns':omit,'email_cells_redacted':redacted,
                'source_url':f'https://github.com/Sparkling-Flames/3D_Manhattan_label/blob/{actual}/'+f.relative_to(repo).as_posix()}
            entry.update(source_manifest.get('display_metadata_overrides', {}).get(tid, {}))
            if dedup[h]['table_id']!=tid:entry['same_content_as']=dedup[h]['table_id']
            index['tables'].append(entry);cache[tid]={'columns':cols,'rows':rows}
            inventory.append({k:v for k,v in entry.items() if k!='parts'})
        for f in sorted(root.rglob('*')):
            if f.relative_to(repo).as_posix() not in permitted: continue
            if f.name not in DOC_NAMES:continue
            if not f.is_file():continue
            b=f.read_bytes()
            if ptr(b): index['warnings'].append({'path':f.relative_to(repo).as_posix(),'issue':'Git LFS pointer document'});continue
            content=b.decode('utf-8-sig');content=EMAIL.sub('[redacted email]',content) if '@' in content else content
            obj=json.loads(content) if f.suffix=='.json' else content
            index['documents'].append({'path':f.relative_to(repo).as_posix(),'module':mid,'kind':f.suffix[1:], 'sha256':sha(b),'content':obj})
    inputroot=repo/MANIFEST
    # Source manifest is linked, not embedded. Raw data/research/comments and
    # identity maps are never part of the explorer bundle.
    for name in ['CHECKS.json','INDEPENDENT_CHECK.json','field_contract.json','research_field_contract.json','validation.json']:
        f=inputroot.parent/name;b=f.read_bytes()
        if ptr(b):index['warnings'].append({'path':f.relative_to(repo).as_posix(),'issue':'Git LFS pointer document'});continue
        s=EMAIL.sub('[redacted email]',b.decode('utf-8-sig'))
        index['documents'].append({'path':f.relative_to(repo).as_posix(),'module':'input','kind':f.suffix[1:],'sha256':sha(b),'content':json.loads(s) if f.suffix=='.json' else s})
    stats=json.loads((repo/MODULES['statistics'][1]/'CHECKS.json').read_text(encoding='utf-8-sig'))
    qchecks=json.loads((repo/MODULES['quality'][1]/'CHECKS.json').read_text(encoding='utf-8-sig'))
    overview={'metadata':{'source_commit':actual,'input_revision':'annotation_batch_98_20261017_v1','score_version':'quality_b8l2_d10_20261017_v2','primary_metric':'B8L2','sensitivity_metric':'D10','D10_is_A10':False},
        'counts':{k:v for k,v in stats.items() if k not in {'tables','figures'}},'quality_checks':qchecks,'tables':{}}
    recordcols=['object_id','image_id','image_code','worker_id','building_id','condition','difficulty_class','scene','scene_bucket','analysis_layer','quality_use','quality_usable','pool_analysis_eligible','original_holdout','is_oos','is_doorway','calculation_status','current_target_id','rescore_target_id','B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','diagnostic_B8L2','diagnostic_D10','source_active_time_seconds','active_time_seconds','target_matched_time_seconds','new_batch','binding_status','quality_exclusion_reasons']
    def add(tid,columns=None):
        if tid not in cache:return
        t=cache[tid]
        if columns:
            cs=[c for c in columns if c in t['columns']];ix=[t['columns'].index(c) for c in cs]
            overview['tables'][tid]={'columns':cs,'rows':[[r[j] for j in ix] for r in t['rows']]}
        else:overview['tables'][tid]=t
    add('statistics__record_lookup',recordcols)
    # Full target identities remain in lazy tables; overview uses an explicit
    # equality flag instead of repeating two long provenance paths per row.
    rt=overview['tables']['statistics__record_lookup']
    ci=rt['columns'].index('current_target_id');ri=rt['columns'].index('rescore_target_id')
    keep=[i for i in range(len(rt['columns'])) if i not in {ci,ri}]
    overview['tables']['statistics__record_lookup']={'columns':[rt['columns'][i] for i in keep]+['targets_match'],
        'rows':[[r[i] for i in keep]+[r[ci] is not None and r[ri] is not None and r[ci]==r[ri]] for r in rt['rows']]}
    overview['metadata']['derived_fields']={'targets_match':'Both targets are nonmissing and current_target_id == rescore_target_id; full identities remain in statistics__record_lookup lazy table.'}
    selected=['statistics__worker_inventory','statistics__image_inventory','statistics__worker_condition_stats','statistics__image_condition_stats','statistics__difficulty_overview','statistics__calculation_summary','statistics__cleaning_summary','statistics__exclusion_time_summary','statistics__diagnostic_quality_stats','difficulty__difficulty_by_condition','difficulty__difficulty_by_quality_use','difficulty__scene_by_condition','workers__coverage','workers__profiles','workers__profile_sensitivity','workers__prediction_performance','workers__condition_general_comparison','workers__four_axis_evidence','fusion__by_image_k','fusion__automatic_endpoints','fusion__assisted_endpoints','fusion__matched_changes','same_room__pair_counts','same_room__by_user_group_ge4','same_room__controls_by_building','same_room__coverage_decomposition','same_room__actual_18_curve_relation_coverage']
    for tid in selected:add(tid)
    # The overview is a plotting aid; full data are always present in lazy tables.
    n=dump(out/'overview.json',overview)
    if n>2*1024*1024:
        # Keep only essential aggregate columns in wide tables before giving up.
        for tid in ['statistics__image_condition_stats','statistics__worker_condition_stats','statistics__image_inventory','workers__profiles']:
            if tid not in overview['tables']:continue
            t=overview['tables'][tid];keep=[i for i,c in enumerate(t['columns']) if not any(s in c for s in ['exclusion_reasons','quality_source_time_','quality_target_time_','q25','q75','_sd'])]
            overview['tables'][tid]={'columns':[t['columns'][i] for i in keep],'rows':[[r[i] for i in keep] for r in t['rows']]}
        n=dump(out/'overview.json',overview)
    if n>2*1024*1024:raise ValueError(f'Overview exceeds 2MiB: {n}')
    index['overview_bytes']=n
    index['source_inventory']=source_manifest['original_source_inventory']
    index['warnings']=source_manifest['original_warnings']
    index['historical_coverage']='Supplementary historical tables are explicitly historical and partial; all inspected source artifacts are indexed with availability.'
    index['table_count']=len(index['tables']);index['current_table_count']=sum(x['status']=='current' for x in index['tables'])
    index['total_row_count']=sum(x['row_count'] for x in index['tables'])
    index['total_unique_part_bytes']=sum(x.stat().st_size for x in (out/'tables').glob('*.json'))
    dump(out/'index.json',index)
    print(json.dumps({'tables':index['table_count'],'current_tables':index['current_table_count'],'rows':index['total_row_count'],'overview_bytes':n,'unique_part_bytes':index['total_unique_part_bytes'],'warnings':index['warnings'],'redacted_columns':sum(len(x['redacted_columns']) for x in index['tables']),'email_cells_redacted':sum(x['email_cells_redacted'] for x in index['tables'])},ensure_ascii=False))
    return index,overview

PACKAGE_REL = Path('research/statistics/research_explorer_20261017')


def validate_relative(path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts or str(p) != path:
        raise ValueError(f'Unsafe manifest path: {path}')
    return p


def materialize(repo, source_dir, target, manifest):
    """Read exact Git objects, or a hash-verified exported snapshot, never latest."""
    if manifest['source_commit'] != COMMIT:
        raise ValueError('Source manifest commit does not match the builder')
    if source_dir is None:
        try:
            found = subprocess.check_output(
                ['git', '-C', str(repo), 'rev-parse', f'{COMMIT}^{{commit}}'],
                text=True, stderr=subprocess.DEVNULL).strip()
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f'Pinned commit {COMMIT} is missing. Fetch that commit, or supply --source-dir containing its verified files.') from exc
        if found != COMMIT:
            raise ValueError('Git resolved an unexpected source commit')
    verified = []
    for entry in manifest['files']:
        relative = validate_relative(entry['path'])
        if source_dir is None:
            data = subprocess.check_output(
                ['git', '-C', str(repo), 'show', f'{COMMIT}:{relative.as_posix()}'])
        else:
            source = (source_dir / relative).resolve()
            if not source.is_relative_to(source_dir.resolve()):
                raise ValueError(f'Source leaves the selected directory: {relative}')
            data = source.read_bytes()
        if ptr(data):
            raise ValueError(f'{relative} is a Git LFS pointer. Use git lfs fetch origin {COMMIT}, materialize that commit in a separate worktree with git lfs checkout, then use --source-dir for that directory.')
        if len(data) != entry['bytes'] or sha(data) != entry['sha256']:
            raise ValueError(f'Source hash or size mismatch: {relative}; refusing a mixed snapshot')
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        verified.append(relative.as_posix())
    return verified


def verify_output(out, expected):
    if expected['source_commit'] != COMMIT:
        raise ValueError('Expected-output commit mismatch')
    errors = []
    for entry in expected['files']:
        relative = validate_relative(entry['path'])
        p = out / relative
        if not p.is_file() or p.stat().st_size != entry['bytes'] or sha(p.read_bytes()) != entry['sha256']:
            errors.append(relative.as_posix())
    actual = {p.relative_to(out).as_posix() for p in out.rglob('*.json')}
    expected_paths = {e['path'] for e in expected['files']}
    if actual != expected_paths:
        errors.append('unexpected/missing data files: ' + ', '.join(sorted(actual ^ expected_paths)))
    if errors:
        raise ValueError('Output differs from the original snapshot: ' + '; '.join(errors))
    return len(expected_paths)


def main():
    default_repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=default_repo,
                        help='Repository with pinned Git commit (default: script repository)')
    parser.add_argument('--source-dir', type=Path,
                        help='Optional exported source root; all required bytes must match pinned hashes')
    parser.add_argument('--out', type=Path,
                        help='Empty output data directory (default: workbench/explorer-data)')
    parser.add_argument('--verify-only', action='store_true', help='Verify existing generated data without rebuilding')
    args = parser.parse_args()
    package = default_repo / PACKAGE_REL
    manifest = json.loads((package / 'source-manifest.json').read_text(encoding='utf-8'))
    expected = json.loads((package / 'expected-data.json').read_text(encoding='utf-8'))
    out = args.out or package / 'explorer-data'
    if args.verify_only:
        print(json.dumps({'status':'passed', 'verified_output_files':verify_output(out, expected)}))
        return
    if out.exists() and any(out.iterdir()):
        raise SystemExit('Output must be empty; choose --out for a fresh directory or use --verify-only.')
    # All inputs are validated before creating the output directory.
    with tempfile.TemporaryDirectory(prefix='research-explorer-sources-') as tmp:
        snapshot = Path(tmp)
        verified = materialize(args.repo, args.source_dir, snapshot, manifest)
        build(snapshot, out, manifest)
    count = verify_output(out, expected)
    print(json.dumps({'status':'passed','source_commit':COMMIT,
                      'verified_sources':len(verified),'byte_identical_output_files':count}))


if __name__ == '__main__':
    main()
