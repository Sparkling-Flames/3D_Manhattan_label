from quality import *
from collections import Counter

def recover():
 data=read(ROOT/'source/historical_current_formal_loader_data.json');images={i['image_id']:i for i in data['images']};objects={o['object_id']:o for o in data['objects']};gate=read(ROOT/'results/recovered_admission_3152.json');rs=gate['reference_restrictions'] if 'reference_restrictions' in gate else gate['ref_restrictions'];ad={r['record_id']:r for r in gate['records']};prep={i['image_id']:i for i in read(ROOT/'source/routing_prepared.json')['candidate_images']};old=read(ROOT/'source/fusion_220_old.json')['rows'];out=[]
 for ix,r in enumerate(old):
  if r['unavailable_reason']!='missing_reference':continue
  im=images[r['image_id']];full=[ref for ref in im['references'].values() if not rs.get(ref) and objects[ref]['geometry']['status']=='surface_valid' and objects[ref]['links_zero_based']]
  admitted=[c for c in prep.get(r['image_id'],{}).get('candidates',[]) if c['admitted_for_routing']]
  ref=None
  if admitted:
   if len(admitted)==1 and admitted[0]['full_reference_available'] and admitted[0]['reference_object_id'] in full:action='unique_existing_full_reference_conditional';ref=admitted[0]['reference_object_id']
   elif not any(c['full_reference_available'] for c in admitted):action='only_confirmed_floor_available';ref=admitted[0]['reference_object_id'] if len(admitted)==1 else None
   else:action='existing_reference_not_bound_to_fused_target'
  elif len(full)==1:action='unique_existing_full_reference_conditional';ref=full[0]
  elif full:action='existing_reference_not_bound_to_fused_target'
  else:action='no_unrestricted_full_reference'
  out.append(dict(source_row_index=ix,image_id=r['image_id'],image_code=r['image_code'],version=r['version'],classification=action,reference_id=ref,member_ids=[m['record_id'] for m in r['members']],current_member_barriers=[m['record_id'] for m in r['members'] if ad[m['record_id']]['personnel_barriers'] or ad[m['record_id']]['context_barriers']],original_holdout_members=[m['record_id'] for m in r['members'] if ad[m['record_id']]['original_holdout']]))
 return out
if __name__=='__main__':
 x=recover();print(Counter(r['classification'] for r in x));print('\n'.join(f"{i}: {r['image_code']} {r['version']}" for i,r in enumerate(x) if r['classification']=='unique_existing_full_reference_conditional'))
 dump(ROOT/'results/FUSION_RECOVERED_BINDINGS.json',dict(records=x))
