import json
from pathlib import Path

from tools.thesis_main.analysis.build_v21_reselection_workbench_20261029 import OUT


def test_snapshot_preserves_direction_and_actual_teams():
    text = (OUT / 'v21-reselection-data.js').read_text(encoding='utf8')
    data = json.loads(text.removeprefix('window.V21_RESELECTION=').strip().removesuffix(';'))
    assert (len(data['conditions']), len(data['images']), len(data['events'])) == (32, 312, 10980)
    key = lambda r: (r['method'], r['n'], r['m'], r['role_direction'], r['image'])
    assert all(key(r) in {key(e) for e in data['events']} for r in data['images'])
    assert all((OUT / photo).is_file() for photo in data['photos'].values())
    assert all(r['image'] in data['photos'] for r in data['images'])
    for e in data['events']:
        d, x, y, z = (set(e[k].split('|')) for k in ('D', 'X', 'Y', 'Z'))
        for arm, block in [('A',x),('B',y),('C',z)]:
            assert set(e[arm+'_members'].split('|')) == d | block


def test_links_are_offline_and_sources_exist():
    from html.parser import HTMLParser
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.paths = []
        def handle_starttag(self, tag, attrs):
            self.paths.extend(v.split('#')[0] for k,v in attrs if k in ('src','href') and v and not v.startswith(('#','http:','https:')))
    parser = Links(); parser.feed((OUT/'v21-reselection.html').read_text(encoding='utf8'))
    assert all((OUT/path).exists() for path in parser.paths)
    assert 'v21-reselection.html' in (OUT/'v21-results.html').read_text(encoding='utf8')


def test_roster_roles_follow_method_fold_and_class():
    import pandas as pd
    from tools.thesis_main.analysis.build_v21_reselection_workbench_20261029 import SRC
    text = (OUT/'v21-reselection-data.js').read_text(encoding='utf8')
    labels = pd.DataFrame(json.loads(text.removeprefix('window.V21_RESELECTION=').strip().removesuffix(';'))['labels'])
    roles = pd.read_csv(SRC/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz', low_memory=False)
    keys = ['method','heldout_building','class_id']
    columns = ['semantic_training_role','m_all_B8L2','m_all_log_time','m_all_turn_n','own_fusion_Q']
    known = labels[labels.known.eq(True)]
    joined = known.merge(roles[keys+columns], on=keys, how='left', validate='many_to_one', suffixes=('_shown','_source'))
    for col in columns:
        assert ((joined[col+'_shown'] == joined[col+'_source']) | (joined[col+'_shown'].isna() & joined[col+'_source'].isna())).all()
    assert labels.loc[labels.known.eq(False), columns].isna().all().all()
