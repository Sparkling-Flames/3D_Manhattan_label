"""已有人工原组、工作单元和直接关系的分类覆盖；不重评分。"""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

from .descriptive_statistics_figures_20261015 import export

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research/statistics/b8l2_usage_v6_20261016/details_room_adopted_v3'
LABELS={'支持':'支持同房','不支持':'不支持同房','待定':'物理待定',
    'user_classified_comparable':'同房·范围可比','user_classified_other_scope':'同房·其它范围',
    'not_supported':'不支持同房','physical_pending':'物理待定','content_disputed':'具体争议'}


def build(source=SOURCE):
    tables=json.loads((source/'tables.json').read_text(encoding='utf-8'))
    checks=json.loads((source/'CHECKS.json').read_text(encoding='utf-8'))
    out=source/'figures';out.mkdir(exist_ok=True)
    font=next(name for name in ['Microsoft YaHei','SimHei','Noto Sans CJK SC']
        if name in {f.name for f in font_manager.fontManager.ttflist})
    plt.rcParams.update({'font.family':font,'axes.unicode_minus':False,'svg.fonttype':'none',
        'axes.spines.top':False,'axes.spines.right':False})
    rows=[]
    panels=[('人工原组','room_raw_group_evidence','user_physical_classification'),
        ('拆分/合并工作单元','room_group_registry','relation_tier'),
        ('直接登记图对','room_direct_pair_registry','relation_tier')]
    fig,axes=plt.subplots(1,3,figsize=(17,5))
    colors={'支持':'#3a8c94','不支持':'#bd7270','待定':'#d1ab57',
        'user_classified_comparable':'#3a8c94','user_classified_other_scope':'#8296b2',
        'not_supported':'#bd7270','physical_pending':'#d1ab57','content_disputed':'#8c6e9f'}
    for ax,(unit,key,axis) in zip(axes,panels):
        frame=pd.DataFrame(tables[key]);counts=frame[axis].value_counts(sort=False)
        assert set(counts.index)<=set(LABELS)
        assert counts.sum()==len(frame)
        counts=counts.reindex([key for key in colors if key in counts])
        ax.bar(range(len(counts)),counts.values,color=[colors[key] for key in counts.index])
        for i,n in enumerate(counts.values):ax.text(i,n+2,str(n),ha='center')
        ax.set(title=f'{unit} n={len(frame)}',ylabel='该单位数量',
            xticks=range(len(counts)),xticklabels=[LABELS[x] for x in counts.index],ylim=(0,counts.max()*1.2))
        ax.tick_params(axis='x',labelrotation=22)
        rows.extend(dict(unit=unit,classification=k,n=int(v)) for k,v in counts.items())
    fig.suptitle('已有人工分类的分层覆盖（各面板单位不同，不能相加）')
    export(fig,out,'人工房间分类与采用覆盖',pd.DataFrame(rows),
        '260原组全部已查看；状态不作门。明确拆分/合并与原组分别保留，否定/范围差异/争议不抹去。直接边无跨组传递补全。')
    (out/'FIGURE_MANIFEST.json').write_text(json.dumps(dict(
        relation_adoption_version=checks['relation_adoption_version'],source='parent tables.json',
        formats=['png','svg','csv'],score_or_source_classification_changed=False,
        units=[p[0] for p in panels],panels_are_not_additive=True),ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':build()
