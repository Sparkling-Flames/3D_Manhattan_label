from pathlib import Path
import pandas as pd,json
R=Path(__file__).resolve().parents[1]
# Exact categorical/count excerpts from current groups.csv; no coordinate recreation.
# Columns image,condition,n,failed,gate,reference compatible,difficulty,source range.
rows=[]
def add(building,condition,spec,span):
 for item in spec.split():
  num,n,f,g,q,d=item.split(':')
  rows.append(dict(image=building+'-'+num,condition=condition,candidate_n=int(n),candidate_bev_failed_n=int(f),consensus_gate={'M':'main_candidate','E':'oos_doorway_exploratory','N':'stable_nonorthogonal_separate'}[g],reference_quality_compatible=q=='1',difficulty={'U':'未记录','D':'未定','E':'简单','M':'中等','H':'困难'}[d],source_lines=span))
add('7y3sRwLe3Va','manual','04:24:0:M:1:U','1-60')
add('7y3sRwLe3Va','oos','08:24:0:E:0:D 12:24:0:E:0:D','1-60')
add('B6ByNegPMKs','manual','11:23:0:M:1:D 33:23:0:M:1:E 40:22:0:M:1:U','1-60')
add('B6ByNegPMKs','semi','10:24:0:M:1:U 22:24:0:M:1:U','1-60')
add('S9hNv5qa7GM','manual','01:20:1:E:0:U 15:20:0:M:1:E','1-115')
add('UwV83HsGsw3','manual','09:24:0:M:1:U 10:23:0:M:1:U 17:23:0:M:1:U','61-115')
add('UwV83HsGsw3','oos','06:21:0:E:0:U 08:22:0:E:0:U 23:24:0:E:0:U','61-115')
add('X7HyMhZNoso','manual','13:24:0:M:1:U','61-115')
add('X7HyMhZNoso','semi','05:22:0:M:1:U','61-115')
add('Z6MFQCViBuw','semi','10:24:0:M:1:U','116-170')
add('b8cTxDM8gDG','manual','04:24:0:E:0:U','116-170')
add('b8cTxDM8gDG','semi','07:24:0:M:1:U','116-170')
add('b8cTxDM8gDG','oos','19:23:0:E:0:U','116-170')
add('e9zR4mvMWw7','manual','19:24:0:M:1:U','116-170')
add('e9zR4mvMWw7','semi','03:24:0:M:1:E 10:24:0:M:1:U 16:24:0:M:1:U 32:24:0:M:1:U 39:24:0:M:1:U','116-170')
add('pRbA3pwrgk9','manual','11:20:3:E:0:U','171-230')
add('q9vSo1VnCiC','manual','02:24:0:M:1:U 13:24:0:E:0:U 23:24:0:M:0:U 32:24:0:M:1:U','171-230')
add('q9vSo1VnCiC','semi','15:24:0:M:1:U','171-230')
add('q9vSo1VnCiC','oos','09:24:0:E:0:U','171-230')
add('rPc6DW4iMge','manual','01:23:0:M:1:U 06:24:0:M:1:U 09:21:0:M:1:U 15:22:0:M:1:E 20:22:0:M:1:U 22:24:1:M:1:U','171-285')
add('rPc6DW4iMge','semi','17:22:0:M:1:U','231-285')
add('uNb9QFRL6hY','manual','06:24:0:M:0:U 08:23:0:M:0:M 21:24:0:E:0:U 25:22:0:E:0:U 29:20:0:M:1:M 45:23:0:M:1:M 47:23:0:M:0:M 50:23:0:M:1:H 60:21:0:M:1:H 63:23:0:M:1:U 65:23:0:M:1:M 66:20:0:M:1:H 70:24:0:M:0:E','231-335')
add('uNb9QFRL6hY','semi','56:23:0:M:1:U','281-335')
add('uNb9QFRL6hY','oos','52:24:0:E:0:U','231-285')
add('wc2JMjhGNzB','manual','15:24:0:M:1:E 53:23:0:M:1:H 59:23:0:M:1:U 60:23:0:M:1:U','281-390')
add('wc2JMjhGNzB','semi','18:24:0:M:1:U 20:24:0:M:1:U 40:24:0:M:1:E 56:23:0:M:1:U','281-390')
add('x8F5xyUWy9e','manual','09:24:0:N:0:U','336-390')
add('yqstnuAEVhm','manual','04:22:0:M:1:U 25:23:0:M:1:U 26:24:0:M:0:E 31:21:0:M:1:U 32:24:0:M:1:U 34:24:0:M:1:U','336-390')
add('yqstnuAEVhm','oos','15:24:0:E:0:U','336-390')
f=pd.DataFrame(rows);f['building']=f.image.str.rsplit('-',n=1).str[0];f['curve_ready']=f.candidate_bev_failed_n==0
f=f.sort_values(['condition','image']);f.to_csv(R/'inputs/high_support_inventory_excerpt.csv',index=False)
s=f.groupby(['condition','curve_ready','consensus_gate','reference_quality_compatible']).agg(images=('image','size'),responses=('candidate_n','sum')).reset_index();s.to_csv(R/'results/high_support_scope_summary.csv',index=False)
print(s.to_string(index=False));print('\nTotal by condition:',f.groupby('condition').size().to_dict());print('\nManual ready reference-compatible',len(f.query("condition=='manual' and curve_ready and reference_quality_compatible")))
