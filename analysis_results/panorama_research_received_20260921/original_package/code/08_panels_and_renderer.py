"""Feasible additional *real* first responses, and execution of the actual JS projector."""
import common as c
import sys,collections,itertools,json,subprocess,hashlib
import pandas as pd,numpy as np

def main():
    args=c.main_parser().parse_args();c.configure(args.source_root)
    rows,_,views,reg,_=c.load();W=set(w for v in views.values() for w in v['workers'])
    # Missing eligible data does not establish absence of prior image exposure.
    # This concerns optional future FIRST responses only, not current independence review.
    exposure=collections.defaultdict(set)
    for row in rows:exposure[row['image_id']].add(row['worker_id'])
    for row in c.read('import_json/scene_stability_stage1_20260913_v2/historical_exposure.json'):
        exposure[row['image_id']].add(f"W{int(row['worker_id']):03d}")
    plan=[]
    for ca in reg['candidates']:
        if not ca['physical_same_supported'] or not ca['comparable_for_prediction']:continue
        for a,b in itertools.combinations([i for i in ca['image_ids'] if i in views and views[i]['N']>=8],2):
            va,vb=views[a],views[b];A=set(va['workers']);B=set(vb['workers']);cost={w:2-int(w in A)-int(w in B) for w in W if (w in A or w not in exposure[a]) and (w in B or w not in exposure[b])}
            p=dict(building=va['building'],candidate=ca['candidate_id'],a_code=va['code'],b_code=vb['code'],a_id=a,b_id=b,a_N=len(A),b_N=len(B),common_N=len(A&B),feasible_first_response_workers=len(cost),unavailable_preexposed_workers=';'.join(sorted(W-set(cost))))
            for H in [12,16,20]:p['additional_responses_for_common_'+str(H)]=sum(sorted(cost.values())[:H]) if len(cost)>=H else None
            plan.append(p)
    x=pd.DataFrame(plan).sort_values(['additional_responses_for_common_12','building','a_code','b_code']).drop_duplicates(['a_id','b_id'])
    c.save('optional_new_common_panel_costs.csv',x)
    # Given {x, y_ceiling, y_floor}, execute the exact projector body, not a retyped JS approximation.
    src=(c.SOURCE/'tools/label_studio/vis_3d.html').read_text()
    begin=src.index('function projectCornersForViewer(corners)');op=src.index('{',begin);depth=0
    for j in range(op,len(src)):
        depth+=int(src[j]=='{')-int(src[j]=='}')
        if depth==0:end=j+1;break
    function=src[begin:end]
    t=pd.read_csv(c.ROOT/'results/ray_derivative_probes.csv.gz')
    # The shared x input is explicitly top_x for this interface-contract test; caller choice is NOT inferred.
    inputs=[dict(x=float(r.top_x),y_ceiling=float(r.top_y),y_floor=float(r.bottom_y)) for r in t.itertuples()]
    p=c.ROOT/'results/js_projector_inputs.json';p.write_text(json.dumps(inputs))
    javascript="""const fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(process.argv[2],'utf8');
const begin=source.indexOf('function projectCornersForViewer(corners)');
let depth=0,end=0,op=source.indexOf('{',begin);
for(let i=op;i<source.length;i++){ if(source[i]==='{')depth++;if(source[i]==='}')depth--;if(depth===0){end=i+1;break;} }
const f=source.slice(begin,end);
class Vector3 { constructor(x,y,z){this.x=x;this.y=y;this.z=z;} }
const ctx={THREE:{Vector3},W:1024,H:512,Math};vm.createContext(ctx);
vm.runInContext(f,ctx,{timeout:1000});
const input=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));
process.stdout.write(JSON.stringify(ctx.projectCornersForViewer(input)));
"""
    script=c.ROOT/'code/verify_js_projector.js';script.write_text(javascript)
    res=subprocess.run(['node',str(script),str(c.SOURCE/'tools/label_studio/vis_3d.html'),str(p)],capture_output=True,text=True,check=True)
    out=json.loads(res.stdout);floor=np.array([[v['x'],v['y'],v['z']] for v in out['floorPoints']]);ceil=np.array([[v['x'],v['y'],v['z']] for v in out['ceilPoints']])
    u=t.top_x.to_numpy()/1024*2*np.pi-np.pi;vf=(t.bottom_y.to_numpy()/512-.5)*np.pi;vc=(t.top_y.to_numpy()/512-.5)*np.pi
    dist=1.6/np.tan(np.clip(vf,.01,1.5));xx=dist*np.sin(u);zz=-dist*np.cos(u)
    expected_f=np.c_[xx,np.full(len(xx),-1.6),zz];expected_c=np.c_[xx,-dist*np.tan(np.clip(vc,-1.5,-.01)),zz]
    error=max(abs(expected_f-floor).max(),abs(expected_c-ceil).max());assert error<1e-9
    c.save('js_projector_validation.json',dict(inputs=len(t),max_absolute_error=float(error),function_source_sha256=hashlib.sha256(function.encode()).hexdigest(),
        camera_height=out['cameraHeight'],qualification='Executed actual coordinate function in Node VM with Vector3 stub; not a WebGL screenshot, UI pairing test, or physical-truth check. Shared x explicitly provided, not inferred from caller.'))
    print(x.drop_duplicates('building').to_string(index=False));print('JS maximum error',error)

if __name__=='__main__':main()
