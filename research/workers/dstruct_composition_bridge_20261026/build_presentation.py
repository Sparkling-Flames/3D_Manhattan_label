from pathlib import Path
import json,html
import pandas as pd
from build_bridge import HERE,ROOT
s=pd.read_csv(HERE/'SUMMARY.csv');p=pd.read_csv(HERE/'PANEL_VARIANCE.csv');c=pd.read_csv(HERE/'CONFIGURATIONS.csv')
h=pd.read_csv(ROOT/'research/workers/personnel_mixture_audit_20261022/RECOMPUTED_DECOMPOSITION.csv')
h=h[(h.stratum=='all') & (((h.domain=='geometry_common') & h.method.isin(['new_coarse','new_fine'])) | ((h.domain=='qt_common') & h.method.isin(['joint_coarse','joint_fine']))) & h.outcome.isin(['B8L2','fusion_turn_n','log_source_time'])].copy()
h.to_csv(HERE/'HISTORICAL_SELECTED.csv',index=False)
def records(df): return json.loads(df.to_json(orient='records',force_ascii=False,double_precision=10))
# Arrays avoid repeating field names for each of the thousands of composition rows.
cf=['panel_id','method','metric','class_counts','teams','valid_teams','missing_teams','mean','p05','p25','median','p75','p95','member_variation_estimable']
data=dict(summary=records(s),panels=records(p),configuration_fields=cf,configurations=json.loads(c[cf].to_json(orient='values',force_ascii=False,double_precision=10)),historical=records(h))
(HERE/'presentation-data.js').write_text('window.CompositionVarianceData = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n')
names={'DSTRUCT_K2':'DSTRUCT K2','DSTRUCT_K3':'DSTRUCT K3','OLD_STRUCTURE_COARSE':'旧结构粗层','OLD_STRUCTURE_FINE':'旧结构细层'}
def overview_svg():
 rows=s[(s.scope=='all') & s.metric.eq('B8L2')]
 out=['<svg xmlns="http://www.w3.org/2000/svg" width="1040" height="450" viewBox="0 0 1040 450"><rect width="1040" height="450" fill="#fff"/><g font-family="Arial, Noto Sans CJK SC, sans-serif" fill="#172c35"><text x="40" y="45" font-size="25" font-weight="700">同一批团队：构成差异与成员波动并存</text><text x="40" y="78" font-size="16">Manual · 231 面板 / 40 图 / 22 楼 · Q（B8L2）</text>']
 for i,r in enumerate(rows.itertuples()):
  y=115+i*59;b=620*r.between_share
  out += [f'<text x="40" y="{y+23}" font-size="18">{names[r.method]}</text>',f'<rect x="260" y="{y}" width="620" height="35" fill="#dfe8eb"/><rect x="260" y="{y}" width="{b:.4f}" height="35" fill="#177e89"/>',f'<text x="895" y="{y+23}" font-size="17">{100*r.between_share:.2f}%</text>']
 out += ['<rect x="40" y="370" width="18" height="18" fill="#177e89"/><text x="68" y="385" font-size="16">构成间占比</text><rect x="250" y="370" width="18" height="18" fill="#dfe8eb"/><text x="278" y="385" font-size="16">同构成内成员占比</text><text x="40" y="422" font-size="14">先按图→楼等权聚合方差，再求占比；不是 Q 升幅、预测准确率或因果贡献。</text></g></svg>']
 return ''.join(out)
(HERE/'Q_VARIANCE_OVERVIEW.svg').write_text(overview_svg())
print('Presentation data:',(HERE/'presentation-data.js').stat().st_size)
