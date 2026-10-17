"""Bounded space-anchor geometry; legacy profiles, timing, and scope sampling."""
from __future__ import annotations
import numpy as np
from . import simulate_annotators as base
from . import difficulty_wild_run as legacy
from .space_inventory_anchor import VERSION, VALID, nearest, continuous_match


def coherence(space,scope):
    expected=space['scope_expected']
    return dict(expected_scope=expected,observed_scope=scope,consistent=scope==expected,policy='diagnostic_only_preserve_vote_sampling',evidence=space.get('scope_counts',{}))


def deletion_indices(points):
    """Wall merging is allowed only at an almost collinear floor vertex."""
    p=np.asarray(points,float).reshape(-1,2,2);bottom=base.rays(p[:,1])
    xy=-bottom[:,(0,2)]/bottom[:,1,None];indices=[]
    if len(p)<=3:return indices
    for i in range(len(p)):
        a=xy[i]-xy[i-1];b=xy[(i+1)%len(p)]-xy[i]
        cos=float(np.dot(a,b)/max(np.linalg.norm(a)*np.linalg.norm(b),1e-12))
        if cos>=np.cos(np.radians(8)):indices.append(i)
    return indices


def generate_geometry(entry,rng,wild=False,force_operation=None,space_quantile=None):
    spaces=[s for s in entry['spaces'] if s['human_n']]
    weights=np.asarray([s['human_frequency'] for s in spaces]);weights/=weights.sum()
    # Switching space is the initial weighted draw, so wild retains the measured
    # marginal space distribution rather than resampling towards rare spaces.
    draw=int(rng.choice(len(spaces),p=weights))
    if space_quantile is not None:draw=min(len(spaces)-1,int(np.searchsorted(np.cumsum(weights),space_quantile,side='right')))
    s=spaces[draw]
    anchors=np.asarray(s['anchors'],float);p=anchors.copy();n=len(p)//2
    counts=list(s['pair_count_histogram']);cw=np.array([s['pair_count_histogram'][c] for c in counts],float);cw/=cw.sum()
    requested=int(rng.choice([int(c) for c in counts],p=cw))
    # Strict complete-link correspondence makes each cluster count-homogeneous.
    if requested!=n:raise ValueError('space_count_anchor_mismatch')
    operations=[];ix=list(range(n));kind=s['space_kind'];sid=s['space_id']
    operation=force_operation or (str(rng.choice(['bounded_jitter','continuous_subset','merge_collinear','alternative_space'])) if wild else 'normal_jitter')
    if wild and operation=='continuous_subset' and n>3:
        keep=int(rng.integers(3,n));start=int(rng.integers(n));ix=[(start+j)%n for j in range(keep)]
        p=p.reshape(-1,2,2)[ix].reshape(-1,2);kind='subrange';sid+= ':continuous_'+'_'.join(map(str,ix));operations=['continuous_subset']
    elif wild and operation=='merge_collinear':
        candidates=deletion_indices(p)
        if candidates:
            removed=int(rng.choice(candidates));ix=[i for i in ix if i!=removed];p=p.reshape(-1,2,2)[ix].reshape(-1,2);operations=['merge_collinear']
    elif wild and operation=='alternative_space' and s['space_kind']=='alternative':operations=['alternative_space']
    if wild:operations.append('bounded_jitter')
    failures=[]
    for attempt in range(96):
        if attempt==48 and len(p)!=len(anchors):
            p=anchors.copy();ix=list(range(n));kind=s['space_kind'];sid=s['space_id'];operations=['bounded_jitter'] if wild else [];operation='bounded_jitter_fallback_invalid_subring'
        radii=np.interp(rng.random(len(p)),np.linspace(0,1,101),s['jitter_calibration']['quantiles'])
        cap=20. if wild else 15.
        radii=np.minimum(cap,radii*(1.6 if wild else 1.))*.5**(attempt//16)
        angle=rng.uniform(0,2*np.pi,len(p));delta=np.column_stack([np.cos(angle)*radii,np.sin(angle)*radii])
        # Independent endpoint draws are projected onto the engineering vertical
        # pair constraint; independent vertical errors and pair shifts remain.
        dx=delta[:,0].reshape(-1,2);shared=dx.mean(axis=1,keepdims=True);dx[:]=shared+np.clip(dx-shared,-.8,.8)
        length=np.linalg.norm(delta,axis=1);delta*=np.minimum(1,cap/np.maximum(length,1e-12))[:,None]
        q=p+delta;q[:,0]%=1024;q[:,1]=np.clip(q[:,1],.01,511.99)
        q[::2,1]=np.minimum(q[::2,1],255.95);q[1::2,1]=np.maximum(q[1::2,1],258.)
        distances=nearest(q,p if sid!=s['space_id'] else anchors)
        status=base.geometry_status(q)
        if status==VALID and distances.max()<=20 and not np.array_equal(q,anchors):break
        failures.append(status)
    else:raise ValueError('anchor_geometry_exhausted:'+','.join(sorted(set(failures))))
    return q,dict(space_id=sid,space_kind=kind,anchor_source=s['anchor_source'],anchor_annotation_id=s['anchor_annotation_id'],anchor_junction_count=len(ix) if sid!=s['space_id'] else n,source_anchor_junction_count=n,corner_anchor_dist_px=distances.tolist(),geometry_source='space_anchor',space_inventory_version=VERSION,space_parent_id=s['space_id'],sampled_space_id=s['space_id'],sampled_pair_count=requested,actual_pair_count=len(q)//2,anchor_operation=operation,anchor_operations=operations,anchor_pair_indices=ix,anchor_generation_attempts=attempt+1,anchor_generation_failures=failures,jitter_calibration=s['jitter_calibration']['method']),s


def sample_row(sources,target,fitted,entry,seed,slot,image_index,draw_nonce=0):
    # Keep the existing empirical personnel/time/scope implementation intact.
    row=legacy.sample_row(sources,target,fitted,seed,slot,image_index,0)
    rng=np.random.default_rng(base.seed_for(seed,target['image_id'],'space_anchor',slot,draw_nonce))
    need=target.get('need',1)
    allocation_rng=np.random.default_rng(base.seed_for(seed,target['image_id'],'space_frequency_stratification'))
    permutation=allocation_rng.permutation(need);offset=float(allocation_rng.random())
    quantile=(int(permutation[slot])+offset)/need
    p,metadata,space=generate_geometry(entry,rng,row['wild'],space_quantile=quantile)
    sw=f'S_MANUAL_{300000+image_index*35+slot:06d}'
    row.update(simulation_id=f"{target['image_id']}:{VERSION}:{seed}:{slot}",simulated_worker_id=sw,export_worker_id=sw,name=sw+(' / wild' if row['wild'] else ' / normal'),generator_version=VERSION,variant=VERSION,points=p.tolist(),final_points=p.tolist(),geometry_status=base.geometry_status(p),generation_status='space_anchor_generated',duplicate_geometry_retries=draw_nonce,wild_error_types=metadata['anchor_operations'] if row['wild'] else [],kept_pair_indices=metadata['anchor_pair_indices'],ring_confirmed=False,order_status='space_anchor_ordered_pairs',evaluation=dict(status='anchor_only_no_gt_score',B8L2=None,D10=None),residual_source='legacy_metadata_only_geometry_replaced',residual_scale=None,empirical_residual_amplitude=None,**metadata)
    row['space_scope_coherence']=coherence(space,row['worker_scope_response'])
    row['scope_space_coherence']=row['space_scope_coherence']
    row['generation_parameters'].update(mode='fill-to-35-anchor-space',generator_version=VERSION,space_seed=int(base.seed_for(seed,target['image_id'],'space_anchor',slot,draw_nonce)),policy='target_geometry_anchors_no_gt_score',personnel_time_scope='unchanged_legacy_sample_row',space_sampling='randomized_systematic_strata_per_image',space_quantile=quantile)
    return row
