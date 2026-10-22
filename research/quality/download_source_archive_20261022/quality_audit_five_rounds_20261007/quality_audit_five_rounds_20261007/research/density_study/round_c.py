from core import *
import traceback
METRICS=['iou','omission_ref','extension_ref','centroid_distance_normalized','top_mae_deg','bottom_mae_deg','top3d_symmetric_mean_h','floor3d_symmetric_mean_h','conditional_volume_iou','height_mean_relative_error']

def select():
    images=json.load(open(EXPANDED/'current/panel.json'))['images']
    inventory={x['image_code']:x for x in json.load(open(EXPANDED/'current/image_inventory.json'))['images']}
    inputs=[]
    for x in images:
        rr=sorted([r for r in x['annotations'] if r.get('condition')=='manual' and r.get('independent') and r.get('consensus_eligible')],key=lambda r:r['id'])
        indices=sorted(set([len(rr)//3,2*len(rr)//3])) if rr else []
        selected=[(rr[i],'id_tertiles_no_gt_or_geometry_selection') for i in indices]
        if x['code']=='x8F5xyUWy9e-09':
            r=next(a for a in x['annotations'] if a['id']=='R02474')
            if r not in [a[0] for a in selected]:selected.append((r,'preexisting_nonorthogonal_diagnostic'))
        for r,selection in selected:
            inputs.append(dict(image=x['code'],building=x['building'],room=x.get('room'),source_panel='prior_49' if x['code'] in prior49 else 'expanded_beyond_prior_49',selection=selection,record=r,references=x['references'],scene=x.get('scene'),image_review=x.get('review'),inventory=inventory.get(x['code'])))
    return inputs
prior49=set(x['code'] for x in json.load(open(FULL/'inputs/panel.json'))['images'])

def main():
    inputs=select();save_json('round_c_inputs.json',inputs);fits=[];comparisons=[];objects=[]
    for ii,c in enumerate(inputs):
        r=c['record'];meta={k:c[k] for k in ['image','building','room','source_panel','selection']};meta.update(expression_id=r['id'],pair_count=len(r.get('points') or [])//2,scene_category=r.get('scene_category'),stable_nonorthogonal=c['inventory'].get('review',{}).get('stable_nonorthogonal') if c['inventory'] else None)
        rawmetrics={g['id']:comp.compare(r,g) for g in c['references']}
        rawintrinsic=comp.intrinsic(r);rawpre=prepare(r)
        ob=dict(**meta,fits={})
        for method,fn in [('equal_node',fit_node),('continuous_boundary',fit_boundary)]:
            start=time.time()
            try:fit=fn(r,starts=3 if method=='continuous_boundary' else 1)
            except Exception as ex:fit=dict(status='blocked',reason=type(ex).__name__+':'+str(ex),traceback=traceback.format_exc())
            row=dict(**meta,input_domain_status=rawpre['status'],input_domain_reason=rawpre.get('reason',''),method=method,status=fit['status'],reason=fit.get('reason'),iterations=fit.get('iterations'),objective=fit.get('objective'),elapsed_seconds=time.time()-start,raw_direction_rms_deg=rawintrinsic.get('direction_rms_deg'),raw_flat_top_rms_deg=rawintrinsic.get('flat_top_angular_rms_deg'),max_depth_sensitivity_h_per_Cpx=rawintrinsic.get('max_depth_sensitivity_h_per_Cpx'))
            if fit['status']=='ok':
                row['nodes_preserved']=len(fit['record']['points'])==len(r['points']);row['expression_preserved']=fit['record']['expression_id']==r['id']
                row.update({'movement_'+k:v for k,v in compare_shapes(fit['record'],r).items()})
                t,f=paired_wall_proxy(r);nt,nf=fit['top'],fit['floor']
                row['max_bottom_depth_move_h']=float(np.max(abs(np.linalg.norm(nf[:,[0,2]],axis=1)-np.linalg.norm(f[:,[0,2]],axis=1))))
                row['max_original_node_floor_move_h']=float(np.max(np.linalg.norm(nf-f,axis=1)))
                row['max_endpoint_angle_move_deg']=float(np.max(np.r_[up.angular_errors(nt,t/np.linalg.norm(t,axis=1)[:,None]),up.angular_errors(nf,f/np.linalg.norm(f,axis=1)[:,None])])*D)
                try:row['continuous_boundary_movement_rms_deg']=float(np.sqrt(boundary_loss(r,fit['record']))*D)
                except ValueError as ex:row['continuous_boundary_movement_reason']=str(ex)
                newintr=comp.intrinsic(fit['record']);row['fit_direction_rms_deg']=newintr.get('direction_rms_deg');row['fit_flat_top_rms_deg']=newintr.get('flat_top_angular_rms_deg')
                for g in c['references']:
                    before=rawmetrics[g['id']];after=comp.compare(fit['record'],g)
                    z=dict(**meta,method=method,reference_id=g['id'],reference_version=g.get('version'),before_reference_status=before.get('reference_status'),after_reference_status=after.get('reference_status'),before_longitude_status=before.get('longitude_status'),after_longitude_status=after.get('longitude_status'))
                    for key in METRICS:
                        if key in before:z['before_'+key]=before[key]
                        if key in after:z['after_'+key]=after[key]
                        if key in before and key in after:z['delta_'+key]=after[key]-before[key]
                    comparisons.append(z)
            fits.append(row);ob['fits'][method]=fit
        objects.append(ob)
        if ii%10==0 or ii==len(inputs)-1:
            save_csv('round_c_fit_status.csv',fits);save_csv('round_c_reference_comparisons.csv',comparisons);save_json('round_c_fit_artifacts.json',objects)
            print(ii+1,len(inputs),c['image'],r['id'],[(m,v['status'],v.get('reason')) for m,v in ob['fits'].items()],flush=True)
if __name__=='__main__':main()
