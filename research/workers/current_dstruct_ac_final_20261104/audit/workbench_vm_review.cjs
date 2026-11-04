/* Run the delivered page's real JavaScript in an offline DOM stub.
 * Checks numerical transforms and selectors; this is not a visual layout test.
 */
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'workbench/index.html'), 'utf8');
const rawData = html.match(/<script id="ac-data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
class Element {
  constructor(id) { this.id=id; this.value=''; this.innerHTML=''; this.textContent=id==='ac-data'?rawData:''; this.events={}; }
  addEventListener(event, handler) {this.events[event]=handler;}
  querySelectorAll() {return [];}
  click() {}
}
const elements=new Map();
const document={getElementById(id){if(!elements.has(id))elements.set(id,new Element(id));return elements.get(id);},createElement(){return new Element('created');}};
const context=vm.createContext({document,Blob,URL,setTimeout,console});
vm.runInContext(script+'\nglobalThis.API={DATA,baseImageRows,currentImageRows,render,renderStrata,updateControls,selected,num,count,signed,finite};',context,{timeout:30000});
const a=context.API;
const failures=[]; const checks={};
const fail=(name,detail)=>{failures.push({check:name,detail});};
const equal=(x,y,tol=1e-9)=>(x===null&&y===null)||(Number.isFinite(x)&&Number.isFinite(y)&&Math.abs(x-y)<=tol);
const choose=row=>{
  for(const [id,key] of [['cohort','analysis_cohort'],['version','version'],['scope','scope'],['support','support'],['direction','direction']])document.getElementById(id).value=row[key];
  document.getElementById('budget').value=`${row.n}/${row.m}`;
};
let imageViews=0;
let maxMeanResidual=0;
let maxEndpointResidual=0;
for(const row of a.DATA.summary){
  choose(row);
  const rows=a.baseImageRows();imageViews++;
  if(rows.length!==row.images)fail('image_count',{key:row.direction,cohort:row.analysis_cohort,n:row.n,m:row.m,expected:row.images,actual:rows.length});
  if(new Set(rows.map(x=>x.building)).size!==row.buildings)fail('building_count',row.direction);
  if(rows.reduce((sum,x)=>sum+x.physical_pairs,0)!==row.common_Q_physical_pairs)fail('pair_count',row.direction);
  if(rows.some(x=>x.n!==row.n||x.m!==row.m||x.scope!==row.scope||x.support!==row.support||x.version!==row.version||x.analysis_cohort!==row.analysis_cohort))fail('selector_leak',row.direction);
  const mean=rows.length?rows.reduce((sum,x)=>sum+x.dQ,0)/rows.length:null;
  const abs=rows.length?rows.reduce((sum,x)=>sum+x.abs_dQ,0)/rows.length:null;
  if(!equal(mean,row.image_equal_mean))fail('displayed_image_mean',{mean,expected:row.image_equal_mean});
  if(!equal(abs,row.abs_dQ_image_equal_mean))fail('displayed_image_absolute_mean',{mean:abs,expected:row.abs_dQ_image_equal_mean});
  if(mean!==null)maxMeanResidual=Math.max(maxMeanResidual,Math.abs(mean-row.image_equal_mean));
  const thresholds=[['up_gt_1p0_images',x=>x.dQ>1],['down_lt_minus_1p0_images',x=>x.dQ < -1],['within_pm_1p0_images',x=>Math.abs(x.dQ)<=1]];
  for(const [field,predicate] of thresholds){
    if(rows.length===0&&row[field]===null)continue; // Empty-support counts remain unavailable, not imputed zero.
    if(rows.filter(predicate).length!==row[field])fail('displayed_image_sign_count',field);
  }
  for(const x of rows){
    maxEndpointResidual=Math.max(maxEndpointResidual,Math.abs(x.dQ-(x.Q_C-x.Q_A)));
    if(!equal(x.dQ,x.Q_C-x.Q_A))fail('reverse_Q_A_Q_C_identity',x.image);
  }
}
checks.image_views_checked=imageViews;
checks.max_image_mean_rounding_residual=maxMeanResidual;
checks.max_endpoint_difference_rounding_residual=maxEndpointResidual;
// Actual numeric missing values must render as missing, while valid zero stays 0.
for(const value of [null,undefined,NaN])for(const fn of ['num','count','signed'])if(a[fn](value)!=='—')fail('missing_render',fn);
if(a.num(0)!=='0.00'||a.count(0)!=='0'||a.signed(0)!=='0.00')fail('valid_zero_render','zero was hidden or reclassified');
const example=a.DATA.images[0],pair=example.class_pair.split('_');
const sentinel={...example,image:'__MISSING_SENTINEL__',dQ:null,Q_A:null,Q_C:null};
a.DATA.images.push(sentinel);
choose({...example,direction:pair[1]+'_to_'+pair[0]});
const transformed=a.baseImageRows().find(x=>x.image==='__MISSING_SENTINEL__');
if(transformed.dQ!==null||transformed.Q_A!==null||transformed.Q_C!==null)fail('reverse_missing_preservation',transformed);
a.DATA.images.pop();
checks.missing_and_true_zero_rendering='passed';
// The stratified table intentionally has full-common support per version.
const axes=['official_difficulty','structural_condition','room_type','difficulty_x_room_type','D_category','design_status'];
const groupMap=new Map();
for(const r of a.DATA.strata){const key=JSON.stringify([r.analysis_cohort,r.version,r.scope,r.n,r.m,r.direction,r.stratum_type]);if(!groupMap.has(key))groupMap.set(key,[]);groupMap.get(key).push(r);}
let strataViews=0,suppressed=0;
for(const group of groupMap.values()){
  const first=group[0],full=first.version==='automatic'?'original_common':'expanded_common';
  choose({...first,support:full});document.getElementById('axis').value=first.stratum_type;a.renderStrata();
  const n=(document.getElementById('strata-body').innerHTML.match(/<tr>/g)||[]).length;
  if(n!==group.length)fail('strata_selector_or_count',{expected:group.length,actual:n,key:first.stratum_type});
  strataViews++;
  if(first.version==='manual_order_assisted')for(const support of ['original_common','new_common_after_approved_order']){
    document.getElementById('support').value=support;a.renderStrata();
    if(!document.getElementById('strata-note').textContent.includes('请切换支持口径'))fail('strata_support_guard',support);
    if(!document.getElementById('strata-body').innerHTML.includes('此口径暂无可显示分层'))fail('strata_support_not_suppressed',support);
    suppressed++;
  }
}
checks.stratum_views_checked=strataViews;checks.incompatible_support_views_suppressed=suppressed;
const values=id=>[...document.getElementById(id).innerHTML.matchAll(/<option value="([^"]*)">/g)].map(m=>m[1]);
let controlStates=0;
for(const cohort of new Set(a.DATA.summary.map(x=>x.analysis_cohort))){
  document.getElementById('cohort').value=cohort;a.updateControls('cohort');
  for(const version of values('version')){
    document.getElementById('version').value=version;a.updateControls('version');
    const expectedSupport=version==='automatic'?'original_common':'expanded_common';
    if(document.getElementById('support').value!==expectedSupport)fail('version_default_support',version);
    for(const scope of values('scope')){
      document.getElementById('scope').value=scope;a.updateControls('scope');
      const available=a.DATA.summary.filter(x=>x.analysis_cohort===cohort&&x.version===version&&x.scope===scope);
      const allowed=[...new Set(available.map(x=>`${x.n}/${x.m}`))].sort();
      if(JSON.stringify(values('budget').sort())!==JSON.stringify(allowed))fail('budget_scope_controls',{cohort,version,scope});
      if(available.some(x=>x.condition!=='manual'))fail('condition_filter_assumption',scope);
      controlStates++;
    }
  }
}
checks.control_states_checked=controlStates;
checks.condition_singleton='manual';
const receipt={status:failures.length?'failed':'passed',review_mode:'delivered JavaScript in Node vm with a minimal DOM stub; no visual layout claim',checks,failures};
fs.writeFileSync(path.join(__dirname,'WORKBENCH_JS_REVIEW.json'),JSON.stringify(receipt,null,2)+'\n');
console.log(JSON.stringify({status:receipt.status,checks,failures:failures.length}));
if(failures.length)process.exitCode=1;
