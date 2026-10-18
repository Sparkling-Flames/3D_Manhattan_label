"""全部现有可评分作答的人员×难度画像；普通Manual主分析，条件分层。"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .worker_classification_progress_20261014 import fit_training_effects

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'research/workers/worker_difficulty_profiles_20261018'
SCORES = ROOT / 'research/quality/quality_b8l2_d10_20261017/quality_records.csv'
META = ROOT / 'research/difficulty/difficulty_current_20261017/image_metadata.csv'
TRAIN = ROOT / 'research/workers/worker_b8l2_d10_20261017/quality_panel.csv'
PAGE = ROOT / 'research/statistics/research_explorer_v1_r2_20261017'
METRICS = ['B8L2', 'D10']
LABELS = {'简单':'easy', '中等':'medium', '困难':'hard'}


def add_relative(d):
    d=d.copy()
    d['peer_n']=d.groupby('context_key').worker_id.transform('nunique')
    for metric in METRICS:
        group=d.groupby('context_key')[metric]
        d[metric+'_rank']=(group.rank(method='average')-1)/(d.peer_n-1).replace(0,np.nan)
        d[metric+'_peer_delta']=(d[metric]-group.transform('mean'))*d.peer_n/(d.peer_n-1).replace(0,np.nan)
    return d


def classify(hard, nonhard, supported):
    if not supported or not np.isfinite([hard,nonhard]).all(): return 'insufficient'
    if hard>=2/3 and hard-nonhard>=.10: return 'hard_advantage'
    if hard>=2/3 and nonhard>=2/3: return 'broadly_high'
    if nonhard>=2/3 and nonhard-hard>=.10: return 'nonhard_advantage'
    if hard-nonhard>=.10: return 'hard_relative_improvement'
    if nonhard-hard>=.10: return 'hard_relative_drop'
    return 'no_clear_preference'


def training_outside(d, building):
    return d[d.training_allowed & d.building_id.ne(building)].copy()


def load():
    q=pd.read_csv(SCORES)
    m=pd.read_csv(META)[['image_id','current_class','difficulty_analysis_eligible','doorway_status','oos_subtype']]
    q=q.rename(columns={c:c+'_score_snapshot' for c in m.columns if c!='image_id'})
    q=q.merge(m,on='image_id',how='left',validate='many_to_one')
    assert len(q)==1911 and q.quality_usable.all() and not q.is_oos.any()
    assert q.current_class.notna().all()
    q['difficulty']=q.current_class.map(LABELS).fillna('special_or_unrated')
    q['panel']=q.condition+'|'+q.quality_use
    q['context_key']=q[['image_id','condition','reference_id','reference_version']].apply(lambda r:json.dumps(r.tolist()),axis=1)
    assert not q.duplicated(['context_key','worker_id']).any()
    assert np.isfinite(q[METRICS]).all().all()
    old=pd.read_csv(TRAIN)
    assert set(old.object_id)<=set(q.object_id)
    q['training_allowed']=q.object_id.isin(old.object_id)
    main=q[q.condition.eq('manual') & q.quality_use.eq('ordinary_primary')]
    assert main.difficulty_analysis_eligible.all()
    assert main.difficulty.isin(LABELS.values()).all()
    return add_relative(q)


def cells(d):
    rows=[]
    for (panel,worker,difficulty),g in d.groupby(['panel','worker_id','difficulty']):
        r=dict(panel=panel,worker_id=worker,difficulty=difficulty,n=len(g),images=g.image_id.nunique(),
               buildings=g.building_id.nunique(),contexts=g.context_key.nunique(),
               comparable_n=int(g.peer_n.ge(2).sum()),training_n=int(g.training_allowed.sum()),
               source_time_n=int(g.source_active_time_seconds.notna().sum()),
               source_time_median=g.source_active_time_seconds.median(),
               target_time_n=int(g.target_matched_time_seconds.notna().sum()),
               target_time_median=g.target_matched_time_seconds.median())
        for metric in METRICS:
            r.update({metric+'_mean':g[metric].mean(),metric+'_median':g[metric].median(),
                      metric+'_p10':g[metric].quantile(.1),metric+'_rank':g[metric+'_rank'].mean(),
                      metric+'_building_equal_rank':g.groupby('building_id')[metric+'_rank'].mean().mean(),
                      metric+'_peer_delta':g[metric+'_peer_delta'].mean()})
        rows.append(r)
    return pd.DataFrame(rows)


def preferences(main):
    rows=[]
    for worker,g in main.groupby('worker_id'):
        hard=g[g.difficulty.eq('hard')];other=g[~g.difficulty.eq('hard')]
        comparable_hard=hard[hard.peer_n.ge(2)];comparable_other=other[other.peer_n.ge(2)]
        supported=all(len(p)>=6 and p.building_id.nunique()>=3 for p in [comparable_hard,comparable_other])
        r=dict(worker_id=worker,n=len(g),buildings=g.building_id.nunique(),hard_n=len(hard),hard_buildings=hard.building_id.nunique(),
               nonhard_n=len(other),nonhard_buildings=other.building_id.nunique(),supported=supported)
        for metric in METRICS:
            h=hard[metric+'_rank'].mean();o=other[metric+'_rank'].mean()
            r.update({metric+'_hard_mean':hard[metric].mean(),metric+'_nonhard_mean':other[metric].mean(),
                      metric+'_hard_rank':h,metric+'_nonhard_rank':o,metric+'_advantage':h-o,
                      metric+'_candidate':classify(h,o,supported)})
            shifts=[]
            for building in g.building_id.unique():
                a=hard[hard.building_id.ne(building)];b=other[other.building_id.ne(building)]
                if len(a)>=6 and a.building_id.nunique()>=3 and len(b)>=6 and b.building_id.nunique()>=3:
                    shifts.append(a[metric+'_rank'].mean()-b[metric+'_rank'].mean())
            r[metric+'_leave_building_min']=min(shifts) if shifts else np.nan
            r[metric+'_leave_building_max']=max(shifts) if shifts else np.nan
            r[metric+'_leave_building_n']=len(shifts)
        rows.append(r)
    return pd.DataFrame(rows)


def cross_validate(main):
    predictions=[];coverage=[]
    development=main[main.training_allowed]
    for metric in METRICS:
        for building in sorted(development.building_id.unique()):
            train=training_outside(main,building)
            assert building not in set(train.building_id)
            general=fit_training_effects(train.assign(value=train[metric]))
            general=general[general.supported][['worker_id','effect']].rename(columns={'effect':'general'})
            for difficulty,test in development[development.building_id.eq(building)].groupby('difficulty'):
                part=train[train.difficulty.eq(difficulty)]
                fit=fit_training_effects(part.assign(value=part[metric]))
                fit=fit[fit.supported][['worker_id','effect']].rename(columns={'effect':'specialized'})
                matched=test.merge(general,on='worker_id',validate='many_to_one').merge(fit,on='worker_id',validate='many_to_one')
                matched=matched[matched.groupby('context_key').worker_id.transform('size').ge(2)].copy()
                coverage.append(dict(metric=metric,building_id=building,difficulty=difficulty,total_n=len(test),compared_n=len(matched)))
                if matched.empty:continue
                for col in [metric,'general','specialized']:
                    matched[col+'_centered']=matched[col]-matched.groupby('context_key')[col].transform('mean')
                for row in matched.to_dict('records'):
                    target=row[metric+'_centered']
                    predictions.append(dict(metric=metric,object_id=row['object_id'],worker_id=row['worker_id'],
                        building_id=building,image_id=row['image_id'],difficulty=difficulty,context_key=row['context_key'],
                        target=target,general=row['general_centered'],specialized=row['specialized_centered'],
                        baseline_sqerr=target**2,general_sqerr=(target-row['general_centered'])**2,
                        specialized_sqerr=(target-row['specialized_centered'])**2))
    return pd.DataFrame(predictions),pd.DataFrame(coverage)


def evaluate(pred):
    out=[]
    for metric,d in pred.groupby('metric'):
        for difficulty in ['all','easy','medium','hard']:
            g=d if difficulty=='all' else d[d.difficulty.eq(difficulty)]
            if g.empty:continue
            # 每图先平均，再同建筑平均，再建筑等权，避免大人员池主导。
            bm=g.groupby(['building_id','image_id'])[['baseline_sqerr','general_sqerr','specialized_sqerr']].mean().groupby('building_id').mean()
            v=bm.mean()
            out.append(dict(metric=metric,difficulty=difficulty,n=len(g),images=g.image_id.nunique(),buildings=len(bm),
                **v.to_dict(),specialized_gain_over_general=1-v.specialized_sqerr/v.general_sqerr,
                buildings_improved=int((bm.specialized_sqerr<bm.general_sqerr).sum())))
    return pd.DataFrame(out)


def build():
    d=load();main=d[d.panel.eq('manual|ordinary_primary')]
    c=cells(d);p=preferences(main);pred,coverage=cross_validate(main);evaluation=evaluate(pred)
    OUT.mkdir(parents=True,exist_ok=True)
    fields=['object_id','worker_id','image_id','image_code','building_id','condition','quality_use','panel','reference_id',
            'reference_version','difficulty','context_key','training_allowed','peer_n','B8L2','D10','B8L2_rank','D10_rank',
            'B8L2_peer_delta','D10_peer_delta','source_active_time_seconds','target_matched_time_seconds','time_source','time_rule_version']
    for name,frame in [('records',d[fields]),('worker_difficulty_cells',c),('difficulty_preferences',p),('predictions',pred),
                       ('validation_coverage',coverage),('validation_summary',evaluation)]:
        frame.to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
    counts=d.groupby(['panel','difficulty']).agg(n=('object_id','size'),images=('image_id','nunique'),workers=('worker_id','nunique'),buildings=('building_id','nunique')).reset_index()
    payload=dict(schema='worker_difficulty_profiles_20261018_v1',sources=[str(x.relative_to(ROOT)) for x in [SCORES,META,TRAIN]],
        summary=dict(quality_rows=len(d),quality_images=d.image_id.nunique(),quality_workers=d.worker_id.nunique(),
            main_rows=len(main),main_images=main.image_id.nunique(),main_buildings=main.building_id.nunique(),
            main_workers=main.worker_id.nunique(),development_rows=int(main.training_allowed.sum())),
        coverage=json.loads(counts.to_json(orient='records')),cells=json.loads(c.to_json(orient='records')),
        preferences=json.loads(p.to_json(orient='records')),validation=json.loads(evaluation.to_json(orient='records')),
        records=json.loads(d[fields].to_json(orient='records')))
    text=json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)
    (OUT/'summary.json').write_text(text,encoding='utf-8')
    (PAGE/'personnel-difficulty-data.js').write_text('window.PERSONNEL_DIFFICULTY='+text+';\n',encoding='utf-8')
    print(json.dumps(payload['summary']))
    print(evaluation.to_string(index=False))
    print(p[['worker_id','B8L2_candidate','B8L2_hard_rank','B8L2_advantage']].to_string(index=False))


if __name__=='__main__':build()
