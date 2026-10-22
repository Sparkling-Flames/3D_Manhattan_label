from core import *
import traceback

def controls():
    xs=[('analytic_exact_rectangle',[[-3,-2],[3,-2],[3,2],[-3,2]],[1.5]*4),('analytic_skew_variable_top',[[-3,-2.2],[3.2,-1.6],[2.7,2.4],[-2.4,1.8]],[1.3,1.8,1.5,1.1]),('analytic_concave_L',[[-3,-2],[3,-2],[3,1],[1,1],[1,3],[-3,3]],[1.2,1.4,1.8,1.5,1.1,1.3])]
    out=[]
    for name,p,h in xs:
        p=np.array(p);f=np.c_[p[:,0],-np.ones(len(p)),p[:,1]];t=np.c_[p[:,0],h,p[:,1]]
        out.append(dict(image=name,building='analytic',kind='control',record=record(t,f,{'id':name},'analytic_control')))
    return out

def select():
    p=json.load(open(FULL/'inputs/panel.json'))['images'];by={x['code']:x for x in p}
    images=['2t7WUuJeko7-09','7y3sRwLe3Va-03','B6ByNegPMKs-40','X7HyMhZNoso-19','Z6MFQCViBuw-03','jtcxE69GiFV-03','uNb9QFRL6hY-18','x8F5xyUWy9e-09','e9zR4mvMWw7-02','UwV83HsGsw3-09','rPc6DW4iMge-06','yqstnuAEVhm-07']
    out=[]
    fixed={'B6ByNegPMKs-40':'R02166','X7HyMhZNoso-19':'R01646','x8F5xyUWy9e-09':'R02474','uNb9QFRL6hY-18':'R02846'}
    for code in images:
        x=by[code];candidates=sorted([r for r in x['annotations'] if r.get('independent') and r.get('consensus_eligible') and r.get('condition')=='manual'],key=lambda r:r['id'])
        if code in fixed:candidates.sort(key=lambda r:r['id']!=fixed[code])
        for r in candidates:
            if prepare(r)['status']=='ok':
                out.append(dict(image=code,building=x['building'],kind='real',record=r));break
    return out+controls()

def main():
    cases=select();save_json('round_a_inputs.json',cases);rows=[];artifacts=[]
    variants=[('uniform',2),('uniform',4),('long',2),('long',4),('long',12),('short',12),('long_cluster',12)]
    for ci,c in enumerate(cases):
        r=c['record'];base=fit_node(r,starts=3);frame=prepare(r)['frame']
        artifact=dict(**c,base_fit=base,variants=[])
        for mode,k in variants:
            v,old=subdivision(r,mode,k);p=prepare(v)
            z=dict(image=c['image'],building=c['building'],kind=c['kind'],expression_id=r['id'],mode=mode,k=k,base_pairs=len(r['points'])//2,subdivided_pairs=len(v['points'])//2,base_status=base['status'],raw_axis_delta_deg=abs((p.get('frame',frame)-frame+np.pi/4)%(np.pi/2)-np.pi/4)*D)
            z.update({'input_'+a:b for a,b in compare_shapes(v,r).items()})
            source_axes=prepare(r)['direction'];mapped=np.array([source_axes[x['original_pair']] for x in v['lineage']]);z['same_axis_assignments']=bool(np.array_equal(prepare(v,frame)['direction'],mapped))
            z['free_axis_labels_identical']=bool(np.array_equal(p.get('direction'),mapped))
            fit=fit_node(v,frame=frame,starts=3 if k==12 else 1);z.update(status=fit['status'],reason=fit.get('reason'),iterations=fit.get('iterations'),base_node_objective=base.get('objective'),fit_node_objective=fit.get('objective'))
            if base['status']=='ok':
                bt,bf=paired_wall_proxy(base['record'])
                vt=np.array([(1*x['t'])*bt[x['next_pair']]+(1-x['t'])*bt[x['original_pair']] for x in v['lineage']])
                vf=np.array([(1*x['t'])*bf[x['next_pair']]+(1-x['t'])*bf[x['original_pair']] for x in v['lineage']])
                vbase=record(vt,vf,base['record'],'same_material_subdivision',v['lineage'])
                z['base_fit_resampled_node_objective']=node_loss(v,vbase)
                z['base_boundary_objective']=boundary_loss(r,base['record'])
                z['base_fit_resampled_boundary_objective']=boundary_loss(v,vbase)
            if fit['status']=='ok' and base['status']=='ok':
                z.update({'output_'+a:b for a,b in compare_shapes(fit['record'],base['record']).items()})
                z['original_vertex_move_max_h']=float(np.max(np.linalg.norm(fit['floor'][old]-base['floor'],axis=1)))
                z['node_objective_improvement_vs_resampled_base']=z['base_fit_resampled_node_objective']-fit['objective']
                objectives=[s['objective'] for s in fit['starts'] if s['status']=='ok'];z['multistart_objective_spread']=max(objectives)-min(objectives)
            rows.append(z);artifact['variants'].append(dict(mode=mode,k=k,record=v,original_node_positions=old,fit=fit))
        artifacts.append(artifact);save_csv('round_a_density.csv',rows);save_json('round_a_artifacts.json',artifacts)
        print(ci+1,len(cases),c['image'],base['status'],flush=True)
if __name__=='__main__':main()
