const assert=require('node:assert/strict');
const fs=require('node:fs');
const {validateReview,blank}=require('../tools/thesis_main/analysis/collection_review.js');
const data=JSON.parse(fs.readFileSync('analysis_results/collection_review_20260921/审核输入.json','utf8'));
assert.equal(data.groups.length,8);
assert.equal(data.groups.flatMap(g=>g.images).length,39);
assert.equal(data.groups.reduce((n,g)=>n+g.tasks,0),528);
const group=data.groups[0],image=group.images[0];
const value={schema:data.schema,binding:data.binding,source_evidence:data.groups,decisions:{[group.id]:{
  ...blank(),comment:'只写文字\n保留 OOS 和细节差异。',defer:true,
  images:{[image.image_id]:{decision:'',comment:'未填选项，仍有审核文字。'}}
}}};
const roundtrip=JSON.parse(JSON.stringify(value));
assert.deepEqual(validateReview(roundtrip,data),value.decisions);
assert.deepEqual(roundtrip.source_evidence,data.groups);
for(const mutate of [v=>v.binding.members[0].images[0].need++,v=>v.decisions[group.id].images.unknown={decision:'',comment:''},v=>v.decisions[group.id].defer='true']){
  const bad=structuredClone(value);mutate(bad);assert.throws(()=>validateReview(bad,data));
}
assert.equal(blank().adoption,'');
assert.equal(blank().purposes.length,0);
console.log('PASS：8组39图、文字/暂缓/逐图例外往返、原文分离、版本和身份拒收。');
