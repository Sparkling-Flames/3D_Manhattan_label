'use strict';
const fs=require('fs'),R=require('./inputs/review-state.js'),A=JSON.parse(fs.readFileSync(__dirname+'/inputs/raw_scope_receipt.json')),D=JSON.parse(fs.readFileSync(__dirname+'/inputs/data.json'));
const clone=x=>JSON.parse(JSON.stringify(x));const r=A.records.find(r=>r.image_code==='uNb9QFRL6hY-88'),c=D.images.find(c=>c.image_code===r.image_code);const results=[];
function rejected(name,fn){let rejected=false,message='';try{fn()}catch(e){rejected=true;message=e.message}results.push({name,rejected,message});}
rejected('tampered root polygon while alias remains original',()=>{let x=clone(r);x.polygon[0][0]+=.2;R.verifyOps(c,x)});
rejected('tampered cropped alias while polygon remains original',()=>{let x=clone(r);x.cropped_floor_xz_h[0][0]+=.2;R.verifyOps(c,x)});
rejected('wrong image identity in candidate binding',()=>{let x=clone(r.space_regions);x.regions[0].source_binding.image_id='other';R.verifyRegions(c,x,A.source_commit)});
rejected('wrong GT version in candidate binding',()=>{let x=clone(r.space_regions);x.regions[0].source_binding.editing_reference_version='other';R.verifyRegions(c,x,A.source_commit)});
rejected('wrong source commit in candidate binding',()=>{let x=clone(r.space_regions);x.regions[0].source_binding.source_commit='other';R.verifyRegions(c,x,A.source_commit)});
rejected('duplicate region identity',()=>{let x=clone(r.space_regions);x.regions.push(clone(x.regions[0]));R.verifyRegions(c,x,A.source_commit)});
rejected('out of bounds edge operation',()=>{let x=clone(r);x.operations[0].index=999;R.verifyOps(c,x)});
rejected('full GT decision cannot contain operations',()=>{let x=clone(r);x.decision='full_gt';R.verifyOps(c,x)});
rejected('candidate cannot promote formal eligibility',()=>{let x=clone(r.space_regions);x.regions[0].formal_eligibility_changed=true;R.verifyRegions(c,x,A.source_commit)});
rejected('edge_follow stored line cannot disagree with polygon',()=>{let x=clone(r);x.operations=[{type:'edge_follow',index:0,line:[[10,-20],[10,20]]}];R.verifyOps(c,x)});
const out={result:results.every(r=>r.rejected)?'PASS':'FAIL',count:results.length,tests:results};fs.writeFileSync(__dirname+'/negative_tests.json',JSON.stringify(out,null,2)+'\n');console.log(JSON.stringify(out,null,2));process.exitCode=out.result==='PASS'?0:1;
