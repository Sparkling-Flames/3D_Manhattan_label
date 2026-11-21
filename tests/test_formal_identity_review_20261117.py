"""Fresh simple review uses original sample and current groups, never old human labels."""
import csv,gzip,io,json,random,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/fusion/formal_identity_review_20261117'
def load():
    return json.loads((BASE/'COORDINATOR_MANIFEST.json').read_text(encoding='utf-8')),json.loads((BASE/'reviewer/data.js').read_text(encoding='utf-8').removeprefix('const REVIEW_DATA = ').strip().removesuffix(';'))
def test_original_sample_restored():
    m,d=load()
    assert m['validation_population']==206 and m['excluded_old_images']==0 and not m['legacy_answers_used']
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/gap75_evidence_20261117.zip') as z:
        def ids(name):return {r['pool_id'] for r in csv.DictReader(io.StringIO(z.read('gap75_audit/'+name).decode('utf-8-sig')))}
        assert {s['pool_id'] for s in m['scenes'] if s['cohort']=='random60'}==ids('formal_validation_srs60.csv')
        assert {s['pool_id'] for s in m['scenes'] if s['cohort']=='diagnostic12'}==ids('formal_validation_diagnostic12.csv')
    assert len(d['scenes'])==72
    assert len({s['code'] for s in d['scenes']})==72
    assert 'answers' not in d

def test_source_groups_and_all_observations():
    m,d=load()
    with zipfile.ZipFile('C:/Users/ASUS/Downloads/gap75_evidence_20261117.zip') as z:
        for s,meta in zip(d['scenes'],m['scenes']):
            raw=json.loads(gzip.decompress(z.read('gap75_audit/states/'+meta['pool_id']+'.json.gz')))
            assert s['observations']==raw['nodes']
            assert [g['members'] for g in s['groups']]==raw['states']['7.5']['groups']
            assert [i for i,g in enumerate(s['groups']) if g['selected']]==raw['states']['7.5']['selected_group_indices']
            assert (BASE/'reviewer'/s['image']).exists()
            assert set(s)=={'id','code','image','n','observations','groups'}
    assert sum(len(s['observations']) for s in d['scenes'])==11700
    assert sum(s['n'] for s in d['scenes'])==2331
