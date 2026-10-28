'use strict';
(()=>{
 const data=window.V21_ADMITTED;
 if(!data){document.getElementById('admittedAvailable').textContent='补充结果暂不可用。';return;}
 const scopes=[['original_current_target','原有目标'],['other_admitted_target','新增目标'],['combined','合并']];
 const fmt=x=>x==null?'不可估':Number(x).toFixed(2);
 function render(id,panel,ks){
  const parent=document.getElementById(id);
  for(const [scope,label] of scopes)for(const k of ks){
   const get=metric=>data.rows.find(r=>r.support===scope&&r.panel===panel&&r.k===k&&r.metric===metric);
   const q=get('Q_mean'),failure=get('actual_consensus_failure_rate');
   const support=r=>r?`${r.pools} / ${r.images} / ${r.eligible_pools}`:'不可估';
   const cells=[label,k,q?fmt(q.estimate):'不可估',support(q),failure?fmt(failure.estimate*100)+'%':'不可估',support(failure)];
   const tr=document.createElement('tr');for(const text of cells){const td=document.createElement('td');td.textContent=String(text);tr.append(td);}parent.append(tr);
  }
 }
 render('admittedAvailable','available_at_k',[3]);render('admittedFixed','fixed_N_ge_6',[3,6]);
})();
