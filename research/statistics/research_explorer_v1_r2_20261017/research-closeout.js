(function(){
'use strict';
const $=id=>document.getElementById(id), api=window.ResearchCloseout;
const el=(tag,text)=>{const n=document.createElement(tag); if(text!==undefined)n.textContent=text; return n;};
function fields(parent,row,keys){const dl=el('dl');keys.forEach(key=>{dl.append(el('dt',key),el('dd',row[key]===undefined || row[key]===''?'未提供／不适用（不是 0）':String(row[key])));});parent.append(dl);}
function detail(parent,title,row,keys){const d=el('details'); d.append(el('summary',title));fields(d,row,keys);parent.append(d);}
try {
 const data=api.normalize(window.RESEARCH_CLOSEOUT_DATA);
 function renderPersonnel(){
  const rows=api.filterPersonnel(data.personnel,$('condition').value,$('search').value);
  $('count').textContent=`显示 ${rows.length} / ${data.personnel.length} 条条件；这些行存在重叠，不汇总相加。`;
  $('personnel-results').replaceChildren();
  rows.forEach(r=>{const card=el('article');card.append(el('h3',r['条件ID']));
   [r['作答条件'],r['分类方法'],r['粗细层级'],r['采用级别']].forEach(v=>{const b=el('span',v);b.className='badge';card.append(b);});
   fields(card,r,['分类依据','实际标法与用途边界','换类方向','人数n','实际换人数m_AB','实际换人数m_AC','推荐用途','核验层级']);
   detail(card,'查看效果、质量/时间与失败分母',r,['注册事件','评价事件','图像数','楼数','同类绝对Q变化','跨类绝对Q变化','跨类减同类绝对Q变化','有向Q_C减A','匹配净Q_C减B','有向D10_C减A','匹配净D10_C减B','时间聚合定义','时间C比A算术百分比','时间C比A几何百分比','时间C比B几何百分比','失败分母数','失败分母单位','C失败加权比例']);
   detail(card,'查看隔离、成员来源与覆盖限制',r,['研究阶段','分类与验证隔离','目标楼成员名单文件','目标楼成员筛选条件','ALL成员仅描述不可代替目标楼标签','父类固定','共同背景与适用范围','非独立重叠组','重叠说明','精确来源选择器']);
   $('personnel-results').append(card);
  });
 }
 $('condition').addEventListener('change',renderPersonnel);$('search').addEventListener('input',renderPersonnel);renderPersonnel();
 const sels=['member-method','member-condition','member-building'];
 const keys=['method','condition','heldout_building'];
 sels.forEach((id,i)=>{const select=$(id);select.append(new Option('请选择',''));[...new Set(data.members.map(r=>r[keys[i]]))].sort().forEach(v=>select.append(new Option(v,v)));select.addEventListener('change',()=>{
  const rows=api.matchingMembers(data.members,...sels.map(s=>$(s).value));$('member-results').replaceChildren();
  if(!rows.length){$('member-results').append(el('p','请选择完整三项；无匹配只表示此快照未列出该组合，不表示没有成员。'));return;}
  rows.forEach(r=>{const c=el('article');c.append(el('h3',`${r.tier} · ${r.class_id}（${r.n_members} 人）`));fields(c,r,['members','实际标法','成员身份']);$('member-results').append(c);});
 });});
 data.sameRoom.forEach(r=>{const c=el('article');c.append(el('h3',r['问题']+'：'+r['归档结论']));fields(c,r,['主要数值','支持范围','本次实核','适用限制']);detail(c,'源表位置（对应同房研究包内）',r,['源表相对路径']);$('room-results').append(c);});
 const links=window.RESEARCH_CLOSEOUT_SOURCES || [
 ['人员独立核验范围','../../workers/personnel_effective_exchange_conditions_20261022/audit/PERSONNEL_ARCHIVE_REVIEW_ZH.md'],
 ['人员统一结果完整 CSV','../../workers/personnel_effective_exchange_conditions_20261022/audit/PERSONNEL_UNIFIED_RESULT_ZH.csv'],
 ['目标楼完整成员 CSV','../../workers/personnel_effective_exchange_conditions_20261022/audit/PERSONNEL_TARGET_CLASS_MEMBERS_ZH.csv'],
 ['人员源报告','../../workers/personnel_effective_exchange_conditions_20261022/report/人员分类与有效换类条件_整合报告_20261022.md'],
 ['同房本次验收范围','../../same_room/same_room_acceptance_20261022/SAME_ROOM_ACCEPTANCE.md'],
 ['同房既有归档','../../same_room/same_room_profile_return_review_20261021/README.md']
 ];
 links.forEach(([title,url])=>{const li=el('li'),a=el('a',title);a.href=url;li.append(a);$('source-links').append(li);});
}catch(error){$('error').textContent='无法载入冻结数据：'+error.message;}
})();
