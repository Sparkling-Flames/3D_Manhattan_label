import json
import pandas as pd
import pytest

from tools.thesis_main.analysis import build_v21_population_display_20261029 as module


def test_method_fragment_preserves_missing_and_separates_support(tmp_path, monkeypatch):
    source = tmp_path/'source'; out = tmp_path/'output'
    (source/'composition').mkdir(parents=True); (source/'exchange').mkdir()
    pd.DataFrame([dict(dataset='primary_manual45',method='OPPJOINT_K4',condition='manual',support='method_known',metric='B8L2',time_source='none')]).to_csv(source/'composition/ALL_METHOD_SUMMARY.csv',index=False)
    pd.DataFrame([dict(dataset='primary_manual45',method='OPPJOINT_K4',counts='research/example.csv')]).to_csv(source/'composition/SOURCE_INDEX.csv',index=False)
    pd.DataFrame([dict(method='OPPJOINT_K4',dimension='Q',status='available',valid_events=1,valid_images=1,valid_buildings=1,missing_events=0,source_table='source.csv',fields='Q',note='')]).to_csv(source/'exchange/METHOD_DIMENSION_COVERAGE.csv',index=False)
    pd.DataFrame([dict(method='OPPJOINT_K4',condition='manual',scope='primary',role_direction='q:1->4',stage='focused_ABC',registered_images=1,net_CB_valid_images=1,delta_net_CB_valid_images=None,source_table='source.csv')]).to_csv(source/'exchange/CHAIN_SUMMARY.csv',index=False)
    dim = dict(method='OPPJOINT_K4', condition='manual', scope='primary', role_direction='q:1->4', n=12, m=6,
               B8L2_CB_mean_image=-2, B8L2_CB_valid_images=1, source_table='research/example.csv')
    for name in ['ALL_DIMENSION_N_M_RESULTS.csv', 'FORMAL_DIFFICULTY_RESULTS.csv', 'STRUCTURAL_CONDITION_RESULTS.csv']:
        pd.DataFrame([dim]).to_csv(source/'exchange'/name, index=False)
    row={key: None for key in module.DIST_FIELDS};row.update(dataset='primary_manual45',method='OPPJOINT_K4',panel_id='p',pool_id='pool',image='i',building='b',condition='manual',n=12,scope='primary',support='method_known',class_counts='6|6',metric='B8L2',time_source='none',teams=1,valid_teams=1,missing_teams=0,mean=90,member_variation_estimable=False)
    pd.DataFrame([row,dict(row,support='shared_known',mean=80)]).to_csv(source/'composition/KEY_DISTRIBUTIONS.csv.gz',index=False,compression='gzip')
    monkeypatch.setattr(module,'SOURCE',source);monkeypatch.setattr(module,'OUT',out);module.build()
    text=(out/'primary_manual45__OPPJOINT_K4.js').read_text(encoding='utf8');payload=json.loads(text.split('concat(',1)[1].split(');',1)[0])
    assert [x['support'] for x in payload]==['method_known','shared_known']
    assert payload[0]['sd'] is None and payload[0]['mean']==90
    dim_text = (out/'dimension__OPPJOINT_K4.js').read_text(encoding='utf8')
    dim_data = json.loads(dim_text.split(']=', 1)[1].strip().removesuffix(';'))
    assert dim_data['difficulty'][0]['B8L2_CB_mean_image'] == -2


def test_fragment_identifier_cannot_escape_directory():
    with pytest.raises(ValueError):module.safe_part('../escape')
