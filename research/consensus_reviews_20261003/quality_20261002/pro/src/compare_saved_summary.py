"""Compare the numeric excerpt with separately read upstream summary fields.
Worker aliases are not joined or used for any inference in this audit.
"""
from pathlib import Path
import pandas as pd
B=Path(__file__).resolve().parents[1]
t=pd.read_csv(B/'inputs/read_upstream_csv_subset.csv')
u=pd.read_csv(B/'results/real_selected_metrics.csv').set_index('annotation')
rows=[]
for r in t.to_dict('records'):
    for field in list(t.columns)[2:]:
        a=u.loc[r['annotation'],field];b=r[field]
        if pd.notna(a) and pd.notna(b):
            rows.append(dict(annotation=r['annotation'],field=field,calculated=a,read_summary=b,
                absolute_difference=abs(a-b),strict_close=bool(abs(a-b)<=1e-10+1e-9*abs(b))))
pd.DataFrame(rows).to_csv(B/'results/source_summary_comparison.csv',index=False)
print('Compared',len(rows),'available numeric fields; all within tolerance:',all(r['strict_close'] for r in rows))
