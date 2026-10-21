"""Assert completed request/result ledgers and package small final deliverables.

The already published endpoint/event data stay independent downloadable files.
This package contains explanations, small results, code and recovery references.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import zipfile
import pandas as pd
from multin_design import HERE, gs, sha


def run():
    endpoints = gs.read(HERE/'delivery/ENDPOINT_DELIVERY_MANIFEST.json')
    assert endpoints['status'] == 'complete'
    assert endpoints['missing_requested_endpoint_results'] == 0
    assert endpoints['global_unique_endpoint_keys'] == 360676
    assert endpoints['registered_stage_endpoint_references'] == 360681
    assert endpoints['all_gzip_EOF_and_exact_keys_verified']
    receipts = {}
    expected = {'PANEL': 65371, 'LARGE': 16244, 'PURE': 1899, 'PURE_CROSS': 2056}
    for stage, count in expected.items():
        r = gs.read(HERE/'matched'/f'{stage}_RESULT_RECEIPT.json')
        assert r['status'] == 'complete'
        assert r['registered_events'] == r['completed_events'] == count
        assert r['pending_events'] == 0
        d = gs.read(HERE/'direction'/f'{stage}_DIRECTED_COMPLETION.json')
        assert d['status'] == 'complete'
        assert d['events'] == count and d['missing_expression_endpoints'] == 0
        manifest_count = 0
        for condition in ['MANUAL', 'SEMI']:
            m = gs.read(HERE/'delivery/events'/f'{stage}_{condition}_EVENT_MANIFEST.json')
            assert m['status'] == 'complete' and m['all_events_present_once']
            assert m['no_subsampling']
            assert sum(x['rows'] for x in m['parts']) == m['rows']
            manifest_count += m['rows']
        assert manifest_count == count
        receipts[stage] = dict(events=count, pending=0, direct_event_manifest_rows=manifest_count,
                               expression_missing=0)
    paths = gs.read(HERE/'paths/PATH_COMPLETION.json')
    assert paths['status'] == 'complete' and paths['edges'] == 195888
    assert paths['pending_edges'] == paths['pending_paths'] == 0
    assert sum(gs.read(HERE/'delivery/events'/f'PATH_{condition}_EVENT_MANIFEST.json')['rows']
               for condition in ['MANUAL', 'SEMI']) == 195888
    receipts['PATH'] = dict(edges=195888, paths=114576, pending=0)
    assert gs.read(HERE/'TAIL_ANALYSIS_COMPLETE.json')['status'] == 'complete'

    # Read the small public views to EOF and compare frozen row counts and hashes.
    for manifest in ['final_summary/SUMMARY_FREEZE.json',
                     'matched/MATCHED_USEFULNESS_TABLES_COMPLETE.json']:
        for r in gs.read(HERE/manifest)['files']:
            path = HERE/r['path']
            assert sha(path) == r['sha256'], path
            if 'rows' in r:
                assert len(pd.read_csv(path, low_memory=False)) == r['rows'], path
    assert gs.read(HERE/'matched/MATCHED_USEFULNESS_TABLES_COMPLETE.json')['stages'] == ['LARGE','PANEL','PURE']
    for link in re.findall(r'\]\(([^)]+)\)', (HERE/'FINAL_FINDINGS_ZH.md').read_text()):
        assert (HERE/link).exists(), ('missing report target', link)

    full_summaries = {}
    for stage in ['PANEL','LARGE','PURE']:
        path = HERE/'matched'/f'{stage}_ALL_COMPONENT_SUMMARY.csv.gz'
        r = gs.read(path.with_suffix('.json'))
        assert sha(path) == r['sha256']
        full_summaries[stage] = dict(path=str(path.relative_to(HERE)), **r)
    export_check = gs.read(HERE/'final_summary/FULL_COMPONENT_EXPORT_CHECK.json')
    assert export_check['status'] == 'complete'
    assert all(row['gzip_EOF_and_full_row_count_verified'] for row in export_check['files'])
    assertion = dict(status='complete', global_unique_endpoint_sets=360676,
        endpoint_stage_references=360681, endpoint_missing_results=0,
        main_complete_member_panels=336, per_panel_enumeration=924,
        strict_ABC_events=83514, pure_AC_only_events=2056,
        total_registered_exchange_events=85570, complete_path_edges=195888,
        event_ledgers=receipts, all_direction_expression_endpoints_present=True,
        small_tables_EOF_row_count_and_sha_verified=True,
        complete_component_summaries=full_summaries,
        tail_component_gzip_EOF_full_rows_and_column_counts_verified=True,
        no_native_fusion_in_final_delivery=True,
        no_global_member_or_order_enumeration_claim=True,
        runtime_recovery='../integration/restore_v3_runtime_from_tables.py',
        report='FINAL_FINDINGS_ZH.md', report_sha256=sha(HERE/'FINAL_FINDINGS_ZH.md'))
    gs.save(HERE/'final_summary/FINAL_COMPLETION.json', assertion)

    small_paths = [HERE/'FINAL_FINDINGS_ZH.md', HERE/'README_ZH.md',
                   HERE/'TAIL_ANALYSIS_COMPLETE.json', HERE/'MAIN_ANALYSIS_COMPLETE.json']
    small_paths += list(HERE.glob('*.py'))
    small_paths += list((HERE/'final_summary').glob('*'))
    small_paths += list((HERE/'matched').glob('MATCHED_USEFULNESS_*.csv'))
    small_paths += [HERE/'matched/MATCHED_USEFULNESS_TABLES_COMPLETE.json',
                    HERE/'matched/STRICT_MATCHED_OVERVIEW.csv',
                    HERE/'matched/STRICT_MATCHED_OVERVIEW.json',
                    HERE/'matched/PURE_EXPLANATORY_CANDIDATES.csv.gz',
                    HERE/'delivery/ENDPOINT_DELIVERY_MANIFEST.json',
                    HERE/'delivery/FROZEN_EVALUATION_LABELS_MANIFEST.json',
                    HERE/'delivery/STAGE_BATCH_RESULT_COVERAGE.csv',
                    HERE/'configuration_union/COMPLETION.json',
                    HERE/'configuration_union/ALL_N_LEDGER_COMPLETE.json',
                    HERE/'configuration_union/CANONICAL_METHOD_COVERAGE.csv']
    small_paths += list((HERE/'delivery/events').glob('*_EVENT_MANIFEST.json'))
    small_paths += list((HERE/'direction').glob('*_DIRECTED_COMPLETION.json'))
    small_paths += list((HERE/'matched').glob('*_ALL_COMPONENT_SUMMARY.csv.json'))
    small_paths = sorted({x for x in small_paths if x.is_file()
                          and not x.name.endswith('.tmp') and 'CHECKPOINT' not in x.name})
    # Do not include a previous package inventory inside its own next inventory.
    small_paths = [x for x in small_paths if x.name not in ['PACKAGE_CONTENTS.json','FINAL_PACKAGE.json']]
    inventory = [dict(path='composition/'+str(x.relative_to(HERE)), bytes=x.stat().st_size,
                      sha256=sha(x)) for x in small_paths]
    package_contents = dict(status='complete', files=inventory,
        excluded='No full endpoints/events/raw-image collection/runtime/venv/duplicate repository inputs/summary parts.',
        interpretation='Extract composition/ beneath personnel_useful_taxonomy_v3_20261021 in the recovered research tree. Large directly downloadable files are referenced by delivery manifests.')
    gs.save(HERE/'final_summary/PACKAGE_CONTENTS.json', package_contents)
    small_paths.append(HERE/'final_summary/PACKAGE_CONTENTS.json')

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in small_paths:
            archive.writestr('composition/'+str(path.relative_to(HERE)), path.read_bytes())
    payload = buffer.getvalue()
    target = HERE/'delivery/COMPOSITION_FINAL_SUMMARY.zip'
    temp = target.with_suffix('.zip.tmp')
    with temp.open('wb') as handle:
        handle.write(payload); handle.flush(); os.fsync(handle.fileno())
    with zipfile.ZipFile(temp) as archive:
        assert archive.testzip() is None
        assert len(archive.infolist()) == len(small_paths)
        for entry in inventory:
            assert hashlib.sha256(archive.read(entry['path'])).hexdigest() == entry['sha256']
    temp.replace(target)
    final = dict(status='complete', path=str(target.relative_to(HERE)), bytes=target.stat().st_size,
                 sha256=sha(target), files=len(small_paths), zip_crc_and_entry_sha_verified=True,
                 report='FINAL_FINDINGS_ZH.md', report_sha256=sha(HERE/'FINAL_FINDINGS_ZH.md'),
                 assertions='final_summary/FINAL_COMPLETION.json',
                 separate_large_delivery='delivery/ENDPOINT_DELIVERY_MANIFEST.json and delivery/events/*_EVENT_MANIFEST.json')
    gs.save(HERE/'final_summary/FINAL_PACKAGE.json', final)
    print(json.dumps(final, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    run()
