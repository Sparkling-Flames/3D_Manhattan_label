import pandas as pd,json
from pathlib import Path
r=Path(__file__).resolve().parents[1];d=pd.read_csv(r/'inputs/JOINT_COMPARISON_1145.csv')
# Literal class projections from live GitHub CSV line windows, not reclassification.
spec={
'2t7WUuJeko7': {'简单':'06 09 13','单列':'07'},
'7y3sRwLe3Va':{'简单':'04 11','困难':'03 21 26','单列':'06 10 18'},
'B6ByNegPMKs':{'简单':'10 11 18 21 33 40 48 50','困难':'37 47','单列':'42 43'},
'UwV83HsGsw3':{'简单':'10 17'},
'VFuaQ6m2Qom':{'困难':'04 07 10'},
'VLzqgDo317F':{'简单':'02'},
'X7HyMhZNoso':{'简单':'05 13 19','困难':'07'},
'Z6MFQCViBuw':{'简单':'02 03 06 08'},
'b8cTxDM8gDG':{'简单':'18','单列':'08'},
'e9zR4mvMWw7':{'简单':'02 10','待复核':'16'},
'jh4fc5c5qoQ':{'简单':'02','单列':'09 14'},
'jtcxE69GiFV':{'简单':'04 09 10 22 23 30','中等':'03 13'},
'pRbA3pwrgk9':{'简单':'04 05 06 07 10 14'},
'pa4otMbVnkk':{'简单':'06 09 14 42 44 48','中等':'11','困难':'05 18'},
'q9vSo1VnCiC':{'简单':'02 30','困难':'34'},
'rPc6DW4iMge':{'简单':'01 09 13 15 20','中等':'05 06 22'},
'uNb9QFRL6hY':{'简单':'01 04 07 09 12 20 29 36 40 43 45 48 53 65 67 68 72 78 79 81 82 87','中等':'14 18 26 41 50 54 59 60 66','困难':'86','单列':'21 25 83'},
'wc2JMjhGNzB':{'简单':'03 15 18 20 40 59 67','中等':'26 53 60'},
'x8F5xyUWy9e':{'中等':'03'},
'yqstnuAEVhm':{'简单':'02 05 10','中等':'27','困难':'08 09'},
'zsNo4HB9uLZ':{'简单':'02 11','中等':'09'}}
classes={f'{b}-{k}':c for b,cs in spec.items() for c,ids in cs.items() for k in ids.split()}
assert set(classes)==set(d.image_code), (set(classes)-set(d.image_code),set(d.image_code)-set(classes))
alt={
'b8cTxDM8gDG-18':'f146bb6adc1669e6','pa4otMbVnkk-14':'1de71ae2efad18af',
'rPc6DW4iMge-05':'49d943171d2a84a4','rPc6DW4iMge-06':'091bdc38b1e8bea5','rPc6DW4iMge-22':'99a6faf3159e8eb0',
'uNb9QFRL6hY-18':'04818e5e62ed343a','uNb9QFRL6hY-26':'7410a171a41fb8be','uNb9QFRL6hY-41':'9b22e9c05049a06e',
'uNb9QFRL6hY-50':'66dc16f5202c8891','uNb9QFRL6hY-59':'008030ca2079191d','uNb9QFRL6hY-60':'4c0a43bb9ca27143',
'uNb9QFRL6hY-66':'34fac57783cf9ee2','uNb9QFRL6hY-67':'1a054f70179e0a7c','uNb9QFRL6hY-68':'2bc89387944138cc',
'uNb9QFRL6hY-81':'201606a19d34a838','wc2JMjhGNzB-03':'4b0aec48f24fb240','wc2JMjhGNzB-26':'aa9ec2c148d8b71e'}
exports={'B6ByNegPMKs-10','X7HyMhZNoso-05','e9zR4mvMWw7-16','uNb9QFRL6hY-45','uNb9QFRL6hY-65'}
valid={'2t7WUuJeko7','VFuaQ6m2Qom','VLzqgDo317F','jh4fc5c5qoQ','jtcxE69GiFV','pRbA3pwrgk9','pa4otMbVnkk','zsNo4HB9uLZ'}
rows=[]
for code,c in classes.items():
 ids=d.loc[d.image_code.eq(code),'image_id'].unique();assert len(ids)==1
 im=ids[0]
 if code in alt: target=f'{code}:primary:floor:{alt[code]}'
 elif code in exports: target=f'gt:{im}:export_label/groudTruth.json'
 else:
  split='valid' if code.split('-')[0] in valid else 'test';target=f'gt:{im}:data/mp3d_layout/{split}/label_cor/{im}.txt'
 rows.append(dict(image_id=im,image_code=code,difficulty_version='scope_preferred_difficulty_20261011_v2',current_class=c,difficulty_reference_id=target,
    projection_source='quality_image_coverage.csv@e3dcf9d11daf9390d6acc09974101f7b6b88a3dd',reference_geometry_rechecked=False))
t=pd.DataFrame(rows);j=d.merge(t,on=['image_id','image_code'],validate='many_to_one');j['same']=j.reference_id.eq(j.difficulty_reference_id)
print('same',j.same.sum(),'different',(~j.same).sum());print(j[~j.same][['image_code','reference_id','difficulty_reference_id']].drop_duplicates().to_string(index=False))
assert j.same.sum()==1050 and (~j.same).sum()==95
p=r/'inputs/difficulty_target_projection_135.csv';t.sort_values('image_id').to_csv(p,index=False)
(r/'provenance/difficulty_projection.json').write_text(json.dumps(dict(source_path='research/difficulty_coarse_closeout_20261014/quality_image_coverage.csv',
 commit='e3dcf9d11daf9390d6acc09974101f7b6b88a3dd',blob='95c648117d8a12bb8217bdf7e569003eb4501113',source_rows=259,projected_rows=135,
 reconstruction='Literal class and target projections from connector-readable source windows; image-code uniqueness resolved to the fixed image IDs. Not an original byte copy. No score-dependent label choice.',
 source_windows=[[1,34],[35,66],[67,98],[99,130],[131,162],[163,194],[195,226],[227,260]],
 crosscheck='1050 same /95 different reference IDs exactly agrees with current cross-module handoff; same ID is not full geometry parity'),ensure_ascii=False,indent=2))
