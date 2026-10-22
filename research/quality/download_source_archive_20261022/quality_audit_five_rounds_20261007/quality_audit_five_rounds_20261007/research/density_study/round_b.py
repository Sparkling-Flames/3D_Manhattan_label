from core import *
from round_a import select

def main():
    cases=select();rows=[];objects=[];quad=[]
    variants=[('uniform',2),('uniform',4),('long',2),('long',4),('long',12),('short',12),('long_cluster',12)]
    for ci,c in enumerate(cases):
        r=c['record'];frame=prepare(r)['frame'];base=fit_boundary(r,frame,starts=3);node=fit_node(r,frame,starts=3)
        ob=dict(**c,boundary_fit=base,node_fit=node,variants=[])
        for mode,k in variants:
            v,old=subdivision(r,mode,k);fit=fit_boundary(v,frame,starts=3)
            z=dict(image=c['image'],building=c['building'],kind=c['kind'],expression_id=r['id'],mode=mode,k=k,base_pairs=len(r['points'])//2,subdivided_pairs=len(v['points'])//2,base_status=base['status'],status=fit['status'],reason=fit.get('reason'),iterations=fit.get('iterations'))
            if fit['status']=='ok' and base['status']=='ok':
                z.update({'output_'+a:b for a,b in compare_shapes(fit['record'],base['record']).items()})
                z['original_vertex_move_max_h']=float(np.max(np.linalg.norm(fit['floor'][old]-base['floor'],axis=1)))
                z['objective_abs_delta']=abs(fit['objective']-base['objective']);z['source_expression_unchanged']=fit['record']['expression_id']==r['id']
                z['all_nodes_retained']=len(fit['record']['points'])==len(v['points'])
                objectives=[s['objective'] for s in fit['starts'] if s['status']=='ok'];z['multistart_objective_spread']=max(objectives)-min(objectives)
            rows.append(z);ob['variants'].append(dict(mode=mode,k=k,fit=fit))
        if base['status']=='ok':
            z=dict(image=c['image'],expression_id=r['id'],kind=c['kind'],objective_4096=base['objective'],objective_evaluated_32768=boundary_loss(r,base['record'],32768))
            finer=fit_boundary(r,frame,nquad=16384,starts=3);z['fine_status']=finer['status']
            if finer['status']=='ok':
                z['fine_objective_evaluated_32768']=boundary_loss(r,finer['record'],32768)
                z.update({'fine_vs_coarse_'+a:b for a,b in compare_shapes(finer['record'],base['record']).items()})
            if node['status']=='ok':
                z['node_boundary_objective_evaluated_32768']=boundary_loss(r,node['record'],32768)
                z['boundary_node_objective']=node_loss(r,base['record']);z['node_node_objective']=node['objective']
                z.update({'boundary_vs_node_'+a:b for a,b in compare_shapes(base['record'],node['record']).items()})
            quad.append(z)
        objects.append(ob);save_csv('round_b_density.csv',rows);save_csv('round_b_quadrature_and_objectives.csv',quad);save_json('round_b_artifacts.json',objects)
        print(ci+1,len(cases),c['image'],base['status'],flush=True)
if __name__=='__main__':main()
