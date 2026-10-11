const fs=require('fs'),assert=require('assert'),crypto=require('crypto'),path=require('path');
const root=path.resolve(__dirname,'..'),G=require('../user/editor/geometry.js'),c=JSON.parse(fs.readFileSync(root+'/inputs/editor_seed_data.json')).images[0],p=G.floor(c.reference_points_1024x512);
let checks=0;const ok=(v,m)=>{assert(v,m);checks++};
const hash=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
ok(hash(root+'/vendor/v3.4.2/dist/geometry.js')===hash(root+'/user/editor/geometry.js'),'archived geometry unchanged');
const offset=-.8478948561575355,merged=G.moveEdge(p,11,offset);
ok(merged.length===13,'actual closing-corner merge');
for(let start=0;start<14;start++){
 const rotated=p.slice(start).concat(p.slice(0,start)),i=(11-start+14)%14,q=G.moveEdge(rotated,i,offset);
 ok(q&&q.length===13,'ring start '+start);ok(Math.abs(G.area(q)-G.area(merged))<1e-9,'rotation area '+start);
 const followed=G.followEdgeGT(rotated,i,offset,rotated,.1,{extensions:true,target:(13-start+14)%14});ok(followed&&followed.polygon.length===12,'exact closure follow '+start);
 const replay=G.replay(rotated,[{type:'edge_follow',index:i,line:followed.line}]);ok(JSON.stringify(replay)===JSON.stringify(followed.polygon),'stored line replay '+start);
}
for(let i=0;i<p.length;i++){
 const a=p[i],b=p[(i+1)%p.length],len=Math.hypot(b[0]-a[0],b[1]-a[1]),n=[-(b[1]-a[1])/len,(b[0]-a[0])/len],eps=.001;
 for(const [d,expected] of [[9*eps,true],[11*eps,false]]){
  const moved=[a,b].map(v=>v.map((z,k)=>z+n[k]*d));ok(G.edgeSnapCandidates(...moved,p,10*eps).some(q=>q.gt_edge===i)===expected,'finite edge acquisition within CSS-equivalent 9/11 px '+i);
 }
}
const report={checks_passed:checks,archived_geometry_sha256:hash(root+'/user/editor/geometry.js'),actual_image:c.image_code,coverage:['14 ring starts','14→13 corner collapse','14→12 exact line follow','stored-line replay','14 finite GT edges at 9/11-pixel equivalent radii'],synthetic_data_in_product:false};fs.writeFileSync(root+'/results/geometry_qa.json',JSON.stringify(report,null,2)+'\n');console.log(report);
