"""Build an offline display from the independently reviewed imported v2.1 packages."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / 'research/workers/personnel_v21_reselection_20261029'
OUT = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'


def records(frame, fields):
    missing = set(fields) - set(frame.columns)
    if missing:
        raise ValueError(f'missing source fields: {sorted(missing)}')
    return frame[fields].astype(object).where(pd.notna(frame[fields]), None).to_dict('records')


def build():
    receipt = json.loads((SRC / 'IMPORT_RECEIPT.json').read_text(encoding='utf8'))
    assert receipt['unique_imported_files'] == 651
    read = lambda p: pd.read_csv(SRC / p, low_memory=False)
    cond = read('stage07_adoption/EFFECTIVE_EXCHANGE_CONDITIONS.csv')
    images = read('stage07_adoption/RECOMMENDED_CONDITIONS_ALL_IMAGES.csv')
    labels = read('classification/MAIN45_LABELS_ALL_LOBO.csv.gz')
    labels = labels[labels.method.isin(['OPPJOINT_K3','OPPJOINT_K4','TARGET_DSTRUCT_K3','RFUSE_GEOM_K2'])]
    roles = read('classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
    role_fields = ['method','heldout_building','class_id','semantic_training_role','m_all_B8L2','m_all_log_time','m_all_turn_n','own_fusion_Q']
    labels = labels.merge(roles[role_fields], on=['method','heldout_building','class_id'], how='left',
                          validate='many_to_one', indicator=True)
    assert labels.loc[labels.known.eq(True), '_merge'].eq('both').all()
    assert labels.loc[labels.known.eq(False), '_merge'].eq('left_only').all()
    labels = labels.drop(columns='_merge')
    events = read('experiment/focused_design/EVENTS_EXACT.csv.gz')
    roles = read('analysis/focused_summary/EVENT_ROLE_LINKS.csv.gz')
    assert len(cond) == 32 and len(images) == 312
    assert not events.event_id.duplicated().any() and not roles.event_id.duplicated().any()
    events = events.merge(roles[['event_id','role_direction']], on='event_id', validate='one_to_one')
    for _, r in events.iterrows():
        groups=[set(str(r[k]).split('|')) for k in ['D','X','Y','Z']]
        assert len(groups[0]) == r.n-r.m and all(len(g)==r.m for g in groups[1:])
        assert sum(map(len,groups)) == len(set().union(*groups))
        for arm, block in [('A',1),('B',2),('C',3)]:
            assert set(str(r[arm+'_members']).split('|')) == groups[0] | groups[block]
    cfields=['method','source_role_zh','target_role_zh','hierarchy','n','m','scope','images','buildings','events','ABC_scored_events','B8L2_within_mean_image','B8L2_cross_mean_image','B8L2_CB_mean_image','B8L2_CB_positive_images','B8L2_CB_valid_images','record_time_CB_pct_source_matched_mean_image','record_time_CB_pct_source_matched_valid_images','A_failed_events','B_failed_events','C_failed_events']
    ifields=['method','scope','n','m','role_direction','image','building','B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','record_time_CB_pct_source_matched','A_failed','B_failed','C_failed','ABC_scored','time_comparable_ABC','counterexample_type']
    lfields=['method','condition','heldout_building','worker_id','known','class_id','coarse_label','fine_label','missing_reason','label_formed_from','semantic_training_role','m_all_B8L2','m_all_log_time','m_all_turn_n','own_fusion_Q']
    efields=['event_id','method','image','building','n','m','role_direction','source_class','target_class','D','X','Y','Z','A_members','B_members','C_members','A_team_key','B_team_key','C_team_key']
    photos = {}
    for path in (OUT/'v2-resources/images').glob('*.js'):
        text = path.read_text(encoding='utf8')
        image = json.loads(text[text.index('= ')+2:-2])
        if image['image_code'] in set(images.image) and image.get('photo') and (OUT/image['photo']).is_file():
            photos[image['image_code']] = image['photo']
    data={'conditions':records(cond,cfields),'images':records(images,ifields),'labels':records(labels,lfields),'events':records(events,efields),'photos':photos}
    (OUT/'v21-reselection-data.js').write_text('window.V21_RESELECTION='+json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(',',':'))+';\n',encoding='utf8')
    result={'import_receipt':'IMPORT_RECEIPT.json','conditions':len(cond),'image_rows':len(images),'label_rows':len(labels),'events':len(events),'image_photo_count':len(photos),'event_role_join':'event_id one-to-one','team_members_checked':True,'missing_values':'null','browser_acceptance':'pending'}
    (OUT/'V21_RESELECTION_DISPLAY_CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    build()
