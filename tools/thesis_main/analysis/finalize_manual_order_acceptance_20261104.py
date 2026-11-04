"""Close the second acceptance: version, references, parent overlays, conclusions.

This file performs no fusion, scoring, selection, or statistical resampling.
All numerical acceptance is owned by the independent module audits.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import numpy as np
import pandas as pd
from lxml import html

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'research/fusion/manual_order_acceptance_20261104'
FROZEN = 'ac395e703d1fef573d1ef3e105df0286d62a0468'
STATES = {'保持','幅度变化','条件变化','需改写','尚不能判断'}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(name, data):
    (BASE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def csv_out(name, data):
    pd.DataFrame(data).to_csv(BASE/name,index=False,encoding='utf-8-sig')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data:=stream.read(1024*1024):
            h.update(data)
    return h.hexdigest()


def conclusions():
    rows=[]
    def evidence_paths(folder, value):
        return '; '.join(folder+'/'+p.strip() for p in str(value).split(';') if p.strip())
    q=pd.read_csv(BASE/'q_only/CONCLUSIONS.csv',keep_default_na=False)
    for r in q.to_dict('records'):
        rows.append(dict(module='Q-only',topic=r['item'],judgment=r['decision'],
                         finding=r['detail'],action=r['action'],source='q_only/REPORT_ZH.md; '+evidence_paths('q_only',r['evidence']),
                         estimand_id='',support_scope='frozen_208_events'))
    s=pd.read_csv(BASE/'secondary/CONCLUSIONS.csv',keep_default_na=False)
    for r in s.to_dict('records'):
        rows.append(dict(module=r['module'],topic=r['item'],judgment=r['judgment'],
                         finding=r['finding'],action='定向验收已完成，实际格式缺口按单独回执修正',
                         source='secondary/REPORT_ZH.md; '+evidence_paths('secondary',r['evidence']),estimand_id='',support_scope='exact_affected_consumers'))
    a=pd.read_csv(BASE/'ac/Q_REVERSALS_WITH_SUPPORT.csv',keep_default_na=False)
    opportunity=pd.read_csv(BASE/'ac/Q_OPPORTUNITY_CONDITIONS.csv',keep_default_na=False)
    assert len(opportunity)==len(a)==60 and opportunity.reversal_id.is_unique
    assert set(opportunity.reversal_id)==set(a.reversal_id)
    op_by_id=opportunity.set_index('reversal_id').to_dict('index')
    for r in a.to_dict('records'):
        o=op_by_id[r['reversal_id']]
        rows.append(dict(module='AC/'+r['family'],topic=r['source_keys']+' / '+r['statistic'],
                         judgment=r['interpretation_status'] if r['interpretation_status'] in STATES else '条件变化',
                         finding=f"原可评支持 {r['old_effect']}；辅助扩展支持 {r['expanded_effect']}；原支持 {r['old_support']}；扩展支持 {r['expanded_support']}",
                         action='采用明确支持及计权下的表述；原事件、新事件和完整登记机会分开',
                         source='ac/Q_REVERSALS_WITH_SUPPORT.csv; ac/Q_REVERSAL_EVENT_TEAM_TRACE.csv.gz; ac/Q_OPPORTUNITY_CONDITIONS.csv; ac/REPORT_ZH.md',
                         estimand_id=r['reversal_id'],support_scope='current_scoreable_support; overlapping_estimands_not_independent_experiments',
                         registered_events=o['registered_events'],original_evaluable_required_events=o['original_required_events'],
                         expanded_evaluable_required_events=o['expanded_required_events'],residual_required_events=o['residual_required_events'],
                         registered_atoms=o['registered_atoms'],registered_atom_kind=o['registered_atom_kind'],
                         required_Q_contract=o['required_Q_contract'],registered_event_count_contract=o['event_count_contract'],
                         all_registered_opportunities_covered=o['all_registered_opportunities_covered'],
                         complete_registered_claim=o['full_registered_numeric_or_fairness_judgment'],
                         legal_completion_lower=o['legal_completion_effect_lower'],legal_completion_upper=o['legal_completion_effect_upper'],
                         completion_direction_proof=o['completion_direction_proof']))
    rows += [
        dict(module='AC',topic='原共同事件与既有57顺序传播',judgment='保持',
             finding='原可评事件值保持；已确认顺序没有发现实际引用漏接。',action='不重跑已接入评分',
             source='ac/ORIGINAL_COMMON_EVENT_SUPPORT.csv; ac/CONSUMER_ACCEPTANCE.csv',estimand_id='',support_scope='original_supported_events'),
        dict(module='AC',topic='完整登记队列的同等人工处理声称',judgment='需改写',
             finding='完整登记队列并未获得同等人工处理；当前数值验收通过不能替代机会完整性。',
             action='限制完整覆盖与公平方法声称，不把当前可评均值称作完整登记均值。',
             source='ac/OPPORTUNITY_CHECKS.json; ac_peer/REPORT_ZH.md; ac_opportunity_secondary/REPORT_ZH.md',
             estimand_id='',support_scope='registration_vs_intervention_opportunity'),
        dict(module='AC',topic='完整登记队列的精确实际Q与方法差异',judgment='尚不能判断',
             finding='登记范围内81个缺Q端点继续缺失；未知真实Q不能用0或数学界限填入。RAW3单一条件的方向另有合法界限证明。',
             action='保留当前可评支持结果；不采用未观测的完整登记均值及全范围公平方法优势。',
             source='ac/OPPORTUNITY_CHECKS.json; ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json; ac_opportunity_secondary/REPORT_ZH.md',
             estimand_id='',support_scope='complete_registered_actual_scores_unobserved'),
        dict(module='AC',topic='RAW3其它目标n=m=4的负方向对3个剩余C端的界限',judgment='保持',
             finding='固定已有13事件的评分及原层级计权规则，3个未评分C保持不可评或取合法Q范围极值的27个组合均负；此为数学界限，非实测填值。',
             action='无需为判断此方向增加排序；完整精确均值与同等机会声称仍受限制。',
             source='ac_peer/RAW3_PURE_CLASS_MISSING_Q_BOUNDS_SCENARIOS.csv; ac_peer/REPORT_ZH.md',
             estimand_id='',support_scope='conditional_missing_score_bounds'),
        dict(module='AC',topic='主目标直接AC 50%条件',judgment='保持',
             finding='14/7、16/8、18/9、20/10、22/11未直接命中本批端点；严格ABC桥另行更新。',
             action='不扩新替换规模，不把直接AC与严格ABC混为一个消费者。',
             source='ac/CONSUMER_ACCEPTANCE.csv; ac/REPORT_ZH.md',estimand_id='',support_scope='direct_AC_primary'),
        dict(module='严格ABC',topic='当前合法14/7的跨类额外幅度和C−B',judgment='幅度变化',
             finding='三队共同支持136→146/147；GA、GS、C−B主要正方向保持，原共同事件保持。',
             action='采用各指标正确分母；C−B原支持138不能用GA/GS原支持136替代。',
             source='../manual_order_impact_20261104/half_qonly/HALF_SUPPORT.csv; ../manual_order_impact_20261104/half_qonly/HALF_SUMMARY.csv',
             estimand_id='',support_scope='current_legal_14_7'),
    ]
    for r in rows:
        assert r['judgment'] in STATES
        r['row_id']=hashlib.sha256((r['module']+'|'+r['topic']).encode()).hexdigest()[:16]
    assert len({r['row_id'] for r in rows})==len(rows)
    csv_out('CONCLUSION_MATRIX.csv',rows)
    source_checks=[]
    for r in rows:
        for ref in r['source'].split(';'):
            ref=ref.strip()
            path=(BASE/ref).resolve()
            source_checks.append(dict(row_id=r['row_id'],source=ref,exists=path.is_file()))
    csv_out('CONCLUSION_SOURCE_CHECKS.csv',source_checks)
    assert all(r['exists'] for r in source_checks),[r for r in source_checks if not r['exists']]
    return rows


def references():
    rows=[]
    def record(source, target):
        target=target.strip().split(' "',1)[0]
        parsed=urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            return
        local=(source.parent/unquote(parsed.path)).resolve()
        rows.append(dict(source=source.relative_to(ROOT).as_posix(),target=target,
                         resolved_path=local.relative_to(ROOT).as_posix() if local.is_relative_to(ROOT) else str(local),
                         exists=local.exists()))
    for path in sorted(BASE.rglob('*.md')):
        rel=path.relative_to(BASE)
        if any(part in {'source','source_cache','current','pre_acceptance','inputs'} for part in rel.parts):
            continue  # Immutable captured source documents keep their original links.
        text=path.read_text(encoding='utf-8-sig')
        for target in re.findall(r'\]\(([^)]+)\)',text):
            record(path,target)
    updates=read_json(BASE/'DOCUMENTATION_UPDATES.json')
    for item in updates:
        path=ROOT/item['path'];text=path.read_text(encoding='utf-8-sig')
        section=text.split('<!-- SECOND_ACCEPTANCE_20261104_BEGIN -->',1)[1].split('<!-- SECOND_ACCEPTANCE_20261104_END -->',1)[0]
        for target in re.findall(r'\]\(([^)]+)\)',section):
            record(path,target)
    page=ROOT/'research/statistics/research_explorer_v1_r2_20261017/v21-manual-order.html'
    document=html.fromstring(page.read_bytes())
    for target in document.xpath('//@href|//@src'):
        record(page,target)
    csv_out('REFERENCE_CHECKS.csv',rows)
    missing=[r for r in rows if not r['exists']]
    assert not missing,missing
    return rows


def parent_overlays():
    baseline=pd.read_csv(BASE/'PARENT_FIVE_BATCH_MANIFEST.csv',keep_default_na=False)
    repair=read_json(BASE/'secondary/repairs/MEMBER_FIELD_FORMAT_REPAIR.json')
    repaired={r['path']:r for r in repair['files']}
    docs={r['path'] for r in read_json(BASE/'DOCUMENTATION_UPDATES.json')}
    ui={'research/statistics/research_explorer_v1_r2_20261017/v21-manual-order.html',
        'research/statistics/research_explorer_v1_r2_20261017/v21-manual-order/fonts/HOHONETSans-Regular.otf',
        'research/statistics/research_explorer_v1_r2_20261017/v21-manual-order/fonts/PROVENANCE.json'}
    allowed=set(repaired)|docs|ui
    rows=[];unchanged=0
    for r in baseline.to_dict('records'):
        p=ROOT/r['path'];assert p.is_file(),r['path']
        h=sha(p)
        if h==r['sha256']:
            unchanged+=1;continue
        assert r['path'] in allowed,('undeclared_parent_change',r['path'])
        kind='member_field_format_or_writer' if r['path'] in repaired else 'documentation' if r['path'] in docs else 'workbench_static_section_or_font'
        if r['path'] in repaired:
            assert h==repaired[r['path']]['after_sha256']
            assert r['sha256']==repaired[r['path']]['before_sha256']
        rows.append(dict(path=r['path'],kind=kind,latest_parent_batch=r['latest_parent_batch'],
                         before_sha256=r['sha256'],after_sha256=h,bytes=p.stat().st_size))
    assert set(repaired)<=set(r['path'] for r in rows)
    csv_out('PARENT_OVERLAY_CHANGES.csv',rows)
    return len(baseline),unchanged,rows


def main():
    q=read_json(BASE/'q_only/CHECKS.json')
    source=read_json(BASE/'source_version/audit/SOURCE_AND_DESIGN_CHECKS.json')
    qp=read_json(BASE/'source_version/audit/PEER_REVIEW_QONLY_CHECKS.json')
    ac=read_json(BASE/'ac/CHECKS.json')
    supplement=read_json(BASE/'ac/SUPPLEMENTAL_CONSUMER_FIELD_CHECKS.json')
    ap=read_json(BASE/'ac_peer/PEER_CHECKS.json')
    bounds=read_json(BASE/'ac_peer/RAW3_RESIDUAL_AND_BOUNDS_CHECKS.json')
    reuse=read_json(BASE/'ac_peer_addendum/CHECKS.json')
    secondary=read_json(BASE/'secondary/CHECKS.json')
    opportunity=read_json(BASE/'ac/OPPORTUNITY_CHECKS.json')
    op_other=read_json(BASE/'ac_opportunity_secondary/CHECKS.json')
    closing=read_json(BASE/'CLOSING_SOURCE_VERSION_CHECK.json')
    assert source['status']=='PASS' and source['version_drift'] is False
    assert source['observed_commit']==FROZEN and source['missing_required_orders']==[]
    assert q['checks_failed']==0 and qp['verdict']=='PASS'
    assert ac['status']=='PASS' and ac['mismatches']==0
    assert supplement['status']=='PASS' and supplement['mismatches']==0 and supplement['new_scores']==0
    assert ap['status']=='PASS' and all(r['passed'] for r in ap['checks'])
    assert bounds['negative_direction_survives_all_legal_completions'] is True
    assert bounds['unavailable_old_Q_imputed'] is False and bounds['complete_opportunity_coverage'] is False
    assert reuse['status']=='PASS_NO_REUSABLE_ORDER_IN_SPECIFIC_SIX'
    assert reuse['reviewed_teams']==6 and reuse['confirmed57_coordinate_matches']==reuse['legacy33_coordinate_matches']==0
    assert secondary['status']=='PASS' and secondary['failed']==0
    assert closing['same_as_frozen'] and closing['observed_commit']==FROZEN
    # Opportunity incompleteness is a scientific scope finding. It is not
    # silently converted into complete coverage by a numerical PASS receipt.
    assert opportunity.get('audit_completed') is True,opportunity
    assert op_other.get('audit_completed') is True,op_other
    assert opportunity.get('confirmed57_propagation_complete') is True,opportunity
    assert opportunity.get('all_registered_opportunities_covered') is False,opportunity
    assert opportunity['registered_cohort_denominator_mismatches']==0 and opportunity['Q_reversal_rows']==60
    assert opportunity['distinct_failed_endpoints_in_confirmed57']==0 and opportunity['missing_Q_imputed'] is False
    matrix=conclusions()
    total,unchanged,overlays=parent_overlays()
    version=dict(version='v21_manual_order_acceptance_20261104_v1',
                 parent_method_version='v21_targeted_manual_order_assisted_20261104_v1',
                 source_commit=FROZEN,source_head_at_closing=closing['observed_commit'],
                 scientific_scores_or_statistics_changed_from_batch05=False,
                 serialization_repair_cells=8,serialization_repair_files=2,writer_repair_files=1,
                 new_teams=0,new_fusions=0,new_endpoint_scores=0,new_classification_runs=0,
                 additional_human_orders_applied=0,coordinate_candidate_adopted=False,
                 Q_only_complete_opportunity_scope='frozen 208 events / 670 teams / 1040 policy links',
                 AC_scope='targeted57 intervention; registered residual failures explicitly retained; complete opportunity not claimed',
                 python=sys.version.split()[0],numpy=np.__version__,pandas=pd.__version__)
    write_json('VERSION.json',version)
    # Create these targets before checking internal report references.
    write_json('FINAL_CHECKS.json',{'status':'in_progress'})
    csv_out('ARTIFACT_MANIFEST.csv',pd.DataFrame(columns=['path','bytes','sha256']))
    refs=references()
    workbench=read_json(BASE/'WORKBENCH_STATIC_CHECKS.json')
    assert workbench['status']=='PASS' and workbench['missing_chinese_codepoints']==[] and workbench['unique_DOM_ids'] is True
    workbench['local_reference_check_file']='REFERENCE_CHECKS.csv'
    workbench['local_references_passed']=True
    write_json('WORKBENCH_STATIC_CHECKS.json',workbench)
    final=dict(status='PASS_WITH_DECLARED_AC_OPPORTUNITY_LIMITS',
               all_requested_automated_acceptance_completed=True,
               numerical_acceptance=dict(q_only_checks=q['checks_passed'],q_only_peer_max_error=qp['largest_numeric_disagreement'],
                                         AC_checks=ac['numerical_checks'],AC_numeric_cells=ac['numeric_cells'],
                                         AC_consumer_groups=ac['consumer_groups'],AC_mismatches=ac['mismatches'],
                                         AC_supplemental_checks=supplement['checks'],AC_supplemental_numeric_cells=supplement['numeric_cells'],
                                         AC_supplemental_mismatches=0,AC_independent_peer_checks=len(ap['checks']),
                                         secondary_checks=secondary['passed'],secondary_failures=secondary['failed']),
               opportunity_scope=dict(Q_only_registered_scope_complete=True,AC_registered_scope_complete=False,
                                      confirmed57_propagation_complete=True,unscored_Q_filled_with_zero=False,
                                      AC_Q_statistical_rows=opportunity['Q_reversal_rows'],
                                      AC_rows_with_opportunity_gap=opportunity['condition_rows_with_opportunity_gap'],
                                      AC_rows_with_residual_required_Q=opportunity['condition_rows_with_residual_required_Q'],
                                      AC_distinct_residual_endpoints=opportunity['distinct_residual_endpoints'],
                                      AC_residual_categories=opportunity['distinct_residual_categories'],
                                      AC_registered_denominator_checks=opportunity['registered_cohort_denominator_checks'],
                                      AC_registered_denominator_mismatches=0,
                                      AC_secondary_opportunity_checks=op_other['passed'],
                                      direct_confirmed_opponent_no_connection_endpoints=opportunity['distinct_no_connection_endpoints_with_confirmed57_opponent']),
               parent_files_checked=total,parent_files_byte_identical=unchanged,
               declared_overlay_files=len(overlays),scientific_numeric_cells_changed_by_format_repair=0,
               conclusion_rows=len(matrix),conclusion_count_is_not_independent_experiments=True,
               local_references_checked=len(refs),broken_local_references=0,
               source_head_unchanged=True,original_five_ZIPs_modified=False,
               new_teams=0,new_fusions=0,new_endpoint_scores=0,new_classification_runs=0,
               additional_human_orders_applied=0,
               workbench_validation='Static DOM, font glyph coverage and all local references; previous interaction JS/data are byte-identical.')
    write_json('FINAL_CHECKS.json',final)
    exclusions=set()
    declaration=BASE/'ac/DELIVERY_EXCLUSIONS.json'
    if declaration.exists():
        exclusions={str((BASE/'ac'/x).resolve()) for x in read_json(declaration)['safe_to_exclude']}
    manifest=[]
    for path in sorted(BASE.rglob('*')):
        if not path.is_file() or path==BASE/'ARTIFACT_MANIFEST.csv' or '__pycache__' in path.parts or path.suffix in {'.log','.pyc'}:
            continue
        if str(path.resolve()) in exclusions:
            continue
        manifest.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    csv_out('ARTIFACT_MANIFEST.csv',manifest)
    print(json.dumps(final,ensure_ascii=False))


if __name__=='__main__':
    main()
