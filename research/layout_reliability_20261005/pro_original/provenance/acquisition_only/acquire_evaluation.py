"""Transcribe four supplied evaluation references; not imported by construction."""
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
# Record immutable construction products separately before local evaluation loads them.
files=list((root/'results/construction').glob('*.json'))+list((root/'results/compression').glob('*.json'))
receipt={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
(root/'results/evaluation_boundary_receipt.json').write_text(json.dumps({'role':'candidate product hashes; no GT-selected compression policy','files':receipt},indent=2))
data=[('2t7WUuJeko7-06','R02502',[[702.49,119.42,396.61],[842.93,121.58,394.47],[197.17,140.13,375.91],[307.08,138.78,377.26]]),('7y3sRwLe3Va-04','R02507',[[644.67,155.96,377.47],[895.72,157.96,375.35],[128.28,157.96,375.35],[379.33,155.96,377.47]]),('rPc6DW4iMge-06','R02670',[[620.03,148.7,374.38],[850.42,120.27,402.85],[897.25,90.25,431.52],[943.34,120.64,402.5],[84.44,121.68,401.48],[33.03,188.56,332.14],[150.54,212.98,305.06],[298.98,204.48,314.57],[340.93,165.0,357.43],[304.07,157.65,365.13],[359.24,100.89,421.51],[428.37,140.72,382.51]]),('uNb9QFRL6hY-67','R02724',[[645.99,110.58,411.46],[877.47,105.35,416.5],[33.32,72.87,446.94],[5.37,202.81,315.86],[117.43,215.39,301.89],[133.19,211.31,306.43],[159.17,219.14,297.7],[223.4,212.69,304.9],[211.27,198.06,321.08],[289.99,197.2,322.04]])]
images=[]
for image,rid,pts in data:
 n=len(pts)
 r=dict(id=rid,points=[[x,y] for x,t,b in pts for y in (t,b)],order_status='original_gt_reference',geometry_status='surface_valid',geometry_issues=['camera_visibility_unresolved'] if n>4 else [],source_point_indices=list(range(2*n)),source_point_labels=[f'GT p{i+1}' for i in range(2*n)],preprocessing_status='ready',ring_confirmed=False,version='original',source_pair_indices=list(range(n)),order_used='original_gt_reference')
 images.append(dict(image=image,references=[r]))
x=dict(policy='original primary; available manual revisions separately; not construction input',images=images)
b=(json.dumps(x,ensure_ascii=False,indent=2)).encode()
sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest();expected='aabb376e049c9611d07dfd884f1685e669c4e3be'
# The source may omit the final newline.
if sha!=expected:
 b+=b'\n';sha=hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
assert sha==expected,(sha,expected)
(root/'evaluation/references.json').write_bytes(b)
print('evaluation source match',len(b),sha)
