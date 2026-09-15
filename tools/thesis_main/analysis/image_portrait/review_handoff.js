/* Optional human-review panel for the existing Studio. No annotation writeback. */
(() => {
 const d=window.DIFFICULTY_REVIEW;if(!d)return;
 const key='image-difficulty-review-20260915-v1',schema='image_difficulty_user_review_v1';
 const rows=new Map(d.rows.map(r=>[r.image_id,r])),units=new Map(d.rows.flatMap(r=>r.units.map(u=>[r.image_id+'|'+u.condition,u])));
 const E=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const base=()=>({status:'未审核',grade:'',reason:'',cluster_semantics:'',singleton_assessment:''});
 const names={simple:'简单',simple_candidate:'简单候选',medium:'中等',medium_candidate:'中等结构候选',difficult_candidate:'困难候选'};
 let edits={},notes={},blocked=false,message='';
 function validate(v){
  if(!v||!['未审核','暂缓','已审核'].includes(v.status)||!['','简单','中等','困难候选','三档不适用'].includes(v.grade)||(v.status==='已审核')!==!!v.grade)throw Error('审核状态与类别不匹配');
  for(const k of ['reason','cluster_semantics','singleton_assessment'])if(typeof v[k]!=='string')throw Error('缺少审核文本');
 }
 function validateImport(v){
  if(v.schema!==schema||v.source_v2!==d.source_v2||!Array.isArray(v.reviews)||!Array.isArray(v.image_notes))throw Error('审核版本不匹配');
  const a={},b={};for(const r of v.reviews){const k=r.image_id+'|'+r.condition;if(!units.has(k)||Object.hasOwn(a,k))throw Error('图片条件重复或未知');validate(r.review);a[k]=r.review;}
  for(const r of v.image_notes){if(!rows.has(r.image_id)||Object.hasOwn(b,r.image_id)||typeof r.note!=='string')throw Error('图片笔记无效');b[r.image_id]=r.note;}
  if(Object.keys(a).length!==units.size||Object.keys(b).length!==rows.size)throw Error('导出记录不完整');return {edits:a,notes:b};
 }
 function exportData(){return {schema,source_v1:d.source_v1,source_v2:d.source_v2,saved_at:new Date().toISOString(),reviews:[...units.keys()].map(k=>{const [image_id,condition]=k.split('|');return {image_id,condition,review:edits[k]||base()};}),image_notes:d.rows.map(r=>({image_id:r.image_id,note:notes[r.image_id]||''}))};}
 try{const v=localStorage.getItem(key);if(v)({edits,notes}=validateImport(JSON.parse(v)));}catch(e){blocked=true;message='旧缓存异常，暂停覆盖；请导入备份。'+e.message;}
 const panel=document.createElement('section');panel.className='history-panel';panel.innerHTML=`<h2>图片难度审核</h2><p>两版算法候选、原106张tag、你的审核分别保存。先看原图，再展开真人证据。拟合更规整不代表更正确；未审核不等于认可候选。</p><div class="history-controls"><label>图片搜索 <input id="rv-search" placeholder="楼名 / 图号 / 场景"></label><select id="rv-image" aria-label="审核图片"></select><button id="rv-prev">上一张</button><button id="rv-next">下一张</button><button id="rv-export">导出审核JSON</button><label>导入 <input id="rv-import" type="file" accept=".json"></label></div><p id="rv-status" role="status"></p><p id="rv-save" role="status"></p><details open><summary>原图（不叠加标注）</summary><a id="rv-original-link" target="_blank"><img id="rv-original" style="width:100%;height:auto" alt="当前图片原图"></a></details><label>仅根据可见图像的观察<textarea id="rv-note" rows="2" style="width:100%" placeholder="具体边界、遮挡位置、开口与反射；未知不猜测"></textarea></label><details><summary>展开候选分类及你的审核</summary><select id="rv-mode" aria-label="审核条件"></select><div id="rv-evidence"></div><label>你的裁决 <select id="rv-decision"><option>未审核</option><option>暂缓</option><option>简单</option><option>中等</option><option>困难候选</option><option>三档不适用</option></select></label><label>理由<textarea id="rv-reason" rows="2" style="width:100%"></textarea></label><div class="history-controls"><label>簇的实际含义 <input id="rv-cluster"></label><label>单人标法判断 <input id="rv-singleton"></label></div></details>`;
 document.querySelector('main').prepend(panel);const $r=id=>document.getElementById('rv-'+id);
 const opt=(v,t)=>{const x=document.createElement('option');x.value=v;x.textContent=t;return x;};
 function progress(){$r('status').textContent=`276图／230个图×条件；已审核 ${Object.values(edits).filter(v=>v.status==='已审核').length}，暂缓 ${Object.values(edits).filter(v=>v.status==='暂缓').length}。`;}
 function save(){progress();if(blocked)return;try{localStorage.setItem(key,JSON.stringify(exportData()));$r('save').textContent='已在浏览器保存，请定期导出JSON。';}catch(e){$r('save').textContent='自动保存失败，请立即导出：'+e.message;}}
 function mode(){const r=rows.get(dataset.cases[currentCase].image_id),c=$r('mode').value,u=r.units.find(x=>x.condition===c),v=edits[r.image_id+'|'+c]||base();
  for(const k of ['decision','reason','cluster','singleton'])$r(k).disabled=!u;
  $r('decision').value=v.status==='已审核'?v.grade:v.status;$r('reason').value=v.reason;$r('cluster').value=v.cluster_semantics;$r('singleton').value=v.singleton_assessment;
  $r('evidence').innerHTML=`<p>原tag：${E(r.expert?.expert_tag||'无')}；${E(r.scene)}</p>`+(u?`<p>第一轮：${E(names[u.previous.grade]||'未分类')}；第二轮：<b>${E(names[u.candidate['建议粗类_非最终']]||u.candidate['建议粗类_非最终']||'未分类')}</b></p><p>${['原作答人数','有效独立人数','单列无效人数','各簇人数_含单人','支持簇数','单人簇数','前8人完整后缀比例','至观察窗口支持核心稳定比例'].map(k=>E(k)+'：'+E(u.candidate[k]||'未计算')).join('；')}</p><details><summary>完整原始数值依据</summary><pre style="white-space:pre-wrap">${E(JSON.stringify(u,null,2))}</pre></details>`:'<p>无本轮历史，不生成历史粗类。可以填写图片观察。</p>');
  if(u){const s=document.getElementById('history-mode');s.value=c==='manual'?'Manual':'Semi';s.dispatchEvent(new Event('change'));}
 }
 function render(){const r=rows.get(dataset.cases[currentCase].image_id);if(!r)return;$r('image').value=r.image_id;$r('mode').replaceChildren(...r.units.map(u=>opt(u.condition,u.condition)));$r('note').value=notes[r.image_id]||'';$r('original').src='../../../'+r.image_path;$r('original-link').href='../../../'+r.image_path;mode();progress();}
 function choices(){const q=$r('search').value.toLowerCase();$r('image').replaceChildren(...d.rows.filter(r=>[r.image_id,r.number,r.scene].join(' ').toLowerCase().includes(q)).map(r=>opt(r.image_id,`${r.priority?'优先 · ':''}${r.building} · ${r.number} · ${r.scene}`)));}
 function open(){const i=dataset.cases.findIndex(c=>c.image_id===$r('image').value);if(i>=0)chooseCase(i);}
 $r('search').oninput=choices;$r('image').onchange=open;$r('mode').onchange=mode;
 for(const [k,n] of [['prev',-1],['next',1]])$r(k).onclick=()=>{const s=$r('image');if(s.options.length){s.selectedIndex=(s.selectedIndex+n+s.options.length)%s.options.length;open();}};
 for(const id of ['decision','reason','cluster','singleton'])$r(id).oninput=()=>{const iid=dataset.cases[currentCase].image_id,c=$r('mode').value,k=iid+'|'+c;if(!units.has(k))return;const x=$r('decision').value,v={status:['未审核','暂缓'].includes(x)?x:'已审核',grade:['未审核','暂缓'].includes(x)?'':x,reason:$r('reason').value,cluster_semantics:$r('cluster').value,singleton_assessment:$r('singleton').value};validate(v);edits[k]=v;save();};
 $r('note').oninput=()=>{notes[dataset.cases[currentCase].image_id]=$r('note').value;save();};
 $r('export').onclick=()=>{const v=exportData();validateImport(v);const url=URL.createObjectURL(new Blob([JSON.stringify(v,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='图片历史难度_我的审核.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
 $r('import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;({edits,notes}=validateImport(JSON.parse(await f.text())));blocked=false;save();render();}catch(error){$r('save').textContent='导入失败，现有审核保留：'+error.message;}finally{e.target.value='';}};
 document.addEventListener('studio-case',render);$r('save').textContent=message;choices();render();
 window.DIFFICULTY_REVIEW_API={exportData,validateImport};
})();
