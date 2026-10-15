from pathlib import Path
import json,csv,collections,gzip,hashlib
P=Path(__file__).parent;D=json.load(open(P/'inventory.json'));C={c['comment_id']:c for c in D['comments']}
def codes(prefix,nums):return [prefix+'-'+x.zfill(2) for x in nums.split()]
TOPICS=collections.defaultdict(list)
def add(tag,pref,nums):
 for c in codes(pref,nums):TOPICS[c].append(tag)
for pref,ns in {'7y3sRwLe3Va':'18 21','B6ByNegPMKs':'43','S9hNv5qa7GM':'08','X7HyMhZNoso':'05','b8cTxDM8gDG':'08 18','e9zR4mvMWw7':'09 17','jh4fc5c5qoQ':'04 09','jtcxE69GiFV':'11 12 30','pRbA3pwrgk9':'01 02 11 14','pa4otMbVnkk':'10 11 14','q9vSo1VnCiC':'01 03 09 11 12 13 16 24 29 34','rPc6DW4iMge':'17','uNb9QFRL6hY':'14 25 29 32 44 47 50 51 54 63 65 67 68 69 81 83 86 88','wc2JMjhGNzB':'03 22 26 29 53 54 56 59 61','yqstnuAEVhm':'04 31 32 34','zsNo4HB9uLZ':'13'}.items():add('room_or_door_adjacent_region',pref,ns)
for pref,ns in {'7y3sRwLe3Va':'23','UwV83HsGsw3':'09 10 17','VFuaQ6m2Qom':'07','rPc6DW4iMge':'05 06 22','uNb9QFRL6hY':'18 26 41 50 51 59 60 66 67 88','wc2JMjhGNzB':'53 59','pRbA3pwrgk9':'02 14'}.items():add('glass_inside_outside_or_hidden_region',pref,ns)
for pref,ns in {'S9hNv5qa7GM':'04','uNb9QFRL6hY':'07 48 72 78 79 87','yqstnuAEVhm':'08'}.items():add('cabinet_as_wall_or_occluded_real_corner',pref,ns)
for pref,ns in {'7y3sRwLe3Va':'13','B6ByNegPMKs':'22 33 37 40 48','S9hNv5qa7GM':'09','UwV83HsGsw3':'06 10','b8cTxDM8gDG':'19','uNb9QFRL6hY':'04 36 40','yqstnuAEVhm':'34'}.items():add('stop_boundary_choice',pref,ns)
for pref,ns in {'UwV83HsGsw3':'01','X7HyMhZNoso':'07','b8cTxDM8gDG':'04','e9zR4mvMWw7':'19','uNb9QFRL6hY':'06'}.items():add('scope_unspecified_or_mixed_with_error',pref,ns)
for pref,ns in {'7y3sRwLe3Va':'03 11 26','X7HyMhZNoso':'19','jtcxE69GiFV':'05 17','uNb9QFRL6hY':'01 09 12 20 43 45 53','x8F5xyUWy9e':'03 08','yqstnuAEVhm':'01 09 25','zsNo4HB9uLZ':'02 05'}.items():add('detail_or_reference_geometry_not_established_target_difference',pref,ns)
for pref,ns in {'e9zR4mvMWw7':'16','q9vSo1VnCiC':'03','yqstnuAEVhm':'04 32'}.items():add('explicit_original_vs_revised_gt_history',pref,ns)
for pref,ns in {'7y3sRwLe3Va':'21','uNb9QFRL6hY':'47'}.items():add('hypothetical_alternative_or_no_observed_gt_difference',pref,ns)
PRIORITY={
'uNb9QFRL6hY-88':('strongest_memory_match','原评论明确说GT范围很大、纳入左右走廊，当前无人这样标；这是历史评语，不据此代替本次逐轮廓确认。'),
'wc2JMjhGNzB-22':('all_omit_specific_gt_region','W037历史评论称GT有门口区域，当前人员均未标。只支持这个局部，不等同GT整体大很多。'),
'wc2JMjhGNzB-29':('all_omit_specific_gt_region','图级历史评论称GT包含门口区域，所有标注者未标；仍需原图确认区域大小。'),
'wc2JMjhGNzB-61':('all_omit_specific_gt_region','图级历史评论称GT包含门口区域，标注者均未标；仍需当前GT版本对照。'),
'7y3sRwLe3Va-18':('large_whole_room_vs_subroom','GT整个空间与仅会客厅对比；门洞探索组，不能恢复主分析资格。'),
'UwV83HsGsw3-09':('larger_gt_but_similar_people_exist','GT包含大块不可见区域，但原文明确簇6最像GT，不能称无人同GT。'),
'uNb9QFRL6hY-67':('majority_small_but_gt_like_minority_exists','多数玻璃内小空间，GT和少数标外面房间；明确不是无人同GT。'),
'zsNo4HB9uLZ-13':('majority_small_but_gt_like_person_exists','W006与GT均标整个房间，其他只标中间；明确有人同GT。'),
'uNb9QFRL6hY-81':('most_omit_specific_gt_region','多数未标门口，措辞是大部分，不能升级为全体。'),
'uNb9QFRL6hY-51':('inner_space_reference_hold','外扩玻璃斜顶与内侧目标已有历史裁决，保留参考暂停。'),
'uNb9QFRL6hY-32':('reference_and_scope_hold','门框内、台阶下范围及GT问题，原hold_main_analysis保持。'),
'jtcxE69GiFV-11':('reference_hold_few_records','GT包含走廊，原评语只有2人不足，原hold_all_analysis保持。'),
'e9zR4mvMWw7-16':('historical_reference_already_revised','原评语明确原始MP3D范围不同、人工修订后已无问题，不能重新宣称当前GT错。'),
'yqstnuAEVhm-04':('compare_current_revised_gt_first','原GT向玻璃门外，用户修订GT停止玻璃处；先比较当前选定修订GT。'),
'uNb9QFRL6hY-47':('hypothetical_only_do_not_count','评论明确GT与所有人均标完整范围；仅提出理论上最小空间可能更合适，不能据此算实际GT不同。'),
'7y3sRwLe3Va-21':('hypothetical_currently_unseen','评论称记忆里可能有走廊-only，但当前结果未见，保留记忆线索。'),
'jtcxE69GiFV-05':('reference_geometry_not_scope','原评语直说不是空间问题而是GT几何错误；不能因关键词升级成目标范围差异。'),
}
by=collections.defaultdict(list)
for c in D['comments']:by[c['image_id']].append(c)
rows=[];site=[]
for r in D['images']:
 code=r['image_code']; cs=by[r['image_id']]; tags=TOPICS[code]
 r['semantic_topic_tags']=tags
 r['memory_identity_confirmed']=code=='uNb9QFRL6hY-88'
 r['memory_identity_confirmation_source']='Sentinel_0c62a95ab8708191801a77096c0d6e0f; 2026-10-10T09:24:02Z; user: 就是这个' if r['memory_identity_confirmed'] else ''
 r['memory_identity_confirmation_is_not_polygon_approval']=r['memory_identity_confirmed']
 r['text_group_is_not_new_human_verdict']=True
 r['history_match_kind'],r['text_evidence_summary']=PRIORITY.get(code,('other_review_candidate','文本检索/既有几何提示；需区分真实目标范围、局部细节和定位误差。' if r['broad_review_queue'] else '本次检索未命中；不代表已证实与GT范围相同。'))
 r['current_scope_semantics_verified']=False
 r['numeric_candidate']=r['has_any_geometry_candidate']
 r['detail_or_locator']=bool(r['detail_or_locator'] or 'detail_or_reference_geometry_not_established_target_difference' in tags)
 # Named physical boundary scope is stronger than the broad keyword matcher; retain both independently.
 r['text_evidence_class']='confirmed_floor_region_only' if r['user_confirmed_floor_region'] else 'hypothetical_or_unseen' if 'hypothetical_alternative_or_no_observed_gt_difference' in tags else 'explicit_room_or_boundary_statement' if any(t in tags for t in ['room_or_door_adjacent_region','glass_inside_outside_or_hidden_region','cabinet_as_wall_or_occluded_real_corner','stop_boundary_choice']) else 'scope_wording_unspecified_or_mixed' if r['scope_comment'] else 'detail_locator_or_context_only' if r['keyword_comments'] else 'geometry_only' if r['numeric_candidate'] else 'no_hit'
 r['suggested_review_order']=0 if code=='uNb9QFRL6hY-88' else 1 if code in ['wc2JMjhGNzB-22','wc2JMjhGNzB-29','wc2JMjhGNzB-61'] else 2 if r['text_evidence_class']=='explicit_room_or_boundary_statement' else 3 if r['scope_comment'] else 4 if r['keyword_comments'] else 5 if r['numeric_candidate'] else 6
 if r['user_confirmed_floor_region']:r['suggested_review_order']=7
 # Every source paragraph retained; never count comment duplicates or excluded records as semantic votes.
 selected=sorted(cs,key=lambda c:(not(c['object_kind']=='image'),not c['memory_match_candidate'],not c['target_difference_candidate'],not c['boundary_candidate'],not c['keyword_hit'],c['comment_id']))
 site.append({**r,'comments':selected,'geometry_groups':[g for g in D['condition_gate_groups'] if g['image_id']==r['image_id']]})
 rows.append(r)
def writecsv(n,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with open(P/n,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()} for r in rs)
writecsv('all_259_images.csv',rows);writecsv('broad_review_queue.csv',sorted([r for r in rows if r['broad_review_queue']],key=lambda x:(x['suggested_review_order'],x['image_code'])));writecsv('memory_match_priority.csv',[r for r in rows if r['image_code'] in PRIORITY]);writecsv('no_hit_images.csv',[r for r in rows if not r['broad_review_queue']]);writecsv('selected_vs_original_reference_pending.csv',[r for r in rows if r['historical_reference_version_pending']]);writecsv('paused_reference_images.csv',[r for r in rows if r['reference_paused']])
(P/'inventory.json').write_text(json.dumps(D,ensure_ascii=False,indent=2));(P/'scope_by_image.json').write_text(json.dumps(site,ensure_ascii=False,separators=(',',':')))
for f in ['inventory.json','scope_by_image.json']:
 with gzip.open(P/(f+'.gz'),'wb',compresslevel=9) as z:z.write((P/f).read_bytes())
S=json.load(open(P/'summary.json'));S['selected_vs_original_reference_difference_images']=sum(r['historical_reference_version_pending'] for r in rows);S['paused_reference_images']=[r['image_code'] for r in rows if r['reference_paused']];S['text_evidence_classes']=dict(collections.Counter(r['text_evidence_class'] for r in rows));(P/'summary.json').write_text(json.dumps(S,ensure_ascii=False,indent=2));print(json.dumps(S,ensure_ascii=False,indent=2))
