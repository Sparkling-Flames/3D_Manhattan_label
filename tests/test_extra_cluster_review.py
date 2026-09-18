import csv
import json
import re
from pathlib import Path


def test_extra_review_identity_and_frozen_labels():
    root = Path(__file__).resolve().parents[1]
    out = root / 'analysis_results/cluster_review_extra_20260919'
    evidence = json.loads((out/'evidence.json').read_text(encoding='utf8'))
    data = json.loads((out/'atlas_snapshot.json').read_text(encoding='utf8'))
    assert [r['priority'] for r in evidence] == sorted(r['priority'] for r in evidence)
    assert evidence[0]['code'] == 'b8cTxDM8gDG-07'
    old = json.loads((root/'analysis_results/pro_cluster_review_20260918/data.json').read_text(encoding='utf8'))
    assert len(data['groups']) == 12 and len(evidence) == 24
    assert not {g['code'] for g in data['groups'].values()} & {c['code'] for c in old['cases']}
    source = root/'analysis_results/full_corpus_research_received_20260918/full_study_20260918/results/memberships.csv'
    with source.open(encoding='utf8',newline='') as f:
        labels={(r['method'],r['id']):int(r['cluster']) for r in csv.DictReader(f)}
    for g in data['groups'].values():
        for method, members in g['methods'].items():
            if method.startswith('A'):
                for cid,label in members.items(): assert labels[method,cid] == label
    for r in evidence:
        assert r['observation'] and r['user_decision'] is None
        people={p['id']:p for p in data['groups'][r['key']]['records']}
        for side in ['a','b']:
            assert people[r['pair']['id_'+side]]['worker'] == r['pair']['worker_'+side]
