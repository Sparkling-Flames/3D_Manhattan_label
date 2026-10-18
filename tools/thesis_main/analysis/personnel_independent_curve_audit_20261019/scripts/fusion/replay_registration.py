import sys,json
from pathlib import Path
BASE=Path(__file__).resolve().parents[2];P=BASE/'extracted/work_v2_20261019/fusion';OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(P));import register_forward as m
from pool_io import read
m.OUT=OUT/'registration_replay';m.OUT.mkdir(exist_ok=True);m.main()
a=read(P/'REQUESTS_FORWARD.json.gz')['requests'];b=read(m.OUT/'REQUESTS_FORWARD.json.gz')['requests'];aa={x['request_id']:x for x in a};bb={x['request_id']:x for x in b}
r=dict(original=len(a),recomputed=len(b),request_ids_equal=aa.keys()==bb.keys(),exact_request_matches=sum(aa[k]==bb.get(k) for k in aa),notes='All forward profiles/compositions selected again from target-building-excluded frozen profile rows. Does not independently refit upstream profiles.')
(OUT/'REGISTRATION_REPLAY_CHECK.json').write_text(json.dumps(r,indent=2));print(r)
