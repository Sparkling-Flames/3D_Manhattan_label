"""Validate final assembly using the completed numerical and identity receipts.

Does not rerun experiments, change scores, or overwrite any scientific table.
"""
from pathlib import Path
import ast
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[2]
COMMIT='48a2fc6aedd51cd701b1bce06c02bd3ef92ec75b'
EXPECTED_MAIN_SHA='aaa59f2cbf5cd3356d9a4c760052ddffae4484a6693fcb91c6bb36793e78ccd3'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[]
    def handle_starttag(self,tag,attrs):
        for k,v in attrs:
            if k in ('href','src','poster') and v:self.links.append(v)


def local_links(p,text):
    if p.suffix=='.html':
        parser=Links();parser.feed(text);return parser.links
    return [m.group(1).strip('<>') for m in re.finditer(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)',text)]


def main():
    failures=[];checks=[]
    def check(name,ok,details=None):
        row=dict(check=name,status='passed' if ok else 'failed',details=details)
        checks.append(row)
        if not ok:failures.append(row)
    # A valid path exists during link validation; final contents are replaced below.
    if not (ROOT/'DELIVERY_CHECKS.json').exists():
        (ROOT/'DELIVERY_CHECKS.json').write_text('{"status":"assembly_in_progress"}\n',encoding='utf-8')
    receipts=[
      'audit/REGISTRY_VALIDATION.json','audit/SUPPLEMENT_DESIGN_INDEPENDENT_REVIEW.json',
      'audit/PAIR_DATASET_INDEPENDENT_REVIEW.json','audit/SCORE_AND_COMPONENT_INDEPENDENT_REVIEW.json',
      'audit/FORMAL_SUMMARY_INDEPENDENT_REVIEW.json','audit/WORKBENCH_DATA_REVIEW.json',
      'supplement/audit/FINAL_VALIDATION.json','analysis/DATASET_CHECKS.json',
      'analysis/STATISTICAL_CHECKS.json','analysis/Q_COMPONENT_INTERVAL_IDENTITY_CHECKS.json',
      'analysis/Q_FORMULA_ATTRIBUTION_CHECKS.json','analysis/FINAL_OUTPUT_CONSISTENCY_CHECKS.json',
      'analysis/DELIVERY_COMPLETION.json','mechanisms/MECHANISMS_FINAL_CHECKS.json',
      'background/BACKGROUND_REVIEW.json','background/BACKGROUND_VISUALIZATION_CHECKS.json']
    for p in receipts:
        check('receipt:'+p,(ROOT/p).exists() and load(p).get('status')=='passed')
    review=load('audit/ROOT_REPORT_REVIEW.json')
    check('independent_root_report_numeric_checks',review['summary']['failed_checks']==0,
          {'checks':review['summary']['numerical_and_identity_checks']})
    check('independent_report_review_bound_to_current_text',review['report_sha256']==sha(ROOT/'REPORT_ZH.md'))
    head=load('inputs/CLOSING_HEAD_CHECK.json')
    check('closing_latest_main_matches_frozen_source',head['matches_pinned'] and head['head_sha']==COMMIT,head)
    core=load('inputs/LOCAL_VERSION_VERIFICATION.json')
    check('nine_core_inputs_match_frozen_source',len(core['checks'])==9 and core['changed_sources']==0 and
          core['missing_sources']==0 and all(x['status']=='matches' for x in core['checks']))
    check('final_main_statistics_identity',sha(ROOT/'analysis/SIX_DIRECTION_Q_BY_BUDGET.csv')==EXPECTED_MAIN_SHA)
    ds=load('analysis/DATASET_CHECKS.json');sup=load('supplement/audit/FINAL_VALIDATION.json')
    check('physical_counts',ds['unique_physical_pairs']==33220 and ds['method_event_aliases']==35524 and
          ds['unique_physical_endpoints_with_labor_audit']==51562)
    check('automatic_vs_assisted_support',ds['automatic_common_pairs']==32086 and ds['assisted_common_pairs']==32127 and
          ds['new_common_pairs']==41 and ds['original_common_Q_max_change']==0 and ds['missing_approved_consumer_events']==0)
    check('frozen_supplement_execution',sup['teams']==1408 and sup['events']==704 and sup['AC_common_Q_pairs']==684 and
          sup['unscored_teams']==20 and sup['manual_orders_added']==0 and sup['coordinate_changes']==0 and sup['reference_changes']==0)
    check('offline_equation_rendering',not load('math_assets/MANIFEST.json')['failures'])
    syntax=[]
    for p in ROOT.rglob('*.py'):
        if '__pycache__' in p.parts:continue
        try:ast.parse(p.read_text(encoding='utf-8-sig'));syntax.append(str(p.relative_to(ROOT)))
        except Exception as exc:failures.append(dict(check='python_syntax',path=str(p),error=str(exc)))
    check('python_source_syntax',not any(x.get('check')=='python_syntax' for x in failures),{'files':len(syntax)})
    documents=[]
    for ext in ('*.md','*.html'):
        for p in ROOT.rglob(ext):
            if any(t in p.parts for t in ['source','inputs','raw_target_metrics','__pycache__']):continue
            documents.append((p,p.read_text(encoding='utf-8-sig')))
    integration=list(csv.DictReader((ROOT/'delivery/INTEGRATED_PROJECT_FILES.csv').open(encoding='utf-8-sig')))
    for row in integration:
        p=REPO/row['path'];text=p.read_text(encoding='utf-8-sig')
        check('integrated_file_identity:'+row['path'],sha(p)==row['after_sha256'])
        if row['change_kind']=='add_navigation_banner_only':
            pattern=r'<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_START -->.*?<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_END -->'
            sections=re.findall(pattern,text,flags=re.S)
            check('single_new_banner:'+row['path'],len(sections)==1)
            restored=re.sub(pattern,'',text,flags=re.S)
            check('old_page_bytes_unchanged_after_removing_banner:'+row['path'],
                  hashlib.sha256(restored.encode()).hexdigest()==row['before_sha256'])
            documents.append((p,'\n'.join(sections)))
        elif row['change_kind']=='new_thesis_adoption_note':documents.append((p,text))
        else:
            sections=re.findall(r'<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_START -->(.*?)<!-- CURRENT_DSTRUCT_AC_FINAL_20261104_END -->',text,flags=re.S)
            documents.append((p,'\n'.join(sections)))
    link_rows=[]
    for p,text in documents:
        for target in local_links(p,text):
            target=unescape(target)
            if target.startswith(('#','data:','blob:','mailto:','javascript:')) or '${' in target:continue
            parts=urlsplit(target)
            if parts.scheme or parts.netloc:continue
            if not parts.path:continue
            dest=(p.parent/unquote(parts.path)).resolve()
            ok=dest.exists()
            link_rows.append(dict(source=str(p.relative_to(REPO)),target=target,exists=ok))
            if not ok:failures.append(dict(check='local_reference',source=str(p.relative_to(REPO)),target=target))
    with (ROOT/'delivery/LOCAL_REFERENCE_CHECKS.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=['source','target','exists']);w.writeheader();w.writerows(link_rows)
    check('all_new_document_and_entry_local_references',all(r['exists'] for r in link_rows),
          {'documents':len(documents),'references':len(link_rows),'distinct_targets':len(set((r['source'],r['target']) for r in link_rows))})
    out=dict(status='passed' if not failures else 'failed',checked_at_utc=datetime.now(timezone.utc).isoformat(),
             input_commit=COMMIT,accepted_prior_batches='08-12',new_delivery_batches=[13,14,15],
             completed_scope='current_DSTRUCT_K3_direct_AC_only',checks=checks,failures=failures,
             scientific_run_counts={'legacy_TARGET_events_audited':52544,'legal_legacy_pairs_reused':28420,
               'batch12_existing_direct_pairs_reused':4096,'new_AC_pairs':704,'new_native_teams':1408,
               'new_native_scored_teams':1388,'new_native_no_connection_teams':20,'new_AC_common_Q_pairs':684,
               'total_unique_physical_pairs':33220,'total_unique_teams':51562,'total_method_event_aliases':35524,
               'native_existing_diagnostic_replays_successful':509,'unique_delivered_existing_traces':508,
               'excluded_pilot_diagnostic_endpoints':1,'outcome_blind_mechanism_sample_pairs':248,
               'illustrative_AC_cases':12,'existing_ABC_appendices':1,'fixed_XZ_background_boards':3,
               'background_previously_computed_endpoints_displayed':14,'original_images_in_atlas':12,
               'additional_background_original_images':3,'new_manual_orders':0},
             unchanged_inputs=['current_LOBO_labels','effective_preprocessed_original_annotations','references',
                               'voting_and_fusion_rules','official_Q_D10_formula','old_automatic_endpoint_scores'],
             reused_only_experiments=['alliances','fixed_composition','team_size_or_entering_curves','strict_ABC',
                                     'RFUSE','JOINT','Q_T_selection'],
             missingness='Missing Q/T never imputed to zero; native status and original/new/expanded common support separate.',
             weighting='Legacy distinct pairs within target/image; gap D within fixed XZ block then block then image; building cluster uncertainty.',
             UI_validation='Node V8 and minimal DOM executed controls and source-data comparisons; no graphical-browser pixel claim.',
             root_visual_review=['F01 six directions','A01 conditional magnitude','A02 score tradeoffs',
                                 'AC07 geometry','AC08 geometry','AC09 positioning',
                                 'fixed_XZ_same_D_composition','fixed_XZ_output_states'],
             limitations=['Conditional analysis of legacy stock, not fresh uniform current-class population sampling.',
                          'Reverse directions share the same physical pairs.',
                          'C13 core-budget capacity is sparse; feasible smaller budgets retained.',
                          'Some directions have no same-source recorded-labor support.',
                          'Mechanism/background associations do not identify a universal selection policy or convergence speed.'],
             delivery_state='Repository-relative overlays prepared; no GitHub push and no access to user Windows D drive.',
             packaging_verification='Each ZIP receives a member size/SHA256 manifest and CRC/readback check; outer ZIP receipts are written beside the packages.')
    (ROOT/'DELIVERY_CHECKS.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':out['status'],'checks':len(checks),'failures':failures,'documents':len(documents),'references':len(link_rows)},ensure_ascii=False))
    if failures:raise SystemExit(1)


if __name__=='__main__':main()
