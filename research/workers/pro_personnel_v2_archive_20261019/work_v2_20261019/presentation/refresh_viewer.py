#!/usr/bin/env python3
"""Refresh template/case prose and lossless encoding without rerunning fusions."""
from pathlib import Path
import base64,gzip,json,re,hashlib,time
from build_viewer import HERE,pack_for_viewer,dumps
start=time.monotonic();p=HERE/'personnel_fusion_v2_viewer.html'
old=p.read_text();packed=re.search(r'<script id="packed" type="application/octet-stream">(.*?)</script>',old,re.S).group(1)
data=json.loads(gzip.decompress(base64.b64decode(packed)))
if data.get('row_encoding'):
    for pool in data['pools'].values():
        for group in ['requests','comparisons']:
            cols=data['row_encoding'][group];pool[group]=[dict(zip(cols,r))for r in pool[group]]
        for s in pool['states'].values():
            for n in s['nodes']:n['members']=[dict(zip(['worker','pair_index'],m))for m in n['members']]
data['cases']=json.loads((HERE/'viewer_cases.json').read_text())['cases']
for c in data['cases']:
    pool=data['pools'][c['pool_id']];byid={r['request_id']:r for r in pool['requests']}
    if c.get('request_a'):
        assert c['request_a']in byid and c['request_b']in byid
        assert any({r['request_a'],r['request_b']}=={c['request_a'],c['request_b']}for r in pool['comparisons']),c['case_id']
raw=dumps(pack_for_viewer(data)).encode();gz=gzip.compress(raw,compresslevel=6,mtime=0)
p.write_text((HERE/'viewer_template.html').read_text().replace('__DATA__',base64.b64encode(gz).decode()))
rp=HERE/'VIEWER_BUILD_RECEIPT.json';receipt=json.loads(rp.read_text());receipt.update({'cases':len(data['cases']),'raw_json_bytes':len(raw),'gzip_bytes':len(gz),'html_bytes':p.stat().st_size,'html_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'lossless_row_encoding':True,'refresh_seconds':time.monotonic()-start,'case_endpoint_and_comparison_check':True});rp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps({k:receipt[k]for k in ['cases','raw_json_bytes','gzip_bytes','html_bytes','lossless_row_encoding','refresh_seconds']},indent=2))
