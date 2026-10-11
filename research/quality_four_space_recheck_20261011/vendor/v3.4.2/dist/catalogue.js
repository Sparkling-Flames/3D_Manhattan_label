(function(root){
'use strict';
const labels={missing_room_scope_review:'优先同房间范围复核',source_backed_scope_clues:'全部来源范围线索',user_scope_batch11:'本轮11图 · 范围复核',all:'全部图片',confirmed:'已确认范围',local_increment:'本地审核增量（含上下文）',scope_comment:'范围评论候选',numeric_candidate:'数值候选',detail_or_locator:'细节／定位线索',reference_paused:'参考／质量暂停证据',unclassified:'其他可查证据'};
function category(c){return c.primary_category||'unclassified'}
function matches(c,{query='',category:cat='all',status='all',paused='all',room_group=''}={},getStatus=()=> 'pending'){
 const q=query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
 const text=[c.image_code,c.image_id,c.search_text,c.preview_comment,...(c.tags||[])].join(' ').toLocaleLowerCase();
 return (!room_group||(c.room_scope_group_ids||[]).includes(room_group))&&q.every(t=>text.includes(t))&&(cat==='all'||cat==='confirmed'&&getStatus(c)==='confirmed'||cat!=='confirmed'&&(c.categories||[category(c)]).includes(cat))&&(status==='all'||status==='pending'&&!['confirmed','uncertain'].includes(getStatus(c))||status==='modified'&&getStatus(c)==='modified'||status==='confirmed'&&getStatus(c)==='confirmed'||status==='uncertain'&&getStatus(c)==='uncertain')&&(paused==='all'||paused==='paused'&&c.reference_paused||paused==='active'&&!c.reference_paused);
}
function filtered(images,filters,getStatus){return images.map((c,i)=>({c,i})).filter(x=>matches(x.c,filters,getStatus))}
function nextIndex(indices,current,direction=1){if(!indices.length)return -1;let at=indices.indexOf(current);return indices[(at<0?(direction>0?0:indices.length-1):(at+direction+indices.length)%indices.length)]}
const api={labels,category,matches,filtered,nextIndex};if(typeof module!=='undefined')module.exports=api;else root.Catalogue=api;
})(typeof window==='undefined'?globalThis:window);
