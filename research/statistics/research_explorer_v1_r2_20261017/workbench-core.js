/* Display semantics shared by the offline UI and its focused checks. */
(function(root){
'use strict';
const empty=v=>v===null||v===undefined||v==='';
const truth=v=>v===true||v==='True'||v==='true';
const numeric=v=>typeof v==='number'&&Number.isFinite(v);
const tokens=v=>Array.isArray(v)?v:String(v??'').split(/[|;,]/).map(x=>x.trim()).filter(Boolean);
const matches=(actual,selection)=>tokens(selection).some(v=>tokens(actual).map(String).includes(v));
const fields={
 B8L2:['B8L2','B8L2_mean','B8L2_median','comparison_B8L2','Q_effect','B8L2_fixed'],
 D10:['D10','D10_mean','D10_median','comparison_D10','D10_fixed'],
 image:['image_id','image','image_code','image_a','image_b','image_id_a','image_id_b'],
 worker:['worker_id','member_workers','worker_ids','requested_worker_ids','worker_ids_a','worker_ids_b'],
 target:['rescore_target_id','current_target_id','target_id','reference_id'],
 condition:['condition','condition_a'], building:['building_id','building'],
};
function field(row,key){return (fields[key]||[key]).find(k=>!empty(row[k]));}
function value(row,key){const k=field(row,key);return k?row[k]:null;}
function stats(values){const a=values.filter(numeric).sort((x,y)=>x-y),n=a.length;
 const quantile=p=>{if(!n)return null;const i=(n-1)*p,j=Math.floor(i);return a[j]+(a[Math.ceil(i)]-a[j])*(i-j);};
 return {n,mean:n?a.reduce((x,y)=>x+y,0)/n:null,median:quantile(.5),p10:quantile(.1),p25:quantile(.25),p75:quantile(.75)};
}
function imageFlags(image){const d=image.scene?.doorway_status;
 return {doorway:!d||d==='not_recorded'?null:!['none','no','not_doorway'].includes(d),
 oos:image.flags?.oos===true?true:!image.scene?.oos_subtype||image.scene.oos_subtype==='not_recorded'?null:false};
}
function matchesImage(image,f){
 const flag=imageFlags(image);
 if(f.image&&!matches([image.image_id,image.image_code],f.image))return false;
 if(f.building&&!matches(image.building_id,f.building))return false;
 if(f.difficulty&&!matches(image.difficulty?.label,f.difficulty))return false;
 for(const key of ['doorway','oos'])if(f[key]&&String(flag[key])!==f[key])return false;
 if(f.gt&&!image.flags?.[f.gt])return false;
 if(f.scope==='multiple'&&!image.multiple_spaces)return false;
 if(f.scope==='candidate'&&!image.spaces?.some(s=>s.user_candidate))return false;
 if(f.scope==='incomplete'&&!image.spaces?.some(s=>!s.reference_full_available))return false;
 return true;
}
function filterRows(rows,f,images){
 if(!rows.length)return {rows:[],unsupported:[]};
 const keys=new Set(rows.flatMap(r=>Object.keys(r))),unsupported=[];
 const has=k=>(fields[k]||[k]).some(x=>keys.has(x));
 const imageFilter=['image','building','difficulty','doorway','oos','gt','scope'].some(k=>f[k]);
 if(imageFilter&&!has('image')&&!keys.has('object_id'))unsupported.push('图片与空间条件');
 for(const k of ['condition','worker','target'])if(f[k]&&!has(k))unsupported.push(k);
 if(f.relation&&!keys.has('group_id')&&!keys.has('request_id')&&!keys.has('user_group'))unsupported.push('关系组');
 if(f.analysis==='quality'&&!keys.has('quality_usable'))unsupported.push('主质量用途');
 if(f.analysis==='diagnostic'&&!keys.has('diagnostic_B8L2'))unsupported.push('诊断用途');
 if(unsupported.length)return {rows:[],unsupported};
 const out=rows.filter(r=>{
   if(imageFilter){const ids=(fields.image||[]).flatMap(k=>tokens(r[k]));
     const linked=ids.map(id=>images.get(id)).filter(Boolean);
     if(!linked.some(i=>matchesImage(i,f)))return false;
   }
   if(f.condition&&!matches(String(value(r,'condition')).toLowerCase(),f.condition))return false;
   if(f.worker&&!matches(value(r,'worker'),f.worker))return false;
   if(f.target&&!matches(value(r,'target'),f.target))return false;
   if(f.relation&&!matches([r.group_id,r.user_group,r.request_id].filter(Boolean),f.relation))return false;
   if(f.search&&!Object.values(r).some(v=>String(v??'').toLowerCase().includes(f.search.toLowerCase())))return false;
   if(f.analysis==='quality'&&(!keys.has('quality_usable')||!truth(r.quality_usable)))return false;
   if(f.analysis==='diagnostic'&&!(numeric(r.diagnostic_B8L2)&&!truth(r.quality_usable)))return false;
   return true;
 });
 return {rows:out,unsupported};
}
function metricRows(rows,column){
 return rows.filter(r=>numeric(r[column])&&
   (!/^worker_attributable_gain_/.test(column)||!Object.hasOwn(r,'current_qualified_gain_available')||truth(r.current_qualified_gain_available))&&
   (!/^(B8L2|D10|IoU3D100)(_|$)/.test(column)||
    ((!Object.hasOwn(r,'quality_usable')||truth(r.quality_usable))&&
     (!Object.hasOwn(r,'main_comparison_allowed')||truth(r.main_comparison_allowed))&&
     (!Object.hasOwn(r,'both_main_quality')||truth(r.both_main_quality))&&
     (!Object.hasOwn(r,'main_comparison_allowed_fixed')||truth(r.main_comparison_allowed_fixed))&&
     (!Object.hasOwn(r,'main_comparison_allowed_reselected')||truth(r.main_comparison_allowed_reselected)))));
}
function csv(rows,columns){const q=v=>'"'+String(empty(v)?'':typeof v==='object'?JSON.stringify(v):v).replace(/"/g,'""')+'"';
 return '\ufeff'+[columns.map(q).join(','),...rows.map(r=>columns.map(k=>q(r[k])).join(','))].join('\r\n');}
function wrapSegment(a,b){let [x1,y1]=a,[x2,y2]=b;if(Math.abs(x2-x1)<=512)return [[a,b]];
 x2+=x2>x1?-1024:1024;const edge=x2<0?0:1024,y=y1+(y2-y1)*(edge-x1)/(x2-x1);
 return [[[x1,y1],[edge,y]],[[edge===0?1024:0,y],[b[0],b[1]]]];
}
function projectFloor(floor){const erp=([x,z])=>[((Math.atan2(x,-z)/(2*Math.PI)+.5)*1024+1024)%1024,(.5+Math.atan2(1,Math.hypot(x,z))/Math.PI)*512];
 return floor.flatMap((a,i)=>{const b=floor[(i+1)%floor.length],out=[];let old=erp(a);
  for(let j=1;j<=80;j++){const p=erp([a[0]+(b[0]-a[0])*j/80,a[1]+(b[1]-a[1])*j/80]);out.push(...wrapSegment(old,p));old=p;}return out;});
}
function geometry(points){
 if(!points||points.length<6||points.length%2)return null;
 const bottom=[],top=[];
 for(let i=0;i<points.length;i+=2){const t=points[i],b=points[i+1],a=(b[0]/1024-.5)*2*Math.PI,v=(b[1]/512-.5)*Math.PI;
  if(v<=0||v>=Math.PI/2)return null;
  const radius=1/Math.tan(v),x=radius*Math.sin(a),z=-radius*Math.cos(a),h=radius*Math.tan((.5-t[1]/512)*Math.PI);
  bottom.push([x,-1,z]);top.push([x,h,z]);
 }return {bottom,top};
}
function selectAnnotation(annotations,focus){return annotations.find(a=>a.object_id===focus)||annotations.find(a=>a.retained)||annotations[0];}
const api={selectAnnotation,empty,truth,numeric,tokens,matches,fields,field,value,stats,imageFlags,matchesImage,filterRows,metricRows,csv,wrapSegment,projectFloor,geometry};
root.WorkbenchCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
